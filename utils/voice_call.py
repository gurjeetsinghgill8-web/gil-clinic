"""
Voice Call Module — Twilio/Exotel Telephony Integration
==========================================================
"""
import uuid
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

TWILIO_CONFIG = {
    "account_sid": "",
    "auth_token": "",
    "from_number": "",
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS voice_calls (
                id TEXT PRIMARY KEY, call_sid TEXT,
                from_number TEXT NOT NULL, to_number TEXT NOT NULL,
                direction TEXT DEFAULT 'outbound',
                status TEXT DEFAULT 'pending',
                duration INTEGER DEFAULT 0,
                recording_url TEXT DEFAULT '',
                call_type TEXT DEFAULT 'notification',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def initiate_call(to_number: str, from_number: str = "",
                  call_type: str = "notification", notes: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO voice_calls (id, from_number, to_number, direction, status, call_type, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (cid, from_number or TWILIO_CONFIG.get("from_number", ""),
             to_number, "outbound", "initiated", call_type, notes, now)
        )
        conn.commit()
        return {"success": True, "call_id": cid,
                "message": f"📞 Call initiated to {to_number}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def update_call_status(call_id: str, status: str, duration: int = 0,
                       recording_url: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE voice_calls SET status=?, duration=?, recording_url=? WHERE id=?",
            (status, duration, recording_url, call_id)
        )
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()


def get_call_log(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM voice_calls ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
