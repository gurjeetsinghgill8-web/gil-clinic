"""
Database module — Tri-mode storage for CardioQueue.
====================================================
Priority: Google Sheets → Local JSON files (cardioqueue_data/) → SQLite
- If Google Sheets URL is set and working → uses GS
- If GS fails → automatically falls back to Local JSON (human-readable files)
- If SUPABASE_URL/KEY are valid → uses Supabase instead of SQLite
"""
import os
import sqlite3
import uuid
import requests
from datetime import date, datetime
from utils.config import SUPABASE_URL, SUPABASE_KEY

# ─── GOOGLE SHEETS BACKEND CONFIG ───────────────────────────────────────────
GOOGLE_SCRIPT_URL = os.getenv("GOOGLE_SCRIPT_URL", "").strip()
USE_GOOGLE_SHEETS = len(GOOGLE_SCRIPT_URL) > 0
_gs_failed = False  # Marks if GS API has failed — triggers Local JSON fallback

# ─── LOCAL JSON FALLBACK ────────────────────────────────────────────────────
USE_LOCAL_JSON = not USE_GOOGLE_SHEETS or _gs_failed  # Will be re-evaluated after GS fail
if not USE_GOOGLE_SHEETS:
    from utils.local_json_db import (
        create_patient_json as _create_patient,
        get_patient_by_id_json as _get_patient_by_id,
        get_patient_by_mobile_json as _get_patient_by_mobile,
        get_today_patients_json as _get_today_patients,
        create_test_json as _create_test,
        get_tests_for_patient_json as _get_tests_for_patient,
        get_tests_by_mobile_json as _get_tests_by_mobile,
        get_queue_json as _get_queue,
        update_test_status_json as _update_test_status,
        get_completed_tests_json as _get_completed_tests,
        get_report_ready_tests_json as _get_report_ready_tests,
        get_current_patient_json as _get_current_patient,
        get_department_stats_json as _get_department_stats,
        log_message_json as _log_message,
        _set_patient_alert_json, _get_patient_alert_json, _clear_patient_alert_json,
        _get_patient_visit_count_json,
        _get_patient_visits_by_mobile_json,
        _get_recent_activity_json,
    )
    print("[DB] Google Sheets not set. Using Local JSON file storage.")
    print(f"[DB] Data directory: {os.path.abspath('cardioqueue_data/')}")

def call_gs_api(action: str, params: dict = None, is_post: bool = False):
    global _gs_failed, USE_LOCAL_JSON
    if _gs_failed:
        return None  # Already failed once — skip retries, use Local JSON
    if params is None:
        params = {}
    params["action"] = action
    try:
        if is_post:
            r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)
            if r.status_code != 200:
                r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)
        else:
            r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)

        if r.status_code == 200:
            return r.json()
        else:
            print(f"[GoogleSheets] API Error: {r.status_code} - {r.text[:200]}")
            _gs_failed = True
            _auto_enable_local_json()
            return None
    except Exception as e:
        print(f"[GoogleSheets] Exception calling API: {e}")
        _gs_failed = True
        _auto_enable_local_json()
        return None


def _auto_enable_local_json():
    """Import JSON functions when Google Sheets fails, so rest of app uses files."""
    global USE_LOCAL_JSON, _create_patient, _get_patient_by_id, _get_patient_by_mobile
    global _get_today_patients, _create_test, _get_tests_for_patient, _get_tests_by_mobile
    global _get_queue, _update_test_status, _get_completed_tests, _get_report_ready_tests
    global _get_current_patient, _get_department_stats, _log_message
    global _set_patient_alert_json, _get_patient_alert_json, _clear_patient_alert_json
    global _get_patient_visit_count_json, _get_patient_visits_by_mobile_json
    global _get_recent_activity_json
    from utils.local_json_db import (
        create_patient_json as _create_patient,
        get_patient_by_id_json as _get_patient_by_id,
        get_patient_by_mobile_json as _get_patient_by_mobile,
        get_today_patients_json as _get_today_patients,
        create_test_json as _create_test,
        get_tests_for_patient_json as _get_tests_for_patient,
        get_tests_by_mobile_json as _get_tests_by_mobile,
        get_queue_json as _get_queue,
        update_test_status_json as _update_test_status,
        get_completed_tests_json as _get_completed_tests,
        get_report_ready_tests_json as _get_report_ready_tests,
        get_current_patient_json as _get_current_patient,
        get_department_stats_json as _get_department_stats,
        log_message_json as _log_message,
        _set_patient_alert_json, _get_patient_alert_json, _clear_patient_alert_json,
        _get_patient_visit_count_json,
        _get_patient_visits_by_mobile_json,
        _get_recent_activity_json,
    )
    USE_LOCAL_JSON = True
    print("[DB] Google Sheets failed. Switched to Local JSON folder storage.")

def to_snake_case(d):
    if isinstance(d, list):
        return [to_snake_case(x) for x in d]
    if isinstance(d, dict):
        mapping = {
            "patientId": "patient_id",
            "registrationDate": "registration_date",
            "createdAt": "created_at",
            "testName": "test_name",
            "tokenNumber": "token_number",
            "queuePosition": "queue_position",
            "calledAt": "called_at",
            "startedAt": "started_at",
            "completedAt": "completed_at",
            "reportReadyAt": "report_ready_at",
            "deliveredAt": "delivered_at",
            "dismissedAt": "dismissed_at",
            "fromRole": "from_role",
            "toRole": "to_role",
            "relatedTestId": "related_test_id"
        }
        return {mapping.get(k, k): to_snake_case(v) for k, v in d.items()}
    return d

# ─── DATABASE DETECTION ──────────────────────────────────────────────────────
USE_SUPABASE = False
_supabase = None
DB_FILE = "cardioqueue.db"

def init_sqlite():
    """Create local SQLite database tables if they do not exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # 1. patients table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id TEXT PRIMARY KEY,
        patient_id TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        mobile VARCHAR(10) NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        registration_date TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """)
    
    # 2. tests table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tests (
        id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        test_name TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'waiting',
        token_number INTEGER NOT NULL,
        queue_position INTEGER DEFAULT 0,
        room TEXT NOT NULL,
        called_at TEXT,
        started_at TEXT,
        completed_at TEXT,
        report_ready_at TEXT,
        delivered_at TEXT,
        created_at TEXT NOT NULL,
        pending_alert INTEGER DEFAULT 0,
        alert_message TEXT DEFAULT '',
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
    )
    """)

    # Migrate existing DB: add alert columns if missing
    try:
        cursor.execute("ALTER TABLE tests ADD COLUMN pending_alert INTEGER DEFAULT 0")
    except Exception:
        pass  # Column already exists
    try:
        cursor.execute("ALTER TABLE tests ADD COLUMN alert_message TEXT DEFAULT ''")
    except Exception:
        pass  # Column already exists
    try:
        cursor.execute("ALTER TABLE patients ADD COLUMN reception_inquiry TEXT DEFAULT NULL")
    except Exception:
        pass
    
    # 3. messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        patient_id TEXT NOT NULL,
        mobile VARCHAR(10) NOT NULL,
        message_type TEXT NOT NULL,
        message_text TEXT NOT NULL,
        sent_via TEXT NOT NULL DEFAULT 'none',
        sent_at TEXT NOT NULL,
        actor TEXT DEFAULT '',
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
    )
    """)

    # Migrate existing DB: add actor column if missing
    try:
        cursor.execute("ALTER TABLE messages ADD COLUMN actor TEXT DEFAULT ''")
    except Exception:
        pass

    # 4. users table (for password-based auth)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL,
        role TEXT NOT NULL,
        password TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_by TEXT,
        created_at TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

    # ─── Auto-seed default users if empty ───────────────────────────────────
    _seed_default_users()


def _seed_default_users():
    """Create default admin + sample staff accounts if users table is empty."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        if count > 0:
            conn.close()
            return

        now = datetime.now().isoformat()
        default_users = [
            (str(uuid.uuid4()), "admin", "Admin", "Admin", "gurjas@123", 1, now),
            (str(uuid.uuid4()), "reception1", "Reception Staff", "Reception", "1234", 1, now),
            (str(uuid.uuid4()), "ecg1", "ECG Technician", "ECG", "1234", 1, now),
            (str(uuid.uuid4()), "echo1", "Echo Technician", "Echo", "1234", 1, now),
            (str(uuid.uuid4()), "tmt1", "TMT Technician", "TMT", "1234", 1, now),
            (str(uuid.uuid4()), "doctor1", "Dr. Sharma", "Doctor", "1234", 1, now),
            (str(uuid.uuid4()), "manager1", "Manager", "Manager", "1234", 1, now),
        ]
        cursor.executemany(
            "INSERT INTO users (id, username, display_name, role, password, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            default_users
        )
        conn.commit()
        print(f"[DB] ✅ Seeded {len(default_users)} default user accounts.")
    except Exception as e:
        print(f"[DB] _seed_default_users error: {e}")
    finally:
        conn.close()


# Detect and configure database connection
    # Supabase is disabled by default to keep data local to the device
    USE_SUPABASE = False

if not USE_SUPABASE:
    init_sqlite()



def get_client():
    """Get the Supabase client if running in Supabase mode."""
    return _supabase


# ─── PATIENTS ────────────────────────────────────────────────────────────────

def create_patient(name: str, mobile: str, age: int, gender: str) -> dict | None:
    """
    Insert a new patient record.
    Returns the created patient dict or None on failure.
    """
    # ─── Google Sheets ────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("createPatient", {"name": name, "mobile": mobile, "age": age, "gender": gender}, is_post=True)
        if res:
            return to_snake_case(res)
        # Fall through to Local JSON if GS fails

    # ─── Local JSON ───────────────────────────────────────────────────────────
    if USE_LOCAL_JSON:
        return _create_patient(name, mobile, age, gender)

    today = date.today().isoformat()
    count = _get_today_patient_count()
    patient_id = f"CQ-{today.replace('-', '')}-{count + 1:03d}"

    if USE_SUPABASE:
        data = {
            "patient_id": patient_id,
            "name": name,
            "mobile": mobile,
            "age": age,
            "gender": gender,
            "registration_date": today,
        }
        try:
            result = get_client().table("patients").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[DB] create_patient error: {e}")
            return None
    else:
        patient_uuid = str(uuid.uuid4())
        now_str = datetime.now().isoformat()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO patients (id, patient_id, name, mobile, age, gender, registration_date, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (patient_uuid, patient_id, name, mobile, age, gender, today, now_str)
            )
            conn.commit()
            return {
                "id": patient_uuid,
                "patient_id": patient_id,
                "name": name,
                "mobile": mobile,
                "age": age,
                "gender": gender,
                "registration_date": today,
                "created_at": now_str
            }
        except Exception as e:
            print(f"[SQLite] create_patient error: {e}")
            return None
        finally:
            conn.close()


def get_patient_by_id(patient_id: str) -> dict | None:
    """Fetch a single patient by patient_id."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getPatientById", {"patientId": patient_id})
        if res:
            return to_snake_case(res)

    if USE_LOCAL_JSON:
        return _get_patient_by_id(patient_id)

    if USE_SUPABASE:
        try:
            result = get_client().table("patients").select("*").eq("patient_id", patient_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[DB] get_patient_by_id error: {e}")
            return None
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"[SQLite] get_patient_by_id error: {e}")
            return None
        finally:
            conn.close()


def get_patient_by_mobile(mobile: str) -> dict | None:
    """Fetch the most recent patient by mobile number."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getPatientByMobile", {"mobile": mobile})
        if res:
            return to_snake_case(res)

    if USE_LOCAL_JSON:
        return _get_patient_by_mobile(mobile)

    if USE_SUPABASE:
        try:
            result = (get_client().table("patients")
                      .select("*")
                      .eq("mobile", mobile)
                      .order("created_at", desc=True)
                      .limit(1)
                      .execute())
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[DB] get_patient_by_mobile error: {e}")
            return None
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM patients WHERE mobile = ? ORDER BY created_at DESC LIMIT 1", (mobile,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            print(f"[SQLite] get_patient_by_mobile error: {e}")
            return None
        finally:
            conn.close()


def get_today_patients() -> list[dict]:
    """Get all patients registered today."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getTodayPatients")
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_today_patients()

    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("patients")
                      .select("*")
                      .eq("registration_date", today)
                      .order("created_at", desc=False)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_today_patients error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM patients WHERE registration_date = ? ORDER BY created_at ASC", (today,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SQLite] get_today_patients error: {e}")
            return []
        finally:
            conn.close()


def get_today_patients_with_tests() -> list[dict]:
    """
    Get all patients registered today, each with their tests nested inside.
    Returns list of dicts with patient fields + 'tests' list.

    Used by CSV export.
    """
    patients = get_today_patients()
    for p in patients:
        p["tests"] = get_tests_for_patient(p["patient_id"])
    return patients


def get_patient_visit_count(mobile: str) -> int:
    """
    Count how many times a patient with this mobile has visited
    (i.e. number of registration records). Used for visit counter badge.
    """
    if not mobile or len(mobile) != 10:
        return 0

    if USE_LOCAL_JSON:
        return _get_patient_visit_count_json(mobile)

    if USE_SUPABASE:
        try:
            result = (get_client().table("patients")
                      .select("patient_id", count="exact")
                      .eq("mobile", mobile)
                      .execute())
            return result.count or 0
        except Exception as e:
            print(f"[DB] get_patient_visit_count error: {e}")
            return 0
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM patients WHERE mobile = ?", (mobile,))
            count = cursor.fetchone()[0]
            return count or 0
        except Exception as e:
            print(f"[SQLite] get_patient_visit_count error: {e}")
            return 0
        finally:
            conn.close()


def get_patient_visits_by_mobile(mobile: str) -> list[dict]:
    """
    Fetch ALL patient records (all visits) for a mobile number,
    ordered most recent first. Returns empty list if none found.

    Used by Patient History page — shows every past visit.
    """
    if not mobile or len(mobile) != 10:
        return []

    if USE_LOCAL_JSON:
        return _get_patient_visits_by_mobile_json(mobile)

    if USE_SUPABASE:
        try:
            result = (get_client().table("patients")
                      .select("*")
                      .eq("mobile", mobile)
                      .order("registration_date", desc=True)
                      .order("created_at", desc=True)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_patient_visits_by_mobile error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT * FROM patients WHERE mobile = ? ORDER BY registration_date DESC, created_at DESC",
                (mobile,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SQLite] get_patient_visits_by_mobile error: {e}")
            return []
        finally:
            conn.close()


def _get_today_patient_count() -> int:
    """Count today's patients for ID generation."""
    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("patients")
                      .select("patient_id", count="exact")
                      .eq("registration_date", today)
                      .execute())
            return result.count or 0
        except Exception as e:
            print(f"[DB] _get_today_patient_count error: {e}")
            return 0
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT COUNT(*) FROM patients WHERE registration_date = ?", (today,))
            count = cursor.fetchone()[0]
            return count or 0
        except Exception as e:
            print(f"[SQLite] _get_today_patient_count error: {e}")
            return 0
        finally:
            conn.close()


# ─── TESTS ───────────────────────────────────────────────────────────────────

def create_test(patient_id: str, test_name: str, room: str) -> dict | None:
    """
    Create a test record for a patient.
    Auto-assigns the next daily token number for this test type.
    """
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("createTest", {"patientId": patient_id, "testName": test_name}, is_post=True)
        if res:
            return to_snake_case(res)

    if USE_LOCAL_JSON:
        return _create_test(patient_id, test_name, room)

    token = _get_next_token(test_name)
    queue_pos = _get_queue_length(test_name) + 1

    if USE_SUPABASE:
        data = {
            "patient_id": patient_id,
            "test_name": test_name,
            "status": "waiting",
            "token_number": token,
            "queue_position": queue_pos,
            "room": room,
        }
        try:
            result = get_client().table("tests").insert(data).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[DB] create_test error: {e}")
            return None
    else:
        test_uuid = str(uuid.uuid4())
        now_str = datetime.now().isoformat()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO tests (id, patient_id, test_name, status, token_number, queue_position, room, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (test_uuid, patient_id, test_name, "waiting", token, queue_pos, room, now_str)
            )
            conn.commit()
            return {
                "id": test_uuid,
                "patient_id": patient_id,
                "test_name": test_name,
                "status": "waiting",
                "token_number": token,
                "queue_position": queue_pos,
                "room": room,
                "created_at": now_str
            }
        except Exception as e:
            print(f"[SQLite] create_test error: {e}")
            return None
        finally:
            conn.close()


def get_tests_for_patient(patient_id: str) -> list[dict]:
    """Get all tests for a patient."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getTestsForPatient", {"patientId": patient_id})
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_tests_for_patient(patient_id)

    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("*")
                      .eq("patient_id", patient_id)
                      .order("created_at", desc=False)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_tests_for_patient error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM tests WHERE patient_id = ? ORDER BY created_at ASC", (patient_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SQLite] get_tests_for_patient error: {e}")
            return []
        finally:
            conn.close()


def get_tests_by_mobile(mobile: str) -> list[dict]:
    """Get all tests for a patient by mobile number."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getTestsByMobile", {"mobile": mobile}, is_post=True)
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_tests_by_mobile(mobile)

    patient = get_patient_by_mobile(mobile)
    if not patient:
        return []
    return get_tests_for_patient(patient["patient_id"])


def get_queue(test_name: str, status_filter: str = "waiting") -> list[dict]:
    """
    Get the queue for a specific test type registered today, ordered by token_number.
    Default returns only 'waiting' items.
    """
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getQueue", {"testName": test_name, "status": status_filter or ""})
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_queue(test_name, status_filter)

    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            query = (get_client().table("tests")
                      .select("*, patients!inner(name, mobile, age, gender, registration_date)")
                      .eq("test_name", test_name)
                      .eq("patients.registration_date", today))
            if status_filter:
                query = query.eq("status", status_filter)
            result = query.order("token_number", desc=False).execute()
            return result.data or []
        except Exception as e:
            print(f"[DB] get_queue error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = """
                SELECT tests.*, 
                       patients.name, patients.mobile, patients.age, patients.gender
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.test_name = ? AND patients.registration_date = ?
            """
            params = [test_name, today]
            if status_filter:
                sql += " AND tests.status = ?"
                params.append(status_filter)
            sql += " ORDER BY tests.token_number ASC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                d = dict(row)
                d["patients"] = {
                    "name": d.pop("name"),
                    "mobile": d.pop("mobile"),
                    "age": d.pop("age"),
                    "gender": d.pop("gender")
                }
                result.append(d)
            return result
        except Exception as e:
            print(f"[SQLite] get_queue error: {e}")
            return []
        finally:
            conn.close()


def update_test_status(test_id: str, new_status: str) -> bool:
    """Update a test's status and set the corresponding timestamp."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("updateTestStatus", {"testId": test_id, "status": new_status}, is_post=True)
        if res and not res.get("error"):
            return True

    if USE_LOCAL_JSON:
        return _update_test_status(test_id, new_status)

    if USE_SUPABASE:
        update_data = {"status": new_status}
        now = datetime.utcnow().isoformat()

        timestamp_map = {
            "called":        "called_at",
            "in_progress":   "started_at",
            "completed":     "completed_at",
            "report_ready":  "report_ready_at",
            "delivered":     "delivered_at",
        }
        if new_status in timestamp_map:
            update_data[timestamp_map[new_status]] = now

        try:
            get_client().table("tests").update(update_data).eq("id", test_id).execute()
            return True
        except Exception as e:
            print(f"[DB] update_test_status error: {e}")
            return False
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        
        timestamp_map = {
            "called":        "called_at",
            "in_progress":   "started_at",
            "completed":     "completed_at",
            "report_ready":  "report_ready_at",
            "delivered":     "delivered_at",
        }
        sql = "UPDATE tests SET status = ?"
        params = [new_status]
        if new_status in timestamp_map:
            sql += f", {timestamp_map[new_status]} = ?"
            params.append(now)
        sql += " WHERE id = ?"
        params.append(test_id)
        
        try:
            cursor.execute(sql, params)
            conn.commit()
            return True
        except Exception as e:
            print(f"[SQLite] update_test_status error: {e}")
            return False
        finally:
            conn.close()


def get_completed_tests() -> list[dict]:
    """Get all tests registered today with status 'completed' (for Doctor dashboard)."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getCompletedTests")
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_completed_tests()

    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("*, patients!inner(name, mobile, registration_date)")
                      .eq("status", "completed")
                      .eq("patients.registration_date", today)
                      .order("completed_at", desc=False)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_completed_tests error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = """
                SELECT tests.*, patients.name, patients.mobile
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.status = 'completed' AND patients.registration_date = ?
                ORDER BY tests.completed_at ASC
            """
            cursor.execute(sql, (today,))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["patients"] = {
                    "name": d.pop("name"),
                    "mobile": d.pop("mobile")
                }
                result.append(d)
            return result
        except Exception as e:
            print(f"[SQLite] get_completed_tests error: {e}")
            return []
        finally:
            conn.close()


def get_report_ready_tests() -> list[dict]:
    """Get all tests registered today with status 'report_ready' (for Doctor dashboard)."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getReportReadyTests")
        if res:
            return to_snake_case(res) or []

    if USE_LOCAL_JSON:
        return _get_report_ready_tests()

    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("*, patients!inner(name, mobile, registration_date)")
                      .eq("status", "report_ready")
                      .eq("patients.registration_date", today)
                      .order("report_ready_at", desc=False)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_report_ready_tests error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = """
                SELECT tests.*, patients.name, patients.mobile
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.status = 'report_ready' AND patients.registration_date = ?
                ORDER BY tests.report_ready_at ASC
            """
            cursor.execute(sql, (today,))
            rows = cursor.fetchall()
            result = []
            for row in rows:
                d = dict(row)
                d["patients"] = {
                    "name": d.pop("name"),
                    "mobile": d.pop("mobile")
                }
                result.append(d)
            return result
        except Exception as e:
            print(f"[SQLite] get_report_ready_tests error: {e}")
            return []
        finally:
            conn.close()


def _get_next_token(test_name: str) -> int:
    """Get the next daily token number for a test type."""
    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("token_number, patients!inner(registration_date)")
                      .eq("test_name", test_name)
                      .eq("patients.registration_date", today)
                      .order("token_number", desc=True)
                      .limit(1)
                      .execute())
            max_token = result.data[0]["token_number"] if result.data else 0
            return max_token + 1
        except Exception as e:
            print(f"[DB] _get_next_token error: {e}")
            return 1
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            sql = """
                SELECT MAX(tests.token_number)
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.test_name = ? AND patients.registration_date = ?
            """
            cursor.execute(sql, (test_name, today))
            val = cursor.fetchone()[0]
            return (val or 0) + 1
        except Exception as e:
            print(f"[SQLite] _get_next_token error: {e}")
            return 1
        finally:
            conn.close()


def _get_queue_length(test_name: str) -> int:
    """Count waiting items in queue for a test type today."""
    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("id, patients!inner(registration_date)", count="exact")
                      .eq("test_name", test_name)
                      .eq("status", "waiting")
                      .eq("patients.registration_date", today)
                      .execute())
            return result.count or 0
        except Exception as e:
            print(f"[DB] _get_queue_length error: {e}")
            return 0
    else:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            sql = """
                SELECT COUNT(*)
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.test_name = ? AND tests.status = 'waiting' AND patients.registration_date = ?
            """
            cursor.execute(sql, (test_name, today))
            count = cursor.fetchone()[0]
            return count or 0
        except Exception as e:
            print(f"[SQLite] _get_queue_length error: {e}")
            return 0
        finally:
            conn.close()


def get_current_patient(test_name: str) -> dict | None:
    """Get the patient currently being served today (called or in_progress)."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getCurrentPatient", {"testName": test_name})
        if res:
            return to_snake_case(res)

    if USE_LOCAL_JSON:
        return _get_current_patient(test_name)

    today = date.today().isoformat()
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("*, patients!inner(name, mobile, age, gender, registration_date)")
                      .eq("test_name", test_name)
                      .eq("patients.registration_date", today)
                      .in_("status", ["called", "in_progress"])
                      .order("called_at", desc=False)
                      .limit(1)
                      .execute())
            return result.data[0] if result.data else None
        except Exception as e:
            print(f"[DB] get_current_patient error: {e}")
            return None
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            sql = """
                SELECT tests.*, 
                       patients.name, patients.mobile, patients.age, patients.gender
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.test_name = ? AND patients.registration_date = ? 
                  AND tests.status IN ('called', 'in_progress')
                ORDER BY tests.called_at ASC
                LIMIT 1
            """
            cursor.execute(sql, (test_name, today))
            row = cursor.fetchone()
            if row:
                d = dict(row)
                d["patients"] = {
                    "name": d.pop("name"),
                    "mobile": d.pop("mobile"),
                    "age": d.pop("age"),
                    "gender": d.pop("gender")
                }
                return d
            return None
        except Exception as e:
            print(f"[SQLite] get_current_patient error: {e}")
            return None
        finally:
            conn.close()


# ─── MESSAGES ────────────────────────────────────────────────────────────────

def log_message(patient_id: str, mobile: str, msg_type: str, text: str,
                sent_via: str = "none", actor: str = ""):
    """Log a sent notification to the messages table."""
    if USE_GOOGLE_SHEETS:
        return

    if USE_LOCAL_JSON:
        return _log_message(patient_id, mobile, msg_type, text, sent_via, actor)

    if USE_SUPABASE:
        data = {
            "patient_id": patient_id,
            "mobile": mobile,
            "message_type": msg_type,
            "message_text": text,
            "sent_via": sent_via,
            "actor": actor,
        }
        try:
            get_client().table("messages").insert(data).execute()
        except Exception as e:
            print(f"[DB] log_message error: {e}")
    else:
        msg_uuid = str(uuid.uuid4())
        now_str = datetime.now().isoformat()
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            cursor.execute(
                """INSERT INTO messages (id, patient_id, mobile, message_type, message_text, sent_via, sent_at, actor)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (msg_uuid, patient_id, mobile, msg_type, text, sent_via, now_str, actor))
            conn.commit()
        except Exception as e:
            print(f"[SQLite] log_message error: {e}")
        finally:
            conn.close()


def get_recent_activity(limit: int = 50) -> list[dict]:
    """
    Get the most recent activity log entries (messages table).
    Joins with patients for name. Returns newest first.
    Used by Manager and Admin activity feed.
    """
    if USE_LOCAL_JSON:
        return _get_recent_activity_json(limit)

    if USE_SUPABASE:
        try:
            result = (get_client().table("messages")
                      .select("*, patients!inner(name)")
                      .order("sent_at", desc=True)
                      .limit(limit)
                      .execute())
            return result.data or []
        except Exception as e:
            print(f"[DB] get_recent_activity error: {e}")
            return []
    else:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute(f"""
                SELECT m.id, m.patient_id, m.mobile, m.message_type,
                       m.message_text, m.sent_via, m.sent_at, m.actor,
                       p.name as patient_name
                FROM messages m
                LEFT JOIN patients p ON m.patient_id = p.patient_id
                ORDER BY m.sent_at DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            print(f"[SQLite] get_recent_activity error: {e}")
            return []
        finally:
            conn.close()


# ─── DASHBOARD STATS ─────────────────────────────────────────────────────────

# ─── USERS (Password Management) ────────────────────────────────────────────

def create_user(username: str, display_name: str, role: str, password: str) -> dict | None:
    """Create a new staff user account."""
    user_uuid = str(uuid.uuid4())
    now_str = datetime.now().isoformat()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (id, username, display_name, role, password, active, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            (user_uuid, username, display_name, role, password, now_str)
        )
        conn.commit()
        return {
            "id": user_uuid,
            "username": username,
            "display_name": display_name,
            "role": role,
            "active": 1,
            "created_at": now_str
        }
    except sqlite3.IntegrityError:
        return None  # Username already exists
    except Exception as e:
        print(f"[SQLite] create_user error: {e}")
        return None
    finally:
        conn.close()


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate a staff user. Returns user dict if valid, None otherwise."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,)
        )
        row = cursor.fetchone()
        if row and row["password"] == password:
            return dict(row)
        return None
    except Exception as e:
        print(f"[SQLite] authenticate_user error: {e}")
        return None
    finally:
        conn.close()


def verify_login(username: str, password: str) -> dict | None:
    """
    Authenticate a staff user. Supports both text passwords and numeric PINs (4-6 digits).
    Returns user dict if valid, None otherwise.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE username = ? AND active = 1",
            (username,)
        )
        row = cursor.fetchone()
        if row and row["password"] == password:
            return dict(row)
        return None
    except Exception as e:
        print(f"[SQLite] verify_login error: {e}")
        return None
    finally:
        conn.close()


def get_all_users() -> list[dict]:
    """Get all staff user accounts."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users ORDER BY role, username ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[SQLite] get_all_users error: {e}")
        return []
    finally:
        conn.close()


def get_user_by_username(username: str) -> dict | None:
    """Get a single user by username."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"[SQLite] get_user_by_username error: {e}")
        return None
    finally:
        conn.close()


def update_user_password(username: str, new_password: str) -> bool:
    """Update a user's password."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (new_password, username)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[SQLite] update_user_password error: {e}")
        return False
    finally:
        conn.close()


def update_user_to_pin(username: str, new_pin: str) -> bool:
    """Convert a user's password to a numeric PIN (4-6 digits)."""
    if not new_pin.isdigit() or len(new_pin) < 4 or len(new_pin) > 6:
        return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET password = ? WHERE username = ?",
            (new_pin, username)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[SQLite] update_user_to_pin error: {e}")
        return False
    finally:
        conn.close()


def delete_user(username: str) -> bool:
    """Delete (deactivate) a user account."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET active = 0 WHERE username = ?",
            (username,)
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[SQLite] delete_user error: {e}")
        return False
    finally:
        conn.close()


def get_all_active_users() -> list[dict]:
    """Get all active (non-deleted) user accounts."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM users WHERE active = 1 ORDER BY role, display_name ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[SQLite] get_all_active_users error: {e}")
        return []
    finally:
        conn.close()


def get_users_by_role(role: str) -> list[dict]:
    """Get all active users for a given role."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM users WHERE role = ? AND active = 1 ORDER BY username ASC",
            (role,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"[SQLite] get_users_by_role error: {e}")
        return []
    finally:
        conn.close()


def get_department_stats(test_name: str) -> dict:
    """Get counts for each status for a given test type (today only)."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getDepartmentStats", {"testName": test_name})
        if res:
            return to_snake_case(res) or {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}

    if USE_LOCAL_JSON:
        return _get_department_stats(test_name)

    today = date.today().isoformat()
    stats = {}
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("status, patients!inner(registration_date)")
                      .eq("test_name", test_name)
                      .eq("patients.registration_date", today)
                      .execute())
            all_tests = result.data or []
            for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]:
                stats[s] = sum(1 for t in all_tests if t["status"] == s)
        except Exception as e:
            print(f"[DB] get_department_stats error: {e}")
            for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]:
                stats[s] = 0
    else:
        stats = {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            sql = """
                SELECT tests.status, COUNT(*)
                FROM tests
                JOIN patients ON tests.patient_id = patients.patient_id
                WHERE tests.test_name = ? AND patients.registration_date = ?
                GROUP BY tests.status
            """
            cursor.execute(sql, (test_name, today))
            rows = cursor.fetchall()
            for row in rows:
                status, count = row
                if status in stats:
                    stats[status] = count
            return stats
        except Exception as e:
            print(f"[SQLite] get_department_stats error: {e}")
            return stats
        finally:
            conn.close()
    return stats


# ─── PATIENT ALERT SYSTEM (DB-Poll Push) ───────────────────────────────────────────────────

def set_patient_alert(patient_id: str, message: str = "") -> bool:
    """
    Set pending_alert=1 for a patient so their status page plays sound on next refresh.
    Works across all DB modes: Google Sheets, Local JSON, Supabase, SQLite.
    Architecture: Staff presses Remind → this writes to DB → Patient's 5s refresh detects it.
    """
    # ─── Google Sheets ────────────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("setPatientAlert", {"patientId": patient_id, "message": message}, is_post=True)
        if res is not None:
            return True
        # Fall through to Local JSON on GS failure

    # ─── Local JSON ───────────────────────────────────────────────────────────────────
    if USE_LOCAL_JSON:
        return _set_patient_alert_json(patient_id, message)

    # ─── Supabase ─────────────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            get_client().table("tests").update(
                {"pending_alert": 1, "alert_message": message}
            ).eq("patient_id", patient_id).execute()
            return True
        except Exception as e:
            print(f"[DB] set_patient_alert (Supabase) error: {e}")
            return False

    # ─── SQLite ─────────────────────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "UPDATE tests SET pending_alert=1, alert_message=? WHERE patient_id=?",
            (message, patient_id)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[SQLite] set_patient_alert error: {e}")
        return False
    finally:
        conn.close()


def get_patient_alert(patient_id: str) -> dict:
    """
    Check if patient has a pending staff alert.
    Returns: {"has_alert": bool, "message": str}
    Called by Patient_Status.py on every 5s refresh.
    """
    # ─── Google Sheets ────────────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getPatientAlert", {"patientId": patient_id})
        if res is not None:
            return {"has_alert": res.get("pendingAlert", 0) == 1, "message": res.get("alertMessage", "")}

    # ─── Local JSON ───────────────────────────────────────────────────────────────────
    if USE_LOCAL_JSON:
        return _get_patient_alert_json(patient_id)

    # ─── Supabase ─────────────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            result = (get_client().table("tests")
                      .select("pending_alert, alert_message")
                      .eq("patient_id", patient_id)
                      .eq("pending_alert", 1)
                      .limit(1)
                      .execute())
            if result.data:
                return {"has_alert": True, "message": result.data[0].get("alert_message", "")}
            return {"has_alert": False, "message": ""}
        except Exception as e:
            print(f"[DB] get_patient_alert (Supabase) error: {e}")
            return {"has_alert": False, "message": ""}

    # ─── SQLite ─────────────────────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT pending_alert, alert_message FROM tests WHERE patient_id=? AND pending_alert=1 LIMIT 1",
            (patient_id,)
        )
        row = cursor.fetchone()
        if row:
            return {"has_alert": True, "message": row["alert_message"] or ""}
        return {"has_alert": False, "message": ""}
    except Exception as e:
        print(f"[SQLite] get_patient_alert error: {e}")
        return {"has_alert": False, "message": ""}
    finally:
        conn.close()


def clear_patient_alert(patient_id: str) -> bool:
    """
    Clear the pending alert after patient's page has shown it.
    Called immediately after get_patient_alert() returns has_alert=True.
    """
    # ─── Google Sheets ────────────────────────────────────────────────────────────────
    if USE_GOOGLE_SHEETS and not _gs_failed:
        call_gs_api("clearPatientAlert", {"patientId": patient_id}, is_post=True)
        return True

    # ─── Local JSON ───────────────────────────────────────────────────────────────────
    if USE_LOCAL_JSON:
        return _clear_patient_alert_json(patient_id)

    # ─── Supabase ─────────────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            get_client().table("tests").update(
                {"pending_alert": 0, "alert_message": ""}
            ).eq("patient_id", patient_id).execute()
            return True
        except Exception as e:
            print(f"[DB] clear_patient_alert (Supabase) error: {e}")
            return False

    # ─── SQLite ─────────────────────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(
            "UPDATE tests SET pending_alert=0, alert_message='' WHERE patient_id=?",
            (patient_id,)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"[SQLite] clear_patient_alert error: {e}")
        return False
    finally:
        conn.close()


# ─── PATIENT INQUIRIES (Help/Time requests to Reception) ──────────────────────

def set_patient_inquiry(patient_id: str, message: str) -> bool:
    """Set a pending inquiry request from a patient for the reception desk."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        # Fallback for GS (just log or return True)
        return True

    if USE_LOCAL_JSON:
        try:
            from utils.local_json_db import set_patient_inquiry_json
            return set_patient_inquiry_json(patient_id, message)
        except Exception:
            return True

    if USE_SUPABASE:
        try:
            get_client().table("patients").update({"reception_inquiry": message}).eq("patient_id", patient_id).execute()
            return True
        except Exception as e:
            print(f"[DB] set_patient_inquiry (Supabase) error: {e}")
            return False

    # SQLite
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("UPDATE patients SET reception_inquiry=? WHERE patient_id=?", (message, patient_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[SQLite] set_patient_inquiry error: {e}")
        return False
    finally:
        conn.close()


def get_patient_inquiry(patient_id: str) -> str | None:
    """Get the active inquiry request for a patient."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        return None

    if USE_LOCAL_JSON:
        try:
            from utils.local_json_db import get_patient_inquiry_json
            return get_patient_inquiry_json(patient_id)
        except Exception:
            return None

    if USE_SUPABASE:
        try:
            res = get_client().table("patients").select("reception_inquiry").eq("patient_id", patient_id).limit(1).execute()
            return res.data[0].get("reception_inquiry") if res.data else None
        except Exception as e:
            print(f"[DB] get_patient_inquiry (Supabase) error: {e}")
            return None

    # SQLite
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT reception_inquiry FROM patients WHERE patient_id=?", (patient_id,))
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"[SQLite] get_patient_inquiry error: {e}")
        return None
    finally:
        conn.close()


def clear_patient_inquiry(patient_id: str) -> bool:
    """Clear/dismiss a patient's pending inquiry."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        return True

    if USE_LOCAL_JSON:
        try:
            from utils.local_json_db import clear_patient_inquiry_json
            return clear_patient_inquiry_json(patient_id)
        except Exception:
            return True

    if USE_SUPABASE:
        try:
            get_client().table("patients").update({"reception_inquiry": None}).eq("patient_id", patient_id).execute()
            return True
        except Exception as e:
            print(f"[DB] clear_patient_inquiry (Supabase) error: {e}")
            return False

    # SQLite
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute("UPDATE patients SET reception_inquiry=NULL WHERE patient_id=?", (patient_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"[SQLite] clear_patient_inquiry error: {e}")
        return False
    finally:
        conn.close()


# ─── DEPARTMENTS (BRICK 6 — Dynamic Department Management) ───────────────────

_DEFAULT_DEPARTMENTS = [
    {"name": "ECG",    "display_name": "ECG",    "room": "ECG Room 1",  "avg_time_minutes": 10, "icon": "❤️",  "active": 1, "sort_order": 1},
    {"name": "Echo",   "display_name": "Echo",   "room": "Echo Room 1", "avg_time_minutes": 20, "icon": "🫀",  "active": 1, "sort_order": 2},
    {"name": "TMT",    "display_name": "TMT",    "room": "TMT Room 1",  "avg_time_minutes": 30, "icon": "🏃",  "active": 1, "sort_order": 3},
    {"name": "OPD",    "display_name": "OPD",    "room": "OPD Room 1",  "avg_time_minutes": 15, "icon": "🩺",  "active": 1, "sort_order": 4},
    {"name": "Holter", "display_name": "Holter", "room": "ECG Room 1",  "avg_time_minutes": 10, "icon": "📟",  "active": 1, "sort_order": 5},
    {"name": "ABPM",   "display_name": "ABPM",   "room": "ECG Room 1",  "avg_time_minutes": 10, "icon": "💉",  "active": 1, "sort_order": 6},
]


def get_departments(active_only: bool = True) -> list:
    """Return list of department dicts, sorted by sort_order."""
    # ─── Supabase ─────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            q = get_client().table("departments").select("*").order("sort_order")
            if active_only:
                q = q.eq("active", 1)
            res = q.execute()
            return res.data or []
        except Exception as e:
            print(f"[DB] get_departments (Supabase) error: {e}")
            return _DEFAULT_DEPARTMENTS

    # ─── SQLite ───────────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        # Create departments table if missing (migration safety)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            room TEXT NOT NULL DEFAULT '',
            avg_time_minutes INTEGER NOT NULL DEFAULT 15,
            icon TEXT NOT NULL DEFAULT '📋',
            active INTEGER NOT NULL DEFAULT 1,
            sort_order INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )""")
        conn.commit()
        where = "WHERE active=1" if active_only else ""
        cursor.execute(f"SELECT name,display_name,room,avg_time_minutes,icon,active,sort_order FROM departments {where} ORDER BY sort_order")
        rows = cursor.fetchall()
        conn.close()
        if not rows:
            # Seed defaults on first run
            _seed_default_departments()
            return _DEFAULT_DEPARTMENTS
        return [{"name": r[0], "display_name": r[1], "room": r[2],
                 "avg_time_minutes": r[3], "icon": r[4], "active": r[5], "sort_order": r[6]}
                for r in rows]
    except Exception as e:
        print(f"[SQLite] get_departments error: {e}")
        return _DEFAULT_DEPARTMENTS


def _seed_default_departments():
    """Seed default departments into SQLite on first run."""
    try:
        conn = sqlite3.connect(DB_FILE)
        now = datetime.now().isoformat()
        for d in _DEFAULT_DEPARTMENTS:
            conn.execute(
                "INSERT OR IGNORE INTO departments (id,name,display_name,room,avg_time_minutes,icon,active,sort_order,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (str(uuid.uuid4()), d["name"], d["display_name"], d["room"],
                 d["avg_time_minutes"], d["icon"], d["active"], d["sort_order"], now)
            )
        conn.commit()
        conn.close()
        print("[DB] ✅ Seeded default departments.")
    except Exception as e:
        print(f"[SQLite] _seed_default_departments error: {e}")


def add_department(name: str, display_name: str, room: str,
                   avg_time_minutes: int = 15, icon: str = "📋") -> bool:
    """Add a new department (BRICK 6)."""
    now = datetime.now().isoformat()
    # ─── Supabase ─────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            get_client().table("departments").insert({
                "name": name, "display_name": display_name, "room": room,
                "avg_time_minutes": avg_time_minutes, "icon": icon,
                "active": 1, "sort_order": 99,
            }).execute()
            return True
        except Exception as e:
            print(f"[DB] add_department (Supabase) error: {e}")
            return False
    # ─── SQLite ───────────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute(
            "INSERT OR IGNORE INTO departments (id,name,display_name,room,avg_time_minutes,icon,active,sort_order,created_at) VALUES (?,?,?,?,?,?,1,99,?)",
            (str(uuid.uuid4()), name, display_name, room, avg_time_minutes, icon, now)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[SQLite] add_department error: {e}")
        return False


def remove_department(name: str) -> bool:
    """Soft-delete a department (set active=0, BRICK 6)."""
    # ─── Supabase ─────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            get_client().table("departments").update({"active": 0}).eq("name", name).execute()
            return True
        except Exception as e:
            print(f"[DB] remove_department (Supabase) error: {e}")
            return False
    # ─── SQLite ───────────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("UPDATE departments SET active=0 WHERE name=?", (name,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[SQLite] remove_department error: {e}")
        return False


# ─── CLINIC SETTINGS (BRICK 5 — Multi-Tenant SaaS) ───────────────────────────

def get_clinic_settings_db() -> dict | None:
    """
    Load clinic settings from DB.
    Returns None if no row found (so config.py falls back to .env defaults).
    """
    # ─── Supabase ─────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            res = get_client().table("clinic_settings").select("*").eq("clinic_id", "default").limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"[DB] get_clinic_settings_db (Supabase) error: {e}")
        return None
    # ─── SQLite ───────────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS clinic_settings (
            id TEXT PRIMARY KEY,
            clinic_id TEXT UNIQUE NOT NULL DEFAULT 'default',
            clinic_name TEXT NOT NULL DEFAULT 'GIL CLINIC',
            specialty TEXT NOT NULL DEFAULT 'Cardiology',
            logo_emoji TEXT NOT NULL DEFAULT '🏥',
            phone TEXT NOT NULL DEFAULT '',
            address TEXT NOT NULL DEFAULT '',
            owner_username TEXT NOT NULL DEFAULT 'admin',
            plan_type TEXT NOT NULL DEFAULT 'basic',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )""")
        conn.commit()
        cursor.execute("SELECT clinic_name,specialty,logo_emoji,phone,address,plan_type FROM clinic_settings WHERE clinic_id='default' LIMIT 1")
        row = cursor.fetchone()
        conn.close()
        if row:
            return {"clinic_name": row[0], "specialty": row[1], "logo_emoji": row[2],
                    "phone": row[3], "address": row[4], "plan_type": row[5]}
    except Exception as e:
        print(f"[SQLite] get_clinic_settings_db error: {e}")
    return None


def save_clinic_settings_db(clinic_name: str, specialty: str, logo_emoji: str,
                             phone: str = "", address: str = "") -> bool:
    """Save clinic settings to DB (BRICK 5 Admin Panel)."""
    now = datetime.now().isoformat()
    # ─── Supabase ─────────────────────────────────────────────────────────────
    if USE_SUPABASE:
        try:
            get_client().table("clinic_settings").upsert({
                "clinic_id": "default",
                "clinic_name": clinic_name,
                "specialty": specialty,
                "logo_emoji": logo_emoji,
                "phone": phone,
                "address": address,
            }).execute()
            return True
        except Exception as e:
            print(f"[DB] save_clinic_settings_db (Supabase) error: {e}")
            return False
    # ─── SQLite ───────────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute("""
            INSERT INTO clinic_settings (id,clinic_id,clinic_name,specialty,logo_emoji,phone,address,owner_username,plan_type,is_active,created_at)
            VALUES (?,?,?,?,?,?,?,'admin','basic',1,?)
            ON CONFLICT(clinic_id) DO UPDATE SET
                clinic_name=excluded.clinic_name,
                specialty=excluded.specialty,
                logo_emoji=excluded.logo_emoji,
                phone=excluded.phone,
                address=excluded.address
        """, (str(uuid.uuid4()), "default", clinic_name, specialty, logo_emoji, phone, address, now))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[SQLite] save_clinic_settings_db error: {e}")
        return False
