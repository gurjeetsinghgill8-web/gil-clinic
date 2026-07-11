"""
Emergency / Casualty Module — Triage, Admission, Emergency Queue
=================================================================
Manages emergency patient triage, emergency physician assignments,
and direct emergency-to-IPD handoff.

Tables:
    emergency_cases   — Emergency case records with triage and disposition
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3

TRIAGE_LEVELS = ["1-Emergency", "2-Urgent", "3-Moderate", "4-Mild", "5-Non-urgent"]
CASE_STATUSES = ["waiting", "in_treatment", "admitted", "discharged", "referred", "dod"]
DISPOSITIONS = ["discharged", "admitted_ipd", "referred", "observed", "dod"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS emergency_cases (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                mobile TEXT, age INTEGER, gender TEXT,
                triage_level TEXT NOT NULL DEFAULT '3-Moderate',
                chief_complaint TEXT NOT NULL, symptoms TEXT DEFAULT '',
                bp TEXT DEFAULT '', pulse TEXT DEFAULT '', spo2 TEXT DEFAULT '',
                temperature TEXT DEFAULT '', status TEXT DEFAULT 'waiting',
                disposition TEXT DEFAULT '', attending_doctor TEXT DEFAULT '',
                referred_to TEXT DEFAULT '', notes TEXT DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception as e:
        print(f"[ERDB] init error: {e}")
    finally:
        conn.close()


_init_tables()


def register_emergency(patient_name: str, mobile: str, age: int = 0,
                       gender: str = "", chief_complaint: str = "",
                       triage_level: str = "3-Moderate", symptoms: str = "",
                       bp: str = "", pulse: str = "", spo2: str = "",
                       temperature: str = "", patient_id: str = "") -> dict:
    if triage_level not in TRIAGE_LEVELS:
        return {"success": False, "message": "Invalid triage level."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        eid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        pid = patient_id or f"ER-{datetime.now().strftime('%y%m%d-%H%M%S')}"
        cursor.execute(
            "INSERT INTO emergency_cases (id, patient_id, patient_name, mobile, age, gender, "
            "triage_level, chief_complaint, symptoms, bp, pulse, spo2, temperature, "
            "status, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, pid, patient_name, mobile, age, gender,
             triage_level, chief_complaint, symptoms, bp, pulse, spo2, temperature,
             "waiting", now, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Emergency case registered (Triage: {triage_level})", "id": eid, "patient_id": pid}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_emergency_queue() -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT * FROM emergency_cases
            WHERE status IN ('waiting','in_treatment')
            ORDER BY
                CASE triage_level
                    WHEN '1-Emergency' THEN 0
                    WHEN '2-Urgent' THEN 1
                    WHEN '3-Moderate' THEN 2
                    WHEN '4-Mild' THEN 3
                    WHEN '5-Non-urgent' THEN 4
                END, created_at ASC
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def update_emergency_status(case_id: str, status: str, attending_doctor: str = "",
                            disposition: str = "", notes: str = "") -> dict:
    if status not in CASE_STATUSES:
        return {"success": False, "message": "Invalid status."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        now = datetime.now().isoformat()
        updates = {"status": status, "updated_at": now}
        if attending_doctor:
            updates["attending_doctor"] = attending_doctor
        if disposition:
            updates["disposition"] = disposition
        if notes:
            updates["notes"] = notes
        set_clause = ", ".join(f"{k}=?" for k in updates)
        cursor.execute(f"UPDATE emergency_cases SET {set_clause} WHERE id=?", list(updates.values()) + [case_id])
        conn.commit()
        return {"success": True, "message": f"✅ Case {status}."}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_emergency_stats() -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        waiting = cursor.execute("SELECT COUNT(*) FROM emergency_cases WHERE status='waiting'").fetchone()[0]
        in_treatment = cursor.execute("SELECT COUNT(*) FROM emergency_cases WHERE status='in_treatment'").fetchone()[0]
        today_count = cursor.execute(
            "SELECT COUNT(*) FROM emergency_cases WHERE date(created_at)=date('now')"
        ).fetchone()[0]
        return {"waiting": waiting, "in_treatment": in_treatment, "today": today_count}
    except Exception:
        return {"waiting": 0, "in_treatment": 0, "today": 0}
    finally:
        conn.close()
