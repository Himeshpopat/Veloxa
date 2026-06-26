from flask import Flask, render_template, request, session, redirect, flash, abort
from models import db, Customer, Product, Cart, Order, OrderItem, Admin
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import random
import os
import logging
import re

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

app.secret_key = os.getenv("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is not set.")

# Session security
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)

# Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
app.config['ORDER_EMAIL_RECEIVER'] = os.getenv("ORDER_EMAIL_RECEIVER")

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    "DATABASE_URL", "sqlite:///database.db"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
UPLOAD_FOLDER = os.path.join('static', 'product_images')

db.init_app(app)
mail = Mail(app)
csrf = CSRFProtect(app)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self';"
    )
    return response

@app.errorhandler(400)
def bad_request(e):
    return render_template('errors/400.html'), 400

@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    logger.exception("Internal server error: %s", e)
    return render_template('errors/500.html'), 500

@app.errorhandler(CSRFError)
def csrf_error(e):
    flash('Session expired or invalid request. Please try again.')
    return redirect(request.referrer or '/'), 400

def allowed_file(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )

def valid_email(email: str) -> bool:
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email))

def safe_positive_float(value: str, field: str) -> float:
    """Parse a string to a positive float; abort(400) on failure."""
    try:
        v = float(value)
        if v < 0:
            raise ValueError
        return v
    except (ValueError, TypeError):
        logger.warning("Invalid value for field '%s': %s", field, value)
        abort(400)

def safe_positive_int(value: str, field: str) -> int:
    """Parse a string to a non-negative int; abort(400) on failure."""
    try:
        v = int(value)
        if v < 0:
            raise ValueError
        return v
    except (ValueError, TypeError):
        logger.warning("Invalid value for field '%s': %s", field, value)
        abort(400)

def require_customer():
    if 'customer_id' not in session:
        abort(403)
    return session['customer_id']

def require_admin():
    if 'admin_id' not in session:
        abort(403)


@app.route('/')
def home():
    return render_template('home.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.')
            return redirect('/login')

        if not valid_email(email):
            flash('Invalid Email or Password')
            return redirect('/login')

        customer = Customer.query.filter_by(email=email).first()

        if customer and check_password_hash(customer.password, password):
            # Regenerate session to prevent fixation
            session.clear()
            session['customer_id'] = customer.id
            session.permanent = True
            logger.info("Customer %s logged in.", customer.id)
            return redirect('/dashboard')

        logger.warning("Failed login attempt for email: [redacted]")
        flash('Invalid Email or Password')
        return redirect('/login')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        shop_name = request.form.get('shop_name', '').strip()
        mobile = request.form.get('mobile', '').strip()
        city = request.form.get('city', '').strip()
        address = request.form.get('address', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Required field validation
        if not all([name, shop_name, mobile, city, address, email, password]):
            flash('All fields are required.')
            return redirect('/register')

        if not valid_email(email):
            flash('Invalid email format.')
            return redirect('/register')

        if len(password) < 8:
            flash('Password must be at least 8 characters.')
            return redirect('/register')

        if not re.match(r'^\d{7,15}$', mobile):
            flash('Invalid mobile number.')
            return redirect('/register')

        existing_customer = Customer.query.filter_by(email=email).first()
        if existing_customer:
            flash('Email already registered')
            return redirect('/register')

        otp = str(random.randint(100000, 999999))

        session['otp'] = otp
        session['otp_time'] = datetime.now().isoformat()

        session['registration_data'] = {
            'name': name,
            'shop_name': shop_name,
            'mobile': mobile,
            'city': city,
            'address': address,
            'email': email,
            'password': password
        }

        msg = Message(
            'WOMS Registration OTP',
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = (
            "Your OTP for WOMS Registration is:\n\n"
            f"{otp}\n\n"
            "Do not share this OTP with anyone.\n"
            "This OTP is valid for 5 minutes."
        )
        mail.send(msg)
        # Do NOT log the OTP
        logger.info("Registration OTP sent to [redacted email].")

        return render_template('register.html', show_otp=True)

    return render_template('register.html', show_otp=False)


@app.route('/verify_otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    if 'otp_time' not in session or 'otp' not in session or 'registration_data' not in session:
        return redirect('/register')

    entered_otp = request.form.get('otp', '').strip()

    if not re.match(r'^\d{6}$', entered_otp):
        flash('Invalid OTP format.')
        return render_template('register.html', show_otp=True)

    otp_time = datetime.fromisoformat(session['otp_time'])

    if datetime.now() - otp_time > timedelta(minutes=5):
        session.pop('otp', None)
        session.pop('otp_time', None)
        session.pop('registration_data', None)
        flash('OTP Expired. Please register again.')
        return redirect('/register')

    if entered_otp == session.get('otp'):
        data = session['registration_data']

        customer = Customer(
            name=data['name'],
            shop_name=data['shop_name'],
            mobile=data['mobile'],
            city=data['city'],
            address=data['address'],
            email=data['email'],
            password=generate_password_hash(data['password'])
        )

        db.session.add(customer)
        db.session.commit()

        session.pop('otp', None)
        session.pop('otp_time', None)
        session.pop('registration_data', None)

        logger.info("New customer registered successfully.")
        flash('Registration Successful')
        return redirect('/login')

    flash('Invalid OTP')
    return render_template('register.html', show_otp=True)


@app.route('/resend_otp')
@limiter.limit("3 per minute")
def resend_otp():
    if 'registration_data' not in session:
        return redirect('/register')

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = datetime.now().isoformat()

    email = session['registration_data']['email']

    msg = Message(
        'WOMS Registration OTP',
        sender=app.config['MAIL_USERNAME'],
        recipients=[email]
    )
    msg.body = (
        "Your OTP for WOMS Registration is:\n\n"
        f"{otp}\n\n"
        "This OTP is valid for 5 minutes."
    )
    mail.send(msg)
    logger.info("OTP resent to [redacted email].")

    flash('New OTP sent successfully.')
    return render_template('register.html', show_otp=True)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/dashboard')
def dashboard():
    if 'customer_id' not in session:
        return redirect('/login')

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


@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if 'admin_id' not in session:
        return redirect('/admin_login')

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
        return "Product Added Successfully"

    return render_template('add_product.html')


@app.route('/products')
def products():
    if 'customer_id' not in session and 'admin_id' not in session:
        return redirect('/login')

    order_id = request.args.get('order_id')
    search = request.args.get('search', '').strip()

    if 'admin_id' in session:
        products = Product.query.filter(Product.name.ilike(f"%{search}%")).all()
    else:
        products = Product.query.filter(
            Product.is_active == True,
            Product.name.ilike(f"%{search}%")
        ).all()

    admin_logged_in = 'admin_id' in session

    return render_template(
        'products.html',
        products=products,
        order_id=order_id,
        admin_logged_in=admin_logged_in
    )


@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

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


@app.route('/delete_product/<int:product_id>', methods=['GET', 'POST'])
def delete_product(product_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

    product = Product.query.get_or_404(product_id)
    product.is_active = False
    db.session.commit()
    logger.info("Admin soft-deleted product id=%s", product_id)
    return redirect('/products')


@app.route('/restore_product/<int:product_id>')
def restore_product(product_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

    product = Product.query.get_or_404(product_id)
    product.is_active = True
    db.session.commit()
    logger.info("Admin restored product id=%s", product_id)
    return redirect('/products')


@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'customer_id' not in session:
        return redirect('/login')

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
    return redirect('/cart')


@app.route('/cart')
def cart():
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    cart_items = Cart.query.filter_by(customer_id=customer_id).all()

    total = 0
    cart_data = []

    for item in cart_items:
        product = Product.query.get(item.product_id)
        if not product:
            continue
        total += product.price * item.quantity
        cart_data.append({'product': product, 'quantity': item.quantity})

    return render_template('cart.html', cart_data=cart_data, total=total)


@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if not cart_item:
        return redirect('/cart')

    db.session.delete(cart_item)
    db.session.commit()
    return redirect('/cart')


@app.route('/increase_quantity/<int:product_id>')
def increase_quantity(product_id):
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    product = Product.query.get_or_404(product_id)
    cart_item = Cart.query.filter_by(customer_id=customer_id, product_id=product_id).first()

    if cart_item and product.stock > cart_item.quantity:
        cart_item.quantity += 1
    elif cart_item:
        flash(f'Only {product.stock} units available in stock.')

    db.session.commit()
    return redirect('/cart')


@app.route('/decrease_quantity/<int:product_id>')
def decrease_quantity(product_id):
    if 'customer_id' not in session:
        return redirect('/login')

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


@app.route('/place_order')
def place_order():
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    cart_items = Cart.query.filter_by(customer_id=customer_id).all()

    if not cart_items:
        flash('Cart is empty.')
        return redirect('/cart')

    for item in cart_items:
        product = Product.query.get(item.product_id)
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

    msg = Message(
        'New Order Received',
        sender=app.config['MAIL_USERNAME'],
        recipients=[app.config['ORDER_EMAIL_RECEIVER']]
    )
    msg.body = (
        f"New Order Received\n\n"
        f"Order ID: {order.id}\n\n"
        f"Customer: {customer.name}\n"
        f"Shop: {customer.shop_name}\n"
        f"Mobile: {customer.mobile}\n"
        f"City: {customer.city}\n\n"
        f"Please check the Order."
    )
    mail.send(msg)

    for item in cart_items:
        order_item = OrderItem(order_id=order.id, product_id=item.product_id, quantity=item.quantity)
        db.session.add(order_item)

    db.session.commit()

    for item in cart_items:
        db.session.delete(item)

    db.session.commit()
    logger.info("Customer %s placed order %s", customer_id, order.id)
    return redirect('/my_orders')


@app.route('/my_orders')
def my_orders():
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    orders = Order.query.filter_by(customer_id=customer_id).order_by(Order.id.desc()).all()

    return render_template('my_orders.html', orders=orders)


@app.route('/order_details/<int:order_id>')
def order_details(order_id):
    order = Order.query.get_or_404(order_id)

    if 'admin_id' not in session:
        if 'customer_id' not in session:
            return redirect('/login')
        # Ownership check
        if order.customer_id != session['customer_id']:
            abort(403)

    order_items = OrderItem.query.filter_by(order_id=order_id).all()

    order_data = []
    total = 0

    for item in order_items:
        product = Product.query.get(item.product_id)
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


@app.route('/confirm_order/<int:order_id>')
def confirm_order(order_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

    order = Order.query.get_or_404(order_id)

    if order.status == 'Pending':
        order_items = OrderItem.query.filter_by(order_id=order.id).all()

        for item in order_items:
            product = Product.query.get(item.product_id)
            if not product or product.stock < item.quantity:
                flash(f'Insufficient stock for {product.name if product else "a product"}.')
                return redirect('/admin_orders')

        for item in order_items:
            product = Product.query.get(item.product_id)
            product.stock -= item.quantity

        order.status = 'Confirmed'

    db.session.commit()
    logger.info("Admin confirmed order %s", order_id)
    return redirect('/admin_orders')


@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

    order = Order.query.get_or_404(order_id)

    if order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()
        logger.info("Admin cancelled order %s", order_id)

    return redirect('/admin_orders')


@app.route('/deliver_order/<int:order_id>')
def deliver_order(order_id):
    if 'admin_id' not in session:
        return redirect('/admin_login')

    order = Order.query.get_or_404(order_id)

    if order.status == 'Confirmed':
        order.status = 'Delivered'

    db.session.commit()
    logger.info("Admin marked order %s as delivered", order_id)
    return redirect('/admin_orders')


@app.route('/customer_cancel_order/<int:order_id>')
def customer_cancel_order(order_id):
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    order = Order.query.get_or_404(order_id)

    # Ownership + status check
    if order.customer_id == customer_id and order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()
        logger.info("Customer %s cancelled order %s", customer_id, order_id)

    return redirect('/my_orders')


@app.route('/edit_order/<int:order_id>')
def edit_order(order_id):
    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']
    order = Order.query.get_or_404(order_id)

    if order.customer_id != customer_id:
        abort(403)

    if order.status != 'Pending':
        flash('Only pending orders can be edited.', 'warning')
        return redirect('/my_orders')

    order_items = OrderItem.query.filter_by(order_id=order_id).all()

    order_data = []
    total = 0
    total_items = 0

    for item in order_items:
        product = Product.query.get(item.product_id)
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


@app.route('/increase_order_quantity/<int:item_id>')
def increase_order_quantity(item_id):
    if 'customer_id' not in session:
        return redirect('/login')

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


@app.route('/decrease_order_quantity/<int:item_id>')
def decrease_order_quantity(item_id):
    if 'customer_id' not in session:
        return redirect('/login')

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


@app.route('/remove_order_item/<int:item_id>')
def remove_order_item(item_id):
    if 'customer_id' not in session:
        return redirect('/login')

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


@app.route('/add_product_to_order/<int:order_id>')
def add_product_to_order(order_id):
    if 'customer_id' not in session:
        return redirect('/login')

    order = Order.query.get_or_404(order_id)

    if order.customer_id != session['customer_id']:
        abort(403)

    if order.status != 'Pending':
        abort(403)

    products = Product.query.filter_by(is_active=True).all()

    return render_template('products.html', products=products, order_id=order_id)


@app.route('/add_to_order/<int:order_id>/<int:product_id>')
def add_to_order(order_id, product_id):
    if 'customer_id' not in session:
        return redirect('/login')

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

@app.route('/admin_login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.')
            return render_template('admin_login.html')

        admin = Admin.query.filter_by(username=username).first()

        if admin and check_password_hash(admin.password, password):
            session.clear()
            session['admin_id'] = admin.id
            session.permanent = True
            logger.info("Admin %s logged in.", admin.id)
            return redirect('/admin_dashboard')

        logger.warning("Failed admin login attempt for username: [redacted]")
        flash('Invalid Username or Password')

    return render_template('admin_login.html')


@app.route('/admin_orders')
def admin_orders():
    if 'admin_id' not in session:
        return redirect('/admin_login')

    orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin_orders.html', orders=orders)


@app.route('/admin_logout')
def admin_logout():
    session.clear()
    return redirect('/admin_login')


@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect('/admin_login')

    return render_template('admin_dashboard.html')


@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'customer_id' not in session:
        return redirect('/login')

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

    return 'Admin Created'

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)