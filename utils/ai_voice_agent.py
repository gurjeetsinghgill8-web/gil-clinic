"""
AI Voice Agent Module — Multi-purpose Voice Interaction
==========================================================
"""
import uuid
import json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

AGENT_TYPES = {
    "receptionist": {"name": "AI Receptionist", "flows": ["greeting", "appointment", "info"]},
    "followup": {"name": "AI Follow-up", "flows": ["check_status", "reminder", "survey"]},
    "triage": {"name": "AI Triage", "flows": ["symptom_check", "emergency_detect", "referral"]},
    "survey": {"name": "AI Survey", "flows": ["feedback", "satisfaction", "outcome"]},
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_voice_sessions (
                id TEXT PRIMARY KEY, agent_type TEXT NOT NULL,
                patient_id TEXT, patient_name TEXT,
                status TEXT DEFAULT 'active',
                flow TEXT DEFAULT '',
                transcript TEXT DEFAULT '[]',
                sentiment TEXT DEFAULT '',
                duration INTEGER DEFAULT 0,
                needs_human INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def create_session(agent_type: str, patient_name: str = "",
                   patient_id: str = "") -> dict:
    if agent_type not in AGENT_TYPES:
        return {"success": False, "message": "Invalid agent type"}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    sid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO ai_voice_sessions (id, agent_type, patient_id, patient_name, status, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (sid, agent_type, patient_id, patient_name, "active", now)
        )
        conn.commit()
        return {"success": True, "session_id": sid,
                "message": f"🎙️ {AGENT_TYPES[agent_type]['name']} session created"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def add_transcript_entry(session_id: str, speaker: str, text: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT transcript FROM ai_voice_sessions WHERE id=?", (session_id,))
        row = cursor.fetchone()
        transcript = json.loads(row[0]) if row and row[0] else []
        transcript.append({"speaker": speaker, "text": text,
                          "timestamp": datetime.now().isoformat()})
        cursor.execute("UPDATE ai_voice_sessions SET transcript=? WHERE id=?",
                      (json.dumps(transcript), session_id))
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()


def end_session(session_id: str, sentiment: str = "", needs_human: bool = False) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "UPDATE ai_voice_sessions SET status='completed', sentiment=?, needs_human=? WHERE id=?",
            (sentiment, 1 if needs_human else 0, session_id)
        )
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()


def get_sessions(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM ai_voice_sessions ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
