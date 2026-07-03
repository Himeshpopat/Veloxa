from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from models import Customer, Product, OrderItem
from datetime import datetime
from zoneinfo import ZoneInfo


# =========================================================
# PAGE / LAYOUT CONSTANTS
# =========================================================
PAGE_WIDTH, PAGE_HEIGHT = A4

MARGIN = 15 * mm

CONTENT_TOP = PAGE_HEIGHT - MARGIN
CONTENT_BOTTOM = MARGIN
CONTENT_RIGHT = PAGE_WIDTH - MARGIN

# Greyscale palette (no colors, per requirements)
GREY_LIGHT = 0.95   # table header shading
GREY_MID = 0.40     # secondary / label text
GREY_LINE = 0.80    # thin borders and dividers

# Table column boundaries (sum of widths = content width = 180mm)
COL_SR_X0 = MARGIN
COL_SR_X1 = COL_SR_X0 + 15 * mm
COL_PRODUCT_X1 = COL_SR_X1 + 85 * mm
COL_QTY_X1 = COL_PRODUCT_X1 + 20 * mm
COL_RATE_X1 = COL_QTY_X1 + 30 * mm
COL_AMOUNT_X1 = COL_RATE_X1 + 30 * mm  # == CONTENT_RIGHT
RATE_X = (COL_QTY_X1 + COL_RATE_X1) / 2 + 1 * mm

TABLE_HEADER_HEIGHT = 9 * mm
ROW_HEIGHT = 8 * mm

# Space reserved at the bottom of the LAST page for the summary box + footer
SUMMARY_FOOTER_RESERVE = 55 * mm

MAX_PRODUCT_NAME_LEN = 40


# =========================================================
# NUMBERED CANVAS (For Page X of Y pagination)
# =========================================================
class NumberedCanvas(canvas.Canvas):
    """Canvas subclass to calculate total pages dynamically and draw 'Page X of Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        if self._pageNumber > num_pages:
            self._saved_page_states.append(dict(self.__dict__))
            num_pages += 1
            
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillGray(GREY_MID)
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawCentredString(PAGE_WIDTH / 2.0, MARGIN - 6 * mm, page_text)
        self.restoreState()


# =========================================================
# SMALL HELPERS
# =========================================================
def format_currency(value):
    """Format a number as Indian-rupee currency with thousands separators."""
    return f"Rs.{value:,.2f}"


def truncate_text(text, max_len=MAX_PRODUCT_NAME_LEN):
    """Shorten long product names and append an ellipsis."""
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def format_date(dt):
    return dt.strftime("%d-%m-%Y") if dt else "-"


def wrap_text_to_lines(c, text, max_width, font_name, font_size):
    """Split text into a list of lines that fit within max_width."""
    words = text.split()
    if not words:
        return [""]
    
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word]) if current_line else word
        width = c.stringWidth(test_line, font_name, font_size)
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))
    return lines


def get_row_height(c, name):
    """Calculate dynamic row height based on text wrapping."""
    lines = wrap_text_to_lines(c, name, 79 * mm, "Helvetica", 9)
    return 8 * mm + (len(lines) - 1) * 4 * mm


# =========================================================
# HEADER (company info + invoice meta) — page 1 only
# =========================================================
def draw_company_header(c, order):
    """Draw the top-left company block and top-right invoice title block.
    Returns the y coordinate directly below the header separator line.
    """
    top = CONTENT_TOP

    # ---- Left: company details ----
    c.setFont("Helvetica-Bold", 18)
    c.setFillGray(0)
    c.drawString(MARGIN, top - 6 * mm, "Admin's Shop Name")

    c.setFont("Helvetica", 9)
    c.setFillGray(GREY_MID)
    address_lines = [
        "Address Line 1",
        "Address Line 2",
        "Contact No.: XXXXXXXXXX",
        "Email: xyz@gmail.com",
    ]
    y = top - 14 * mm
    for line in address_lines:
        c.drawString(MARGIN, y, line)
        y -= 5 * mm
    c.setFillGray(0)  # reset to black

    # ---- Right: invoice title + meta ----
    c.setFont("Helvetica-Bold", 18)
    c.drawRightString(CONTENT_RIGHT, top - 6 * mm, "INVOICE")

    invoice_no = f"INV-{order.id:06d}"
    invoice_date = format_date(datetime.now(ZoneInfo("Asia/Kolkata")))
    order_date = format_date(getattr(order, "order_date", None) or getattr(order, "created_at", None))

    meta_rows = [
        ("Invoice No.:", invoice_no),
        ("Invoice Date:", invoice_date),
        ("Order Date:", order_date),
    ]

    y_meta = top - 14 * mm
    for label, value in meta_rows:
        c.setFont("Helvetica", 8)
        c.setFillGray(GREY_MID)
        c.drawString(CONTENT_RIGHT - 35 * mm, y_meta, label)
        
        c.setFont("Helvetica-Bold", 9)
        c.setFillGray(0)
        c.drawRightString(CONTENT_RIGHT, y_meta, value)
        y_meta -= 4.5 * mm

    # ---- Separator below header ----
    header_bottom = top - 35 * mm
    c.setStrokeGray(GREY_LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, header_bottom, CONTENT_RIGHT, header_bottom)
    c.setStrokeGray(0)
    c.setLineWidth(1)

    return header_bottom

# =========================================================
# CUSTOMER "BILL TO" BOX
# =========================================================
def draw_customer_box(c, customer, y_top):
    """Draw Bill To box."""
    
    box_height = 28 * mm
    box_top = y_top - 6 * mm
    box_bottom = box_top - box_height

    # Box
    c.setStrokeGray(GREY_LINE)
    c.setLineWidth(0.5)
    c.setFillGray(0.98)
    c.roundRect(
        MARGIN,
        box_bottom,
        CONTENT_RIGHT - MARGIN,
        box_height,
        3 * mm,
        fill=1,
        stroke=1,
    )
    c.setFillGray(0)

    pad_x = 6 * mm
    x = MARGIN + pad_x
    y = box_top - 7 * mm

    # BILL TO
    c.setFont("Helvetica-Bold", 8)
    c.setFillGray(GREY_MID)
    c.drawString(x, y, "BILL TO")
    c.setFillGray(0)

    shop_name = getattr(customer, "shop_name", "") or getattr(customer, "name", "") or "Valued Customer"
    address = getattr(customer, "address", "") or ""
    city = getattr(customer, "city", "") or ""

    # Shop Name
    y -= 6 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(x, y, f"M/s. {shop_name}")

    
    # Address
    if address:
        y -= 5.5 * mm
        c.setFont("Helvetica", 9)
        clean_address = (
            address.replace("\r\n", ", ")
                .replace("\n", ", ")
                .replace("\r", ", ")
                .replace("•", ", ")
                .replace("—", "-")
                .replace("–", "-")
                .replace(" ,", ",")
                .strip()
        )

    c.drawString(x, y, f"Address: {clean_address}")

    # City
    if city:
        y -= 4.8 * mm
        c.setFont("Helvetica", 9)
        c.drawString(x, y, f"City: {city}")

    return box_bottom - 6 * mm

# =========================================================
# PRODUCT TABLE
# =========================================================
def draw_table_header(c, y_top):
    """Draw the shaded table header row and borders.
    Returns the y coordinate of the header's bottom border.
    """
    header_bottom = y_top - TABLE_HEADER_HEIGHT

    # Shaded header background
    c.setFillGray(GREY_LIGHT)
    c.rect(MARGIN, header_bottom, CONTENT_RIGHT - MARGIN, TABLE_HEADER_HEIGHT, fill=1, stroke=0)
    c.setFillGray(0)

    # Top and bottom borders
    c.setStrokeGray(GREY_LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, y_top, CONTENT_RIGHT, y_top)
    c.line(MARGIN, header_bottom, CONTENT_RIGHT, header_bottom)
    c.setStrokeGray(0)

    # Header labels
    label_y = header_bottom + 3 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString((COL_SR_X0 + COL_SR_X1) / 2, label_y, "Sr.")
    c.drawString(COL_SR_X1 + 3 * mm, label_y, "Product")
    c.drawCentredString((COL_PRODUCT_X1 + COL_QTY_X1) / 2, label_y, "Qty")
    c.drawCentredString(
        RATE_X,
        label_y,
        "Rate"
    )
    c.drawRightString(COL_AMOUNT_X1 - 3 * mm, label_y, "Amount")

    return header_bottom


def draw_table_row(c, y_top, sr, name, qty, rate, amount):
    """Draw a single product row with optional text wrapping and bottom border.
    Returns the y coordinate of the row's bottom border.
    """
    lines = wrap_text_to_lines(c, name, 79 * mm, "Helvetica", 9)
    num_lines = len(lines)
    
    # Calculate dynamic row height
    height = 8 * mm + (num_lines - 1) * 4 * mm
    row_bottom = y_top - height

    # Alternate row shading
    if sr % 2 == 0:
        c.setFillGray(0.98)
        c.rect(MARGIN, row_bottom, CONTENT_RIGHT - MARGIN, height, fill=1, stroke=0)
        c.setFillGray(0)

    # Bottom border
    c.setStrokeGray(GREY_LINE)
    c.setLineWidth(0.5)
    c.line(MARGIN, row_bottom, CONTENT_RIGHT, row_bottom)
    c.setStrokeGray(0)

    c.setFont("Helvetica", 9)
    text_y = y_top - 5.5 * mm

    # Sr. No. — centered on the first text line
    c.drawCentredString((COL_SR_X0 + COL_SR_X1) / 2, text_y, str(sr))

    # Product — left aligned, wrapped
    for i, line_text in enumerate(lines):
        c.drawString(COL_SR_X1 + 3 * mm, text_y - i * 4 * mm, line_text)

    # Qty — centered on the first text line
    c.drawCentredString((COL_PRODUCT_X1 + COL_QTY_X1) / 2, text_y, str(qty))

    # Rate — left aligned
    c.drawCentredString(
        RATE_X,
        text_y,
        format_currency(rate)
    )

    # Amount — right aligned
    c.drawRightString(COL_AMOUNT_X1 - 3 * mm, text_y, format_currency(amount))

    return row_bottom

def start_new_page(c):
    """Begin a new page and redraw the table header. Returns the new y cursor."""
    c.showPage()
    return draw_table_header(c, CONTENT_TOP)

# =========================================================
# SUMMARY BOX (bottom right)
# =========================================================
def draw_summary(c, y_top, subtotal, grand_total):
    """Draw premium Total box."""

    box_width = 75 * mm
    box_height = 11 * mm

    box_x0 = CONTENT_RIGHT - box_width
    box_bottom = y_top - box_height

    # Background
    c.setFillGray(0.96)
    c.rect(box_x0, box_bottom, box_width, box_height, fill=1, stroke=0)

    # Border
    c.setStrokeGray(GREY_LINE)
    c.setLineWidth(0.5)
    c.rect(box_x0, box_bottom, box_width, box_height, fill=0, stroke=1)
    c.setStrokeGray(0)

    # Text
    c.setFillGray(0)
    c.setFont("Helvetica-Bold", 11)

    text_y = box_bottom + 3.6 * mm

    c.drawString(
        box_x0 + 4 * mm,
        text_y,
        "Total"
    )

    c.drawRightString(
        CONTENT_RIGHT - 4 * mm,
        text_y,
        format_currency(grand_total)
    )

    return box_bottom - 6 * mm

# =========================================================
# FOOTER
# =========================================================
def draw_footer(c):
    """Draw the footer."""

    footer_y = CONTENT_BOTTOM - 6 * mm

    # Left
    c.setFont("Helvetica", 8)
    c.setFillGray(GREY_MID)
    c.drawString(MARGIN, footer_y + 3 * mm, "Thank you for your business")

    # Center
    center_text = "Generated by Veloxa"
    text_width = c.stringWidth(center_text, "Helvetica", 8)
    c.drawString((PAGE_WIDTH - text_width) / 2, footer_y + 3 * mm, center_text)

    # Right
    right_text = "Payment Due: X Days"
    c.drawRightString(CONTENT_RIGHT, footer_y + 3 * mm, right_text)

    c.setFillGray(0)

# =========================================================
# MAIN ENTRY POINT
# =========================================================
def generate_invoice(order):

    customer = Customer.query.get(order.customer_id)
    items = OrderItem.query.filter_by(order_id=order.id).all()

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    # Page Border
    c.setStrokeGray(0.72)
    c.setLineWidth(0.5)
    c.rect(
        6 * mm,
        6 * mm,
        PAGE_WIDTH - 12 * mm,
        PAGE_HEIGHT - 12 * mm
    )

    # ---- Page 1: header + customer box + table header ----
    y = draw_company_header(c, order)
    y = draw_customer_box(c, customer, y)
    y = draw_table_header(c, y)

    # ---- Product rows, with automatic pagination ----
    grand_total = 0
    sr = 1

    for index, item in enumerate(items):
        product = Product.query.get(item.product_id)

        qty = item.quantity
        rate = product.price
        amount = qty * rate
        grand_total += amount

        # Compute dynamic row height
        row_height = get_row_height(c, product.name)

        is_last_item = index == len(items) - 1
        # Reserve extra space on the row that will be followed by the
        # summary box + footer so they aren't pushed onto a page break mid-row.
        needed = row_height + (SUMMARY_FOOTER_RESERVE if is_last_item else 0)

        if y - needed < CONTENT_BOTTOM:
            y = start_new_page(c)

        y = draw_table_row(c, y, sr, product.name, qty, rate, amount)
        sr += 1

    # ---- Summary + footer (guaranteed to fit due to reservation above) ----
    subtotal = grand_total
    y = draw_summary(c, y - 8 * mm, subtotal, grand_total)
    draw_footer(c)

    c.save()
    buffer.seek(0)

    return buffer