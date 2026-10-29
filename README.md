# Ration Fraud Detection System

A modular, production-ready web application designed for academic evaluation, final-year project demonstration, and research in **Public Distribution System (PDS)** transparency and fraud mitigation.

Built with **Python Flask**, **SQLite**, **SQLAlchemy**, **Bootstrap 5**, and **Chart.js**.

---

## 📌 Project Overview

The **Ration Fraud Detection System** is designed to oversee Fair Price Shops (FPS), monitor grain allocations, track distribution transactions, and detect potential fraud anomalies in real time.

### Key Capabilities:
1. **Modular Architecture**: Built using Flask application factory pattern and isolated blueprints (`auth`, `admin`, `dealer`, `main`, `fraud`).
2. **Relational Database Design**: Comprehensive models for Users, Fair Price Shops, Beneficiaries, Stock Movements, Distribution Transactions, and Fraud Alerts.
3. **Role-Based Access Control (RBAC)**: Distinct authorization tiers for **Admin** (Vigilance Officers) and **Dealer** (Fair Price Shop Operators) with secure password hashing (`werkzeug.security`).
4. **Duplicate Ration Card Detection**: Flags identity collisions (shared Aadhaar hash), impossible cross-shop withdrawals within 24 hours, and same-day repeat claims.
5. **Stock Reconciliation Formula**: Implements `Opening Stock + Received Stock - Distributed Stock = Expected Closing Stock` with automated discrepancy alerts.
6. **Suspicious Patterns & Quota Breach**: Detects single transactions exceeding card quotas and rapid-fire transaction bursts.
7. **Isolation Forest ML Anomaly Detection**: Pure Python cross-platform implementation with numerical feature extraction, missing value imputation, insufficient data safeguards, and clear non-proof-of-fraud disclaimers.
8. **Interactive Alert Register**: Filterable alert table with columns for Shop, Transaction, Alert Reason, Risk Level, Investigation Status, and Timestamp, plus status updates and notes logging.

---

## 📂 Project Structure

```text
Ration_Fraud_Detection/
├── app/
│   ├── __init__.py           # Application factory (create_app) & error handlers
│   ├── config.py             # Environment-aware configuration (Dev, Test, Prod)
│   ├── extensions.py         # SQLAlchemy & Flask-Login instances
│   ├── models/               # SQLAlchemy database models
│   │   ├── __init__.py       # Model registry export
│   │   ├── user.py           # User model (Admin, Dealer roles, password hash)
│   │   ├── shop.py           # RationShop (Fair Price Shops)
│   │   ├── beneficiary.py    # Beneficiary (NFSA categories: AAY, BPL, APL)
│   │   ├── stock.py          # StockMovement (Inward & allocation logs)
│   │   ├── transaction.py    # DistributionTransaction (POS distribution records)
│   │   └── alert.py          # FraudAlert (Heuristic alert indicators)
│   ├── auth/                 # Authentication blueprint
│   │   ├── __init__.py
│   │   ├── routes.py         # /login, /logout, session validation
│   │   └── utils.py          # RBAC decorators (@admin_required, @dealer_required)
│   ├── admin/                # Admin vigilance blueprint
│   │   ├── __init__.py
│   │   └── routes.py         # /admin/dashboard & analytics queries
│   ├── dealer/               # FPS Dealer blueprint
│   │   ├── __init__.py
│   │   └── routes.py         # /dealer/dashboard (mapped shop operations)
│   ├── main/                 # General navigation blueprint
│   │   ├── __init__.py
│   │   └── routes.py         # Root redirect routing
│   ├── templates/            # Jinja2 HTML templates
│   │   ├── base.html         # Responsive Bootstrap 5 layout & navbar
│   │   ├── auth/
│   │   │   └── login.html    # Login page with demo autofill buttons
│   │   ├── admin/
│   │   │   └── dashboard.html# Vigilance dashboard with Chart.js
│   │   ├── dealer/
│   │   │   └── dashboard.html# FPS Dealer shop console
│   │   └── errors/           # Custom error pages (403, 404, 500)
│   └── static/               # Assets
│       ├── css/style.css     # Custom UI styling and card designs
│       └── js/dashboard.js   # Client scripts
├── instance/                 # SQLite database storage (ration_fraud.db)
├── tests/                    # Automated test suite
│   ├── __init__.py
│   ├── conftest.py           # Pytest fixtures and in-memory SQLite isolation
│   ├── test_models.py        # Model schema and password hashing tests
│   └── test_auth.py          # Authentication and RBAC security tests
├── seed_data.py              # Synthetic demo data populator
├── run.py                    # Application launch script
├── requirements.txt          # Python dependencies
├── .env.example              # Environment variables template
├── .gitignore                # Git exclusions
└── README.md                 # Project documentation
```

---

## 🗄️ Database Models

| Model | Table | Description |
|---|---|---|
| **User** | `users` | Accounts for Admins and Dealers. Stores hashed passwords (`scrypt`/`pbkdf2`) and role tags. |
| **RationShop** | `ration_shops` | Fair Price Shops (FPS) with location, dealer mapping, and activation state. |
| **Beneficiary** | `beneficiaries` | Ration card holders with NFSA categories (`AAY`, `BPL`, `APL`), family size, quotas, and synthetic Aadhaar hashes. |
| **StockMovement** | `stock_movements` | Depot grain arrivals and allocations (`Rice`, `Wheat`, `Sugar`) with batch references. |
| **DistributionTransaction** | `distribution_transactions` | Point of Sale distribution logs with authentication mode (`BIOMETRIC`, `OTP`, `MANUAL`) and status. |
| **FraudAlert** | `fraud_alerts` | Automated detection records (`BULK_DISPATCH_ANOMALY`, `BIOMETRIC_BYPASS_SPIKE`, `GHOST_BENEFICIARY`, etc.) with confidence scores and severity tiers. |

---

## 🔑 Synthetic Demo Credentials

The login page contains **one-click autofill buttons** for instant evaluation:

| Role | Username | Password | Access Level |
|---|---|---|---|
| **Vigilance Administrator** | `admin` | `Admin@123` | Full access to Admin Operations Dashboard, system-wide analytics, and all alerts. |
| **FPS Dealer 1** | `dealer_fps101` | `Dealer@123` | Mapped to Sri Venkateshwara Fair Price Depot (`FPS-KA-101`). |
| **FPS Dealer 2** | `dealer_fps102` | `Dealer@123` | Mapped to Gramin Seva Samiti Distribution Center (`FPS-KA-102`). |

> *Note: All data, identification numbers, and transactions are strictly synthetic and generated for demonstration purposes.*

---

## 🚀 Setup & Execution Guide

### Prerequisites
- **Python 3.10+** (Tested on Python 3.11)
- **pip** and **PowerShell** (Windows) or **bash** (macOS/Linux)

---

### Step 1: Clone / Navigate to the Directory
```bash
cd c:\Users\LENOVO\OneDrive\Desktop\Ration_Fraud_Detection
```

### Step 2: Create and Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv

# If script execution is restricted, allow it for the current session or user:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# Then activate:
.\venv\Scripts\Activate.ps1
```

> **Tip (No Activation Needed)**: You can also run commands directly with the virtual environment binary without activating:
> ```powershell
> .\venv\Scripts\python.exe run.py
> .\venv\Scripts\pytest.exe -v
> ```

**On Windows (Command Prompt `cmd.exe`):**
```cmd
venv\Scripts\activate.bat
```

**On macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3: Install Required Packages
```bash
pip install -r requirements.txt
```

---

### Step 4: Configure Environment Variables
Copy `.env.example` to `.env`:

**On Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**On macOS / Linux:**
```bash
cp .env.example .env
```

---

### Step 5: Seed Synthetic Demonstration Data
Run the database seeder to generate synthetic users, shops, beneficiaries, stock logs, transactions, and fraud alerts:

```bash
python seed_data.py
```

*Output:*
```text
Initializing database tables...
Seeding synthetic users (Admin and Dealers)...
Seeding synthetic Ration Shops (FPS)...
Seeding synthetic beneficiaries...
Seeding stock movements...
Seeding distribution transactions...
Seeding synthetic fraud alerts...
Synthetic demo data seeding successfully completed!
```

---

### Step 6: Run Automated Tests
Verify that all model relationships, password security, login authentication, and role authorization policies pass:

```bash
pytest -v
```

*Expected Result:*
```text
tests/test_auth.py (13 tests) ............................. PASSED
tests/test_models.py (5 tests) ............................ PASSED
tests/test_fraud_detection.py::test_stock_reconciliation_exact_formula PASSED
tests/test_fraud_detection.py::test_stock_discrepancy_alert_on_shortage PASSED
tests/test_fraud_detection.py::test_negative_stock_balance_triggers_critical_alert PASSED
tests/test_fraud_detection.py::test_normal_transactions_no_duplicate_alert PASSED
tests/test_fraud_detection.py::test_cross_shop_duplicate_card_detection PASSED
tests/test_fraud_detection.py::test_duplicate_synthetic_identity_hash PASSED
tests/test_fraud_detection.py::test_suspicious_quantity_detection PASSED
tests/test_fraud_detection.py::test_rapid_burst_transaction_pattern PASSED
tests/test_fraud_detection.py::test_isolation_forest_normal_and_anomalous_samples PASSED
tests/test_fraud_detection.py::test_isolation_forest_missing_values_and_insufficient_data PASSED
tests/test_fraud_detection.py::test_isolation_forest_model_persistence PASSED
tests/test_fraud_detection.py::test_full_fraud_audit_execution_and_table_routes PASSED
============================= 30 passed in 9.74s ==============================
```

---

### Step 7: Launch the Application
Start the Flask development server:

```bash
python run.py
```

Open your browser and navigate to:
```text
http://127.0.0.1:5000/
```

- Login as **Admin**: `admin` / `Admin@123`
- Login as **Dealer**: `dealer_fps101` / `Dealer@123`

---

## 🛡️ Security Features
- **Password Protection**: Passwords are never stored in plaintext; hashed using Werkzeug (`generate_password_hash`).
- **Role Verification**: Routes protected using custom decorators (`@admin_required`, `@dealer_required`).
- **Session Management**: Session cookies handled via Flask-Login.
- **Open Redirect Mitigation**: URL parameters checked against local origins (`is_safe_url`).
- **Strict Error Handling**: Custom HTTP `403` (Forbidden), `404` (Not Found), and `500` (Internal Error) templates prevent system leakage.

---

## 📈 Next Phase Roadmap
- Implementation of automated fraud rule engine & machine learning anomaly scoring.
- Dealer Point-of-Sale (POS) transaction processing terminal.
- Beneficiary quota deduction and SMS/OTP verification simulation.
- PDF audit report generation and Fair Price Shop geo-tagging.

