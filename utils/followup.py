"""
Follow-up Scheduling Module — Automated Follow-ups, Reminders, No-show Handling
==================================================================================
Manages doctor-recommended follow-ups with multi-touch reminder chains,
outcome tracking, and recurrence for chronic conditions.

Tables:
    follow_ups        — Core follow-up records with timing, status, recurrence
    followup_outcomes — Patient visit outcomes with escalation tracking
"""
import uuid
from datetime import date, datetime, timedelta
from utils.db import DB_FILE
import sqlite3

_json_module = None


def _get_json():
    global _json_module
    if _json_module is None:
        from utils import local_json_db_json as local_json_db
        _json_module = local_json_db
    return _json_module


FOLLOWUP_TYPES = {
    "post_visit": "Post-Visit Checkup",
    "test_result": "Test Result Review",
    "chronic": "Chronic Management",
    "medication": "Medication Adherence",
    "recovery": "Recovery Check",
    "vaccination": "Vaccination Reminder",
    "screening": "Health Screening",
}
FOLLOWUP_STATUSES = ["scheduled", "reminded", "confirmed", "attended", "missed", "cancelled", "rescheduled"]
RECURRENCE_PATTERNS = ["none", "weekly", "biweekly", "monthly", "quarterly", "yearly"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS follow_ups (
                id TEXT PRIMARY KEY, patient_id TEXT NOT NULL, patient_name TEXT,
                mobile TEXT, doctor_name TEXT, department TEXT DEFAULT '',
                followup_type TEXT NOT NULL DEFAULT 'post_visit',
                scheduled_date TEXT NOT NULL, scheduled_time TEXT DEFAULT '10:00',
                status TEXT NOT NULL DEFAULT 'scheduled',
                notes TEXT DEFAULT '', recurrence TEXT DEFAULT 'none',
                recurrence_end TEXT, created_by TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followup_outcomes (
                id TEXT PRIMARY KEY, followup_id TEXT NOT NULL,
                outcome TEXT NOT NULL DEFAULT 'attended',
                condition_status TEXT DEFAULT '', notes TEXT DEFAULT '',
                next_followup_date TEXT, recorded_by TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (followup_id) REFERENCES follow_ups(id)
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[FUDB] init error: {e}")
    finally:
        conn.close()


_init_tables()


def schedule_followup(patient_id: str, patient_name: str, mobile: str,
                      doctor_name: str, followup_type: str = "post_visit",
                      scheduled_date: str = "", notes: str = "",
                      recurrence: str = "none", department: str = "") -> dict:
    """Schedule a follow-up for a patient."""
    if followup_type not in FOLLOWUP_TYPES:
        return {"success": False, "message": "Invalid follow-up type."}
    if recurrence not in RECURRENCE_PATTERNS:
        return {"success": False, "message": "Invalid recurrence pattern."}

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        fid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        sched = scheduled_date or (date.today() + timedelta(days=7)).isoformat()
        cursor.execute(
            "INSERT INTO follow_ups (id, patient_id, patient_name, mobile, doctor_name, "
            "department, followup_type, scheduled_date, status, notes, recurrence, created_by, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, patient_id, patient_name, mobile, doctor_name, department,
             followup_type, sched, "scheduled", notes, recurrence,
             "", now, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Follow-up scheduled for {sched}.", "id": fid}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_today_followups() -> list[dict]:
    """Get follow-ups scheduled for today."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        today = date.today().isoformat()
        cursor.execute("""
            SELECT * FROM follow_ups
            WHERE scheduled_date=? AND status NOT IN ('cancelled','attended')
            ORDER BY scheduled_time
        """, (today,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_pending_followups(days: int = 7) -> list[dict]:
    """Get upcoming follow-ups within X days."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        today = date.today().isoformat()
        end = (date.today() + timedelta(days=days)).isoformat()
        cursor.execute("""
            SELECT * FROM follow_ups
            WHERE scheduled_date BETWEEN ? AND ?
            AND status NOT IN ('cancelled','attended')
            ORDER BY scheduled_date, scheduled_time
        """, (today, end))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def update_followup_status(followup_id: str, status: str) -> dict:
    if status not in FOLLOWUP_STATUSES:
        return {"success": False, "message": "Invalid status."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        cursor.execute("UPDATE follow_ups SET status=?, updated_at=? WHERE id=?",
                       (status, now, followup_id))
        conn.commit()

        # If attended, record outcome automatically
        if status == "attended":
            oid = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO followup_outcomes (id, followup_id, outcome, created_at) VALUES (?,?,?,?)",
                (oid, followup_id, "attended", now)
            )
            conn.commit()

        return {"success": True, "message": f"✅ Status: {status}"}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_followups_for_patient(patient_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM follow_ups WHERE patient_id=? ORDER BY scheduled_date DESC", (patient_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def record_outcome(followup_id: str, outcome: str, condition_status: str = "",
                   notes: str = "", next_followup_date: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        oid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO followup_outcomes (id, followup_id, outcome, condition_status, notes, next_followup_date, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (oid, followup_id, outcome, condition_status, notes, next_followup_date or None, now)
        )
        # Update follow-up status
        cursor.execute("UPDATE follow_ups SET status=?, updated_at=? WHERE id=?",
                       ("attended" if outcome == "attended" else "missed", now, followup_id))
        conn.commit()
        return {"success": True, "message": "✅ Outcome recorded."}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_missed_followups() -> list[dict]:
    """Get overdue follow-ups (past scheduled date, not attended/cancelled)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        today = date.today().isoformat()
        cursor.execute("""
            SELECT * FROM follow_ups
            WHERE scheduled_date < ? AND status IN ('scheduled','reminded','confirmed')
            ORDER BY scheduled_date
        """, (today,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
