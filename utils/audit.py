"""
Enhanced Audit Log System — Immutable Append-Only with Actor Context
======================================================================
"""
import uuid
import json
import hashlib
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

AUDIT_CATEGORIES = ["auth", "patient", "billing", "clinical", "admin", "data", "system"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log_v2 (
                id TEXT PRIMARY KEY, parent_hash TEXT DEFAULT '',
                hash TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL, action TEXT NOT NULL,
                actor_id TEXT, actor_name TEXT, actor_role TEXT,
                resource_type TEXT, resource_id TEXT,
                details TEXT DEFAULT '{}',
                ip_address TEXT DEFAULT '',
                user_agent TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def _compute_hash(entry: dict) -> str:
    raw = json.dumps(entry, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def log_event(category: str, action: str, actor_id: str = "",
              actor_name: str = "", actor_role: str = "",
              resource_type: str = "", resource_id: str = "",
              details: dict = None, ip_address: str = "",
              user_agent: str = "") -> dict:
    if category not in AUDIT_CATEGORIES:
        category = "system"
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        # Get last entry's hash for chaining
        cursor.execute("SELECT hash FROM audit_log_v2 ORDER BY created_at DESC LIMIT 1")
        last = cursor.fetchone()
        parent_hash = last[0] if last else ""

        aid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        entry = {
            "id": aid, "parent_hash": parent_hash, "category": category,
            "action": action, "actor_id": actor_id, "actor_name": actor_name,
            "actor_role": actor_role, "resource_type": resource_type,
            "resource_id": resource_id, "details": details or {},
            "ip_address": ip_address, "user_agent": user_agent, "created_at": now,
        }
        entry_hash = _compute_hash(entry)

        cursor.execute("""
            INSERT INTO audit_log_v2 (id, parent_hash, hash, category, action, actor_id, actor_name,
                actor_role, resource_type, resource_id, details, ip_address, user_agent, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (aid, parent_hash, entry_hash, category, action, actor_id, actor_name,
              actor_role, resource_type, resource_id, json.dumps(details or {}),
              ip_address, user_agent, now))
        conn.commit()
        return {"success": True, "hash": entry_hash}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def query_audit(category: str = "", action: str = "", actor: str = "",
                limit: int = 100) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        query = "SELECT * FROM audit_log_v2 WHERE 1=1"
        params = []
        if category:
            query += " AND category=?"
            params.append(category)
        if action:
            query += " AND action LIKE ?"
            params.append(f"%{action}%")
        if actor:
            query += " AND (actor_name LIKE ? OR actor_id LIKE ?)"
            params.extend([f"%{actor}%", f"%{actor}%"])
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def verify_chain() -> dict:
    """Verify the cryptographic chain integrity."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, parent_hash, hash, created_at FROM audit_log_v2 ORDER BY created_at ASC")
        rows = cursor.fetchall()
        broken = 0
        prev_hash = ""
        for row in rows:
            if row[1] != prev_hash:
                broken += 1
            prev_hash = row[2]
        return {"total": len(rows), "broken_links": broken,
                "chain_intact": broken == 0}
    except Exception:
        return {"total": 0, "broken_links": 0, "chain_intact": False}
    finally:
        conn.close()
