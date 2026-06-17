from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from zoneinfo import ZoneInfo

db = SQLAlchemy()

class Customer(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    shop_name = db.Column(db.String(150))

    mobile = db.Column(db.String(20))

    address = db.Column(db.Text)

    city = db.Column(db.String(100))

    email = db.Column(db.String(100), unique=True, nullable=False)
    
    password = db.Column(db.String(200), nullable=False)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    description = db.Column(db.String(500))

    image = db.Column(db.String(200))

    mrp = db.Column(db.Float, nullable=False)

    price = db.Column(db.Float, nullable=False)

    stock = db.Column(db.Integer, nullable=False)

    is_active = db.Column(db.Boolean, default=True)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer)

    product_id = db.Column(db.Integer)

    quantity = db.Column(db.Integer)

class Order(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    customer_id = db.Column(db.Integer)

    status = db.Column(db.String(50))

    created_at = db.Column(
    db.DateTime,
    default=lambda: datetime.now(
        ZoneInfo("Asia/Kolkata")
        )
    )

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    order_id = db.Column(db.Integer)

    product_id = db.Column(db.Integer)

    quantity = db.Column(db.Integer)

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), unique=True)

    password = db.Column(db.String(100))