# Petal & Pour — Full-stack cafe website (Flask + PostgreSQL + Razorpay)

A flower-themed cafe website with menu browsing, cart, Razorpay Checkout integration, server-side payment verification, Razorpay webhooks, reservation requests with admin approval, protected admin dashboard, and PostgreSQL persistence.

## Features

### Customer website
- Responsive botanical/floral design.
- Menu categories and cart.
- Server-calculated totals (client prices are never trusted).
- Razorpay Checkout integration.
- Reservation request form. Requests are saved as **Pending**, not auto-confirmed.

### Backend and database
- Flask application and JSON APIs.
- PostgreSQL via Flask-SQLAlchemy and psycopg 3.
- SQLite fallback for local experimentation.
- Order/payment/reservation/admin models.
- Payment signature verification and webhook signature verification.
- Webhook-safe state update for captured/failed payments.
- Admin login with hashed password.
- CSRF protection on forms; Razorpay webhook endpoint is CSRF-exempt but validates its HMAC signature.
- Capacity check on admin confirmation (demo seat-capacity model).

### Admin dashboard
- View reservations and their current status.
- Confirm, reject or cancel reservation requests.
- View orders and payment status.
- Update paid orders through preparation/ready/completed states.

## 1. Requirements

- Python 3.10 or newer.
- PostgreSQL 14+ (recommended for this configured stack).
- A Razorpay account. Use **test mode keys** during development.
- Git optional.

## 2. Create a PostgreSQL database

Example using `psql`:

```sql
CREATE USER petal_user WITH PASSWORD 'choose-a-strong-password';
CREATE DATABASE petal_cafe OWNER petal_user;
```

Use the connection URL in `.env`:

```env
DATABASE_URL=postgresql+psycopg://petal_user:choose-a-strong-password@localhost:5432/petal_cafe
```

For local learning without PostgreSQL, set `DATABASE_URL=sqlite:///petal_and_pour_dev.db`. Production should use PostgreSQL.

## 3. Install and run (Windows PowerShell)

Extract the ZIP, open the folder in VS Code, then:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and replace the placeholders. Generate a strong Flask secret key, set PostgreSQL credentials, and set Razorpay test keys.

Then initialize tables and create your admin:

```powershell
flask --app app init-db
flask --app app create-admin
flask --app app run --debug
```

Open:
- Customer site: http://127.0.0.1:5000
- Admin login: http://127.0.0.1:5000/admin/login
- Health check: http://127.0.0.1:5000/health

On macOS/Linux, activate the venv with `source .venv/bin/activate` and copy the env file with `cp .env.example .env`.

## 4. Configure Razorpay TEST mode

1. Create/sign in to your Razorpay account and enable/test the test-mode account.
2. In the Razorpay Dashboard, find API Keys and generate test keys.
3. Put `rzp_test_...` in `RAZORPAY_KEY_ID` and its secret in `RAZORPAY_KEY_SECRET`.
4. Configure a webhook URL pointing to `https://YOUR_PUBLIC_HOST/webhooks/razorpay`.
5. Subscribe to `payment.captured`, `payment.failed` and `order.paid`.
6. Set the webhook signing secret in `RAZORPAY_WEBHOOK_SECRET`.
7. For local testing, expose the local Flask server through a secure development tunnel and use that public HTTPS webhook URL.
8. Keep the key secret and webhook secret server-side only. Never put either in HTML/JavaScript or commit `.env`.

The browser checkout returns order/payment/signature fields to `/api/payments/verify`; the backend verifies the signature with the Razorpay SDK. Webhooks are independently HMAC-verified. The payment status is not trusted from the browser alone. The synchronous verification path also fetches the payment from Razorpay and checks that its status is `captured` before marking the order paid.

## 5. Test the flow

### Payment
1. Open the menu and add items.
2. Checkout, enter a test customer name and phone.
3. Complete Razorpay test checkout with the test payment details from Razorpay's current docs/dashboard.
4. Confirm the website reports verified payment.
5. Sign into `/admin` and inspect payment status/order status.
6. Also test cancellation/failure and confirm failed payments do not become paid.

### Reservation
1. Submit a reservation request from the website.
2. Sign into `/admin/login`.
3. Find the new booking in the Reservations table.
4. Click Confirm or Reject.
5. Confirm the status updates in the dashboard.

## 6. Reservation capacity behaviour — important

This starter uses a simple **30-seat capacity** rule and assumes a two-hour seating duration. Confirmed reservations whose time ranges overlap consume capacity. This is a demonstration rule, not a full table-allocation engine. Before a real cafe uses it, model the actual tables, table sizes, seating durations, opening hours, buffers, holidays and staff overrides. Add database-level locking/transactions to prevent simultaneous admin confirmations from overselling capacity.

The current app saves reservation requests as Pending and lets staff approve/reject them in the protected dashboard. It updates the database status but does not yet send customer email/SMS notifications. Add a trusted email/SMS provider before relying on customer notifications.

## 7. Production launch checklist — do not skip

This code is a functional integration starter, not a certified production deployment. Before taking real customer payments:

- Use live Razorpay keys only after the merchant account and payment methods are approved.
- Deploy behind HTTPS with a production WSGI server such as Gunicorn.
- Set `FLASK_DEBUG=0`; never run Flask debug mode publicly.
- Use a strong unique `SECRET_KEY`; keep all secrets in the host's secret manager/environment.
- Use managed PostgreSQL with backups, restricted network access and least-privilege credentials.
- Add rate limiting, structured logs, monitoring and error reporting.
- Add email/SMS notifications and customer support/refund workflows.
- Add proper table allocation and concurrency-safe reservation confirmation.
- Add terms, privacy, cancellation/refund policies, business identity and contact information.
- Test successful payments, failed payments, duplicate webhook delivery, delayed webhooks, refunds, browser closure and network interruptions.
- Reconcile captured payments with Razorpay dashboard and database.
- Add database migrations (e.g. Flask-Migrate/Alembic) before evolving schemas.
- Review security with a qualified developer before public launch.

### Payment implementation notes
- Amounts are stored in integer paise; never accept the final amount from the browser.
- `razorpay_order_id` is created server-side.
- Checkout signature is verified server-side.
- Webhook signature uses the exact raw request body and HMAC-SHA256.
- Webhooks are idempotent for the handled captured/failed transitions.
- For production, also handle `refund.processed`, `order.paid` if used, dispute events and reconciliation as required by your chosen Razorpay flow.
- A captured payment should not be marked paid solely from a client-side callback.

## Project structure

```text
petal_and_pour_pro/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   ├── index.html
│   ├── admin.html
│   └── login.html
└── static/
    ├── style.css
    └── app.js
```
