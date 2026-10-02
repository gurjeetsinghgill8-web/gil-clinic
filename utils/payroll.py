"""
Payroll Module — Salary Processing, Payslips, Deductions
===========================================================
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payroll_records (
                id TEXT PRIMARY KEY, staff_id TEXT NOT NULL, staff_name TEXT,
                month INTEGER NOT NULL, year INTEGER NOT NULL,
                basic_salary REAL DEFAULT 0, allowances REAL DEFAULT 0,
                deductions REAL DEFAULT 0, net_pay REAL DEFAULT 0,
                days_worked INTEGER DEFAULT 0, status TEXT DEFAULT 'pending',
                paid_date TEXT, created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def process_payroll(staff_id: str, staff_name: str, month: int, year: int,
                    basic_salary: float, allowances: float = 0,
                    deductions: float = 0, days_worked: int = 0) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        rid = str(uuid.uuid4())
        net = basic_salary + allowances - deductions
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO payroll_records (id, staff_id, staff_name, month, year, "
            "basic_salary, allowances, deductions, net_pay, days_worked, status, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (rid, staff_id, staff_name, month, year, basic_salary, allowances,
             deductions, net, days_worked, "processed", now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Payroll processed: ₹{net:,.2f}", "id": rid}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_payroll_history(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM payroll_records ORDER BY year DESC, month DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
