"""
HR Module — Staff Management, Attendance, Leave Tracking
===========================================================
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3

LEAVE_TYPES = ["sick", "casual", "annual", "maternity", "paternity", "unpaid"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_staff (
                id TEXT PRIMARY KEY, user_id TEXT, name TEXT NOT NULL,
                role TEXT DEFAULT '', department TEXT DEFAULT '',
                mobile TEXT DEFAULT '', email TEXT DEFAULT '',
                join_date TEXT, salary REAL DEFAULT 0,
                is_active INTEGER DEFAULT 1, created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_attendance (
                id TEXT PRIMARY KEY, staff_id TEXT NOT NULL,
                date TEXT NOT NULL, status TEXT DEFAULT 'present',
                check_in TEXT, check_out TEXT, notes TEXT DEFAULT '',
                FOREIGN KEY (staff_id) REFERENCES hr_staff(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hr_leave (
                id TEXT PRIMARY KEY, staff_id TEXT NOT NULL,
                leave_type TEXT NOT NULL, from_date TEXT NOT NULL,
                to_date TEXT NOT NULL, reason TEXT DEFAULT '',
                status TEXT DEFAULT 'pending', approved_by TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (staff_id) REFERENCES hr_staff(id)
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def add_staff(name: str, role: str = "", department: str = "",
              mobile: str = "", email: str = "", join_date: str = "",
              salary: float = 0.0) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        sid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO hr_staff (id, name, role, department, mobile, email, join_date, salary, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, name, role, department, mobile, email, join_date or date.today().isoformat(), salary, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Staff {name} added.", "id": sid}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_staff(active_only: bool = True) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM hr_staff"
        if active_only:
            query += " WHERE is_active=1"
        query += " ORDER BY name"
        cursor.execute(query)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def mark_attendance(staff_id: str, status: str = "present",
                    check_in: str = "", check_out: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        aid = str(uuid.uuid4())
        now = datetime.now().strftime("%H:%M:%S")
        cursor.execute(
            "INSERT INTO hr_attendance (id, staff_id, date, status, check_in, check_out) VALUES (?,?,?,?,?,?)",
            (aid, staff_id, date.today().isoformat(), status, check_in or now, check_out or "")
        )
        conn.commit()
        return {"success": True, "message": f"✅ Attendance: {status}."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def apply_leave(staff_id: str, leave_type: str, from_date: str, to_date: str,
                reason: str = "") -> dict:
    if leave_type not in LEAVE_TYPES:
        return {"success": False, "message": "Invalid leave type."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        lid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO hr_leave (id, staff_id, leave_type, from_date, to_date, reason, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (lid, staff_id, leave_type, from_date, to_date, reason, now)
        )
        conn.commit()
        return {"success": True, "message": "✅ Leave applied (pending approval)."}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
