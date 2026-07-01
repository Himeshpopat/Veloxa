# 🚀 Veloxa — Velocity for Wholesale

<p align="center">
  <b>A Full-Stack B2B commerce platform that digitizes traditional wholesale ordering through secure authentication, inventory management, and automated order processing.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Flask-Web_Framework-000000?logo=flask&logoColor=white">
  <img src="https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/SQLite-Database-003B57?logo=sqlite&logoColor=white">
  <img src="https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap&logoColor=white">
  <img src="https://img.shields.io/badge/Cloudinary-Image_Storage-3448C5">
  <img src="https://img.shields.io/badge/Flask--Limiter-Rate_Limiting-yellow">
  <img src="https://img.shields.io/badge/REST-API-green">
</p>

---

## 📖 Overview

Small and mid-sized wholesale businesses often rely on field representatives to travel from shop to shop collecting orders manually from retailers. These orders are then communicated through phone calls, WhatsApp messages, or handwritten registers. While this traditional workflow has worked for years, it is time-consuming, difficult to scale, prone to communication errors, and often results in inventory mismatches.

**Veloxa** replaces this process with a centralized digital platform where retailers can independently browse products, place orders, and track purchases online, while administrators efficiently manage inventory, customers, and the complete order lifecycle from a single dashboard.

---

## 📊 Project at a Glance

- 👥 100+ Registered Users
- 👤 2 User Roles (Customer & Admin)
- 🔄 3-Stage Order Workflow
- ☁️ Cloud Integrations (Cloudinary & Brevo)
- 📱 Responsive Desktop & Mobile UI
- 🚀 Production Deployment on Render

---

## 💡 Motivation

Traditional wholesale distribution relies heavily on field agents who visit shops, manually note down orders, and relay them back to the office — a workflow that is slow, error-prone, and hard to audit. Veloxa digitizes that relationship: retailers place their own orders directly, admins process them from one screen, and every order carries a full, timestamped history instead of a slip of paper.

---

## 💼 Business Impact

Veloxa replaces manual order collection with a centralized digital platform, enabling wholesalers to reduce paperwork, improve inventory accuracy, streamline order processing, and provide retailers with a faster, more convenient ordering experience.

---

## ✨ Features

### 👤 Customer Features

* Self-service registration with **email OTP verification** (6-digit code, 5-minute expiry, resend with rate limiting)
* Secure login/logout with session regeneration on authentication
* Personal dashboard — total, pending, and delivered order counts, cart count, and recent orders
* Browse and **search the live product catalog**
* Add to cart, adjust quantities, and remove items (bounded by live stock)
* Place orders directly from the cart, with **automatic admin email notification**
* View complete order history and detailed order breakdowns
* **Edit or cancel orders** while they remain in the `Pending` state — add products, change quantities, or remove line items
* Manage shop profile (name, mobile, address, city)

### 🛠️ Admin Features

* Dedicated, session-isolated admin login
* Admin dashboard and full order management view
* Add, edit, **soft-delete, and restore** products (soft-deleted products stay in the database but disappear from the customer catalog)
* Product image upload with file-type and path-safety validation
* Search products from the admin panel
* Move orders through their lifecycle: **Confirm → Deliver**, or **Cancel**
* **Automatic stock deduction** on confirmation, with a stock-availability check that blocks confirmation if inventory has run out

---

## 🔄 Order Workflow

```text
Customer                          Admin
   │                                │
   ▼                                │
Browse Products                     │
   │                                │
   ▼                                │
Add to Cart                         │
   │                                │
   ▼                                │
Place Order  ───────────────────►  Pending
                                     │
                        ┌────────────┴────────────┐
                        ▼                          ▼
                    Confirmed                  Cancelled
                (stock deducted)         (by admin or customer,
                        │                  only while Pending)
                        ▼
                    Delivered
```

Customers can edit or cancel an order only while it is `Pending`. Once an admin confirms it, stock is deducted and the order moves forward to `Delivered`.

---

## 🛠 Tech Stack

**Frontend**
* HTML5, CSS3 (custom stylesheet)
* Bootstrap 5.3 + Bootstrap Icons
* Jinja2 templating

**Backend**
* Python & Flask
* Flask-SQLAlchemy (ORM)
* Brevo REST API (email delivery)
* Flask-Limiter (per-route rate limiting)
* Flask-WTF (CSRF tooling)
* python-dotenv (environment configuration)

**Database**
* SQLite by default, with `DATABASE_URL` support for drop-in Postgres/MySQL in production

**Security**
* Werkzeug password hashing
* Role-Based Access Control (RBAC)
* Server-side session authentication with session regeneration on login
* HTTP-only, SameSite cookies with a configurable `Secure` flag
* Security response headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`)
* Rate limiting on login, registration, and OTP endpoints
* Ownership checks on every order/cart action (a customer can never touch another customer's data)

---

## ⭐ Key Highlights

* 🔐 Email OTP-verified registration flow
* 📦 Real-time inventory validation — orders can never exceed available stock
* 🛒 Full cart → checkout → order-lifecycle pipeline
* 📧 Automated email notifications on new orders and OTPs
* 🧾 Editable pending orders with per-item add/remove/adjust controls
* 🗑️ Soft-delete/restore for products instead of destructive deletes
* 📱 Responsive UI, verified on both desktop and mobile
* 🧱 Clean route-level access control separating customer and admin sessions

---

## 📸 Application Screenshots

### Customer Experience

| Dashboard | Products |
|---|---|
| ![Customer Dashboard](assets/Customer_Dashboard.png) | ![Products](assets/Products.png) |

| Cart | Orders |
|---|---|
| ![Cart](assets/Cart.png) | ![Orders](assets/Orders.png) |

**Mobile View**

| Dashboard | Products |
|---|---|
| ![Customer Dashboard Mobile](assets/Customer_Dashboard_Mobile_View.png) | ![Products Mobile](assets/Products_Mobile_View.png) |

### Admin Experience

| Admin Dashboard | Add Product |
|---|---|
| ![Admin Dashboard](assets/Admin_Dashboard.png) | ![Add Product](assets/Add_Product.png) |

**Mobile View**

![Admin Dashboard Mobile](assets/Admin_Dashboard_Mobile_View.png)

---

## 🎥 Project Demo

▶️ **[Watch Demo Video](https://drive.google.com/file/d/1YtrFeUnOcULB42dMl4MQb3Z9Ywd7UxNh/view?usp=sharing)**

---

## 📂 Project Structure

```
Veloxa/
├── app.py
├── models.py
├── templates/
├── static/
├── assets/
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🚀 Installation

**1. Clone the repository**
```bash
git clone https://github.com/Himeshpopat/woms.git
cd woms
```

**2. Create and activate a virtual environment**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux / macOS
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Create a `.env` file in the project root:
```env
SECRET_KEY=your_secret_key
BREVO_API_KEY=your_brevo_api_key
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
SESSION_COOKIE_SECURE=false
```

**5. Run the application**
```bash
python app.py
```
The app will be available at `http://127.0.0.1:5000`.

---

## 🔐 Security Features

* Passwords hashed with Werkzeug — never stored in plaintext
* OTP-gated registration with a 5-minute expiry window and rate-limited resend
* Session fixation prevention (`session.clear()` + regeneration on every login)
* HTTP-only, SameSite session cookies with an environment-configurable `Secure` flag
* Rate limiting on login, registration, and OTP routes via Flask-Limiter
* Strict server-side ownership checks on carts, orders, and order edits
* File-upload validation — extension whitelisting plus path-traversal protection on saved images
* Centralized error handling with dedicated 403 / 404 / 500 pages and server-side exception logging

---

## 📈 Future Enhancements

* 🤖 AI-based Demand Forecasting
* 📊 Sales Analytics Dashboard
* 💳 Payment Gateway Integration
* 📄 Automated Invoice Generation
* 📤 Export Reports (Excel/PDF)
* 🐳 Docker Deployment
* 📱 Progressive Web App (PWA)
* 🛡️ Complete CSRF Protection

---

## 👨‍💻 Author

**Himesh Popat**

📧 [himeshpopat2006@gmail.com](mailto:himeshpopat2006@gmail.com)

🔗 LinkedIn: [linkedin.com/in/himesh-popat](https://linkedin.com/in/himesh-popat)

💻 GitHub: [github.com/Himeshpopat](https://github.com/Himeshpopat)

---

## ⭐ Support

If this project was useful to you, consider giving it a **star** — it helps others discover it and supports future improvements.

---

> Built to turn a manual, error-prone wholesale ordering process into a secure, auditable digital workflow.