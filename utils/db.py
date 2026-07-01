"""
Database module — all Supabase CRUD operations for CardioQueue.
Centralizes every database call so pages never touch Supabase directly.
"""
from datetime import date, datetime
from supabase import create_client, Client
from utils.config import SUPABASE_URL, SUPABASE_KEY

_supabase: Client | None = None


def get_client() -> Client:
    """Lazy-init singleton Supabase client."""
    global _supabase
    if _supabase is None:
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ─── PATIENTS ────────────────────────────────────────────────────────────────

def create_patient(name: str, mobile: str, age: int, gender: str) -> dict | None:
    """
    Insert a new patient record.
    Returns the created patient dict or None on failure.
    """
    today = date.today().isoformat()
    # Generate patient ID: CQ-YYYYMMDD-XXX (sequential daily)
    count = _get_today_patient_count()
    patient_id = f"CQ-{today.replace('-', '')}-{count + 1:03d}"

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


def get_patient_by_id(patient_id: str) -> dict | None:
    """Fetch a single patient by patient_id."""
    try:
        result = get_client().table("patients").select("*").eq("patient_id", patient_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB] get_patient_by_id error: {e}")
        return None


def get_patient_by_mobile(mobile: str) -> dict | None:
    """Fetch the most recent patient by mobile number."""
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


def get_today_patients() -> list[dict]:
    """Get all patients registered today."""
    today = date.today().isoformat()
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


def _get_today_patient_count() -> int:
    """Count today's patients for ID generation."""
    today = date.today().isoformat()
    try:
        result = (get_client().table("patients")
                  .select("patient_id", count="exact")
                  .eq("registration_date", today)
                  .execute())
        return result.count or 0
    except Exception as e:
        print(f"[DB] _get_today_patient_count error: {e}")
        return 0


# ─── TESTS ───────────────────────────────────────────────────────────────────

def create_test(patient_id: str, test_name: str, room: str) -> dict | None:
    """
    Create a test record for a patient.
    Auto-assigns the next daily token number for this test type.
    """
    token = _get_next_token(test_name)
    data = {
        "patient_id": patient_id,
        "test_name": test_name,
        "status": "waiting",
        "token_number": token,
        "queue_position": _get_queue_length(test_name) + 1,
        "room": room,
    }
    try:
        result = get_client().table("tests").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB] create_test error: {e}")
        return None


def get_tests_for_patient(patient_id: str) -> list[dict]:
    """Get all tests for a patient."""
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


def get_tests_by_mobile(mobile: str) -> list[dict]:
    """Get all tests for a patient by mobile number (via join-like fetch)."""
    patient = get_patient_by_mobile(mobile)
    if not patient:
        return []
    return get_tests_for_patient(patient["patient_id"])


def get_queue(test_name: str, status_filter: str = "waiting") -> list[dict]:
    """
    Get the queue for a specific test type, ordered by token_number.
    Default returns only 'waiting' items.
    """
    try:
        query = (get_client().table("tests")
                  .select("*, patients!inner(name, mobile, age, gender)")
                  .eq("test_name", test_name))
        if status_filter:
            query = query.eq("status", status_filter)
        result = query.order("token_number", desc=False).execute()
        return result.data or []
    except Exception as e:
        print(f"[DB] get_queue error: {e}")
        return []


def update_test_status(test_id: str, new_status: str) -> bool:
    """Update a test's status and set the corresponding timestamp."""
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


def get_completed_tests() -> list[dict]:
    """Get all tests with status 'completed' (for Doctor dashboard)."""
    try:
        result = (get_client().table("tests")
                  .select("*, patients!inner(name, mobile)")
                  .eq("status", "completed")
                  .order("completed_at", desc=False)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"[DB] get_completed_tests error: {e}")
        return []


def get_report_ready_tests() -> list[dict]:
    """Get all tests with status 'report_ready' (for Doctor dashboard)."""
    try:
        result = (get_client().table("tests")
                  .select("*, patients!inner(name, mobile)")
                  .eq("status", "report_ready")
                  .order("report_ready_at", desc=False)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"[DB] get_report_ready_tests error: {e}")
        return []


def _get_next_token(test_name: str) -> int:
    """Get the next daily token number for a test type."""
    today = date.today().isoformat()
    try:
        # We need to find the max token for today for this test type
        # Join with patients to filter by today's registration
        result = (get_client().table("tests")
                  .select("token_number")
                  .eq("test_name", test_name)
                  .order("token_number", desc=True)
                  .limit(1)
                  .execute())
        max_token = result.data[0]["token_number"] if result.data else 0
        return max_token + 1
    except Exception:
        return 1


def _get_queue_length(test_name: str) -> int:
    """Count waiting items in queue for a test type."""
    try:
        result = (get_client().table("tests")
                  .select("id", count="exact")
                  .eq("test_name", test_name)
                  .eq("status", "waiting")
                  .execute())
        return result.count or 0
    except Exception:
        return 0


def get_current_patient(test_name: str) -> dict | None:
    """Get the patient currently being served (called or in_progress)."""
    try:
        result = (get_client().table("tests")
                  .select("*, patients!inner(name, mobile, age, gender)")
                  .eq("test_name", test_name)
                  .in_("status", ["called", "in_progress"])
                  .order("called_at", desc=False)
                  .limit(1)
                  .execute())
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB] get_current_patient error: {e}")
        return None


# ─── MESSAGES ────────────────────────────────────────────────────────────────

def log_message(patient_id: str, mobile: str, msg_type: str, text: str, sent_via: str = "none"):
    """Log a sent notification to the messages table."""
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


# ─── DASHBOARD STATS ─────────────────────────────────────────────────────────

def get_department_stats(test_name: str) -> dict:
    """Get counts for each status for a given test type (today only)."""
    today = date.today().isoformat()
    stats = {}
    try:
        # Get all tests for today matching this test_name
        result = (get_client().table("tests")
                  .select("status")
                  .eq("test_name", test_name)
                  .execute())
        all_tests = result.data or []
        for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]:
            stats[s] = sum(1 for t in all_tests if t["status"] == s)
    except Exception as e:
        print(f"[DB] get_department_stats error: {e}")
        for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]:
            stats[s] = 0
    return stats
