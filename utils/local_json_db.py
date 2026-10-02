"""
Local JSON File Storage — Drop-in replacement for SQLite
==========================================================
Stores all patient & test data as human-readable JSON files
in date-stamped folders. No database setup needed.

Folder structure:
  cardioqueue_data/
    ├── 2026-07-02/
    │   ├── patients.json           # All patients registered today
    │   ├── tests_{patient_id}.json  # Tests for each patient
    │   └── counters.json            # Token counters per test type
    ├── 2026-07-03/
    │   └── ...
    └── meta.json                    # All-time references

Each patient has a sequential numeric ID per day:
  CQ-20260702-001, CQ-20260702-002, ...
"""
import json
import os
import uuid
from datetime import date, datetime
from typing import Optional

DATA_DIR = "cardioqueue_data"


def _today_dir() -> str:
    """Get today's date-stamped folder path, create if missing."""
    d = date.today().isoformat()  # 2026-07-02
    path = os.path.join(DATA_DIR, d)
    os.makedirs(path, exist_ok=True)
    return path


def _today_str() -> str:
    return date.today().isoformat()


def _now_str() -> str:
    return datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENTS
# ═══════════════════════════════════════════════════════════════════════════════

def _patients_path() -> str:
    return os.path.join(_today_dir(), "patients.json")


def _load_patients() -> list[dict]:
    path = _patients_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_patients(patients: list[dict]):
    with open(_patients_path(), "w", encoding="utf-8") as f:
        json.dump(patients, f, indent=2, ensure_ascii=False)


def create_patient_json(name: str, mobile: str, age: int, gender: str) -> Optional[dict]:
    """Create a new patient record in today's JSON file.
    Returns the patient dict or None on failure."""
    patients = _load_patients()
    today = _today_str()
    now = _now_str()

    # Generate sequential patient ID
    count = len(patients)
    patient_id = f"CQ-{today.replace('-', '')}-{count + 1:03d}"

    patient = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "name": name,
        "mobile": mobile,
        "age": age,
        "gender": gender,
        "registration_date": today,
        "created_at": now
    }
    patients.append(patient)
    _save_patients(patients)
    return patient


def get_patient_by_id_json(patient_id: str) -> Optional[dict]:
    """Fetch a patient by patient_id across all date folders."""
    # Check today first
    for p in _load_patients():
        if p["patient_id"] == patient_id:
            return p
    # Check previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p["patient_id"] == patient_id:
                            return p
    return None


def get_patient_by_mobile_json(mobile: str) -> Optional[dict]:
    """Fetch the most recent patient by mobile number."""
    # Check all date folders newest first
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in reversed(patients):
                        if p["mobile"] == mobile:
                            return p
    return None


def get_today_patients_json() -> list[dict]:
    """Get all patients registered today."""
    return _load_patients()


def _get_patient_visit_count_json(mobile: str) -> int:
    """Count how many times a mobile number appears across all date folders."""
    count = 0
    if not mobile or len(mobile) != 10:
        return 0
    # Check today
    today_patients = _load_patients()
    for p in today_patients:
        if p.get("mobile") == mobile:
            count += 1
    # Check previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p.get("mobile") == mobile:
                            count += 1
    return count


def _get_patient_visits_by_mobile_json(mobile: str) -> list[dict]:
    """Fetch ALL patient records (all visits) for a mobile across all date folders."""
    results = []
    if not mobile or len(mobile) != 10:
        return results
    # Check today first
    today_patients = _load_patients()
    for p in today_patients:
        if p.get("mobile") == mobile:
            results.append(p)
    # Check previous days (newest first)
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    patients = json.load(f)
                    for p in patients:
                        if p.get("mobile") == mobile:
                            results.append(p)
    # Sort by registration_date DESC, created_at DESC
    results.sort(key=lambda x: (x.get("registration_date", ""), x.get("created_at", "")), reverse=True)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def _tests_path(patient_id: str) -> str:
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    return os.path.join(_today_dir(), f"tests_{safe_id}.json")


def _all_tests_files(day_dir: str = None) -> list[str]:
    """Get all tests_*.json files in a directory."""
    dir_path = day_dir or _today_dir()
    if not os.path.exists(dir_path):
        return []
    return sorted(
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.startswith("tests_") and f.endswith(".json")
    )


def _load_tests_for_patient(patient_id: str) -> list[dict]:
    path = _tests_path(patient_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_tests_for_patient(patient_id: str, tests: list[dict]):
    with open(_tests_path(patient_id), "w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2, ensure_ascii=False)


# ─── Counter for token numbers ───────────────────────────────────────────────

def _counters_path() -> str:
    return os.path.join(_today_dir(), "counters.json")


def _get_next_token(test_name: str) -> int:
    path = _counters_path()
    counters = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            counters = json.load(f)
    next_token = counters.get(test_name, 0) + 1
    counters[test_name] = next_token
    with open(path, "w", encoding="utf-8") as f:
        json.dump(counters, f, indent=2)
    return next_token


def create_test_json(patient_id: str, test_name: str, room: str) -> Optional[dict]:
    """Create a test record for a patient."""
    tests = _load_tests_for_patient(patient_id)
    now = _now_str()
    token = _get_next_token(test_name)
    queue_pos = len(tests) + 1

    test = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "test_name": test_name,
        "status": "waiting",
        "token_number": token,
        "queue_position": queue_pos,
        "room": room,
        "called_at": None,
        "started_at": None,
        "completed_at": None,
        "report_ready_at": None,
        "delivered_at": None,
        "created_at": now
    }
    tests.append(test)
    _save_tests_for_patient(patient_id, tests)
    return test


def get_tests_for_patient_json(patient_id: str) -> list[dict]:
    """Get all tests for a patient."""
    return _load_tests_for_patient(patient_id)


def get_tests_by_mobile_json(mobile: str) -> list[dict]:
    """Get all tests for a patient by mobile number."""
    patient = get_patient_by_mobile_json(mobile)
    if not patient:
        return []
    return get_tests_for_patient_json(patient["patient_id"])


def get_queue_json(test_name: str, status_filter: str = "waiting") -> list[dict]:
    """Get the queue for a test type today, joined with patient info."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}

    # Collect all tests from today
    all_tests = []
    for f in _all_tests_files():
        with open(f, "r", encoding="utf-8") as fh:
            all_tests.extend(json.load(fh))

    # Filter by test_name and status
    filtered = []
    for t in all_tests:
        if t["test_name"] != test_name:
            continue
        if status_filter and t["status"] != status_filter:
            continue
        p = patient_map.get(t["patient_id"])
        if p:
            t["patients"] = {
                "name": p["name"],
                "mobile": p["mobile"],
                "age": p["age"],
                "gender": p["gender"]
            }
            filtered.append(t)

    filtered.sort(key=lambda x: x["token_number"])
    return filtered


def update_test_status_json(test_id: str, new_status: str) -> bool:
    """Update a test's status and set the corresponding timestamp."""
    now = _now_str()
    timestamp_map = {
        "called":       "called_at",
        "in_progress":  "started_at",
        "completed":    "completed_at",
        "report_ready": "report_ready_at",
        "delivered":    "delivered_at",
    }

    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        updated = False
        for t in tests:
            if t["id"] == test_id:
                t["status"] = new_status
                if new_status in timestamp_map:
                    t[timestamp_map[new_status]] = now
                updated = True
                break
        if updated:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(tests, fh, indent=2, ensure_ascii=False)
            return True
    return False


def _save_test_notes_json(test_id: str, notes: str) -> bool:
    """Save doctor's consultation notes to a test record in JSON."""
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        updated = False
        for t in tests:
            if t["id"] == test_id:
                t["doctor_notes"] = notes
                updated = True
                break
        if updated:
            with open(f, "w", encoding="utf-8") as fh:
                json.dump(tests, fh, indent=2, ensure_ascii=False)
            return True
    return False


def get_completed_tests_json() -> list[dict]:
    """Get all tests registered today with status 'completed'."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}
    results = []
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["status"] == "completed":
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {"name": p["name"], "mobile": p["mobile"]}
                    results.append(t)
    results.sort(key=lambda x: x.get("completed_at") or "")
    return results


def get_report_ready_tests_json() -> list[dict]:
    """Get all tests with status 'report_ready'."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}
    results = []
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["status"] == "report_ready":
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {"name": p["name"], "mobile": p["mobile"]}
                    results.append(t)
    results.sort(key=lambda x: x.get("report_ready_at") or "")
    return results


def get_current_patient_json(test_name: str) -> Optional[dict]:
    """Get the patient currently being served (called or in_progress)."""
    patients = _load_patients()
    patient_map = {p["patient_id"]: p for p in patients}

    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["test_name"] == test_name and t["status"] in ("called", "in_progress"):
                p = patient_map.get(t["patient_id"])
                if p:
                    t["patients"] = {
                        "name": p["name"], "mobile": p["mobile"],
                        "age": p["age"], "gender": p["gender"]
                    }
                    return t
    return None


def get_department_stats_json(test_name: str) -> dict:
    """Get counts for each status for a test type (today only)."""
    stats = {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}
    for f in _all_tests_files():
        tests = json.load(open(f, "r", encoding="utf-8"))
        for t in tests:
            if t["test_name"] == test_name and t["status"] in stats:
                stats[t["status"]] += 1
    return stats


# ═══════════════════════════════════════════════════════════════════════════════════
#  ANALYTICS / AGGREGATION (cross-date, used by Reports & Analytics page)
# ═══════════════════════════════════════════════════════════════════════════════════

def _tests_files_in_range(start_date: str, end_date: str) -> list[str]:
    """Get all tests_*.json files from date folders within [start_date, end_date]."""
    files = []
    if not os.path.exists(DATA_DIR):
        return files
    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        if day < start_date or day > end_date:
            continue
        dir_path = os.path.join(DATA_DIR, day)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if fname.startswith("tests_") and fname.endswith(".json"):
                files.append(os.path.join(dir_path, fname))
    return files


def _patients_files_in_range(start_date: str, end_date: str) -> list[str]:
    """Get patients.json files from date folders within [start_date, end_date]."""
    files = []
    if not os.path.exists(DATA_DIR):
        return files
    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        if day < start_date or day > end_date:
            continue
        pfile = os.path.join(DATA_DIR, day, "patients.json")
        if os.path.exists(pfile):
            files.append(pfile)
    return files


def get_department_stats_date_range_json(test_name: str, start_date: str, end_date: str) -> dict:
    """Get status counts for a test type across a date range (JSON folder iteration)."""
    stats = {s: 0 for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"]}
    for f in _tests_files_in_range(start_date, end_date):
        try:
            tests = json.load(open(f, "r", encoding="utf-8"))
            for t in tests:
                if t.get("test_name") == test_name and t.get("status") in stats:
                    stats[t["status"]] += 1
        except Exception:
            continue
    return stats


def get_daily_patient_counts_json(days: int = 30) -> list[dict]:
    """Get patient counts per day across JSON date folders for the last N days."""
    from datetime import timedelta
    today = date.today()
    start_dt = today - timedelta(days=days - 1)
    start_str = start_dt.isoformat()
    end_str = today.isoformat()

    counts: dict[str, int] = {}
    for pf in _patients_files_in_range(start_str, end_str):
        try:
            patients = json.load(open(pf, "r", encoding="utf-8"))
            for p in patients:
                reg_date = p.get("registration_date", "")
                if start_str <= reg_date <= end_str:
                    counts[reg_date] = counts.get(reg_date, 0) + 1
        except Exception:
            continue

    return [{"date": d, "count": counts[d]} for d in sorted(counts.keys())]


def get_test_duration_stats_json(test_name: str) -> dict:
    """Calculate average durations across ALL dates for a test type (JSON)."""
    from datetime import datetime
    # We need to look at ALL date folders
    totals = {"wait_to_call": 0.0, "wait_to_start": 0.0, "wait_to_complete": 0.0}
    counts_dur = {"wait_to_call": 0, "wait_to_start": 0, "wait_to_complete": 0}

    if not os.path.exists(DATA_DIR):
        return _empty_durations_json()

    for day in sorted(os.listdir(DATA_DIR)):
        if day == "meta.json" or day.startswith("."):
            continue
        dir_path = os.path.join(DATA_DIR, day)
        if not os.path.isdir(dir_path):
            continue
        for fname in sorted(os.listdir(dir_path)):
            if not fname.startswith("tests_") or not fname.endswith(".json"):
                continue
            try:
                tests = json.load(open(os.path.join(dir_path, fname), "r", encoding="utf-8"))
            except Exception:
                continue
            for t in tests:
                if t.get("test_name") != test_name or t.get("status") != "completed":
                    continue
                try:
                    created = datetime.fromisoformat(t["created_at"]) if t.get("created_at") else None
                    called = datetime.fromisoformat(t["called_at"]) if t.get("called_at") else None
                    started = datetime.fromisoformat(t["started_at"]) if t.get("started_at") else None
                    completed = datetime.fromisoformat(t["completed_at"]) if t.get("completed_at") else None
                except Exception:
                    continue
                if created and called:
                    diff = (called - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_call"] += diff
                        counts_dur["wait_to_call"] += 1
                if created and started:
                    diff = (started - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_start"] += diff
                        counts_dur["wait_to_start"] += 1
                if created and completed:
                    diff = (completed - created).total_seconds() / 60
                    if diff >= 0:
                        totals["wait_to_complete"] += diff
                        counts_dur["wait_to_complete"] += 1

    return {
        "avg_wait_to_call": round(totals["wait_to_call"] / counts_dur["wait_to_call"], 1) if counts_dur["wait_to_call"] else 0,
        "avg_wait_to_start": round(totals["wait_to_start"] / counts_dur["wait_to_start"], 1) if counts_dur["wait_to_start"] else 0,
        "avg_wait_to_complete": round(totals["wait_to_complete"] / counts_dur["wait_to_complete"], 1) if counts_dur["wait_to_complete"] else 0,
        "total_completed": counts_dur["wait_to_complete"],
    }


def _empty_durations_json() -> dict:
    return {
        "avg_wait_to_call": 0,
        "avg_wait_to_start": 0,
        "avg_wait_to_complete": 0,
        "total_completed": 0,
    }


def log_message_json(patient_id: str, mobile: str, msg_type: str, text: str,
                     sent_via: str = "none", actor: str = ""):
    """Log a message to today's messages file."""
    msgs_path = os.path.join(_today_dir(), "messages.json")
    msgs = []
    if os.path.exists(msgs_path):
        with open(msgs_path, "r", encoding="utf-8") as f:
            msgs = json.load(f)
    msgs.append({
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "mobile": mobile,
        "message_type": msg_type,
        "message_text": text,
        "sent_via": sent_via,
        "actor": actor,
        "sent_at": _now_str()
    })
    with open(msgs_path, "w", encoding="utf-8") as f:
        json.dump(msgs, f, indent=2, ensure_ascii=False)


def _get_recent_activity_json(limit: int = 50) -> list[dict]:
    """Get recent activity across all date folders (JSON fallback)."""
    all_msgs = []
    # Today first
    msgs_path = os.path.join(_today_dir(), "messages.json")
    if os.path.exists(msgs_path):
        with open(msgs_path, "r", encoding="utf-8") as f:
            all_msgs.extend(json.load(f))
    # Previous days
    if os.path.exists(DATA_DIR):
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            path = os.path.join(DATA_DIR, day, "messages.json")
            if os.path.exists(path) and day != os.path.basename(_today_dir()):
                with open(path, "r", encoding="utf-8") as f:
                    all_msgs.extend(json.load(f))
    # Sort by sent_at DESC, take limit
    all_msgs.sort(key=lambda x: x.get("sent_at", ""), reverse=True)
    # Attach patient name from patients file in same directory
    results = []
    for msg in all_msgs[:limit]:
        pid = msg.get("patient_id", "")
        pname = pid  # fallback
        # Try to find patient name from today's or any patients file
        for day in sorted(os.listdir(DATA_DIR), reverse=True):
            if day == "meta.json" or day.startswith("."):
                continue
            ppath = os.path.join(DATA_DIR, day, "patients.json")
            if os.path.exists(ppath):
                with open(ppath, "r", encoding="utf-8") as f:
                    for p in json.load(f):
                        if p.get("patient_id") == pid:
                            pname = p.get("name", pid)
                            break
                if pname != pid:
                    break
        msg["patient_name"] = pname
        results.append(msg)
    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  PATIENT ALERT SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _alert_path(patient_id: str) -> str:
    """Path to the per-patient alert flag file."""
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    # Store in today's dir — alert is ephemeral (same day)
    return os.path.join(_today_dir(), f"alert_{safe_id}.json")


def _set_patient_alert_json(patient_id: str, message: str = "") -> bool:
    """Write pending_alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        with open(alert_file, "w", encoding="utf-8") as f:
            json.dump({"pending_alert": 1, "alert_message": message, "set_at": _now_str()}, f)
        return True
    except Exception as e:
        print(f"[LocalJSON] _set_patient_alert_json error: {e}")
        return False


def _get_patient_alert_json(patient_id: str) -> dict:
    """Read pending_alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        if os.path.exists(alert_file):
            with open(alert_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("pending_alert") == 1:
                return {"has_alert": True, "message": data.get("alert_message", "")}
        return {"has_alert": False, "message": ""}
    except Exception as e:
        print(f"[LocalJSON] _get_patient_alert_json error: {e}")
        return {"has_alert": False, "message": ""}


def _clear_patient_alert_json(patient_id: str) -> bool:
    """Clear the alert flag for a patient (Local JSON mode)."""
    try:
        alert_file = _alert_path(patient_id)
        if os.path.exists(alert_file):
            os.remove(alert_file)
        return True
    except Exception as e:
        print(f"[LocalJSON] _clear_patient_alert_json error: {e}")
        return False


# ─── PATIENT INQUIRY SYSTEM (for Local JSON mode) ───────────────────────────

def _inquiry_path(patient_id: str) -> str:
    """Path to the per-patient inquiry file."""
    safe_id = patient_id.replace("/", "_").replace("\\", "_")
    return os.path.join(_today_dir(), f"inquiry_{safe_id}.json")


def set_patient_inquiry_json(patient_id: str, message: str) -> bool:
    """Set patient inquiry text (Local JSON mode)."""
    try:
        with open(_inquiry_path(patient_id), "w", encoding="utf-8") as f:
            json.dump({"inquiry": message, "set_at": _now_str()}, f)
        return True
    except Exception as e:
        print(f"[LocalJSON] set_patient_inquiry_json error: {e}")
        return False


def get_patient_inquiry_json(patient_id: str) -> str | None:
    """Get active patient inquiry text (Local JSON mode)."""
    try:
        path = _inquiry_path(patient_id)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("inquiry", None)
        return None
    except Exception as e:
        print(f"[LocalJSON] get_patient_inquiry_json error: {e}")
        return None


def clear_patient_inquiry_json(patient_id: str) -> bool:
    """Clear active patient inquiry (Local JSON mode)."""
    try:
        path = _inquiry_path(patient_id)
        if os.path.exists(path):
            os.remove(path)
        return True
    except Exception as e:
        print(f"[LocalJSON] clear_patient_inquiry_json error: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  FEEDBACK SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _feedback_path() -> str:
    return os.path.join(_today_dir(), "feedback.json")


def _load_feedback() -> list[dict]:
    path = _feedback_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_feedback(feedback: list[dict]):
    with open(_feedback_path(), "w", encoding="utf-8") as f:
        json.dump(feedback, f, indent=2, ensure_ascii=False)


def _feedback_stats_path() -> str:
    return os.path.join(_today_dir(), "feedback_stats.json")


def _load_feedback_stats() -> list[dict]:
    path = _feedback_stats_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_feedback_stats(stats: list[dict]):
    with open(_feedback_stats_path(), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)


def submit_feedback_json(patient_id: str, test_id: str, rating: int,
                         category: str = "general", comments: str = "") -> dict:
    """Submit feedback entry in Local JSON mode."""
    try:
        feedback = _load_feedback()
        entry = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "test_id": test_id,
            "rating": rating,
            "category": category,
            "comments": comments,
            "acknowledged": 0,
            "created_at": _now_str(),
        }
        feedback.append(entry)
        _save_feedback(feedback)
        return {"success": True, "message": "✅ Feedback submitted. Thank you!"}
    except Exception as e:
        print(f"[LocalJSON] submit_feedback_json error: {e}")
        return {"success": False, "message": "❌ Failed to submit feedback."}


def update_feedback_stats_json(test_id: str, rating: int):
    """Update feedback stats for department."""
    try:
        # Get test's department from tests file
        tests = _load_tests()
        dept = ""
        for t in tests:
            if t.get("id") == test_id:
                dept = t.get("test_name", "")
                break
        if not dept:
            # Try reading from per-patient test files
            today = _today_str()
            safe_date = today
            meta_path = os.path.join(DATA_DIR, safe_date)
            if os.path.isdir(meta_path):
                for fname in os.listdir(meta_path):
                    if fname.startswith("tests_") and fname.endswith(".json"):
                        with open(os.path.join(meta_path, fname), "r") as f:
                            test_list = json.load(f)
                            for t in test_list:
                                if t.get("id") == test_id:
                                    dept = t.get("test_name", "")
                                    break
                    if dept:
                        break

        if not dept:
            return

        stats = _load_feedback_stats()
        today_str = _today_str()
        existing = None
        for s in stats:
            if s.get("dept_name") == dept and s.get("stat_date") == today_str:
                existing = s
                break

        if existing:
            total = existing["total_count"]
            avg = existing["avg_rating"]
            new_total = total + 1
            new_avg = round(((avg * total) + rating) / new_total, 1)
            existing["total_count"] = new_total
            existing["avg_rating"] = new_avg
            existing[f"rating_{rating}"] = existing.get(f"rating_{rating}", 0) + 1
        else:
            rating_map = {f"rating_{i}": (1 if i == rating else 0) for i in range(1, 6)}
            stats.append({
                "id": str(uuid.uuid4()),
                "dept_name": dept,
                "stat_date": today_str,
                "total_count": 1,
                "avg_rating": float(rating),
                **rating_map,
            })
        _save_feedback_stats(stats)
    except Exception as e:
        print(f"[LocalJSON] update_feedback_stats_json error: {e}")


def get_feedback_for_test_json(test_id: str) -> dict | None:
    """Get feedback for a specific test."""
    try:
        feedback = _load_feedback()
        for fb in feedback:
            if fb.get("test_id") == test_id:
                return fb
        return None
    except Exception:
        return None


def get_all_feedback_json(limit: int = 50, dept: str = "", min_rating: int = 0) -> list[dict]:
    """Get all feedback entries with filters."""
    try:
        # Collect feedback from all date folders
        all_feedback = []
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                fpath = os.path.join(DATA_DIR, d, "feedback.json")
                if os.path.exists(fpath):
                    with open(fpath, "r") as f:
                        feedback = json.load(f)
                        for fb in feedback:
                            if dept:
                                # Need test_name — try to get it
                                pass
                            if min_rating > 0 and fb.get("rating", 0) < min_rating:
                                continue
                            # Enrich with patient name
                            p_path = os.path.join(DATA_DIR, d, "patients.json")
                            pname = "Unknown"
                            if os.path.exists(p_path):
                                with open(p_path, "r") as pf:
                                    patients = json.load(pf)
                                    for p in patients:
                                        if p.get("patient_id") == fb.get("patient_id"):
                                            pname = p.get("name", "Unknown")
                                            break
                            fb["patient_name"] = pname
                            fb["test_name"] = dept or "—"
                            all_feedback.append(fb)
                        if len(all_feedback) >= limit:
                            break

        return all_feedback[:limit]
    except Exception as e:
        print(f"[LocalJSON] get_all_feedback_json error: {e}")
        return []


def get_feedback_stats_json(start_date: str = "", end_date: str = "") -> list[dict]:
    """Get aggregated feedback stats."""
    try:
        all_stats = []
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                if start_date and d < start_date:
                    continue
                if end_date and d > end_date:
                    continue
                spath = os.path.join(DATA_DIR, d, "feedback_stats.json")
                if os.path.exists(spath):
                    with open(spath, "r") as f:
                        stats = json.load(f)
                        all_stats.extend(stats)

        # Aggregate by dept
        from collections import defaultdict
        agg = defaultdict(lambda: {"total_count": 0, "total_weighted": 0.0,
                                   "rating_1": 0, "rating_2": 0, "rating_3": 0,
                                   "rating_4": 0, "rating_5": 0})
        for s in all_stats:
            dept = s.get("dept_name", "?")
            agg[dept]["total_count"] += s.get("total_count", 0)
            agg[dept]["total_weighted"] += s.get("avg_rating", 0) * s.get("total_count", 0)
            for i in range(1, 6):
                agg[dept][f"rating_{i}"] += s.get(f"rating_{i}", 0)

        result = []
        for dept, data in agg.items():
            result.append({
                "dept_name": dept,
                "total_count": data["total_count"],
                "avg_rating": round(data["total_weighted"] / data["total_count"], 1) if data["total_count"] > 0 else 0.0,
                "rating_1": data["rating_1"],
                "rating_2": data["rating_2"],
                "rating_3": data["rating_3"],
                "rating_4": data["rating_4"],
                "rating_5": data["rating_5"],
            })
        return result
    except Exception as e:
        print(f"[LocalJSON] get_feedback_stats_json error: {e}")
        return []


def acknowledge_feedback_json(feedback_id: str) -> bool:
    """Mark feedback as acknowledged."""
    try:
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                fpath = os.path.join(DATA_DIR, d, "feedback.json")
                if os.path.exists(fpath):
                    with open(fpath, "r") as f:
                        feedback = json.load(f)
                    changed = False
                    for fb in feedback:
                        if fb.get("id") == feedback_id:
                            fb["acknowledged"] = 1
                            changed = True
                            break
                    if changed:
                        with open(fpath, "w", encoding="utf-8") as f:
                            json.dump(feedback, f, indent=2, ensure_ascii=False)
                        return True
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  APPOINTMENTS SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _appointments_path() -> str:
    return os.path.join(_today_dir(), "appointments.json")


def _load_appointments() -> list[dict]:
    path = _appointments_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_appointments(appointments: list[dict]):
    with open(_appointments_path(), "w", encoding="utf-8") as f:
        json.dump(appointments, f, indent=2, ensure_ascii=False)


def _time_slots_path() -> str:
    return os.path.join(DATA_DIR, "time_slots.json")


def _load_time_slots_global() -> list[dict]:
    path = _time_slots_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_time_slots_global(slots: list[dict]):
    with open(_time_slots_path(), "w", encoding="utf-8") as f:
        json.dump(slots, f, indent=2, ensure_ascii=False)


def book_appointment_json(patient_id: str, patient_name: str, mobile: str,
                          test_name: str, appt_date: str, time_slot: str,
                          notes: str = "") -> dict:
    """Book appointment in Local JSON mode."""
    try:
        # Store in the date folder matching the appointment date
        # Use a combined file for all appointments
        appointments = _load_appointments()
        appt = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "test_name": test_name,
            "appointment_date": appt_date,
            "time_slot": time_slot,
            "status": "scheduled",
            "notes": notes,
            "created_at": _now_str(),
            "updated_at": _now_str(),
        }
        appointments.append(appt)
        _save_appointments(appointments)
        return {"success": True, "message": f"✅ Appointment booked for {appt_date} at {time_slot}", "appointment": appt}
    except Exception as e:
        print(f"[LocalJSON] book_appointment_json error: {e}")
        return {"success": False, "message": "❌ Failed to book appointment."}


def get_appointments_for_date_json(appt_date: str, test_name: str = "") -> list[dict]:
    """Get appointments for a specific date."""
    try:
        all_appts = []
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                apath = os.path.join(DATA_DIR, d, "appointments.json")
                if os.path.exists(apath):
                    with open(apath, "r") as f:
                        appts = json.load(f)
                        for a in appts:
                            if a.get("appointment_date") == appt_date:
                                if test_name and a.get("test_name") != test_name:
                                    continue
                                all_appts.append(a)
        return sorted(all_appts, key=lambda x: x.get("time_slot", ""))
    except Exception as e:
        print(f"[LocalJSON] get_appointments_for_date_json error: {e}")
        return []


def get_appointments_for_patient_json(mobile: str) -> list[dict]:
    """Get all appointments for a patient."""
    try:
        all_appts = []
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                apath = os.path.join(DATA_DIR, d, "appointments.json")
                if os.path.exists(apath):
                    with open(apath, "r") as f:
                        appts = json.load(f)
                        for a in appts:
                            if a.get("mobile") == mobile:
                                all_appts.append(a)
        return all_appts
    except Exception:
        return []


def update_appointment_status_json(appt_id: str, new_status: str) -> bool:
    """Update appointment status in Local JSON mode."""
    try:
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                apath = os.path.join(DATA_DIR, d, "appointments.json")
                if os.path.exists(apath):
                    with open(apath, "r") as f:
                        appts = json.load(f)
                    changed = False
                    for a in appts:
                        if a.get("id") == appt_id:
                            a["status"] = new_status
                            a["updated_at"] = _now_str()
                            changed = True
                            break
                    if changed:
                        with open(apath, "w", encoding="utf-8") as f:
                            json.dump(appts, f, indent=2, ensure_ascii=False)
                        return True
        return False
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  BILLING SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _bills_path() -> str:
    return os.path.join(_today_dir(), "bills.json")


def _load_bills() -> list[dict]:
    path = _bills_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_bills(bills: list[dict]):
    with open(_bills_path(), "w", encoding="utf-8") as f:
        json.dump(bills, f, indent=2, ensure_ascii=False)


def _payments_path() -> str:
    return os.path.join(_today_dir(), "payments.json")


def _load_payments() -> list[dict]:
    path = _payments_path()
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_payments(payments: list[dict]):
    with open(_payments_path(), "w", encoding="utf-8") as f:
        json.dump(payments, f, indent=2, ensure_ascii=False)


def _bill_items_json() -> str:
    return os.path.join(DATA_DIR, "bill_items.json")


def _load_bill_items_json() -> list[dict]:
    path = _bill_items_json()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    # Default prices
    items = [
        {"id": str(uuid.uuid4()), "test_name": "ECG", "price": 300, "active": 1},
        {"id": str(uuid.uuid4()), "test_name": "Echo", "price": 1200, "active": 1},
        {"id": str(uuid.uuid4()), "test_name": "TMT", "price": 800, "active": 1},
        {"id": str(uuid.uuid4()), "test_name": "Holter", "price": 1500, "active": 1},
        {"id": str(uuid.uuid4()), "test_name": "ABPM", "price": 1000, "active": 1},
        {"id": str(uuid.uuid4()), "test_name": "OPD", "price": 500, "active": 1},
    ]
    _save_bill_items_json(items)
    return items


def _save_bill_items_json(items: list[dict]):
    with open(_bill_items_json(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def get_test_prices_json() -> dict:
    """Get test prices from Local JSON."""
    items = _load_bill_items_json()
    return {item["test_name"]: item["price"] for item in items if item.get("active")}


def create_bill_json(patient_id: str, patient_name: str, mobile: str,
                     tests: list[dict], discount: float = 0.0,
                     notes: str = "") -> dict:
    """Create a bill in Local JSON mode."""
    try:
        prices = get_test_prices_json()
        total = sum(prices.get(t.get("test_name", ""), 0) for t in tests)
        final = max(0, total - discount)
        invoice_no = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        bills = _load_bills()
        bill = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "invoice_number": invoice_no,
            "total_amount": total,
            "discount": discount,
            "final_amount": final,
            "amount_paid": 0,
            "status": "pending",
            "payment_mode": "",
            "notes": notes,
            "created_at": _now_str(),
        }
        bills.append(bill)
        _save_bills(bills)
        return {"success": True, "message": f"💰 Bill #{invoice_no} created!", "bill": bill}
    except Exception as e:
        print(f"[LocalJSON] create_bill_json error: {e}")
        return {"success": False, "message": "❌ Failed to create bill."}


def record_payment_json(bill_id: str, amount: float, mode: str = "cash",
                        reference_no: str = "") -> dict:
    """Record payment in Local JSON mode."""
    try:
        payments = _load_payments()
        payment = {
            "id": str(uuid.uuid4()),
            "bill_id": bill_id,
            "amount": amount,
            "mode": mode,
            "reference_no": reference_no,
            "paid_at": _now_str(),
        }
        payments.append(payment)
        _save_payments(payments)

        # Update bill
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                bpath = os.path.join(DATA_DIR, d, "bills.json")
                if os.path.exists(bpath):
                    with open(bpath, "r") as f:
                        bills = json.load(f)
                    changed = False
                    for b in bills:
                        if b.get("id") == bill_id:
                            new_paid = b.get("amount_paid", 0) + amount
                            b["amount_paid"] = new_paid
                            if new_paid >= b.get("final_amount", 0):
                                b["status"] = "paid"
                                b["payment_mode"] = mode
                                b["paid_at"] = _now_str()
                                message = f"✅ Bill fully paid! ₹{new_paid:,.2f} received."
                            else:
                                b["payment_mode"] = mode
                                remaining = b["final_amount"] - new_paid
                                message = f"💰 Partial payment recorded. Remaining: ₹{remaining:,.2f}"
                            changed = True
                            break
                    if changed:
                        with open(bpath, "w", encoding="utf-8") as f:
                            json.dump(bills, f, indent=2, ensure_ascii=False)
                        return {"success": True, "message": message}

        return {"success": False, "message": "❌ Bill not found."}
    except Exception as e:
        print(f"[LocalJSON] record_payment_json error: {e}")
        return {"success": False, "message": "❌ Failed to record payment."}


def get_bills_for_patient_json(mobile: str) -> list[dict]:
    """Get bills for a patient by mobile."""
    try:
        all_bills = []
        if os.path.isdir(DATA_DIR):
            for d in sorted(os.listdir(DATA_DIR), reverse=True):
                bpath = os.path.join(DATA_DIR, d, "bills.json")
                if os.path.exists(bpath):
                    with open(bpath, "r") as f:
                        bills = json.load(f)
                        for b in bills:
                            if b.get("mobile") == mobile:
                                all_bills.append(b)
        return all_bills
    except Exception:
        return []


def get_bills_for_date_json(bill_date: str, status: str = "") -> list[dict]:
    """Get bills created on a specific date."""
    try:
        bpath = os.path.join(DATA_DIR, bill_date, "bills.json")
        if os.path.exists(bpath):
            with open(bpath, "r") as f:
                bills = json.load(f)
                if status:
                    bills = [b for b in bills if b.get("status") == status]
                return sorted(bills, key=lambda x: x.get("created_at", ""), reverse=True)
        return []
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
#  IPD (INPATIENT) SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _wards_path() -> str:
    return os.path.join(DATA_DIR, "wards.json")


def _load_wards_json() -> list[dict]:
    path = _wards_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_wards_json(wards: list[dict]):
    with open(_wards_path(), "w", encoding="utf-8") as f:
        json.dump(wards, f, indent=2, ensure_ascii=False)


def _beds_path() -> str:
    return os.path.join(DATA_DIR, "beds.json")


def _load_beds_json() -> list[dict]:
    path = _beds_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_beds_json(beds: list[dict]):
    with open(_beds_path(), "w", encoding="utf-8") as f:
        json.dump(beds, f, indent=2, ensure_ascii=False)


def _ipd_admissions_path() -> str:
    return os.path.join(DATA_DIR, "ipd_admissions.json")


def _load_ipd_admissions_json() -> list[dict]:
    path = _ipd_admissions_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_ipd_admissions_json(admissions: list[dict]):
    with open(_ipd_admissions_path(), "w", encoding="utf-8") as f:
        json.dump(admissions, f, indent=2, ensure_ascii=False)


def _ipd_vitals_path() -> str:
    return os.path.join(DATA_DIR, "ipd_vitals.json")


def _load_ipd_vitals_json() -> list[dict]:
    path = _ipd_vitals_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_ipd_vitals_json(vitals: list[dict]):
    with open(_ipd_vitals_path(), "w", encoding="utf-8") as f:
        json.dump(vitals, f, indent=2, ensure_ascii=False)


def _ipd_notes_path() -> str:
    return os.path.join(DATA_DIR, "ipd_notes.json")


def _load_ipd_notes_json() -> list[dict]:
    path = _ipd_notes_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_ipd_notes_json(notes: list[dict]):
    with open(_ipd_notes_path(), "w", encoding="utf-8") as f:
        json.dump(notes, f, indent=2, ensure_ascii=False)


def _seed_default_wards_json():
    """Create default wards with beds if file doesn't exist."""
    wards = _load_wards_json()
    beds = _load_beds_json()
    if wards:
        return

    now = _now_str()
    default_wards = [
        ("General Ward", "general", 10, "General medicine ward"),
        ("Private Wing", "private", 6, "Private rooms with attached bathroom"),
        ("ICU", "icu", 4, "Intensive Care Unit — cardiac monitoring"),
    ]

    for wname, wtype, bcount, desc in default_wards:
        wid = str(uuid.uuid4())
        wards.append({
            "id": wid, "name": wname, "ward_type": wtype,
            "total_beds": bcount, "description": desc,
            "is_active": 1, "created_at": now,
        })
        prefix = {"general": "G", "private": "P", "icu": "I"}.get(wtype, "W")
        for i in range(1, bcount + 1):
            beds.append({
                "id": str(uuid.uuid4()),
                "ward_id": wid,
                "bed_label": f"{prefix}-{i:02d} Bed-{i:02d}",
                "status": "available",
                "last_cleaned": None,
                "is_active": 1,
                "created_at": now,
            })

    _save_wards_json(wards)
    _save_beds_json(beds)


# Seed on import
_seed_default_wards_json()


def admit_patient_json(patient_id: str, patient_name: str, mobile: str,
                       source: str = "direct", admitting_doctor: str = "",
                       diagnosis_primary: str = "", diagnosis_secondary: str = "",
                       bed_id: str = "", notes: str = "") -> dict:
    """Admit patient in Local JSON mode."""
    try:
        admissions = _load_ipd_admissions_json()
        admission = {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "patient_name": patient_name,
            "mobile": mobile,
            "source": source,
            "admitting_doctor": admitting_doctor,
            "diagnosis_primary": diagnosis_primary,
            "diagnosis_secondary": diagnosis_secondary,
            "assigned_bed_id": bed_id,
            "admission_date": _today_str(),
            "status": "active",
            "discharge_date": None,
            "discharge_type": None,
            "discharge_summary": "",
            "follow_up_date": None,
            "notes": notes,
            "created_at": _now_str(),
        }
        admissions.append(admission)
        _save_ipd_admissions_json(admissions)

        # Mark bed as occupied
        if bed_id:
            beds = _load_beds_json()
            for b in beds:
                if b["id"] == bed_id:
                    b["status"] = "occupied"
                    break
            _save_beds_json(beds)

        return {"success": True, "message": f"✅ {patient_name} admitted successfully!", "admission": admission}
    except Exception as e:
        print(f"[LocalJSON] admit_patient_json error: {e}")
        return {"success": False, "message": "❌ Failed to admit patient."}


def discharge_patient_json(admission_id: str, discharge_type: str = "normal",
                           discharge_summary: str = "", follow_up_date: str = "") -> dict:
    """Discharge patient in Local JSON mode."""
    try:
        admissions = _load_ipd_admissions_json()
        bed_id = None
        for a in admissions:
            if a["id"] == admission_id and a["status"] == "active":
                a["status"] = "discharged"
                a["discharge_type"] = discharge_type
                a["discharge_summary"] = discharge_summary
                a["discharge_date"] = _now_str()
                a["follow_up_date"] = follow_up_date or None
                bed_id = a.get("assigned_bed_id")
                break
        else:
            return {"success": False, "message": "❌ Active admission not found."}
        _save_ipd_admissions_json(admissions)

        if bed_id:
            beds = _load_beds_json()
            for b in beds:
                if b["id"] == bed_id:
                    b["status"] = "discharge_pending"
                    break
            _save_beds_json(beds)

        return {"success": True, "message": f"✅ Patient discharged ({discharge_type}). Bed marked for cleaning."}
    except Exception as e:
        print(f"[LocalJSON] discharge_patient_json error: {e}")
        return {"success": False, "message": "❌ Failed to discharge patient."}


def record_vitals_json(admission_id: str, bp_systolic: int = 0, bp_diastolic: int = 0,
                       pulse: int = 0, temperature: float = 0.0, spo2: int = 0,
                       weight: float = 0.0, recorded_by: str = "") -> dict:
    """Record vitals in Local JSON mode."""
    try:
        vitals = _load_ipd_vitals_json()
        vitals.append({
            "id": str(uuid.uuid4()),
            "admission_id": admission_id,
            "bp_systolic": bp_systolic,
            "bp_diastolic": bp_diastolic,
            "pulse": pulse,
            "temperature": temperature,
            "spo2": spo2,
            "weight": weight,
            "recorded_at": _now_str(),
            "recorded_by": recorded_by,
        })
        _save_ipd_vitals_json(vitals)
        return {"success": True, "message": "✅ Vitals recorded."}
    except Exception as e:
        print(f"[LocalJSON] record_vitals_json error: {e}")
        return {"success": False, "message": "❌ Failed to record vitals."}


def add_ipd_note_json(admission_id: str, doctor_name: str, notes: str,
                      note_type: str = "progress") -> dict:
    """Add clinical note in Local JSON mode."""
    try:
        all_notes = _load_ipd_notes_json()
        all_notes.append({
            "id": str(uuid.uuid4()),
            "admission_id": admission_id,
            "doctor_name": doctor_name,
            "notes": notes,
            "note_type": note_type,
            "created_at": _now_str(),
        })
        _save_ipd_notes_json(all_notes)
        return {"success": True, "message": "📝 Note added."}
    except Exception as e:
        print(f"[LocalJSON] add_ipd_note_json error: {e}")
        return {"success": False, "message": "❌ Failed to add note."}


def get_wards_json(active_only: bool = True) -> list[dict]:
    """Get all wards from JSON storage."""
    try:
        wards = _load_wards_json()
        if active_only:
            wards = [w for w in wards if w.get("is_active", 1)]
        return wards
    except Exception:
        return []


def get_beds_for_ward_json(ward_id: str, status: str = "") -> list[dict]:
    """Get beds for a ward from JSON storage."""
    try:
        beds = _load_beds_json()
        beds = [b for b in beds if b.get("ward_id") == ward_id and b.get("is_active", 1)]
        if status:
            beds = [b for b in beds if b.get("status") == status]
        return sorted(beds, key=lambda x: x.get("bed_label", ""))
    except Exception:
        return []


def get_ward_occupancy_json() -> list[dict]:
    """Get occupancy summary for all wards."""
    try:
        wards = _load_wards_json()
        beds = _load_beds_json()
        result = []
        for w in wards:
            if not w.get("is_active", 1):
                continue
            ward_beds = [b for b in beds if b.get("ward_id") == w["id"] and b.get("is_active", 1)]
            available = sum(1 for b in ward_beds if b.get("status") == "available")
            occupied = sum(1 for b in ward_beds if b.get("status") == "occupied")
            cleaning = sum(1 for b in ward_beds if b.get("status") == "cleaning")
            other = sum(1 for b in ward_beds if b.get("status") in ("maintenance", "discharge_pending"))
            result.append({
                "id": w["id"],
                "name": w["name"],
                "ward_type": w["ward_type"],
                "total_beds": w.get("total_beds", len(ward_beds)),
                "available": available,
                "occupied": occupied,
                "cleaning": cleaning,
                "other": other,
            })
        return result
    except Exception:
        return []


def get_available_beds_json(ward_id: str = "") -> list[dict]:
    """Get all available beds from JSON storage."""
    try:
        beds = _load_beds_json()
        wards = _load_wards_json()
        ward_map = {w["id"]: w for w in wards}

        available = [b for b in beds if b.get("status") == "available" and b.get("is_active", 1)]
        if ward_id:
            available = [b for b in available if b.get("ward_id") == ward_id]

        result = []
        for b in available:
            w = ward_map.get(b.get("ward_id", ""), {})
            result.append({
                **b,
                "ward_name": w.get("name", "?"),
                "ward_type": w.get("ward_type", "?"),
            })
        return result
    except Exception:
        return []


def get_active_admissions_json(ward_id: str = "") -> list[dict]:
    """Get active IPD admissions from JSON storage."""
    try:
        admissions = _load_ipd_admissions_json()
        beds = _load_beds_json()
        wards = _load_wards_json()

        ward_map = {w["id"]: w for w in wards}
        bed_map = {}
        for b in beds:
            w = ward_map.get(b.get("ward_id", ""), {})
            bed_map[b["id"]] = {**b, "ward_name": w.get("name", "?"), "ward_type": w.get("ward_type", "?")}

        active = [a for a in admissions if a.get("status") == "active"]
        if ward_id:
            active = [a for a in active if bed_map.get(a.get("assigned_bed_id", ""), {}).get("ward_id") == ward_id]

        result = []
        for a in active:
            b = bed_map.get(a.get("assigned_bed_id", ""), {})
            result.append({
                **a,
                "bed_label": b.get("bed_label", "—"),
                "ward_name": b.get("ward_name", "—"),
                "ward_type": b.get("ward_type", "—"),
            })
        return sorted(result, key=lambda x: x.get("admission_date", ""), reverse=True)
    except Exception:
        return []


def get_discharged_patients_json(limit: int = 50, ward_id: str = "") -> list[dict]:
    """Get discharged patients from JSON storage."""
    try:
        admissions = _load_ipd_admissions_json()
        beds = _load_beds_json()
        wards = _load_wards_json()

        ward_map = {w["id"]: w for w in wards}
        bed_map = {}
        for b in beds:
            w = ward_map.get(b.get("ward_id", ""), {})
            bed_map[b["id"]] = {**b, "ward_name": w.get("name", "?"), "ward_type": w.get("ward_type", "?")}

        discharged = [a for a in admissions if a.get("status") == "discharged"]
        if ward_id:
            discharged = [a for a in discharged if bed_map.get(a.get("assigned_bed_id", ""), {}).get("ward_id") == ward_id]

        result = []
        for a in discharged[:limit]:
            b = bed_map.get(a.get("assigned_bed_id", ""), {})
            result.append({
                **a,
                "bed_label": b.get("bed_label", "—"),
                "ward_name": b.get("ward_name", "—"),
                "ward_type": b.get("ward_type", "—"),
            })
        return sorted(result, key=lambda x: x.get("discharge_date", ""), reverse=True)
    except Exception:
        return []


def get_ipd_patient_status_json(patient_id: str) -> dict | None:
    """Get active admission for a patient from JSON storage."""
    try:
        admissions = _load_ipd_admissions_json()
        beds = _load_beds_json()
        wards = _load_wards_json()

        ward_map = {w["id"]: w for w in wards}
        bed_map = {}
        for b in beds:
            w = ward_map.get(b.get("ward_id", ""), {})
            bed_map[b["id"]] = {**b, "ward_name": w.get("name", "?"), "ward_type": w.get("ward_type", "?")}

        for a in admissions:
            if a.get("patient_id") == patient_id and a.get("status") == "active":
                b = bed_map.get(a.get("assigned_bed_id", ""), {})
                return {
                    **a,
                    "bed_label": b.get("bed_label", "—"),
                    "ward_name": b.get("ward_name", "—"),
                    "ward_type": b.get("ward_type", "—"),
                }
        return None
    except Exception:
        return None


def get_vitals_for_admission_json(admission_id: str, limit: int = 20) -> list[dict]:
    """Get vitals for an admission from JSON storage."""
    try:
        vitals = _load_ipd_vitals_json()
        filtered = [v for v in vitals if v.get("admission_id") == admission_id]
        return sorted(filtered, key=lambda x: x.get("recorded_at", ""), reverse=True)[:limit]
    except Exception:
        return []


def get_notes_for_admission_json(admission_id: str, limit: int = 50) -> list[dict]:
    """Get clinical notes for an admission from JSON storage."""
    try:
        notes = _load_ipd_notes_json()
        filtered = [n for n in notes if n.get("admission_id") == admission_id]
        return sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]
    except Exception:
        return []


def get_beds_json() -> list[dict]:
    """Get all beds from JSON storage."""
    return _load_beds_json()


def update_bed_status_json(bed_id: str, new_status: str) -> bool:
    """Update a bed's status in JSON storage."""
    try:
        beds = _load_beds_json()
        for b in beds:
            if b["id"] == bed_id:
                b["status"] = new_status
                if new_status == "available":
                    b["last_cleaned"] = _now_str()
                _save_beds_json(beds)
                return True
        return False
    except Exception:
        return False


def get_patient_admission_history_json(patient_id: str) -> list[dict]:
    """Get all admissions (past and present) for a patient from JSON storage."""
    try:
        admissions = _load_ipd_admissions_json()
        beds = _load_beds_json()
        wards = _load_wards_json()

        ward_map = {w["id"]: w for w in wards}
        bed_map = {}
        for b in beds:
            w = ward_map.get(b.get("ward_id", ""), {})
            bed_map[b["id"]] = {**b, "ward_name": w.get("name", "?")}

        patient_admissions = [a for a in admissions if a.get("patient_id") == patient_id]
        result = []
        for a in sorted(patient_admissions, key=lambda x: x.get("created_at", ""), reverse=True):
            b = bed_map.get(a.get("assigned_bed_id", ""), {})
            result.append({
                **a,
                "bed_label": b.get("bed_label", "—"),
                "ward_name": b.get("ward_name", "—"),
            })
        return result
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
#  INVENTORY / PHARMACY SYSTEM (for Local JSON mode)
# ═══════════════════════════════════════════════════════════════════════════════

def _inventory_categories_path() -> str:
    return os.path.join(DATA_DIR, "inventory_categories.json")


def _load_inventory_categories_json() -> list[dict]:
    path = _inventory_categories_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_inventory_categories_json(cats: list[dict]):
    with open(_inventory_categories_path(), "w", encoding="utf-8") as f:
        json.dump(cats, f, indent=2, ensure_ascii=False)


def _inventory_items_path() -> str:
    return os.path.join(DATA_DIR, "inventory_items.json")


def _load_inventory_items_json() -> list[dict]:
    path = _inventory_items_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_inventory_items_json(items: list[dict]):
    with open(_inventory_items_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def _inventory_batches_path() -> str:
    return os.path.join(DATA_DIR, "inventory_batches.json")


def _load_inventory_batches_json() -> list[dict]:
    path = _inventory_batches_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_inventory_batches_json(batches: list[dict]):
    with open(_inventory_batches_path(), "w", encoding="utf-8") as f:
        json.dump(batches, f, indent=2, ensure_ascii=False)


def _stock_movements_path() -> str:
    return os.path.join(DATA_DIR, "stock_movements.json")


def _load_stock_movements_json() -> list[dict]:
    path = _stock_movements_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_stock_movements_json(movements: list[dict]):
    with open(_stock_movements_path(), "w", encoding="utf-8") as f:
        json.dump(movements, f, indent=2, ensure_ascii=False)


def _stock_audits_path() -> str:
    return os.path.join(DATA_DIR, "stock_audits.json")


def _load_stock_audits_json() -> list[dict]:
    path = _stock_audits_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_stock_audits_json(audits: list[dict]):
    with open(_stock_audits_path(), "w", encoding="utf-8") as f:
        json.dump(audits, f, indent=2, ensure_ascii=False)


def _stock_audit_items_path() -> str:
    return os.path.join(DATA_DIR, "stock_audit_items.json")


def _load_stock_audit_items_json() -> list[dict]:
    path = _stock_audit_items_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []


def _save_stock_audit_items_json(items: list[dict]):
    with open(_stock_audit_items_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def _seed_default_inventory_categories_json():
    """Create default categories if file doesn't exist."""
    cats = _load_inventory_categories_json()
    if cats:
        return

    now = _now_str()
    defaults = [
        ("Cardiac Medications", "medicine"),
        ("General Medications", "medicine"),
        ("Consumables", "consumable"),
        ("Surgical Supplies", "surgical"),
        ("Lab Reagents", "lab_reagent"),
        ("Other Supplies", "other"),
    ]
    for name, ctype in defaults:
        cats.append({
            "id": str(uuid.uuid4()),
            "name": name,
            "category_type": ctype,
            "parent_id": None,
            "requires_batch": 1,
            "requires_expiry": 1,
            "is_cold_chain": 0,
            "created_at": now,
        })
    _save_inventory_categories_json(cats)


# Seed on import
_seed_default_inventory_categories_json()


# ─── Categories ─────────────────────────────────────────────────────────────

def get_inventory_categories_json(category_type: str = "") -> list[dict]:
    try:
        cats = _load_inventory_categories_json()
        if category_type:
            cats = [c for c in cats if c.get("category_type") == category_type]
        return sorted(cats, key=lambda x: x.get("name", ""))
    except Exception:
        return []


def create_inventory_category_json(
    name: str, category_type: str = "other",
    requires_batch: bool = True, requires_expiry: bool = True,
    is_cold_chain: bool = False
) -> dict:
    try:
        cats = _load_inventory_categories_json()
        cid = str(uuid.uuid4())
        cats.append({
            "id": cid, "name": name, "category_type": category_type,
            "parent_id": None,
            "requires_batch": int(requires_batch),
            "requires_expiry": int(requires_expiry),
            "is_cold_chain": int(is_cold_chain),
            "created_at": _now_str(),
        })
        _save_inventory_categories_json(cats)
        return {"success": True, "message": f"✅ Category '{name}' created.", "id": cid}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create category: {e}"}


# ─── Items ─────────────────────────────────────────────────────────────────

def create_inventory_item_json(
    name: str, category_id: str, unit: str = "tab",
    generic_name: str = "", manufacturer: str = "",
    reorder_level: float = 10.0, reorder_qty: float = 50.0,
    sku_code: str = "", hsn_code: str = ""
) -> dict:
    try:
        items = _load_inventory_items_json()
        item_id = str(uuid.uuid4())
        code = sku_code or f"SKU-{item_id[:8].upper()}"
        items.append({
            "id": item_id, "sku_code": code, "name": name,
            "generic_name": generic_name, "category_id": category_id,
            "manufacturer": manufacturer, "unit": unit,
            "reorder_level": reorder_level, "reorder_qty": reorder_qty,
            "is_active": 1, "hsn_code": hsn_code, "created_at": _now_str(),
        })
        _save_inventory_items_json(items)
        return {"success": True, "message": f"✅ '{name}' added to inventory.", "id": item_id, "sku": code}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create item: {e}"}


def get_inventory_items_json(category_id: str = "", search: str = "",
                             active_only: bool = True) -> list[dict]:
    try:
        items = _load_inventory_items_json()
        cats = _load_inventory_categories_json()
        cat_map = {c["id"]: c for c in cats}

        if active_only:
            items = [i for i in items if i.get("is_active", 1)]
        if category_id:
            items = [i for i in items if i.get("category_id") == category_id]
        if search:
            s = search.lower()
            items = [i for i in items if s in i.get("name", "").lower()
                     or s in i.get("generic_name", "").lower()
                     or s in i.get("sku_code", "").lower()]

        result = []
        for i in items:
            c = cat_map.get(i.get("category_id", ""), {})
            result.append({
                **i,
                "category_name": c.get("name", "?"),
                "category_type": c.get("category_type", "?"),
            })
        return sorted(result, key=lambda x: x.get("name", ""))
    except Exception:
        return []


def get_inventory_item_json(item_id: str) -> dict | None:
    try:
        items = _load_inventory_items_json()
        cats = _load_inventory_categories_json()
        cat_map = {c["id"]: c for c in cats}
        for i in items:
            if i["id"] == item_id:
                c = cat_map.get(i.get("category_id", ""), {})
                return {**i, "category_name": c.get("name", "?"), "category_type": c.get("category_type", "?")}
        return None
    except Exception:
        return None


def update_inventory_item_json(item_id: str, updates: dict) -> dict:
    try:
        items = _load_inventory_items_json()
        for i in items:
            if i["id"] == item_id:
                i.update(updates)
                _save_inventory_items_json(items)
                return {"success": True, "message": "✅ Item updated."}
        return {"success": False, "message": "❌ Item not found."}
    except Exception as e:
        return {"success": False, "message": f"❌ Update failed: {e}"}


# ─── Batches ───────────────────────────────────────────────────────────────

def add_inventory_batch_json(
    item_id: str, batch_no: str, quantity: float, unit_rate: float,
    mrp: float = 0.0, mfg_date: str = "", expiry_date: str = "",
    supplier_id: str = "", grn_ref: str = "",
    is_cold_chain: bool = False, created_by: str = ""
) -> dict:
    try:
        batches = _load_inventory_batches_json()
        movements = _load_stock_movements_json()
        batch_id = str(uuid.uuid4())
        now = _now_str()
        batches.append({
            "id": batch_id, "item_id": item_id, "batch_no": batch_no,
            "mfg_date": mfg_date, "expiry_date": expiry_date,
            "quantity": quantity, "unit_rate": unit_rate, "mrp": mrp,
            "supplier_id": supplier_id, "grn_ref": grn_ref,
            "is_cold_chain": int(is_cold_chain), "created_at": now,
        })
        movements.append({
            "id": str(uuid.uuid4()), "item_id": item_id, "batch_id": batch_id,
            "movement_type": "in", "quantity": quantity,
            "reference_type": "purchase", "reference_id": grn_ref,
            "notes": f"GRN: {grn_ref or 'Direct'}", "created_by": created_by,
            "created_at": now,
        })
        _save_inventory_batches_json(batches)
        _save_stock_movements_json(movements)
        return {"success": True, "message": f"✅ Batch {batch_no} added ({quantity} units).", "batch_id": batch_id}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to add batch: {e}"}


def get_inventory_batches_json(item_id: str = "", low_stock_only: bool = False,
                               expiring_within_days: int = 0) -> list[dict]:
    try:
        batches = _load_inventory_batches_json()
        items = _load_inventory_items_json()
        item_map = {i["id"]: i for i in items}

        if item_id:
            batches = [b for b in batches if b.get("item_id") == item_id]
        if low_stock_only:
            threshold_map = {i["id"]: i.get("reorder_level", 10) for i in items}
            batches = [b for b in batches if b.get("quantity", 0) <= threshold_map.get(b.get("item_id", ""), 10)]
        if expiring_within_days > 0:
            from datetime import date, timedelta
            cutoff = (date.today() + timedelta(days=expiring_within_days)).isoformat()
            today = date.today().isoformat()
            batches = [b for b in batches if b.get("expiry_date")
                       and b["expiry_date"] <= cutoff
                       and b["expiry_date"] >= today
                       and b.get("quantity", 0) > 0]

        result = []
        for b in batches:
            i = item_map.get(b.get("item_id", ""), {})
            result.append({
                **b,
                "item_name": i.get("name", "?"),
                "sku_code": i.get("sku_code", ""),
                "unit": i.get("unit", "?"),
                "reorder_level": i.get("reorder_level", 0),
            })
        return sorted(result, key=lambda x: x.get("expiry_date", "") or "")
    except Exception:
        return []


def get_inventory_batch_json(batch_id: str) -> dict | None:
    try:
        batches = _load_inventory_batches_json()
        items = _load_inventory_items_json()
        item_map = {i["id"]: i for i in items}
        for b in batches:
            if b["id"] == batch_id:
                i = item_map.get(b.get("item_id", ""), {})
                return {**b, "item_name": i.get("name", "?"), "sku_code": i.get("sku_code", ""), "unit": i.get("unit", "?")}
        return None
    except Exception:
        return None


# ─── Dispensing ────────────────────────────────────────────────────────────

def get_total_stock_json(item_id: str) -> float:
    try:
        batches = _load_inventory_batches_json()
        return sum(b.get("quantity", 0) for b in batches if b.get("item_id") == item_id)
    except Exception:
        return 0.0


def dispense_inventory_item_json(
    item_id: str, quantity: float, reference_type: str = "dispense",
    reference_id: str = "", created_by: str = "", notes: str = ""
) -> dict:
    try:
        if quantity <= 0:
            return {"success": False, "message": "❌ Quantity must be positive."}
        batches = _load_inventory_batches_json()
        movements = _load_stock_movements_json()

        valid = [b for b in batches if b.get("item_id") == item_id and b.get("quantity", 0) > 0]
        valid.sort(key=lambda x: (x.get("expiry_date") or "", x.get("created_at") or ""))

        if not valid:
            return {"success": False, "message": "❌ No stock available for this item."}

        total = sum(b.get("quantity", 0) for b in valid)
        if quantity > total:
            return {"success": False, "message": f"❌ Insufficient stock. Available: {total}, Requested: {quantity}"}

        remaining = quantity
        dispensed = []
        now = _now_str()

        for b in valid:
            if remaining <= 0:
                break
            deduct = min(remaining, b["quantity"])
            b["quantity"] -= deduct
            movements.append({
                "id": str(uuid.uuid4()), "item_id": item_id, "batch_id": b["id"],
                "movement_type": "out", "quantity": deduct,
                "reference_type": reference_type, "reference_id": reference_id,
                "notes": notes, "created_by": created_by, "created_at": now,
            })
            dispensed.append({
                "batch_id": b["id"], "batch_no": b.get("batch_no", ""),
                "quantity": deduct, "expiry_date": b.get("expiry_date", ""),
            })
            remaining -= deduct

        _save_inventory_batches_json(batches)
        _save_stock_movements_json(movements)
        return {"success": True, "message": f"✅ Dispensed {quantity} units from {len(dispensed)} batch(es).", "dispensed": dispensed}
    except Exception as e:
        return {"success": False, "message": f"❌ Dispense failed: {e}"}


# ─── Stock Movements ───────────────────────────────────────────────────────

def get_stock_movements_json(item_id: str = "", movement_type: str = "",
                             days: int = 30) -> list[dict]:
    try:
        movements = _load_stock_movements_json()
        items = _load_inventory_items_json()
        batches = _load_inventory_batches_json()
        item_map = {i["id"]: i for i in items}
        batch_map = {b["id"]: b for b in batches}

        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        filtered = [m for m in movements if m.get("created_at", "") >= cutoff]
        if item_id:
            filtered = [m for m in filtered if m.get("item_id") == item_id]
        if movement_type:
            filtered = [m for m in filtered if m.get("movement_type") == movement_type]

        result = []
        for m in sorted(filtered, key=lambda x: x.get("created_at", ""), reverse=True)[:200]:
            i = item_map.get(m.get("item_id", ""), {})
            b = batch_map.get(m.get("batch_id", ""), {})
            result.append({
                **m,
                "item_name": i.get("name", "?"),
                "sku_code": i.get("sku_code", ""),
                "unit": i.get("unit", "?"),
                "batch_no": b.get("batch_no", ""),
            })
        return result
    except Exception:
        return []


# ─── Low Stock & Expiry ────────────────────────────────────────────────────

def get_low_stock_items_json() -> list[dict]:
    try:
        items = _load_inventory_items_json()
        batches = _load_inventory_batches_json()
        cats = _load_inventory_categories_json()
        cat_map = {c["id"]: c for c in cats}

        stock = {}
        for b in batches:
            stock[b["item_id"]] = stock.get(b["item_id"], 0) + b.get("quantity", 0)

        result = []
        for i in items:
            if not i.get("is_active", 1):
                continue
            total = stock.get(i["id"], 0)
            if total <= i.get("reorder_level", 10):
                c = cat_map.get(i.get("category_id", ""), {})
                result.append({
                    "id": i["id"], "name": i.get("name", ""),
                    "sku_code": i.get("sku_code", ""), "unit": i.get("unit", ""),
                    "reorder_level": i.get("reorder_level", 10),
                    "reorder_qty": i.get("reorder_qty", 50),
                    "total_stock": total,
                    "category_name": c.get("name", "?"),
                })
        return sorted(result, key=lambda x: x.get("total_stock", 0))
    except Exception:
        return []


def get_expiring_batches_json(days: int = 30) -> list[dict]:
    try:
        batches = _load_inventory_batches_json()
        items = _load_inventory_items_json()
        item_map = {i["id"]: i for i in items}

        from datetime import date, timedelta
        cutoff = (date.today() + timedelta(days=days)).isoformat()
        today = date.today().isoformat()

        result = []
        for b in batches:
            if (b.get("expiry_date") and b["expiry_date"] <= cutoff
                    and b["expiry_date"] >= today and b.get("quantity", 0) > 0):
                i = item_map.get(b.get("item_id", ""), {})
                result.append({
                    **b,
                    "item_name": i.get("name", "?"),
                    "sku_code": i.get("sku_code", ""),
                    "unit": i.get("unit", "?"),
                })
        return sorted(result, key=lambda x: x.get("expiry_date", "") or "")
    except Exception:
        return []


# ─── Audits ────────────────────────────────────────────────────────────────

def create_stock_audit_json(audit_type: str = "full", notes: str = "",
                            created_by: str = "") -> dict:
    try:
        audits = _load_stock_audits_json()
        audit_id = str(uuid.uuid4())
        audits.append({
            "id": audit_id, "audit_date": _today_str(),
            "audit_type": audit_type, "status": "in_progress",
            "notes": notes, "created_by": created_by, "created_at": _now_str(),
        })
        _save_stock_audits_json(audits)
        return {"success": True, "message": f"✅ Audit '{audit_type}' created.", "audit_id": audit_id}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to create audit: {e}"}


def record_audit_item_json(audit_id: str, item_id: str, batch_id: str,
                           expected_qty: float, actual_qty: float,
                           resolution_notes: str = "") -> dict:
    try:
        items = _load_stock_audit_items_json()
        variance = actual_qty - expected_qty
        items.append({
            "id": str(uuid.uuid4()), "audit_id": audit_id,
            "item_id": item_id, "batch_id": batch_id,
            "expected_qty": expected_qty, "actual_qty": actual_qty,
            "variance": variance,
            "resolved": 1 if abs(variance) < 0.01 else 0,
            "resolution_notes": resolution_notes,
        })
        _save_stock_audit_items_json(items)
        return {"success": True, "message": "✅ Audit entry recorded."}
    except Exception as e:
        return {"success": False, "message": f"❌ Audit recording failed: {e}"}


def complete_stock_audit_json(audit_id: str) -> dict:
    try:
        audits = _load_stock_audits_json()
        for a in audits:
            if a["id"] == audit_id:
                a["status"] = "completed"
                _save_stock_audits_json(audits)
                return {"success": True, "message": "✅ Audit completed."}
        return {"success": False, "message": "❌ Audit not found."}
    except Exception as e:
        return {"success": False, "message": f"❌ Failed to close audit: {e}"}


def get_stock_audits_json(limit: int = 20) -> list[dict]:
    try:
        audits = _load_stock_audits_json()
        return sorted(audits, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]
    except Exception:
        return []


def get_audit_items_json(audit_id: str) -> list[dict]:
    try:
        items = _load_stock_audit_items_json()
        inv_items = _load_inventory_items_json()
        batches = _load_inventory_batches_json()
        item_map = {i["id"]: i for i in inv_items}
        batch_map = {b["id"]: b for b in batches}

        filtered = [ai for ai in items if ai.get("audit_id") == audit_id]
        result = []
        for ai in filtered:
            i = item_map.get(ai.get("item_id", ""), {})
            b = batch_map.get(ai.get("batch_id", ""), {})
            result.append({
                **ai,
                "item_name": i.get("name", "?"),
                "sku_code": i.get("sku_code", ""),
                "batch_no": b.get("batch_no", ""),
            })
        return result
    except Exception:
        return []


# ─── Dashboard Summary ─────────────────────────────────────────────────────

def get_inventory_summary_json() -> dict:
    try:
        items = _load_inventory_items_json()
        batches = _load_inventory_batches_json()
        active_items = [i for i in items if i.get("is_active", 1)]
        total_items = len(active_items)
        total_batches = len(batches)
        total_stock_value = sum(b.get("quantity", 0) * b.get("unit_rate", 0) for b in batches)

        stock_agg = {}
        for b in batches:
            stock_agg[b["item_id"]] = stock_agg.get(b["item_id"], 0) + b.get("quantity", 0)
        low_stock_count = sum(1 for i in active_items
                              if stock_agg.get(i["id"], 0) <= i.get("reorder_level", 10))

        from datetime import date, timedelta
        cutoff = (date.today() + timedelta(days=30)).isoformat()
        today = date.today().isoformat()
        expiring_30 = sum(1 for b in batches
                          if b.get("expiry_date") and b["expiry_date"] <= cutoff
                          and b["expiry_date"] >= today and b.get("quantity", 0) > 0)

        return {
            "total_items": total_items,
            "total_batches": total_batches,
            "total_stock_value": total_stock_value,
            "low_stock_count": low_stock_count,
            "expiring_30_days": expiring_30,
        }
    except Exception:
        return {"total_items": 0, "total_batches": 0, "total_stock_value": 0,
                "low_stock_count": 0, "expiring_30_days": 0}