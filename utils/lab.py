"""
Lab / Pathology Module — Sample Management, Test Panels, Results
=================================================================
Manages lab sample collection, test panel assignment, result entry, and reporting.
Lab tests are tracked in the existing test system but with additional
sample-level tracking and panel grouping.

New Tables:
    lab_panels       — Test panel definitions (CBC, LFT, KFT, Lipid, etc.)
    lab_panel_tests  — Individual tests within a panel
    lab_samples      — Sample collection tracking (blood, urine, etc.)
    lab_results      — Test results with normal ranges and flags
"""
import uuid
from datetime import date, datetime
from utils.db import DB_FILE
import sqlite3

_json_module = None


def _get_json():
    global _json_module
    if _json_module is None:
        from utils import local_json_db_json as local_json_db
        _json_module = local_json_db
    return _json_module


LAB_PANELS = [
    "CBC", "LFT", "KFT", "Lipid Profile", "Thyroid", "Blood Sugar",
    "Cardiac Enzymes", "Coagulation", "Urinalysis", "Culture",
]

SAMPLE_TYPES = ["Blood", "Urine", "Stool", "Sputum", "Swab", "CSF", "Tissue"]
SAMPLE_STATUSES = ["collected", "received", "processing", "completed", "rejected"]


def _init_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_panels (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT DEFAULT '',
                sample_type TEXT DEFAULT 'Blood', created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_panel_tests (
                id TEXT PRIMARY KEY, panel_id TEXT NOT NULL, test_name TEXT NOT NULL,
                unit TEXT DEFAULT '', normal_range TEXT DEFAULT '',
                min_normal REAL, max_normal REAL,
                FOREIGN KEY (panel_id) REFERENCES lab_panels(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_samples (
                id TEXT PRIMARY KEY, test_id TEXT NOT NULL, patient_id TEXT NOT NULL,
                sample_type TEXT NOT NULL, collection_date TEXT NOT NULL,
                collected_by TEXT DEFAULT '', status TEXT DEFAULT 'collected',
                notes TEXT DEFAULT '', created_at TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS lab_results (
                id TEXT PRIMARY KEY, sample_id TEXT NOT NULL, panel_test_id TEXT,
                test_name TEXT NOT NULL, value TEXT NOT NULL, unit TEXT DEFAULT '',
                normal_range TEXT DEFAULT '', flag TEXT DEFAULT '',
                entered_by TEXT DEFAULT '', entered_at TEXT NOT NULL,
                FOREIGN KEY (sample_id) REFERENCES lab_samples(id)
            )
        """)
        conn.commit()
        _seed_panels(cursor, conn)
    except Exception as e:
        print(f"[LABDB] init error: {e}")
    finally:
        conn.close()


def _seed_panels(cursor, conn):
    cursor.execute("SELECT COUNT(*) FROM lab_panels")
    if cursor.fetchone()[0] > 0:
        return
    now = datetime.now().isoformat()
    panels = [
        ("CBC", "Complete Blood Count", "Blood"),
        ("LFT", "Liver Function Test", "Blood"),
        ("KFT", "Kidney Function Test", "Blood"),
        ("Lipid Profile", "Lipid Profile", "Blood"),
        ("Cardiac Enzymes", "Cardiac Enzyme Panel", "Blood"),
        ("Urinalysis", "Urine Analysis", "Urine"),
    ]
    for name, desc, sample in panels:
        pid = str(uuid.uuid4())
        cursor.execute("INSERT INTO lab_panels (id, name, description, sample_type, created_at) VALUES (?,?,?,?,?)",
                       (pid, name, desc, sample, now))
    conn.commit()
    print(f"[LABDB] Seeded {len(panels)} lab panels.")


_init_tables()


def get_panels() -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM lab_panels ORDER BY name")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_panel_tests(panel_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM lab_panel_tests WHERE panel_id=? ORDER BY test_name", (panel_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def register_sample(test_id: str, patient_id: str, sample_type: str,
                    collected_by: str = "", notes: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        sid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO lab_samples (id, test_id, patient_id, sample_type, collection_date, collected_by, status, notes, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (sid, test_id, patient_id, sample_type, date.today().isoformat(), collected_by, "collected", notes, now)
        )
        conn.commit()
        return {"success": True, "message": "✅ Sample registered.", "sample_id": sid}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def update_sample_status(sample_id: str, status: str) -> dict:
    if status not in SAMPLE_STATUSES:
        return {"success": False, "message": "Invalid status."}
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE lab_samples SET status=? WHERE id=?", (status, sample_id))
        conn.commit()
        return {"success": True, "message": f"✅ Sample {status}."}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def enter_result(sample_id: str, test_name: str, value: str,
                 unit: str = "", normal_range: str = "",
                 flag: str = "", entered_by: str = "") -> dict:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        rid = str(uuid.uuid4())
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO lab_results (id, sample_id, test_name, value, unit, normal_range, flag, entered_by, entered_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (rid, sample_id, test_name, value, unit, normal_range, flag, entered_by, now)
        )
        conn.commit()
        return {"success": True, "message": "✅ Result entered."}
    except Exception as e:
        return {"success": False, "message": f"❌ {e}"}
    finally:
        conn.close()


def get_pending_samples() -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT s.*, p.name AS patient_name
            FROM lab_samples s
            LEFT JOIN patients p ON s.patient_id = p.patient_id
            WHERE s.status IN ('collected','received','processing')
            ORDER BY s.collection_date DESC
        """)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()


def get_results_for_sample(sample_id: str) -> list[dict]:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM lab_results WHERE sample_id=? ORDER BY entered_at", (sample_id,))
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]
    except Exception:
        return []
    finally:
        conn.close()
