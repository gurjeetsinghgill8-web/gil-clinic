"""
Push Notification Module — FCM / Web Push / Categories
==========================================================
"""
import uuid
import json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

NOTIFICATION_CATEGORIES = {
    "appointment_reminder": {"priority": "high", "ttl": 3600, "icon": "📅"},
    "report_ready": {"priority": "high", "ttl": 7200, "icon": "📄"},
    "test_called": {"priority": "urgent", "ttl": 1800, "icon": "🔔"},
    "payment_reminder": {"priority": "normal", "ttl": 86400, "icon": "💰"},
    "follow_up": {"priority": "normal", "ttl": 43200, "icon": "📋"},
    "general": {"priority": "low", "ttl": 86400, "icon": "ℹ️"},
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_devices (
                id TEXT PRIMARY KEY, device_token TEXT NOT NULL UNIQUE,
                platform TEXT DEFAULT 'web', patient_id TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT NOT NULL, last_seen TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_notifications (
                id TEXT PRIMARY KEY, device_token TEXT,
                category TEXT NOT NULL, title TEXT NOT NULL,
                body TEXT NOT NULL, data TEXT DEFAULT '{}',
                priority TEXT DEFAULT 'normal',
                status TEXT DEFAULT 'pending',
                sent_at TEXT, read_at TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def register_device(device_token: str, platform: str = "web",
                    patient_id: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO push_devices (id, device_token, platform, patient_id, is_active, created_at, last_seen) "
            "VALUES (?,?,?,?,1,?,?)",
            (str(uuid.uuid4()), device_token, platform, patient_id, now, now)
        )
        conn.commit()
        return {"success": True}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def send_push_notification(device_token: str, title: str, body: str,
                           category: str = "general", data: dict = None) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    nid = str(uuid.uuid4())
    now = datetime.now().isoformat()
    cat_config = NOTIFICATION_CATEGORIES.get(category, NOTIFICATION_CATEGORIES["general"])
    try:
        cursor.execute("""
            INSERT INTO push_notifications (id, device_token, category, title, body, data, priority, status, sent_at, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (nid, device_token, category, title, body,
              json.dumps(data or {}), cat_config["priority"], "sent", now, now))
        conn.commit()
        return {"success": True, "notification_id": nid}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def broadcast_notification(title: str, body: str, category: str = "general",
                           data: dict = None, platform: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT device_token FROM push_devices WHERE is_active=1"
        params = []
        if platform:
            query += " AND platform=?"
            params.append(platform)
        cursor.execute(query, params)
        tokens = [row[0] for row in cursor.fetchall()]
        sent = 0
        for token in tokens:
            r = send_push_notification(token, title, body, category, data)
            if r.get("success"):
                sent += 1
        return {"success": True, "sent": sent, "total": len(tokens)}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_notification_log(limit: int = 50) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM push_notifications ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
