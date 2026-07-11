import os
import logging
from functools import wraps
from flask import session, redirect, abort

from models import Product

logger = logging.getLogger(__name__)

# File uploads
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
UPLOAD_FOLDER = os.path.join('static', 'product_images')


def allowed_file(filename: str) -> bool:
    return (
        '.' in filename
        and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    )


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


def products_by_id(product_ids):
    """Batch-fetch products for a list of ids in a single query.

    Returns a dict of {product_id: Product}, avoiding the N+1 pattern of
    calling Product.query.get() once per row in a loop.
    """
    ids = {pid for pid in product_ids if pid is not None}
    if not ids:
        return {}
    products = Product.query.filter(Product.id.in_(ids)).all()
    return {p.id: p for p in products}


def require_customer(f):
    """Route decorator: redirect to /login if no customer is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'customer_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Route decorator: redirect to /admin_login if no admin is logged in."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect('/admin_login')
        return f(*args, **kwargs)
    return decorated