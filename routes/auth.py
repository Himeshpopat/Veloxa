from flask import Blueprint, render_template, request, session, redirect, flash
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random
import re

from utils.brevo_email import send_email

from models import db, Customer, Admin
from routes.extensions import limiter
from routes.helpers import logger

IST = ZoneInfo("Asia/Kolkata")

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Email and password are required.')
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


@auth_bp.route('/register', methods=['GET', 'POST'])
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

        try:
            email = validate_email(
                email,
                check_deliverability=False
            ).email
        except EmailNotValidError:
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
        session['otp_time'] = datetime.now(IST).isoformat()

        session['registration_data'] = {
            'name': name,
            'shop_name': shop_name,
            'mobile': mobile,
            'city': city,
            'address': address,
            'email': email,
            'password': generate_password_hash(password)
        }

        try:
            send_email(
                email,
                "Veloxa Registration OTP",
                f"""Your OTP for Veloxa Registration is:

        {otp}

        Do not share this OTP with anyone.

        This OTP is valid for 5 minutes."""
            )

            logger.info("Registration OTP sent to [redacted email].")

        except Exception as e:
            logger.exception("Failed to send registration OTP email: %s", e)
            flash("Unable to send OTP at the moment. Please try again later.")
            return redirect('/register')

        return render_template('register.html', show_otp=True)

    return render_template('register.html', show_otp=False)


@auth_bp.route('/verify_otp', methods=['POST'])
@limiter.limit("10 per minute")
def verify_otp():
    if 'otp_time' not in session or 'otp' not in session or 'registration_data' not in session:
        return redirect('/register')

    entered_otp = request.form.get('otp', '').strip()

    if not re.match(r'^\d{6}$', entered_otp):
        flash('Invalid OTP format.')
        return render_template('register.html', show_otp=True)

    otp_time = datetime.fromisoformat(session['otp_time'])

    if datetime.now(IST) - otp_time > timedelta(minutes=5):
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
            password=data['password']
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


@auth_bp.route('/resend_otp', methods=['POST'])
@limiter.limit("3 per minute")
def resend_otp():
    if 'registration_data' not in session:
        return redirect('/register')

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['otp_time'] = datetime.now(IST).isoformat()

    email = session['registration_data']['email']

    try:
        send_email(
            email,
            "Veloxa Registration OTP",
            f"""Your OTP for Veloxa Registration is:

    {otp}

    Do not share this OTP with anyone.

    This OTP is valid for 5 minutes."""
        )

        logger.info("OTP resent to [redacted email].")

    except Exception as e:
        logger.exception("Failed to resend OTP email: %s", e)
        flash("Unable to resend OTP. Please try again later.")
        return redirect('/register')

    flash("New OTP sent successfully.")
    return render_template("register.html", show_otp=True)


@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect('/login')


@auth_bp.route('/admin_login', methods=['GET', 'POST'])
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


@auth_bp.route('/admin_logout', methods=['POST'])
def admin_logout():
    session.clear()
    return redirect('/admin_login')