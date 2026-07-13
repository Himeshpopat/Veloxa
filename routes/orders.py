from flask import Blueprint, render_template, request, session, redirect, flash, abort, current_app

from models import db, Customer, Product, Cart, Order, OrderItem
from routes.helpers import require_customer, logger, products_by_id
from utils.brevo_email import send_email

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/place_order', methods=['POST'])
@require_customer
def place_order():
    customer_id = session['customer_id']
    cart_items = Cart.query.filter_by(customer_id=customer_id).all()

    if not cart_items:
        flash('Cart is empty.')
        return redirect('/cart')

    products = products_by_id(item.product_id for item in cart_items)

    for item in cart_items:
        product = products.get(item.product_id)
        if not product or not product.is_active:
            flash(f'A product in your cart is no longer available.')
            return redirect('/cart')
        if item.quantity > product.stock:
            flash(f'Only {product.stock} units of {product.name} are available.')
            return redirect('/cart')

    order = Order(customer_id=customer_id, status='Pending')
    db.session.add(order)
    db.session.commit()

    customer = Customer.query.get(customer_id)

    order_body = (
        f"New Order Received\n\n"
        f"Order ID: {order.id}\n\n"
        f"Customer: {customer.name}\n"
        f"Shop: {customer.shop_name}\n"
        f"Mobile: {customer.mobile}\n"
        f"City: {customer.city}\n\n"
        f"Please check the Order."
    )
    try:
        send_email(
            current_app.config['ORDER_EMAIL_RECEIVER'],
            'New Order Received',
            order_body
        )
        logger.info("Order notification email sent successfully.")
    except Exception as e:
        logger.exception("Failed to send order notification email: %s", e)

    for item in cart_items:
        order_item = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity)
        db.session.add(order_item)

    db.session.commit()

    for item in cart_items:
        db.session.delete(item)

    db.session.commit()
    logger.info("Customer %s placed order %s", customer_id, order.id)
    return redirect('/my_orders')


@orders_bp.route('/my_orders')
@require_customer
def my_orders():
    customer_id = session['customer_id']
    orders = Order.query.filter_by(customer_id=customer_id).order_by(Order.id.desc()).all()

    return render_template('my_orders.html', orders=orders)


@orders_bp.route('/order_details/<int:order_id>')
def order_details(order_id):
    order = Order.query.get_or_404(order_id)

    if 'admin_id' not in session:
        if 'customer_id' not in session:
            return redirect('/login')
        # Ownership check
        if order.customer_id != session['customer_id']:
            abort(403)

    order_items = OrderItem.query.filter_by(order_id=order_id).all()
    products = products_by_id(item.product_id for item in order_items)

    order_data = []
    total = 0

    for item in order_items:
        product = products.get(item.product_id)
        if not product:
            continue
        item_total = product.price * item.quantity
        total += item_total
        order_data.append({'product': product, 'quantity': item.quantity, 'item_total': item_total})

    customer = Customer.query.get(order.customer_id)

    return render_template(
        'order_details.html',
        customer=customer,
        order_data=order_data,
        order=order,
        total=total
    )


@orders_bp.route('/customer_cancel_order/<int:order_id>', methods=['POST'])
@require_customer
def customer_cancel_order(order_id):
    customer_id = session['customer_id']
    order = Order.query.get_or_404(order_id)

    # Ownership + status check
    if order.customer_id == customer_id and order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()
        logger.info("Customer %s cancelled order %s", customer_id, order_id)

    return redirect('/my_orders')


@orders_bp.route('/edit_order/<int:order_id>')
@require_customer
def edit_order(order_id):
    customer_id = session['customer_id']
    order = Order.query.get_or_404(order_id)

    if order.customer_id != customer_id:
        abort(403)

    if order.status != 'Pending':
        flash('Only pending orders can be edited.', 'warning')
        return redirect('/my_orders')

    order_items = OrderItem.query.filter_by(order_id=order_id).all()
    products = products_by_id(item.product_id for item in order_items)

    order_data = []
    total = 0
    total_items = 0

    for item in order_items:
        product = products.get(item.product_id)
        if not product:
            continue
        subtotal = product.price * item.quantity
        total += subtotal
        total_items += item.quantity
        order_data.append({
            'product': product,
            'quantity': item.quantity,
            'item_id': item.id,
            'subtotal': subtotal
        })

    return render_template(
        'edit_order.html',
        order=order,
        order_id=order_id,
        order_data=order_data,
        total=total,
        total_items=total_items
    )


@orders_bp.route('/increase_order_quantity/<int:item_id>', methods=['POST'])
@require_customer
def increase_order_quantity(item_id):
    customer_id = session['customer_id']
    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get_or_404(item.order_id)
    product = Product.query.get_or_404(item.product_id)

    # Ownership check
    if order.customer_id != customer_id:
        abort(403)

    if order.status != 'Pending':
        abort(403)

    if product.stock > item.quantity:
        item.quantity += 1
    else:
        flash(f'Only {product.stock} units available in stock.')

    db.session.commit()
    return redirect(f'/edit_order/{item.order_id}')


@orders_bp.route('/decrease_order_quantity/<int:item_id>', methods=['POST'])
@require_customer
def decrease_order_quantity(item_id):
    customer_id = session['customer_id']
    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get_or_404(item.order_id)

    if order.customer_id != customer_id:
        abort(403)

    if order.status != 'Pending':
        abort(403)

    if item.quantity > 1:
        item.quantity -= 1
        db.session.commit()
    else:
        total_items = OrderItem.query.filter_by(order_id=order.id).count()
        if total_items > 1:
            db.session.delete(item)
            db.session.commit()
            flash('Item removed successfully.', 'success')
        else:
            flash('Order must contain at least one item.', 'warning')

    return redirect(f'/edit_order/{item.order_id}')


@orders_bp.route('/remove_order_item/<int:item_id>', methods=['POST'])
@require_customer
def remove_order_item(item_id):
    customer_id = session['customer_id']
    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get_or_404(item.order_id)

    if order.customer_id != customer_id:
        abort(403)

    if order.status != 'Pending':
        abort(403)

    remaining_items = OrderItem.query.filter_by(order_id=order.id).count()
    if remaining_items <= 1:
        flash('Order must contain at least one item.', 'warning')
        return redirect(f'/edit_order/{order.id}')

    db.session.delete(item)
    db.session.commit()
    flash('Item removed successfully.', 'success')
    return redirect(f'/edit_order/{order.id}')


@orders_bp.route('/add_to_order/<int:order_id>/<int:product_id>', methods=['POST'])
@require_customer
def add_to_order(order_id, product_id):
    order = Order.query.get_or_404(order_id)

    if order.customer_id != session['customer_id']:
        abort(403)

    if order.status != 'Pending':
        abort(403)

    product = Product.query.get_or_404(product_id)

    if not product.is_active:
        flash('Product is not available.')
        return redirect(f'/edit_order/{order_id}')

    item = OrderItem.query.filter_by(order_id=order_id, product_id=product_id).first()

    if item:
        if item.quantity < product.stock:
            item.quantity += 1
        else:
            flash(f'Only {product.stock} units available in stock.')
    else:
        if product.stock > 0:
            item = OrderItem(order_id=order_id, product_id=product_id, quantity=1)
            db.session.add(item)
        else:
            flash('Product is out of stock.')

    db.session.commit()
    return redirect(f'/edit_order/{order_id}')