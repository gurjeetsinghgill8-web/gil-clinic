"""
Video Call / Telemedicine Module — WebRTC Room Management
============================================================
"""
import uuid
import json
from datetime import datetime, timedelta
from utils.db import DB_FILE
import sqlite3


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS video_rooms (
                id TEXT PRIMARY KEY, room_name TEXT UNIQUE NOT NULL,
                patient_id TEXT, doctor_id TEXT,
                status TEXT DEFAULT 'scheduled',
                scheduled_at TEXT, started_at TEXT, ended_at TEXT,
                recording_url TEXT DEFAULT '',
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


def create_room(patient_name: str, doctor_name: str = "",
                patient_id: str = "", doctor_id: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    rid = str(uuid.uuid4())
    room_name = f"tele-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{rid[:6]}"
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT INTO video_rooms (id, room_name, patient_id, doctor_id, status, scheduled_at, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (rid, room_name, patient_id, doctor_id, "scheduled", now, now)
        )
        conn.commit()
        return {"success": True, "room_name": room_name,
                "room_url": f"/telemedicine/{room_name}",
                "message": f"✅ Room created: {room_name}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def start_room(room_name: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("UPDATE video_rooms SET status='active', started_at=? WHERE room_name=?",
                      (now, room_name))
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()


def end_room(room_name: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("UPDATE video_rooms SET status='completed', ended_at=? WHERE room_name=?",
                      (now, room_name))
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()


def get_rooms(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM video_rooms ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
