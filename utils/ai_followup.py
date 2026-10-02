"""
AI Follow-up Engine — Smart Reminder Scheduling, No-show Prediction
======================================================================
"""
import uuid
from datetime import date, datetime, timedelta
from utils.db import DB_FILE
import sqlite3


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_followup_suggestions (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                mobile TEXT, diagnosis TEXT DEFAULT '',
                suggested_days INTEGER DEFAULT 7,
                suggested_dept TEXT DEFAULT '',
                priority TEXT DEFAULT 'normal',
                reason TEXT DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def suggest_followup(patient_id: str, patient_name: str, mobile: str,
                     diagnosis: str = "", suggested_days: int = 7,
                     suggested_dept: str = "", priority: str = "normal") -> dict:
    """AI suggests a follow-up based on diagnosis."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        fid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO ai_followup_suggestions (id, patient_id, patient_name, mobile, "
            "diagnosis, suggested_days, suggested_dept, priority, reason, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (fid, patient_id, patient_name, mobile, diagnosis, suggested_days,
             suggested_dept, priority, f"Follow-up in {suggested_days} days based on {diagnosis}", now)
        )
        conn.commit()
        return {
            "success": True, "message": f"📅 Suggested follow-up in {suggested_days} days.",
            "suggestion_id": fid, "suggested_date": (date.today() + timedelta(days=suggested_days)).isoformat()
        }
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def diagnose_to_followup_days(diagnosis: str) -> int:
    """AI maps diagnosis to recommended follow-up days."""
    d = diagnosis.lower()
    if any(kw in d for kw in ["heart attack", "mi", "stent", "angioplasty", "cabg"]):
        return 7
    elif any(kw in d for kw in ["angina", "chest pain", "ecg abnormal"]):
        return 14
    elif any(kw in d for kw in ["hypertension", "high bp", "blood pressure"]):
        return 30
    elif any(kw in d for kw in ["diabetes", "sugar"]):
        return 30
    elif any(kw in d for kw in ["infection", "fever", "viral"]):
        return 7
    elif any(kw in d for kw in ["surgery", "operation", "post-op"]):
        return 7
    elif any(kw in d for kw in ["routine", "checkup", "general"]):
        return 90
    return 14


def get_pending_suggestions() -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ai_followup_suggestions ORDER BY created_at DESC LIMIT 50")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
