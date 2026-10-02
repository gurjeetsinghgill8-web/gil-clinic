"""
Vendor Management Module — Supplier Registry, Performance Tracking
====================================================================
"""
import uuid
from datetime import datetime
from utils.db import DB_FILE
import sqlite3


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vendors (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, contact_person TEXT DEFAULT '',
                mobile TEXT DEFAULT '', email TEXT DEFAULT '', address TEXT DEFAULT '',
                gst TEXT DEFAULT '', category TEXT DEFAULT 'general',
                payment_terms TEXT DEFAULT '30 days', is_active INTEGER DEFAULT 1,
                rating REAL DEFAULT 0, created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def create_vendor(name: str, contact_person: str = "", mobile: str = "",
                  email: str = "", address: str = "", gst: str = "",
                  category: str = "general", payment_terms: str = "30 days") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        vid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO vendors (id, name, contact_person, mobile, email, address, gst, category, payment_terms, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (vid, name, contact_person, mobile, email, address, gst, category, payment_terms, now)
        )
        conn.commit()
        return {"success": True, "message": f"✅ Vendor '{name}' added.", "id": vid}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_vendors(active_only: bool = True) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM vendors"
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
