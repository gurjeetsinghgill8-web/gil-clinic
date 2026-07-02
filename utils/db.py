"""
Database module — Dual database support (SQLite + Supabase) for CardioQueue.
If Supabase URL and Key are left as defaults or empty, it automatically falls back
to a local SQLite database (cardioqueue.db) in the project directory.
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
_gs_failed = False  # Marks if GS API has failed — triggers SQLite fallback

def call_gs_api(action: str, params: dict = None, is_post: bool = False):
    global _gs_failed
    if _gs_failed:
        return None  # Already failed once — skip retries, use SQLite
    if params is None:
        params = {}
    params["action"] = action
    try:
        if is_post:
            r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)
            # Some GS web apps don't handle POST well — fallback to GET if POST fails
            if r.status_code != 200:
                r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)
        else:
            r = requests.get(GOOGLE_SCRIPT_URL, params=params, timeout=10)

        if r.status_code == 200:
            return r.json()
        else:
            print(f"[GoogleSheets] API Error: {r.status_code} - {r.text[:200]}")
            _gs_failed = True
            return None
    except Exception as e:
        print(f"[GoogleSheets] Exception calling API: {e}")
        _gs_failed = True
        return None

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
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
    )
    """)
    
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
        FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
    )
    """)
    
    conn.commit()
    conn.close()

# Detect and configure database connection
if (
    SUPABASE_URL 
    and SUPABASE_KEY 
    and "your-project-id" not in SUPABASE_URL 
    and "your-supabase-anon" not in SUPABASE_KEY
    and SUPABASE_URL.strip() != ""
    and SUPABASE_KEY.strip() != ""
):
    try:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        USE_SUPABASE = True
        print("[DB] Configured to run on Supabase Cloud database.")
    except Exception as e:
        print(f"[DB] Error connecting to Supabase: {e}. Falling back to SQLite.")
        USE_SUPABASE = False
else:
    print("[DB] Supabase credentials not set or left as default. Using local SQLite database.")
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
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("createPatient", {"name": name, "mobile": mobile, "age": age, "gender": gender}, is_post=True)
        if res:
            return to_snake_case(res)
        # Fall through to SQLite if Google Sheets fails

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

def log_message(patient_id: str, mobile: str, msg_type: str, text: str, sent_via: str = "none"):
    """Log a sent notification to the messages table."""
    if USE_GOOGLE_SHEETS:
        return

    if USE_SUPABASE:
        data = {
            "patient_id": patient_id,
            "mobile": mobile,
            "message_type": msg_type,
            "message_text": text,
            "sent_via": sent_via,
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
                """INSERT INTO messages (id, patient_id, mobile, message_type, message_text, sent_via, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (msg_uuid, patient_id, mobile, msg_type, text, sent_via, now_str)
            )
            conn.commit()
        except Exception as e:
            print(f"[SQLite] log_message error: {e}")
        finally:
            conn.close()


# ─── DASHBOARD STATS ─────────────────────────────────────────────────────────

def get_department_stats(test_name: str) -> dict:
    """Get counts for each status for a given test type (today only)."""
    if USE_GOOGLE_SHEETS and not _gs_failed:
        res = call_gs_api("getDepartmentStats", {"testName": test_name})
        if res:
            return to_snake_case(res) or {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}

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
