"""
Backup & Disaster Recovery Module
====================================
"""
import os
import shutil
import uuid
import json
from datetime import datetime, timedelta
from utils.db import DB_FILE
import sqlite3

BACKUP_DIR = "backups"


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_log (
                id TEXT PRIMARY KEY, backup_type TEXT NOT NULL,
                file_path TEXT, size_bytes INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                checksum TEXT DEFAULT '',
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
os.makedirs(BACKUP_DIR, exist_ok=True)


def create_backup(backup_type: str = "manual") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    bid = str(uuid.uuid4())
    now = datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    backup_file = f"{BACKUP_DIR}/backup_{timestamp}_{backup_type}.db"
    try:
        # SQLite backup via .backup command
        conn.execute(f"VACUUM INTO '{backup_file}'")
        size = os.path.getsize(backup_file)
        cursor.execute(
            "INSERT INTO backup_log (id, backup_type, file_path, size_bytes, status, created_at) VALUES (?,?,?,?,?,?)",
            (bid, backup_type, backup_file, size, "completed", now.isoformat())
        )
        conn.commit()
        return {"success": True, "file": backup_file, "size_kb": size // 1024}
    except Exception as e:
        cursor.execute(
            "INSERT INTO backup_log (id, backup_type, status, notes, created_at) VALUES (?,?,?,?,?)",
            (bid, backup_type, "failed", str(e), now.isoformat())
        )
        conn.commit()
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_backup_history(limit: int = 20) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM backup_log ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_backup_stats() -> dict:
    backups = get_backup_history(100)
    total_size = sum(b.get("size_bytes", 0) for b in backups)
    recent = [b for b in backups if b.get("status") == "completed"]
    return {
        "total": len(backups),
        "successful": len(recent),
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "last_backup": recent[0].get("created_at", "") if recent else "Never",
    }
