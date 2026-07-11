"""
Billing & Invoices Module — Pricing, Bills, Payments
=====================================================
DB operations for billing, invoice generation, and payment tracking.

Tables:
    bill_items — Test price catalogue (configurable per test)
    bills — Bill headers (patient, totals, status)
    payments — Payment records per bill
    invoice_sequence — Auto-incrementing invoice number counter

Bill status flow: pending → paid | cancelled
"""
import uuid
from datetime import date, datetime
from typing import Optional

from utils.db import (
    USE_GOOGLE_SHEETS, USE_SUPABASE, USE_LOCAL_JSON, _gs_failed,
    call_gs_api, get_client, DB_FILE, get_completed_tests
)
import sqlite3

# ─── JSON fallback (lazy import) ──────────────────────────────────────────────
_json_module = None


def _get_json():
    global _json_module
    if _json_module is None and USE_LOCAL_JSON:
        from utils import local_json_db
        _json_module = local_json_db
    return _json_module


# ─── CONSTANTS ─────────────────────────────────────────────────────────────────

BILL_STATUSES = ["pending", "paid", "cancelled"]
PAYMENT_MODES = ["cash", "card", "upi", "neft", "other"]

# Default test prices (can be customized via bill_items table)
DEFAULT_TEST_PRICES = {
    "ECG": 300,
    "Echo": 1200,
    "TMT": 800,
    "Holter": 1500,
    "ABPM": 1000,
    "OPD": 500,
}

INVOICE_PREFIX = "INV"
INVOICE_NUMBER_FORMAT = f"{INVOICE_PREFIX}-{{:05d}}"


# ─── SCHEMA INIT ──────────────────────────────────────────────────────────────

def _init_billing_tables():
    """Create billing tables in SQLite if they don't exist."""
    if USE_SUPABASE or USE_GOOGLE_SHEETS:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bill_items (
                id TEXT PRIMARY KEY,
                test_name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bills (
                id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL,
                patient_name TEXT NOT NULL,
                mobile TEXT NOT NULL,
                invoice_number TEXT UNIQUE,
                total_amount REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                final_amount REAL NOT NULL DEFAULT 0,
                amount_paid REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                payment_mode TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                paid_at TEXT,
                cancelled_at TEXT,
                FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                bill_id TEXT NOT NULL,
                amount REAL NOT NULL,
                mode TEXT NOT NULL DEFAULT 'cash',
                reference_no TEXT DEFAULT '',
                paid_at TEXT NOT NULL,
                FOREIGN KEY (bill_id) REFERENCES bills(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS invoice_sequence (
                id TEXT PRIMARY KEY,
                prefix TEXT NOT NULL DEFAULT 'INV',
                last_number INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()

        # Seed default prices
        _seed_default_prices(cursor, conn)
    except Exception as e:
        print(f"[BillingDB] init error: {e}")
    finally:
        conn.close()


def _seed_default_prices(cursor, conn):
    """Seed default test prices if bill_items table is empty."""
    try:
        cursor.execute("SELECT COUNT(*) FROM bill_items")
        if cursor.fetchone()[0] > 0:
            return
        now_str = datetime.now().isoformat()
        for test_name, price in DEFAULT_TEST_PRICES.items():
            cursor.execute(
                "INSERT INTO bill_items (id, test_name, price, active, updated_at) VALUES (?, ?, ?, 1, ?)",
                (str(uuid.uuid4()), test_name, price, now_str)
            )
        conn.commit()
        print(f"[BillingDB] Seeded {len(DEFAULT_TEST_PRICES)} default prices.")
    except Exception as e:
        print(f"[BillingDB] seed error: {e}")


# Initialize on import
_init_billing_tables()


# ─── PRICE CATALOGUE ──────────────────────────────────────────────────────────

def get_test_prices() -> dict:
    """Get all active test prices as {test_name: price} dict."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_test_prices_json()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT test_name, price FROM bill_items WHERE active=1")
        rows = cursor.fetchall()
        return {row[0]: row[1] for row in rows} or dict(DEFAULT_TEST_PRICES)
    except Exception:
        return dict(DEFAULT_TEST_PRICES)
    finally:
        conn.close()


def update_test_price(test_name: str, new_price: float) -> bool:
    """Update price for a test type."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE bill_items SET price=?, updated_at=? WHERE test_name=?",
            (new_price, datetime.now().isoformat(), test_name)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception:
        return False
    finally:
        conn.close()


# ─── INVOICE NUMBER GENERATION ────────────────────────────────────────────────

def _get_next_invoice_number() -> str:
    """Generate the next invoice number (thread-safe via DB lock)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, last_number FROM invoice_sequence WHERE prefix=? LIMIT 1",
                       (INVOICE_PREFIX,))
        row = cursor.fetchone()
        if row:
            seq_id, last_num = row
            next_num = last_num + 1
            cursor.execute("UPDATE invoice_sequence SET last_number=? WHERE id=?",
                           (next_num, seq_id))
        else:
            seq_id = str(uuid.uuid4())
            next_num = 1
            cursor.execute(
                "INSERT INTO invoice_sequence (id, prefix, last_number) VALUES (?, ?, ?)",
                (seq_id, INVOICE_PREFIX, next_num)
            )
        conn.commit()
        return INVOICE_NUMBER_FORMAT.format(next_num)
    except Exception as e:
        print(f"[BillingDB] invoice error: {e}")
        # Fallback: generate a timestamp-based number
        return f"{INVOICE_PREFIX}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    finally:
        conn.close()


# ─── BILL CRUD ────────────────────────────────────────────────────────────────

def create_bill(patient_id: str, patient_name: str, mobile: str,
                tests: list[dict], discount: float = 0.0,
                notes: str = "") -> dict:
    """
    Create a new bill for a patient's completed tests.

    Args:
        patient_id: Patient's public ID
        patient_name: Patient's name
        mobile: 10-digit mobile
        tests: List of test dicts (must include "test_name")
        discount: Discount amount to subtract
        notes: Optional bill notes

    Returns:
        dict with "success" bool, "message" string, and optionally "bill" dict
    """
    # Calculate totals
    prices = get_test_prices()
    total_amount = sum(prices.get(t.get("test_name", ""), 0) for t in tests)
    final_amount = max(0, total_amount - discount)

    invoice_number = _get_next_invoice_number()
    now_str = datetime.now().isoformat()
    bill_id = str(uuid.uuid4())

    # ─── Google Sheets ────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("createBill", {
            "id": bill_id,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "invoice_number": invoice_number,
            "total_amount": total_amount,
            "discount": discount,
            "final_amount": final_amount,
            "notes": notes,
            "created_at": now_str,
        }, is_post=True)
        if res:
            return {"success": True, "message": f"💰 Bill #{invoice_number} created!", "bill": res}
        # Fall through to Local JSON

    # ─── Local JSON ───────────────────────────────────────────────────────────
    json_mod = _get_json()
    if json_mod:
        return json_mod.create_bill_json(patient_id, patient_name, mobile, tests, discount, notes)

    # ─── SQLite / Supabase ────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            data = {
                "id": bill_id,
                "patient_id": patient_id,
                "patient_name": patient_name,
                "mobile": mobile,
                "invoice_number": invoice_number,
                "total_amount": total_amount,
                "discount": discount,
                "final_amount": final_amount,
                "notes": notes,
                "created_at": now_str,
            }
            get_client().table("bills").insert(data).execute()
            return {"success": True, "message": f"💰 Bill #{invoice_number} created!", "bill": data}
        except Exception as e:
            print(f"[BillingDB] Supabase error: {e}")
            return {"success": False, "message": "❌ Failed to create bill."}
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO bills (id, patient_id, patient_name, mobile, invoice_number, "
                "total_amount, discount, final_amount, notes, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (bill_id, patient_id, patient_name, mobile, invoice_number,
                 total_amount, discount, final_amount, notes, now_str)
            )
            conn.commit()
            # Auto-generate GST invoice
            try:
                from utils.gst import generate_gst_invoice
                test_name = tests[0] if isinstance(tests, list) and tests else "Consultation"
                generate_gst_invoice(bill_id, patient_name, final_amount, test_name)
            except Exception:
                pass
            return {
                "success": True,
                "message": f"💰 Bill #{invoice_number} created!",
                "bill": {
                    "id": bill_id,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "mobile": mobile,
                    "invoice_number": invoice_number,
                    "total_amount": total_amount,
                    "discount": discount,
                    "final_amount": final_amount,
                    "amount_paid": 0,
                    "status": "pending",
                    "payment_mode": "",
                    "notes": notes,
                    "created_at": now_str,
                }
            }
        except Exception as e:
            print(f"[BillingDB] SQLite error: {e}")
            return {"success": False, "message": "❌ Failed to create bill."}
        finally:
            conn.close()


def record_payment(bill_id: str, amount: float, mode: str = "cash",
                   reference_no: str = "") -> dict:
    """
    Record a payment against a bill. If fully paid, marks bill as paid.

    Args:
        bill_id: Bill record UUID
        amount: Amount being paid
        mode: Payment mode (cash/card/upi/neft/other)
        reference_no: Optional reference/transaction number

    Returns:
        dict with "success" bool and "message" string
    """
    if mode not in PAYMENT_MODES:
        return {"success": False, "message": f"Invalid payment mode. Choose from: {', '.join(PAYMENT_MODES)}"}

    json_mod = _get_json()
    if json_mod:
        return json_mod.record_payment_json(bill_id, amount, mode, reference_no)

    now_str = datetime.now().isoformat()
    payment_id = str(uuid.uuid4())

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Get current bill
        cursor.execute("SELECT final_amount, amount_paid, status FROM bills WHERE id=?", (bill_id,))
        bill = cursor.fetchone()
        if not bill:
            return {"success": False, "message": "❌ Bill not found."}
        if bill[2] == "paid":
            return {"success": False, "message": "❌ Bill is already paid."}
        if bill[2] == "cancelled":
            return {"success": False, "message": "❌ Bill is cancelled."}

        final_amount, amount_paid, _ = bill
        new_amount_paid = amount_paid + amount

        # Insert payment record
        cursor.execute(
            "INSERT INTO payments (id, bill_id, amount, mode, reference_no, paid_at) VALUES (?, ?, ?, ?, ?, ?)",
            (payment_id, bill_id, amount, mode, reference_no, now_str)
        )

        # Update bill
        if new_amount_paid >= final_amount:
            # Fully paid
            cursor.execute(
                "UPDATE bills SET amount_paid=?, status='paid', payment_mode=?, paid_at=? WHERE id=?",
                (final_amount, mode, now_str, bill_id)
            )
            message = f"✅ Bill fully paid! ₹{final_amount:,.2f} received."
        else:
            # Partial payment
            cursor.execute(
                "UPDATE bills SET amount_paid=?, payment_mode=? WHERE id=?",
                (new_amount_paid, mode, bill_id)
            )
            remaining = final_amount - new_amount_paid
            message = f"💰 Partial payment of ₹{amount:,.2f} recorded. Remaining: ₹{remaining:,.2f}"

        conn.commit()
        return {"success": True, "message": message}
    except Exception as e:
        print(f"[BillingDB] payment error: {e}")
        return {"success": False, "message": "❌ Failed to record payment."}
    finally:
        conn.close()


def get_bills_for_patient(mobile: str) -> list[dict]:
    """Get all bills for a patient by mobile number."""
    json_mod = _get_json()
    if json_mod:
        return json_mod.get_bills_for_patient_json(mobile)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM bills WHERE mobile=? ORDER BY created_at DESC",
            (mobile,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_bills_for_date(bill_date: Optional[str] = None,
                       status: str = "") -> list[dict]:
    """Get all bills created on a given date, optionally filtered by status."""
    if bill_date is None:
        bill_date = date.today().isoformat()

    json_mod = _get_json()
    if json_mod:
        return json_mod.get_bills_for_date_json(bill_date, status)

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM bills WHERE DATE(created_at)=?"
        params = [bill_date]
        if status:
            query += " AND status=?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_today_billing_summary() -> dict:
    """Get today's billing summary: total, paid, pending counts and amounts."""
    today = date.today().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT
                COUNT(*) AS total_bills,
                COALESCE(SUM(final_amount), 0) AS total_amount,
                SUM(CASE WHEN status='paid' THEN 1 ELSE 0 END) AS paid_count,
                COALESCE(SUM(CASE WHEN status='paid' THEN amount_paid ELSE 0 END), 0) AS paid_amount,
                SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS pending_count,
                COALESCE(SUM(CASE WHEN status='pending' THEN final_amount ELSE 0 END), 0) AS pending_amount
            FROM bills WHERE DATE(created_at)=?
        """, (today,))
        row = cursor.fetchone()
        if row:
            return {
                "total_bills": row[0],
                "total_amount": row[1],
                "paid_count": row[2],
                "paid_amount": row[3],
                "pending_count": row[4],
                "pending_amount": row[5],
            }
        return {"total_bills": 0, "total_amount": 0, "paid_count": 0, "paid_amount": 0,
                "pending_count": 0, "pending_amount": 0}
    except Exception:
        return {"total_bills": 0, "total_amount": 0, "paid_count": 0, "paid_amount": 0,
                "pending_count": 0, "pending_amount": 0}
    finally:
        conn.close()


def generate_invoice_html(bill: dict, clinic_name: str = "GIL CLINIC",
                          clinic_logo: str = "🏥", clinic_address: str = "",
                          clinic_phone: str = "") -> str:
    """
    Generate a print-optimised HTML invoice/receipt.
    """
    invoice_no = bill.get("invoice_number", "N/A")
    patient_name = bill.get("patient_name", "")
    patient_id = bill.get("patient_id", "")
    created = bill.get("created_at", "")
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        date_str = created_dt.strftime("%d-%b-%Y %I:%M %p")
    except Exception:
        date_str = created

    total = bill.get("total_amount", 0)
    discount = bill.get("discount", 0)
    final = bill.get("final_amount", 0)
    paid = bill.get("amount_paid", 0)
    status = bill.get("status", "pending").upper()

    status_color = "#4CAF50" if status == "PAID" else "#FF9800"
    balance = max(0, final - paid)

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Invoice {invoice_no}</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Segoe UI','Arial',sans-serif; background:#f5f5f5; padding:20px; }}
    .invoice {{
        max-width:500px; margin:0 auto; background:#fff;
        border-radius:14px; box-shadow:0 4px 24px rgba(0,0,0,0.12);
        overflow:hidden;
    }}
    .header {{
        background:linear-gradient(135deg,#667eea,#764ba2);
        color:#fff; text-align:center; padding:20px 16px 14px;
    }}
    .header h1 {{ font-size:28px; margin:0; }}
    .header h2 {{ font-size:16px; font-weight:400; opacity:0.9; margin:4px 0 2px; }}
    .body {{ padding:16px 18px; }}
    .patient-info {{ margin-bottom:12px; }}
    .patient-info .name {{ font-size:18px; font-weight:700; color:#222; }}
    .patient-info .meta {{ font-size:12px; color:#666; margin-top:2px; }}
    .invoice-no {{ font-size:14px; color:#667eea; font-weight:700; text-align:right; margin-bottom:12px; }}
    table {{ width:100%; border-collapse:collapse; margin:12px 0; }}
    th {{ text-align:left; font-size:11px; text-transform:uppercase; color:#999;
         padding:6px 4px 4px; border-bottom:2px solid #eee; }}
    td {{ padding:8px 4px; border-bottom:1px solid #f0f0f0; }}
    .total-row td {{ font-weight:700; font-size:16px; padding:10px 4px; border-top:2px solid #667eea; }}
    .status {{ text-align:center; padding:8px; border-radius:6px; font-weight:700; font-size:14px; }}
    .footer {{ text-align:center; padding:12px 16px 18px; font-size:11px; color:#aaa;
              border-top:1px solid #f0f0f0; }}
    @media print {{
        body {{ background:#fff; padding:0; }}
        .invoice {{ box-shadow:none; border-radius:0; max-width:100%; }}
        .header {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    }}
</style></head>
<body>
<div class="invoice">
    <div class="header">
        <h1>{clinic_logo}</h1>
        <h2>{clinic_name}</h2>
        <div style="font-size:12px;opacity:0.75;margin-top:4px;">{clinic_address}{" · " if clinic_address and clinic_phone else ""}{clinic_phone}</div>
    </div>
    <div class="body">
        <div class="invoice-no">Invoice #{invoice_no}</div>
        <div class="patient-info">
            <div class="name">{patient_name}</div>
            <div class="meta">ID: {patient_id} &nbsp;|&nbsp; {date_str}</div>
        </div>
        <table>
            <tr><th>Description</th><th style="text-align:right;">Amount</th></tr>
            <tr><td>Tests & Services</td><td style="text-align:right;">₹{total:,.2f}</td></tr>
            <tr><td>Discount</td><td style="text-align:right;color:#e74c3c;">-₹{discount:,.2f}</td></tr>
            <tr class="total-row"><td>Total</td><td style="text-align:right;">₹{final:,.2f}</td></tr>
            <tr><td>Paid</td><td style="text-align:right;color:#4CAF50;">₹{paid:,.2f}</td></tr>
            {f'<tr><td>Balance Due</td><td style="text-align:right;color:#FF5722;">₹{balance:,.2f}</td></tr>' if balance > 0 else ''}
        </table>
        <div class="status" style="background:{status_color}15;color:{status_color};border:1px solid {status_color}30;">
            {status}
        </div>
    </div>
    <div class="footer">
        CardioQueue Billing System &middot; Thank you for your visit!
    </div>
</div>
<script>window.print();</script>
</body>
</html>"""
