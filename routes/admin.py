from flask import Blueprint, render_template, request, redirect, flash, abort, send_file
from werkzeug.utils import secure_filename
import os

from models import db, Product, Order, OrderItem
from routes.helpers import require_admin, allowed_file, safe_positive_float, safe_positive_int, UPLOAD_FOLDER, logger, products_by_id
from utils.invoice_generator import generate_invoice

ORDERS_PER_PAGE = 20

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin_dashboard')
@require_admin
def admin_dashboard():
    return render_template('admin_dashboard.html')


@admin_bp.route('/admin_orders')
@require_admin
def admin_orders():
    page = request.args.get('page', 1, type=int) or 1
    if page < 1:
        page = 1
    pagination = Order.query.order_by(Order.id.desc()).paginate(
        page=page, per_page=ORDERS_PER_PAGE, error_out=False
    )
    orders = pagination.items
    return render_template('admin_orders.html', orders=orders, pagination=pagination)


@admin_bp.route('/add_product', methods=['GET', 'POST'])
@require_admin
def add_product():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Product name is required.')
            return redirect('/add_product')

        image = request.files.get('image')
        if not image or image.filename == '':
            flash('Please select an image.')
            return redirect('/add_product')

        if not allowed_file(image.filename):
            flash('Invalid file type. Allowed: png, jpg, jpeg, gif, webp.')
            return redirect('/add_product')

        image_name = secure_filename(image.filename)
        if not image_name:
            flash('Invalid filename.')
            return redirect('/add_product')

        # Prevent path traversal
        save_path = os.path.join(UPLOAD_FOLDER, image_name)
        abs_upload = os.path.realpath(UPLOAD_FOLDER)
        abs_save = os.path.realpath(save_path)
        if not abs_save.startswith(abs_upload + os.sep):
            abort(400)

        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        image.save(save_path)

        mrp = safe_positive_float(request.form.get('mrp', ''), 'mrp')
        price = safe_positive_float(request.form.get('price', ''), 'price')
        stock = safe_positive_int(request.form.get('stock', ''), 'stock')

        product = Product(name=name, image=image_name, mrp=mrp, price=price, stock=stock)
        db.session.add(product)
        db.session.commit()

        logger.info("Admin added product id=%s", product.id)

        flash("Product added successfully.", "success")
        return redirect('/products')

    return render_template('add_product.html')


@admin_bp.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
@require_admin
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Product name is required.')
            return redirect(f'/edit_product/{product_id}')

        product.name = name
        product.mrp = safe_positive_float(request.form.get('mrp', ''), 'mrp')
        product.price = safe_positive_float(request.form.get('price', ''), 'price')
        product.stock = safe_positive_int(request.form.get('stock', ''), 'stock')

        image = request.files.get('image')
        if image and image.filename != '':
            if not allowed_file(image.filename):
                flash('Invalid file type. Allowed: png, jpg, jpeg, gif, webp.')
                return redirect(f'/edit_product/{product_id}')

            image_name = secure_filename(image.filename)
            if not image_name:
                flash('Invalid filename.')
                return redirect(f'/edit_product/{product_id}')

            save_path = os.path.join(UPLOAD_FOLDER, image_name)
            abs_upload = os.path.realpath(UPLOAD_FOLDER)
            abs_save = os.path.realpath(save_path)
            if not abs_save.startswith(abs_upload + os.sep):
                abort(400)

            os.makedirs(UPLOAD_FOLDER, exist_ok=True)
            image.save(save_path)
            product.image = image_name

        db.session.commit()
        logger.info("Admin updated product id=%s", product_id)
        return redirect('/products')

    return render_template('add_product.html', product=product)


@admin_bp.route('/delete_product/<int:product_id>', methods=['POST'])
@require_admin
def delete_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    logger.info("Admin soft-deleted product id=%s", product_id)
    return redirect('/products')


@admin_bp.route('/restore_product/<int:product_id>', methods=['POST'])
@require_admin
def restore_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = True
    db.session.commit()
    logger.info("Admin restored product id=%s", product_id)
    return redirect('/products')


@admin_bp.route('/confirm_order/<int:order_id>', methods=['POST'])
@require_admin
def confirm_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.status == 'Pending':
        order_items = OrderItem.query.filter_by(order_id=order.id).all()
        products = products_by_id(item.product_id for item in order_items)

        for item in order_items:
            product = products.get(item.product_id)
            if not product or product.stock < item.quantity:
                flash(f'Insufficient stock for {product.name if product else "a product"}.')
                return redirect('/admin_orders')

        for item in order_items:
            product = products[item.product_id]
            product.stock -= item.quantity

        order.status = 'Confirmed'

    db.session.commit()
    logger.info("Admin confirmed order %s", order_id)
    return redirect('/admin_orders')


@admin_bp.route('/cancel_order/<int:order_id>', methods=['POST'])
@require_admin
def cancel_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()
        logger.info("Admin cancelled order %s", order_id)

    return redirect('/admin_orders')


@admin_bp.route('/deliver_order/<int:order_id>', methods=['POST'])
@require_admin
def deliver_order(order_id):
    order = Order.query.get_or_404(order_id)

    if order.status == 'Confirmed':
        order.status = 'Delivered'

    db.session.commit()
    logger.info("Admin marked order %s as delivered", order_id)
    return redirect('/admin_orders')


@admin_bp.route("/admin/download_invoice/<int:order_id>")
@require_admin
def admin_download_invoice(order_id):
    order = Order.query.get_or_404(order_id)

    pdf = generate_invoice(order)

    return send_file(
        pdf,
        as_attachment=True,
        download_name=f"Invoice_LG-{order.id:06d}.pdf",
        mimetype="application/pdf",
    )