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


def format_html_token_slip(
    patient_name: str,
    patient_id: str,
    tests: list[dict],
    clinic_name: str = "GIL CLINIC",
    clinic_logo: str = "🏥",
    clinic_address: str = "",
    clinic_phone: str = "",
    qr_data_uri: str = "",
) -> str:
    """
    Generate a print-optimised HTML token slip with clinic branding,
    QR code, and estimated wait times for each test.

    Returns a complete HTML page with @media print CSS.
    """
    today_str = date.today().strftime("%d-%b-%Y")
    now_str = datetime.now().strftime("%I:%M %p").lstrip("0")

    # Build test rows
    test_rows = ""
    for t in tests:
        tn = t.get("token_number", "?")
        tname = t.get("test_name", "Test")
        room = t.get("room", ROOM_NAMES.get(tname, f"{tname} Room"))
        pos = t.get("queue_position", 0)
        eta = calculate_expected_time(tname, pos)
        test_rows += f"""
            <tr>
                <td style="font-size:18px;font-weight:700;">#{tn:03d}</td>
                <td style="font-size:16px;">{tname}</td>
                <td style="font-size:14px;color:#555;">{room}</td>
                <td style="font-size:14px;color:#667eea;font-weight:600;text-align:right;">{eta}</td>
            </tr>"""

    qr_html = ""
    if qr_data_uri:
        qr_html = f"""
            <div style="text-align:center;margin:16px 0;">
                <img src="{qr_data_uri}" style="width:130px;height:130px;border-radius:6px;
                     background:white;padding:6px;border:1px solid #ddd;" alt="QR">
                <p style="font-size:11px;color:#888;margin:4px 0 0;">Scan to track live status</p>
            </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Token Slip — {patient_name}</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ font-family:'Segoe UI','Arial',sans-serif; background:#f5f5f5; padding:20px; }}
    .slip {{
        max-width:380px; margin:0 auto; background:#fff;
        border-radius:14px; box-shadow:0 4px 24px rgba(0,0,0,0.12);
        overflow:hidden;
    }}
    .header {{
        background:linear-gradient(135deg,#667eea,#764ba2);
        color:#fff; text-align:center; padding:20px 16px 14px;
    }}
    .header h1 {{ font-size:28px; margin:0; }}
    .header h2 {{ font-size:16px; font-weight:400; opacity:0.9; margin:4px 0 2px; }}
    .header .details {{ font-size:12px; opacity:0.75; margin-top:6px; line-height:1.5; }}
    .body {{ padding:16px 18px; }}
    .patient-info {{ margin-bottom:12px; }}
    .patient-info .name {{ font-size:20px; font-weight:700; color:#222; }}
    .patient-info .meta {{ font-size:13px; color:#666; margin-top:2px; }}
    table {{ width:100%; border-collapse:collapse; }}
    th {{ text-align:left; font-size:11px; text-transform:uppercase; color:#999;
         padding:6px 4px 4px; border-bottom:2px solid #eee; }}
    td {{ padding:8px 4px; border-bottom:1px solid #f0f0f0; }}
    tr:last-child td {{ border-bottom:none; }}
    .footer {{ text-align:center; padding:12px 16px 18px; font-size:11px; color:#aaa;
              border-top:1px solid #f0f0f0; }}
    .badge {{ display:inline-block; background:#e8f0fe; color:#667eea; font-size:10px;
              font-weight:700; padding:2px 10px; border-radius:20px; }}
    @media print {{
        body {{ background:#fff; padding:0; }}
        .slip {{ box-shadow:none; border-radius:0; max-width:100%; }}
        .header {{ -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
    }}
</style></head>
<body>
<div class="slip">
    <div class="header">
        <h1>{clinic_logo}</h1>
        <h2>{clinic_name}</h2>
        <div class="details">
            {clinic_address}{" · " if clinic_address and clinic_phone else ""}{clinic_phone}
        </div>
    </div>
    <div class="body">
        <div class="patient-info">
            <div class="name">{patient_name}</div>
            <div class="meta">ID: {patient_id} &nbsp;|&nbsp; {today_str} &nbsp;|&nbsp; {now_str}</div>
        </div>
        {qr_html}
        <table>
            <tr><th>Token</th><th>Test</th><th>Room</th><th style="text-align:right;">ETA</th></tr>
            {test_rows}
        </table>
        <div style="text-align:center;margin-top:14px;">
            <span class="badge">⚡ Please wait for your call</span>
        </div>
    </div>
    <div class="footer">
        CardioQueue v2 &middot; Live status: scan QR or visit reception
    </div>
</div>
<script>window.print();</script>
</body>
</html>"""
