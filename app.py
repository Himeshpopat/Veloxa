from flask import Flask, render_template, request, session, redirect, flash
from models import db, Customer, Product, Cart, Order, OrderItem, Admin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from zoneinfo import ZoneInfo
from flask_mail import Mail, Message
import random

app = Flask(__name__)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'woms.proj@gmail.com'
app.config['MAIL_PASSWORD'] = 'uybe hqwn ojzv ylnp'
mail = Mail(app)

app.secret_key = 'mysecretkey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db.init_app(app)

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form['email']
        password = request.form['password']

        customer = Customer.query.filter_by(email=email).first()

        if customer and check_password_hash(customer.password,password):
            session['customer_id'] = customer.id
            return redirect('/dashboard')
        return "Invalid Email or Password"

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        name = request.form['name']
        shop_name = request.form['shop_name']
        mobile = request.form['mobile']
        city = request.form['city']
        address = request.form['address']
        email = request.form['email']
        password = request.form['password']

        existing_customer = Customer.query.filter_by(
            email=email
        ).first()

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

        msg.body = f'''
        Your OTP for WOMS Registration is:

        {otp}

        Do not share this OTP with anyone.
        '''

        mail.send(msg)

        return render_template(
            'register.html',
            show_otp=True
        )

    return render_template(
        'register.html',
        show_otp=False
    )

@app.route('/verify_otp', methods=['POST'])
def verify_otp():

    entered_otp = request.form['otp']

    otp_time = datetime.fromisoformat(
    session['otp_time']
    )

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
            password=generate_password_hash(
                data['password']
            )
        )

        db.session.add(customer)
        db.session.commit()

        session.pop('otp', None)
        session.pop('registration_data', None)

        flash('Registration Successful')
        return redirect('/login')

    flash('Invalid OTP')

    return render_template(
        'register.html',
        show_otp=True
    )

@app.route('/resend_otp')
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

    msg.body = f'''
Your OTP for WOMS Registration is:

{otp}

This OTP is valid for 5 minutes.
'''

    mail.send(msg)

    flash('New OTP sent successfully.')

    return render_template(
        'register.html',
        show_otp=True
    )

@app.route('/customers')
def customers():

    all_customers = Customer.query.all()

    result = ""

    for customer in all_customers:
        result += f"{customer.name} - {customer.email}<br>"

    return result

@app.route('/dashboard')
def dashboard():

    if 'customer_id' not in session:
        return redirect('/login')

    customer_id = session['customer_id']

    customer = Customer.query.get(customer_id)

    total_orders = Order.query.filter_by(
        customer_id=customer_id
    ).count()

    pending_orders = Order.query.filter_by(
        customer_id=customer_id,
        status='Pending'
    ).count()

    delivered_orders = Order.query.filter_by(
        customer_id=customer_id,
        status='Delivered'
    ).count()

    cart_count = Cart.query.filter_by(
        customer_id=customer_id
    ).count()

    recent_orders = Order.query.filter_by(
        customer_id=customer_id
    ).order_by(Order.id.desc()).limit(5).all()

    return render_template(
        'dashboard.html',
        customer=customer,
        total_orders=total_orders,
        pending_orders=pending_orders,
        delivered_orders=delivered_orders,
        cart_count=cart_count,
        recent_orders=recent_orders
    )

@app.route('/logout')
def logout():

    session.pop('customer_id', None)

    return render_template('login.html')

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():

    if 'admin_id' not in session:
        return redirect('/admin_login')

    if request.method == 'POST':

        name = request.form['name']
        description = request.form['description']

        image = request.files['image']
        image_name = image.filename
        print(image_name)
        print(type(image_name))
        path = 'static/product_images/' + image_name
        print(path)

        image.save(path)

        mrp = float(request.form['mrp'])
        price = float(request.form['price'])
        stock = int(request.form['stock'])

        product = Product(
            name=name,
            description=description,
            image=image_name,
            mrp=mrp,
            price=price,
            stock=stock
        )

        db.session.add(product)
        db.session.commit()

        return "Product Added Successfully"

    return render_template('add_product.html')

@app.route('/products')
def products():
    if 'customer_id' not in session and 'admin_id' not in session:
        return redirect('/login')

    order_id = request.args.get('order_id')
    search = request.args.get('search', '')
    
    if 'admin_id' in session:
        products = Product.query.filter(
            Product.name.ilike(f"%{search}%")
        ).all()

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

@app.route('/cart_test')
def cart_test():

    all_cart_items = Cart.query.all()

    result = ""

    for item in all_cart_items:

        result += f"""
        Customer ID: {item.customer_id}
        Product ID: {item.product_id}
        Quantity: {item.quantity}
        <br><br>
        """

    return result

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):

    customer_id = session['customer_id']
    product = Product.query.get(product_id)

    cart_item = Cart.query.filter_by(
        customer_id=customer_id,
        product_id=product_id
    ).first()

    if cart_item:
        if cart_item.quantity < product.stock:
            cart_item.quantity += 1

    else:
        if product.stock > 0:
            cart_item = Cart(
                customer_id=customer_id,
                product_id=product_id,
                quantity=1
            )

            db.session.add(cart_item)

    db.session.commit()
    return redirect('/cart')

@app.route('/cart')
def cart():

    customer_id = session['customer_id']

    cart_items = Cart.query.filter_by(
        customer_id=customer_id
    ).all()

    total = 0
    cart_data = []

    for item in cart_items:
        product = Product.query.get(item.product_id)
        total += product.price * item.quantity

        cart_data.append({
            'product': product,
            'quantity': item.quantity
        })

    return render_template(
        'cart.html',
        cart_data=cart_data,
        total=total
    )

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):

    customer_id = session['customer_id']

    cart_item = Cart.query.filter_by(
        customer_id=customer_id,
        product_id=product_id
    ).first()

    db.session.delete(cart_item)
    db.session.commit()

    return redirect('/cart')

@app.route('/increase_quantity/<int:product_id>')
def increase_quantity(product_id):

    customer_id = session['customer_id']
    product = Product.query.get(product_id)

    cart_item = Cart.query.filter_by(
        customer_id=customer_id,
        product_id=product_id
    ).first()

    if cart_item and product.stock > cart_item.quantity:
        cart_item.quantity += 1
    else:
        flash(f'Only {product.stock} units available in stock.')

    db.session.commit()

    return redirect('/cart')

@app.route('/decrease_quantity/<int:product_id>')
def decrease_quantity(product_id):

    customer_id = session['customer_id']

    cart_item = Cart.query.filter_by(
        customer_id=customer_id,
        product_id=product_id
    ).first()

    cart_item.quantity -= 1

    db.session.commit()

    return redirect('/cart')

@app.route('/place_order')
def place_order():

    customer_id = session['customer_id']

    cart_items = Cart.query.filter_by(
        customer_id=customer_id
    ).all()

    for item in cart_items:

        product = Product.query.get(item.product_id)

        if not product.is_active:
            flash(f'{product.name} is no longer available.')
            return redirect('/cart')

        if item.quantity > product.stock:
            flash(f'Only {product.stock} units of {product.name} are available.')
            return redirect('/cart')

    order = Order(
        customer_id=customer_id,
        status='Pending'
    )

    db.session.add(order)
    db.session.commit()

    for item in cart_items:

        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            quantity=item.quantity
        )

        db.session.add(order_item)

    db.session.commit()

    for item in cart_items:
        db.session.delete(item)

    db.session.commit()
    return redirect('/my_orders')

@app.route('/my_orders')
def my_orders():

    customer_id = session['customer_id']

    orders = Order.query.filter_by(
        customer_id=customer_id
    ).order_by(Order.id.desc()).all()

    return render_template(
        'my_orders.html',
        orders=orders
    )

@app.route('/order_details/<int:order_id>')
def order_details(order_id):

    order = Order.query.get(order_id)

    if 'admin_id' not in session:

        customer_id = session['customer_id']

        if order.customer_id != customer_id:
            return redirect('/my_orders')

    order_items = OrderItem.query.filter_by(
        order_id=order_id
    ).all()

    order_data = []
    total = 0

    for item in order_items:

        product = Product.query.get(item.product_id)

        item_total = product.price * item.quantity
        total += item_total

        order_data.append({
            'product': product,
            'quantity': item.quantity,
            'item_total': item_total
        })

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

    order = Order.query.get(order_id)

    if order.status == 'Pending':
        order_items = OrderItem.query.filter_by(
            order_id=order.id
        ).all()

        for item in order_items:
            product = Product.query.get(item.product_id)
            if product.stock < item.quantity:
                flash(f'Insufficient stock for {product.name}.')
                return redirect('/admin_orders')

        for item in order_items:
            product = Product.query.get(item.product_id)
            product.stock -= item.quantity

        order.status = 'Confirmed'

    db.session.commit()
    return redirect('/admin_orders')

@app.route('/cancel_order/<int:order_id>')
def cancel_order(order_id):

    if 'admin_id' not in session:
        return redirect('/admin_login')

    order = Order.query.get(order_id)

    if order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()

    return redirect('/admin_orders')

@app.route('/deliver_order/<int:order_id>')
def deliver_order(order_id):

    if 'admin_id' not in session:
        return redirect('/admin_login')

    order = Order.query.get(order_id)

    if order.status == 'Confirmed':
        order.status = 'Delivered'

    db.session.commit()

    return redirect('/admin_orders')

@app.route('/customer_cancel_order/<int:order_id>')
def customer_cancel_order(order_id):

    customer_id = session['customer_id']

    order = Order.query.get(order_id)

    if order.customer_id == customer_id and order.status == 'Pending':
        order.status = 'Cancelled'
        db.session.commit()

    return redirect('/my_orders')

@app.route('/edit_order/<int:order_id>')
def edit_order(order_id):

    customer_id = session['customer_id']

    order = Order.query.get_or_404(order_id)

    if order.customer_id != customer_id:
        flash('Unauthorized access.', 'danger')
        return redirect('/my_orders')

    if order.status != 'Pending':
        flash('Only pending orders can be edited.', 'warning')
        return redirect('/my_orders')

    order_items = OrderItem.query.filter_by(
        order_id=order_id
    ).all()

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

    customer_id = session['customer_id']

    item = OrderItem.query.get(item_id)
    order = Order.query.get(item.order_id)
    product = Product.query.get(item.product_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    if product.stock > item.quantity:
        item.quantity += 1
    else:
        flash(f'Only {product.stock} units available in stock.')

    db.session.commit()
    return redirect(f'/edit_order/{item.order_id}')

@app.route('/decrease_order_quantity/<int:item_id>')
def decrease_order_quantity(item_id):

    customer_id = session['customer_id']

    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get(item.order_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    if item.quantity > 1:

        item.quantity -= 1
        db.session.commit()

    else:

        total_items = OrderItem.query.filter_by(
            order_id=order.id
        ).count()

        if total_items <= 1:

            flash(
                'An order must contain at least one item.',
                'warning'
            )

    return redirect(f'/edit_order/{item.order_id}')

@app.route('/remove_order_item/<int:item_id>')
def remove_order_item(item_id):

    customer_id = session['customer_id']

    item = OrderItem.query.get_or_404(item_id)
    order = Order.query.get(item.order_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    remaining_items = OrderItem.query.filter_by(
        order_id=order.id
    ).count()

    if remaining_items <= 1:

        flash(
            'Order must contain at least one item.',
            'warning'
        )

        return redirect(f'/edit_order/{order.id}')

    db.session.delete(item)
    db.session.commit()

    flash(
        'Item removed successfully.',
        'success'
    )

    return redirect(f'/edit_order/{order.id}')

@app.route('/add_product_to_order/<int:order_id>')
def add_product_to_order(order_id):

    products = Product.query.all()

    return render_template(
        'products.html',
        products=products,
        order_id=order_id
    )

@app.route('/add_to_order/<int:order_id>/<int:product_id>')
def add_to_order(order_id, product_id):

    product = Product.query.get(product_id)

    item = OrderItem.query.filter_by(
        order_id=order_id,
        product_id=product_id
    ).first()

    if item:
        if item.quantity < product.stock:
            item.quantity += 1
        else:
            flash(f'Only {product.stock} units available in stock.')

    else:

        if product.stock > 0:
            item = OrderItem(
                order_id=order_id,
                product_id=product_id,
                quantity=1
            )
            db.session.add(item)

        else:
            flash('Product is out of stock.')

    db.session.commit()

    return redirect(f'/edit_order/{order_id}')

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = Admin.query.filter_by(
            username=username,
            password=password
        ).first()

        if admin:
            session['admin_id'] = admin.id
            return redirect('/admin_dashboard')

    return render_template('admin_login.html')

@app.route('/admin_orders')
def admin_orders():

    if 'admin_id' not in session:
        return redirect('/admin_login')

    orders = Order.query.order_by(Order.id.desc()).all()

    return render_template(
        'admin_orders.html',
        orders=orders
    )

@app.route('/admin_logout')
def admin_logout():

    session.pop('admin_id', None)

    return redirect('/admin_login')

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin_login')

    product = Product.query.get(product_id)

    if request.method == 'POST':

        product.name = request.form['name']
        product.description = request.form['description']
        product.mrp = request.form['mrp']
        product.price = request.form['price']
        product.stock = request.form['stock']

        image = request.files['image']
        if image.filename != '':
            image_name = image.filename
            image.save(
                'static/product_images/' + image_name
            )
            product.image = image_name

        db.session.commit()

        return redirect('/products')

    return render_template(
        'add_product.html',
        product=product
    )

@app.route('/delete_product/<int:product_id>', methods=['GET', 'POST'])
def delete_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin_login')

    product = Product.query.get(product_id)

    product.is_active = False
    db.session.commit()

    return redirect('/products')

@app.route('/restore_product/<int:product_id>')
def restore_product(product_id):

    if 'admin_id' not in session:
        return redirect('/admin_login')

    product = Product.query.get_or_404(product_id)

    product.is_active = True
    db.session.commit()

    return redirect('/products')

@app.route('/admin_dashboard')
def admin_dashboard():

    if 'admin_id' not in session:
        return redirect('/admin_login')

    return render_template('admin_dashboard.html')

@app.route('/create_admin')
def create_admin():

    admin = Admin(
        username='admin',
        password='admin123'
    )

    db.session.add(admin)
    db.session.commit()

    return 'Admin Created'

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)