"""
Finance Module — Revenue Tracking, Expense Management, P&L
=============================================================
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3

EXPENSE_CATEGORIES = ["salary", "utilities", "rent", "supplies", "equipment",
                      "maintenance", "marketing", "travel", "other"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id TEXT PRIMARY KEY, category TEXT NOT NULL,
                description TEXT NOT NULL, amount REAL NOT NULL,
                expense_date TEXT NOT NULL, paid_to TEXT DEFAULT '',
                payment_mode TEXT DEFAULT 'cash', notes TEXT DEFAULT '',
                created_by TEXT DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def add_expense(category: str, description: str, amount: float,
                expense_date: str = "", paid_to: str = "",
                payment_mode: str = "cash", notes: str = "",
                created_by: str = "") -> dict:
    if category not in EXPENSE_CATEGORIES:
        return {"success": False, "message": "Invalid category."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        eid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO expenses (id, category, description, amount, expense_date, "
            "paid_to, payment_mode, notes, created_by, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (eid, category, description, amount, expense_date or date.today().isoformat(),
             paid_to, payment_mode, notes, created_by, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Expense recorded: ₹{amount:,.2f}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_monthly_summary(month: int = 0, year: int = 0) -> dict:
    from utils.billing import get_today_billing_summary
    conn = sqlite3.connect(DB_FILE)
    try:
        m = month or date.today().month
        y = year or date.today().year
        start = f"{y}-{m:02d}-01"
        if m == 12:
            end = f"{y+1}-01-01"
        else:
            end = f"{y}-{m+1:02d}-01"

        total_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM bills WHERE bill_date >= ? AND bill_date < ? AND status='paid'",
            (start, end)
        ).fetchone()[0]

        total_expenses = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE expense_date >= ? AND expense_date < ?",
            (start, end)
        ).fetchone()[0]

        return {
            "month": m, "year": y,
            "revenue": total_revenue,
            "expenses": total_expenses,
            "profit": total_revenue - total_expenses,
        }
    except Exception:
        return {"revenue": 0, "expenses": 0, "profit": 0}
    finally:
        conn.close()


def get_expenses(month: int = 0, year: int = 0) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        m = month or date.today().month
        y = year or date.today().year
        start = f"{y}-{m:02d}-01"
        if m == 12:
            end = f"{y+1}-01-01"
        else:
            end = f"{y}-{m+1:02d}-01"
        cursor.execute("SELECT * FROM expenses WHERE expense_date >= ? AND expense_date < ? ORDER BY expense_date DESC", (start, end))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
