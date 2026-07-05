"""
Queue logic module — token generation, position calculation, wait time estimation.
All pure functions, no database calls directly.
"""
from datetime import date, datetime, timedelta
from utils.config import PATIENT_ID_PREFIX, AVG_TEST_TIME, STATUS_ICONS, STATUS_LABELS, ROOM_NAMES


def generate_patient_id(sequence_number: int) -> str:
    """
    Generate a unique patient ID.
    Format: CQ-YYYYMMDD-XXX
    Example: CQ-20260630-001
    """
    today = date.today().strftime("%Y%m%d")
    return f"{PATIENT_ID_PREFIX}-{today}-{sequence_number:03d}"


def calculate_wait_time(test_name: str, queue_position: int) -> int:
    """
    Estimate wait time in minutes.
    Formula: (queue_position - 1) * avg_time_for_test
    If position is 1 (currently being served), wait is the avg time.
    """
    avg_minutes = AVG_TEST_TIME.get(test_name, 15)
    if queue_position <= 0:
        return 0
    # Position 1 means currently called/in_progress — estimate remaining avg time
    effective_position = max(queue_position - 1, 0)
    return effective_position * avg_minutes


def calculate_expected_time(test_name: str, queue_position: int) -> str:
    """
    Returns estimated appointment clock time as a formatted string.
    Example: '~3:45 PM' or 'Now / अभी'

    Used on Patient Status page and Token Slips to show WHEN, not just HOW LONG.
    """
    wait_minutes = calculate_wait_time(test_name, queue_position)
    if wait_minutes <= 0:
        return "Now / अभी"
    expected_dt = datetime.now() + timedelta(minutes=wait_minutes)
    # Format: ~3:45 PM (no leading zero)
    hour = expected_dt.strftime("%I").lstrip("0") or "12"
    minute = expected_dt.strftime("%M")
    ampm = expected_dt.strftime("%p")
    return f"~{hour}:{minute} {ampm}"


def get_department_from_test(test_name: str) -> str:
    """Get the department/room name for a test type."""
    return ROOM_NAMES.get(test_name, f"{test_name} Room")


def format_status_display(status: str) -> str:
    """Get icon + label for a status value."""
    icon = STATUS_ICONS.get(status, "❓")
    label = STATUS_LABELS.get(status, status.replace("_", " ").title())
    return f"{icon} {label}"


def get_available_actions(current_status: str) -> list[str]:
    """
    Given the current status, return the list of allowed next actions.
    Follows the status flow: waiting → called → in_progress → completed → report_ready → delivered
    """
    flow = {
        "waiting":       ["called"],
        "called":        ["in_progress"],
        "in_progress":   ["completed"],
        "completed":     ["report_ready"],
        "report_ready":  ["delivered"],
        "delivered":     [],
    }
    return flow.get(current_status, [])


def format_token_slip(patient_name: str, patient_id: str, tests: list[dict]) -> str:
    """
    Generate a formatted token slip string for printing.
    """
    lines = [
        "=" * 40,
        f"      {ROOM_NAMES.get('ECG', 'Cardiology').split(' Room')[0].upper()} DEPARTMENT",
        f"         {ROOM_NAMES.get('ECG', 'Cardiology').replace(' Room', '')}",
        "=" * 40,
        "",
        f"  Token: {patient_id}",
        f"  Patient: {patient_name}",
        f"  Date: {date.today().strftime('%d-%b-%Y')}",
        "",
        "-" * 40,
        "  Tests:",
    ]
    for t in tests:
        lines.append(f"    {t['token_number']:03d}  {t['test_name']}  —  {t['room']}")
    lines += [
        "",
        "-" * 40,
        "  Please wait for your call.",
        "  Watch the display board for updates.",
        "=" * 40,
    ]
    return "\n".join(lines)
