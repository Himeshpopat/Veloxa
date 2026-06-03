from flask import Flask, render_template, request, session
from models import db, Customer, Product, Cart

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

        if customer and customer.password == password:
            session['customer_id'] = customer.id
            return render_template('dashboard.html')
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
            password=password
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
        return render_template('login.html')

    return render_template('dashboard.html')

@app.route('/logout')
def logout():

    session.pop('customer_id', None)

    return render_template('login.html')

@app.route('/add_product', methods=['GET', 'POST'])
def add_product():

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
    products = Product.query.all()

    return render_template(
        'products.html',
        products=products
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

    cart_item = Cart.query.filter_by(
        customer_id=customer_id,
        product_id=product_id
    ).first()

    if cart_item:

        cart_item.quantity += 1

    else:

        cart_item = Cart(
            customer_id=customer_id,
            product_id=product_id,
            quantity=1
        )

        db.session.add(cart_item)

    db.session.commit()

    return "Product Added To Cart"

@app.route('/cart')
def cart():

    customer_id = session['customer_id']

    cart_items = Cart.query.filter_by(
        customer_id=customer_id
    ).all()

    cart_data = []

    for item in cart_items:

        product = Product.query.get(item.product_id)

        cart_data.append({
            'product': product,
            'quantity': item.quantity
        })

    return render_template(
        'cart.html',
        cart_data=cart_data
    )

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)