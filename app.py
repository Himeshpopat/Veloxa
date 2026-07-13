from flask import Flask, render_template, request, redirect, flash
from flask_wtf.csrf import CSRFError
from datetime import timedelta
from dotenv import load_dotenv
import os
import logging

from models import db
from routes.extensions import csrf, limiter

load_dotenv()

import cloudinary_config

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
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['ORDER_EMAIL_RECEIVER'] = os.getenv("ORDER_EMAIL_RECEIVER")
app.config['BREVO_API_KEY'] = os.getenv("BREVO_API_KEY")

# Database
database_url = os.getenv("DATABASE_URL")

if database_url:
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or "sqlite:///database.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
csrf.init_app(app)
limiter.init_app(app)

# Register blueprints (imported after extensions are initialized to avoid
# circular imports; blueprint modules only depend on models/extensions/helpers)
from routes.auth import auth_bp
from routes.customer import customer_bp
from routes.orders import orders_bp
from routes.admin import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(customer_bp)
app.register_blueprint(orders_bp)
app.register_blueprint(admin_bp)


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    flash("Session expired or invalid request. Please try again.")
    return redirect(request.referrer or "/"), 400


@app.after_request
def set_security_headers(response):
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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


@app.route('/')
def home():
    return render_template('home.html')


with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=False)