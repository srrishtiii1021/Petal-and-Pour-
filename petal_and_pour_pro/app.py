import os
import json
import hmac
import hashlib
from datetime import datetime, date, time, timedelta
from decimal import Decimal, InvalidOperation

import razorpay
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import func, and_
from werkzeug.security import generate_password_hash, check_password_hash

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-only-change-me")
database_url = os.getenv("DATABASE_URL", "sqlite:///petal_and_pour_dev.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
app.config["WTF_CSRF_TIME_LIMIT"] = 3600

db = SQLAlchemy(app)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = "admin_login"
login_manager.login_message = "Please sign in to access the admin dashboard."

MENU = [
    {"id": 1, "name": "Rose Vanilla Latte", "category": "Coffee", "price": 190, "description": "Espresso, steamed milk and a gentle rose-vanilla note.", "emoji": "🌹"},
    {"id": 2, "name": "Lavender Iced Coffee", "category": "Coffee", "price": 210, "description": "Cold brew with lavender syrup and silky oat milk.", "emoji": "🪻"},
    {"id": 3, "name": "Caramel Cloud Cappuccino", "category": "Coffee", "price": 200, "description": "A classic cappuccino finished with caramel foam.", "emoji": "☁️"},
    {"id": 4, "name": "Strawberry Matcha", "category": "Tea", "price": 220, "description": "Matcha layered over fresh strawberry milk.", "emoji": "🍓"},
    {"id": 5, "name": "Chamomile Honey Tea", "category": "Tea", "price": 150, "description": "A calming floral infusion with a touch of honey.", "emoji": "🌼"},
    {"id": 6, "name": "Blueberry Cheesecake", "category": "Dessert", "price": 240, "description": "Creamy baked cheesecake with a blueberry swirl.", "emoji": "🫐"},
    {"id": 7, "name": "Rose Petal Cupcake", "category": "Dessert", "price": 130, "description": "Vanilla sponge with rose buttercream.", "emoji": "🧁"},
    {"id": 8, "name": "Garden Pesto Sandwich", "category": "Food", "price": 260, "description": "Grilled sourdough, basil pesto, tomato and mozzarella.", "emoji": "🥪"},
    {"id": 9, "name": "Avocado Garden Toast", "category": "Food", "price": 230, "description": "Sourdough toast with avocado, herbs and chilli flakes.", "emoji": "🥑"},
]
MENU_BY_ID = {item["id"]: item for item in MENU}

class Admin(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    reservation_date = db.Column(db.Date, nullable=False, index=True)
    reservation_time = db.Column(db.Time, nullable=False)
    guests = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="Pending", index=True)
    admin_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class CafeOrder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    items_json = db.Column(db.Text, nullable=False)
    total_paise = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="INR")
    payment_status = db.Column(db.String(20), nullable=False, default="Created", index=True)
    order_status = db.Column(db.String(30), nullable=False, default="Awaiting payment")
    razorpay_order_id = db.Column(db.String(100), unique=True)
    razorpay_payment_id = db.Column(db.String(100), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def total_rupees(self):
        return self.total_paise / 100

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Admin, int(user_id))

def razorpay_client():
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        return None
    return razorpay.Client(auth=(key_id, key_secret))

def reservation_slot_available(res_date, res_time, guests, exclude_id=None):
    """Demo capacity rule: 30 seats total; confirmed reservations occupy seats for 2 hours.
    Replace this with real table allocation/turnover rules for a real venue.
    """
    start_dt = datetime.combine(res_date, res_time)
    end_dt = start_dt + timedelta(hours=2)
    query = Reservation.query.filter(
        Reservation.reservation_date == res_date,
        Reservation.status == "Confirmed"
    )
    if exclude_id:
        query = query.filter(Reservation.id != exclude_id)
    occupied = 0
    for booking in query.all():
        booked_start = datetime.combine(booking.reservation_date, booking.reservation_time)
        booked_end = booked_start + timedelta(hours=2)
        if start_dt < booked_end and end_dt > booked_start:
            occupied += booking.guests
    return occupied + guests <= int(os.getenv("CAFE_SEAT_CAPACITY", "30"))

@app.get("/")
def home():
    return render_template("index.html", menu=MENU)

@app.post("/reserve")
def reserve():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    notes = request.form.get("notes", "").strip()
    guests = request.form.get("guests", type=int)
    try:
        res_date = date.fromisoformat(request.form.get("date", ""))
        res_time = time.fromisoformat(request.form.get("time", ""))
    except ValueError:
        flash("Please select a valid date and time.", "error")
        return redirect(url_for("home") + "#reserve")

    if not all([name, email, phone]) or not guests or not 1 <= guests <= 12:
        flash("Please complete all required fields. Guest count must be 1–12.", "error")
        return redirect(url_for("home") + "#reserve")
    if res_date < date.today():
        flash("Please choose today or a future date.", "error")
        return redirect(url_for("home") + "#reserve")
    if not (time(9, 0) <= res_time <= time(20, 30)):
        flash("Please choose a time between 9:00 AM and 8:30 PM.", "error")
        return redirect(url_for("home") + "#reserve")

    booking = Reservation(customer_name=name, email=email, phone=phone,
                          reservation_date=res_date, reservation_time=res_time,
                          guests=guests, notes=notes, status="Pending")
    db.session.add(booking)
    db.session.commit()
    flash(f"Reservation request #{booking.id} received. It is pending until the cafe confirms it.", "success")
    return redirect(url_for("home") + "#reserve")

@app.post("/api/orders/create")
def create_payment_order():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    items = data.get("items", [])
    if not name or not phone or not isinstance(items, list) or not items:
        return jsonify(ok=False, error="Enter your name, phone number and add at least one item."), 400

    clean_items, total_paise = [], 0
    for entry in items:
        try:
            item_id, quantity = int(entry.get("id")), int(entry.get("quantity"))
        except (TypeError, ValueError, AttributeError):
            return jsonify(ok=False, error="Invalid cart item."), 400
        if item_id not in MENU_BY_ID or not 1 <= quantity <= 20:
            return jsonify(ok=False, error="Invalid menu item or quantity."), 400
        item = MENU_BY_ID[item_id]
        line_paise = item["price"] * 100 * quantity
        total_paise += line_paise
        clean_items.append({"id": item_id, "name": item["name"], "quantity": quantity,
                            "unit_price_rupees": item["price"], "line_total_rupees": line_paise // 100})

    client = razorpay_client()
    if client is None:
        return jsonify(ok=False, error="Online payments are not configured yet. Set Razorpay test keys in .env."), 503

    order = CafeOrder(customer_name=name, phone=phone, items_json=json.dumps(clean_items),
                      total_paise=total_paise, payment_status="Created", order_status="Awaiting payment")
    db.session.add(order)
    db.session.flush()
    try:
        rp_order = client.order.create({
            "amount": total_paise,
            "currency": "INR",
            "receipt": f"petal_order_{order.id}",
            "notes": {"cafe_order_id": str(order.id)}
        })
        order.razorpay_order_id = rp_order["id"]
        db.session.commit()
    except Exception:
        db.session.rollback()
        app.logger.exception("Razorpay order creation failed")
        return jsonify(ok=False, error="Could not start payment. Please try again."), 502

    return jsonify(ok=True, order_id=order.id, razorpay_order_id=rp_order["id"],
                   amount=total_paise, currency="INR",
                   key_id=os.getenv("RAZORPAY_KEY_ID"),
                   customer_name=name, customer_phone=phone,
                   cafe_name=os.getenv("CAFE_NAME", "Petal & Pour"))

@app.post("/api/payments/verify")
def verify_payment():
    data = request.get_json(silent=True) or {}
    rp_order_id = data.get("razorpay_order_id", "")
    rp_payment_id = data.get("razorpay_payment_id", "")
    signature = data.get("razorpay_signature", "")
    order = CafeOrder.query.filter_by(razorpay_order_id=rp_order_id).first()
    if not order or not rp_payment_id or not signature:
        return jsonify(ok=False, error="Payment details could not be matched to an order."), 400
    client = razorpay_client()
    try:
        # Verify against the Razorpay order ID already stored in our database.
        client.utility.verify_payment_signature({
            "razorpay_order_id": order.razorpay_order_id,
            "razorpay_payment_id": rp_payment_id,
            "razorpay_signature": signature
        })
        # A valid checkout signature alone is not the final fulfilment check.
        # Confirm Razorpay reports the payment as captured before marking the order paid.
        payment = client.payment.fetch(rp_payment_id)
        if payment.get("order_id") != order.razorpay_order_id or payment.get("status") != "captured":
            return jsonify(ok=False, error="Payment is not captured yet. The order will update when Razorpay confirms it."), 409
        order.razorpay_payment_id = rp_payment_id
        order.payment_status = "Paid"
        order.order_status = "Received"
        db.session.commit()
        return jsonify(ok=True, message="Payment verified and captured. Your cafe order is confirmed.", order_id=order.id)
    except razorpay.errors.SignatureVerificationError:
        app.logger.warning("Invalid Razorpay signature for cafe order %s", order.id)
        return jsonify(ok=False, error="Payment verification failed. Contact the cafe if money was deducted."), 400
    except Exception:
        app.logger.exception("Payment verification error")
        return jsonify(ok=False, error="Payment verification is temporarily unavailable."), 500

@app.post("/webhooks/razorpay")
@csrf.exempt
def razorpay_webhook():
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    received_signature = request.headers.get("X-Razorpay-Signature", "")
    if not webhook_secret or not received_signature:
        abort(400)
    expected = hmac.new(webhook_secret.encode(), request.get_data(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_signature):
        abort(400)

    payload = request.get_json(silent=True) or {}
    event = payload.get("event")
    payment_entity = (payload.get("payload", {}).get("payment", {}).get("entity", {}))
    order_entity = (payload.get("payload", {}).get("order", {}).get("entity", {}))
    rp_order_id = payment_entity.get("order_id") or order_entity.get("id")
    if event in {"payment.captured", "order.paid"} and rp_order_id:
        order = CafeOrder.query.filter_by(razorpay_order_id=rp_order_id).first()
        if order and order.payment_status != "Paid":
            order.razorpay_payment_id = payment_entity.get("id") or order.razorpay_payment_id
            order.payment_status = "Paid"
            order.order_status = "Received"
            db.session.commit()
    elif event == "payment.failed" and rp_order_id:
        order = CafeOrder.query.filter_by(razorpay_order_id=rp_order_id).first()
        if order and order.payment_status != "Paid":
            order.payment_status = "Failed"
            order.order_status = "Payment failed"
            db.session.commit()
    return jsonify(status="ok")

@app.get("/admin/login")
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for("admin_dashboard"))
    return render_template("login.html")

@app.post("/admin/login")
def admin_login_post():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    admin = Admin.query.filter_by(username=username).first()
    if admin and admin.check_password(password):
        login_user(admin)
        return redirect(url_for("admin_dashboard"))
    flash("Invalid username or password.", "error")
    return redirect(url_for("admin_login"))

@app.post("/admin/logout")
@login_required
def admin_logout():
    logout_user()
    return redirect(url_for("home"))

@app.get("/admin")
@login_required
def admin_dashboard():
    reservations = Reservation.query.order_by(Reservation.created_at.desc()).limit(100).all()
    orders = CafeOrder.query.order_by(CafeOrder.created_at.desc()).limit(100).all()
    return render_template("admin.html", reservations=reservations, orders=orders)

@app.post("/admin/reservations/<int:reservation_id>/status")
@login_required
def update_reservation(reservation_id):
    booking = db.get_or_404(Reservation, reservation_id)
    new_status = request.form.get("status")
    if new_status not in {"Confirmed", "Rejected", "Cancelled"}:
        abort(400)
    if new_status == "Confirmed" and not reservation_slot_available(
        booking.reservation_date, booking.reservation_time, booking.guests, exclude_id=booking.id
    ):
        flash("Not enough capacity for this time slot. Adjust the booking or contact the customer.", "error")
        return redirect(url_for("admin_dashboard"))
    booking.status = new_status
    booking.admin_note = request.form.get("admin_note", "").strip()
    db.session.commit()
    # Add an email/SMS provider here to notify the customer. Do not mark sent unless provider confirms.
    flash(f"Reservation #{booking.id} updated to {new_status}.", "success")
    return redirect(url_for("admin_dashboard"))

@app.post("/admin/orders/<int:order_id>/status")
@login_required
def update_order(order_id):
    order = db.get_or_404(CafeOrder, order_id)
    new_status = request.form.get("status")
    allowed = {"Received", "Preparing", "Ready for pickup", "Completed", "Cancelled"}
    if new_status not in allowed:
        abort(400)
    if order.payment_status != "Paid" and new_status not in {"Cancelled"}:
        flash("Only paid orders can move into preparation.", "error")
        return redirect(url_for("admin_dashboard"))
    order.order_status = new_status
    db.session.commit()
    flash(f"Order #{order.id} updated.", "success")
    return redirect(url_for("admin_dashboard"))

@app.get("/health")
def health():
    try:
        db.session.execute(db.text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception:
        return jsonify(status="error", database="unavailable"), 503

@app.cli.command("init-db")
def init_db_command():
    db.create_all()
    print("Database tables created.")

@app.cli.command("create-admin")
def create_admin_command():
    """Create the first admin using ADMIN_USERNAME and ADMIN_PASSWORD environment variables."""
    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        raise SystemExit("Set ADMIN_USERNAME and ADMIN_PASSWORD in your environment/.env first.")
    if Admin.query.filter_by(username=username).first():
        print("Admin already exists.")
        return
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    print(f"Admin user '{username}' created.")

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0") == "1")
