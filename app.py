from flask import Flask, render_template, request, session, redirect, flash
from models import db, Customer, Product, Cart, Order, OrderItem, Admin
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
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
        email = request.form['email']
        password = request.form['password']

        customer = Customer(
            name=name,
            email=email,
            password=generate_password_hash(password)
        )

        db.session.add(customer)
        db.session.commit()

        return "Registration Successful"

    return render_template('register.html')

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
    order_id = request.args.get('order_id')
    search = request.args.get('search', '')
    
    if 'admin_id' in session:
        products = Product.query.filter(
            Product.name.contains(search)
        ).all()

    else:
        products = Product.query.filter(
            Product.is_active == True,
            Product.name.contains(search)
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
    ).all()

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

    return render_template(
        'order_details.html',
        order_data=order_data,
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

    order = Order.query.get(order_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    order_items = OrderItem.query.filter_by(
        order_id=order_id
    ).all()

    order_data = []

    for item in order_items:

        product = Product.query.get(item.product_id)

        order_data.append({
            'product': product,
            'quantity': item.quantity,
            'item_id': item.id
        })

    return render_template(
        'edit_order.html',
        order_id=order_id,
        order_data=order_data
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
    item = OrderItem.query.get(item_id)
    order = Order.query.get(item.order_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    if item.quantity > 1:
        item.quantity -= 1

    db.session.commit()

    return redirect(f'/edit_order/{item.order_id}')

@app.route('/remove_order_item/<int:item_id>')
def remove_order_item(item_id):

    customer_id = session['customer_id']

    item = OrderItem.query.get(item_id)
    order_id = item.order_id
    order = Order.query.get(item.order_id)

    if order.customer_id != customer_id:
        return redirect('/my_orders')

    db.session.delete(item)
    db.session.commit()

    remaining_items = OrderItem.query.filter_by(
    order_id=order_id
    ).all()

    if len(remaining_items) == 0 :
        order = Order.query.get(order_id)
        order.status = 'Cancelled'

    db.session.commit()

    return redirect(f'/edit_order/{order_id}')

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

    orders = Order.query.all()

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