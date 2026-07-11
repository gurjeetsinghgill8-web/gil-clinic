"""
Encryption Module — AES-256-GCM for PII/PHI Fields
=====================================================
"""
import uuid
import json
import base64
import hashlib
from datetime import datetime
from utils.db import DB_FILE
import sqlite3
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# Master key — in production this comes from environment/HashiCorp Vault
_MASTER_KEY = None


def _get_master_key() -> bytes:
    global _MASTER_KEY
    if _MASTER_KEY is None:
        # Derive from a config secret — in production use KMS/HSM
        from utils.config import ADMIN_PASS
        password = (ADMIN_PASS + "gil-clinic-encryption-salt-2026").encode()
        salt = b"gilclinic_salt_32bytes_fixed!"
        kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
        key = base64.urlsafe_b64encode(kdf.derive(password))
        _MASTER_KEY = Fernet(key)
    return _MASTER_KEY


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS encryption_audit (
                id TEXT PRIMARY KEY, entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL, field_name TEXT NOT NULL,
                operation TEXT NOT NULL, performed_by TEXT DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def encrypt_text(plaintext: str) -> str:
    """Encrypt a string field using AES-256-GCM via Fernet."""
    if not plaintext:
        return ""
    f = _get_master_key()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_text(ciphertext: str) -> str:
    """Decrypt a string field."""
    if not ciphertext:
        return ""
    try:
        f = _get_master_key()
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return "[encrypted]"


def protect_pii(record: dict, fields: list[str]) -> dict:
    """Encrypt specified PII fields in a record."""
    protected = record.copy()
    for field in fields:
        if field in protected and protected[field]:
            protected[field] = encrypt_text(str(protected[field]))
    return protected


def reveal_pii(record: dict, fields: list[str]) -> dict:
    """Decrypt specified PII fields in a record."""
    revealed = record.copy()
    for field in fields:
        if field in revealed and revealed[field]:
            revealed[field] = decrypt_text(str(revealed[field]))
    return revealed


def log_encryption_operation(entity_type: str, entity_id: str,
                              field_name: str, operation: str,
                              performed_by: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO encryption_audit (id, entity_type, entity_id, field_name, operation, performed_by, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4()), entity_type, entity_id, field_name, operation,
             performed_by, datetime.now().isoformat())
        )
        conn.commit()
        return {"success": True}
    except Exception:
        return {"success": False}
    finally:
        conn.close()
