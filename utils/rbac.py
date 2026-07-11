"""
Role-Based Access Control — Permission Matrix
================================================
"""
import uuid
import json
from datetime import datetime
from utils.db import DB_FILE
import sqlite3

# 12-role hierarchy
ROLES = [
    "super_admin", "admin", "doctor", "nurse", "technician",
    "receptionist", "accountant", "pharmacist", "lab_technician",
    "manager", "patient", "ai_agent",
]

ROLE_HIERARCHY = {
    "super_admin": 0, "admin": 1, "manager": 2, "doctor": 3,
    "accountant": 4, "nurse": 5, "technician": 6, "lab_technician": 6,
    "pharmacist": 6, "receptionist": 7, "patient": 8, "ai_agent": 9,
}

RESOURCES = [
    "patient", "appointment", "billing", "inventory", "pharmacy",
    "lab", "radiology", "ipd", "emergency", "hr", "payroll",
    "finance", "reports", "settings", "audit", "users",
]

PERMISSIONS = ["create", "read", "update", "delete", "approve", "export"]

# Default permission matrix (role -> resource -> permissions)
DEFAULT_PERMS = {
    "super_admin": {r: PERMISSIONS for r in RESOURCES},
    "admin": {r: PERMISSIONS for r in RESOURCES},
    "manager": {r: ["read", "export"] for r in RESOURCES},
    "doctor": {"patient": ["read", "update"], "appointment": ["read"],
               "lab": ["read"], "pharmacy": ["create", "read"],
               "reports": ["read"], **{r: ["read"] for r in ["ipd", "emergency", "radiology"]}},
    "nurse": {"patient": ["read"], "emergency": ["read", "update"],
              "ipd": ["read"], **{r: ["read"] for r in ["appointment"]}},
    "receptionist": {"patient": ["create", "read", "update"],
                     "appointment": ["create", "read", "update"],
                     "billing": ["read"]},
    "accountant": {"billing": ["create", "read", "update"],
                   "finance": ["read", "export"], "payroll": ["read"]},
    "pharmacist": {"pharmacy": PERMISSIONS, "inventory": ["read"]},
    "lab_technician": {"lab": PERMISSIONS, "patient": ["read"]},
}


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rbac_roles (
                id TEXT PRIMARY KEY, role_name TEXT UNIQUE NOT NULL,
                permission_matrix TEXT NOT NULL,
                is_system INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        conn.commit()
        # Seed default roles
        for role, perms in DEFAULT_PERMS.items():
            cursor.execute(
                "INSERT OR IGNORE INTO rbac_roles (id, role_name, permission_matrix, is_system, created_at) VALUES (?,?,?,1,?)",
                (str(uuid.uuid4()), role, json.dumps(perms), datetime.now().isoformat())
            )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


_init_tables()


def check_permission(role: str, resource: str, permission: str) -> bool:
    if role in ("super_admin", "admin"):
        return True
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT permission_matrix FROM rbac_roles WHERE role_name=?", (role,))
        row = cursor.fetchone()
        if not row:
            return False
        matrix = json.loads(row[0])
        resource_perms = matrix.get(resource, [])
        return permission in resource_perms
    except Exception:
        return False
    finally:
        conn.close()


def get_role_permissions(role: str) -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT permission_matrix FROM rbac_roles WHERE role_name=?", (role,))
        row = cursor.fetchone()
        return json.loads(row[0]) if row else {}
    except Exception:
        return {}
    finally:
        conn.close()


def get_all_roles() -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM rbac_roles ORDER BY role_name")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        roles = []
        for row in rows:
            r = dict(zip(columns, row))
            r["permission_matrix"] = json.loads(r["permission_matrix"])
            roles.append(r)
        return roles
    except Exception:
        return []
    finally:
        conn.close()
