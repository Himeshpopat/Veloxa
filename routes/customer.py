from flask import Blueprint, render_template, request, session, redirect, flash, abort, send_file
import re

from models import db, Customer, Product, Cart, Order
from routes.helpers import require_customer, products_by_id
from utils.invoice_generator import generate_invoice

PRODUCTS_PER_PAGE = 12

customer_bp = Blueprint('customer', __name__)


@customer_bp.route('/dashboard')
@require_customer
def dashboard():
    customer_id = session['customer_id']
    customer = Customer.query.get_or_404(customer_id)

    total_orders = Order.query.filter_by(customer_id=customer_id).count()
    pending_orders = Order.query.filter_by(customer_id=customer_id, status='Pending').count()
    delivered_orders = Order.query.filter_by(customer_id=customer_id, status='Delivered').count()
    cart_count = Cart.query.filter_by(customer_id=customer_id).count()
    recent_orders = Order.query.filter_by(customer_id=customer_id).order_by(Order.id.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        customer=customer,
        total_orders=total_orders,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        cart_count=cart_count,
        recent_orders=recent_orders
    )


@customer_bp.route('/products')
def products():
    # Accessible to both logged-in customers and admins (different querysets)
    if 'customer_id' not in session and 'admin_id' not in session:
        return redirect('/login')

    order_id = request.args.get('order_id')
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int) or 1
    if page < 1:
        page = 1

    if 'admin_id' in session:
        query = Product.query.filter(Product.name.ilike(f"%{search}%"))
    else:
        query = Product.query.filter(
            Product.is_active == True,
            Product.name.ilike(f"%{search}%")
        )

    pagination = query.paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)
    products = pagination.items

    admin_logged_in = 'admin_id' in session

    return render_template(
        'products.html',
        products=products,
        pagination=pagination,
        search=search,
        order_id=order_id,
        admin_logged_in=admin_logged_in
    )


@customer_bp.route('/add_to_cart/<int:product_id>', methods=['POST'])
@require_customer
def add_to_cart(product_id):
    customer_id = session['customer_id']
    product = Product.query.get_or_404(product_id)

    # Only allow active products
    if not product.is_active:
        flash('Product is not available.')
        return redirect('/products')

    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if cart_item:
        if cart_item.quantity < product.stock:
            cart_item.quantity += 1
    else:
        if product.stock > 0:
            cart_item = Cart(customer_id=customer_id, product_id=product_id, quantity=1)
            db.session.add(cart_item)

    db.session.commit()
    flash('Product added to cart.')
    return redirect('/products')


@customer_bp.route('/cart')
@require_customer
def cart():
    customer_id = session['customer_id']
    cart_items = Cart.query.filter_by(customer_id=customer_id).all()

    products = products_by_id(item.product_id for item in cart_items)

    total = 0
    cart_data = []

    for item in cart_items:
        product = products.get(item.product_id)
        if not product:
            continue
        total += product.price * item.quantity
        cart_data.append({'product': product, 'quantity': item.quantity})

    return render_template('cart.html', cart_data=cart_data, total=total)


@customer_bp.route('/remove_from_cart/<int:product_id>', methods=['POST'])
@require_customer
def remove_from_cart(product_id):
    customer_id = session['customer_id']
    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if not cart_item:
        return redirect('/cart')

    db.session.delete(cart_item)
    db.session.commit()
    return redirect('/cart')


@customer_bp.route('/increase_quantity/<int:product_id>', methods=['POST'])
@require_customer
def increase_quantity(product_id):
    customer_id = session['customer_id']
    product = Product.query.get_or_404(product_id)
    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if cart_item and product.stock > cart_item.quantity:
        cart_item.quantity += 1
    elif cart_item:
        flash(f'Only {product.stock} units available in stock.')

    db.session.commit()
    return redirect('/cart')


@customer_bp.route('/decrease_quantity/<int:product_id>', methods=['POST'])
@require_customer
def decrease_quantity(product_id):
    customer_id = session['customer_id']
    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if not cart_item:
        return redirect('/cart')

    if cart_item.quantity > 1:
        cart_item.quantity -= 1
    else:
        db.session.delete(cart_item)

    db.session.commit()
    return redirect('/cart')


@customer_bp.route('/profile', methods=['GET', 'POST'])
@require_customer
def profile():
    customer = Customer.query.get_or_404(session['customer_id'])

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        shop_name = request.form.get('shop_name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()

        if not all([name, shop_name, mobile, city, address]):
            flash('All fields are required.')
            return redirect('/profile')

        if not re.match(r'^\d{7,15}$', mobile):
            flash('Invalid mobile number.')
            return redirect('/profile')

        customer.name = name
        customer.shop_name = shop_name
        customer.mobile = mobile
        customer.city = city
        customer.address = address

        db.session.commit()
        flash('Profile Updated Successfully')
        return redirect('/profile')

    return render_template('profile.html', customer=customer)


@customer_bp.route("/download_invoice/<int:order_id>")
@require_customer
def download_invoice(order_id):
    order = Order.query.get_or_404(order_id)

    if order.customer_id != session["customer_id"]:
        abort(403)

    pdf = generate_invoice(order)

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"Invoice_LG-{order.id:06d}.pdf",
        mimetype="application/pdf",
    )