"""
Compliance Framework — DPDP Act 2023, Consent Management, Data Rights
========================================================================
"""
import uuid
import json
from datetime import datetime, date
from utils.db import DB_FILE
import sqlite3

CONSENT_TYPES = ["medical_record", "communication", "data_sharing", "research", "billing"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consent_records (
                id TEXT PRIMARY KEY, patient_id TEXT NOT NULL,
                consent_type TEXT NOT NULL, granted INTEGER DEFAULT 1,
                purpose TEXT DEFAULT '', granted_at TEXT NOT NULL,
                revoked_at TEXT, expiry_date TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_rights_requests (
                id TEXT PRIMARY KEY, patient_id TEXT, patient_name TEXT,
                request_type TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                details TEXT DEFAULT '',
                fulfilled_at TEXT, created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def record_consent(patient_id: str, consent_type: str,
                   granted: bool = True, purpose: str = "") -> dict:
    if consent_type not in CONSENT_TYPES:
        return {"success": False, "message": "Invalid consent type"}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    try:
        cursor.execute("""
            INSERT INTO consent_records (id, patient_id, consent_type, granted, purpose, granted_at, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (str(uuid.uuid4()), patient_id, consent_type, 1 if granted else 0,
              purpose, now, now))
        conn.commit()
        return {"success": True,
                "message": f"✅ {'Granted' if granted else 'Revoked'} consent for {consent_type}"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


def get_consent_status(patient_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM consent_records WHERE patient_id=? ORDER BY created_at DESC",
            (patient_id,)
        )
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def create_data_rights_request(patient_id: str, patient_name: str,
                                request_type: str, details: str = "") -> dict:
    valid_types = ["access", "correction", "deletion", "portability", "restrict"]
    if request_type not in valid_types:
        return {"success": False, "message": "Invalid request type"}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO data_rights_requests (id, patient_id, patient_name, request_type, status, details, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (str(uuid.uuid4()), patient_id, patient_name, request_type,
              "pending", details, datetime.now().isoformat()))
        conn.commit()
        return {"success": True, "message": f"✅ {request_type} request submitted"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()
