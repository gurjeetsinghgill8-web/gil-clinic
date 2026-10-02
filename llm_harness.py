"""
LLM Harness — Central Orchestrator for CardioQueue
====================================================

Architecture:      UI (Streamlit) → Harness (This file) → Database / LLM / Notifications

Principles (Harness Engineering):
  1. The LLM is just the CPU — this file is the motherboard, memory bus, and I/O controller.
  2. "Craft of Subtraction" — natural language rules over brittle regex/if-else chains.
  3. Portability — swap the LLM engine by changing one method, not the entire app.
  4. Memory Management — all context flows through here, not scattered across pages.

This file acts as the single entry point for ALL user actions from the UI.
Pages never call db.py or notifications.py directly — they call the Harness.

Phase 1: Rule-based deterministic actions (registration, queue ops, status updates).
Phase 2+: LLM-powered actions (patient questions, AI assistant, smart triage).
"""
import streamlit as st
from datetime import date, datetime
from typing import Callable

from utils.config import (
    TEST_TYPES, ROOM_NAMES, AVG_TEST_TIME, STATUS_ICONS, STATUS_LABELS,
    HOSPITAL_NAME, APP_NAME, DOCTOR_MOBILE, BABLU_MOBILE, BASE_URL
)
from utils.db import (
    create_patient, get_patient_by_id, get_patient_by_mobile,
    get_today_patients, create_test, get_tests_for_patient,
    get_tests_by_mobile, get_queue, update_test_status,
    get_completed_tests, get_report_ready_tests,
    get_current_patient, log_message, get_department_stats,
    USE_GOOGLE_SHEETS
)
from utils.queue import (
    generate_patient_id, calculate_wait_time, format_status_display,
    get_available_actions, format_token_slip, format_html_token_slip
)
from utils.notifications import (
    registration_message, called_message, completed_message,
    report_ready_message, browser_notification_script,
    request_notification_permission_script, misscall_alert_script
)
# Optional imports — WhatsApp/SMS modules handle missing dependencies gracefully
try:
    from utils.whatsapp import send_whatsapp_message, get_whatsapp_template
except Exception:
    send_whatsapp_message = None
    get_whatsapp_template = None

try:
    from utils.sms import send_sms_message, get_sms_template
except Exception:
    send_sms_message = None
    get_sms_template = None


# ═══════════════════════════════════════════════════════════════════════════════
#  HARNESS CORE
# ═══════════════════════════════════════════════════════════════════════════════

class Harness:
    """
    Central Orchestrator for all CardioQueue operations.

    The Harness receives structured 'intents' from the UI and routes them
    to the appropriate handler — database, notification, or (in future) LLM.
    """

    def __init__(self):
        self.app_name = APP_NAME
        self.hospital = HOSPITAL_NAME
        self.today = date.today()

    @staticmethod
    def _get_actor() -> str:
        """Get the current logged-in user's display name for audit logging."""
        import streamlit as st
        return st.session_state.get("auth_username", "Unknown")

    # ─── PATIENT OPERATIONS ───────────────────────────────────────────────────

    def register_patient(self, name: str, mobile: str, age: int, gender: str,
                         selected_tests: list[str]) -> dict:
        """
        Register a new patient with selected tests.

        Returns: {
            "success": bool,
            "patient": dict | None,
            "tests": list[dict],
            "message": str,
            "notification": str | None
        }
        """
        # Validate
        if not mobile or len(mobile) != 10 or not mobile.isdigit():
            return {"success": False, "patient": None, "tests": [],
                    "message": "⚠️ Please enter a valid 10-digit mobile number.",
                    "notification": None}
        if not name or name.strip() == "":
            return {"success": False, "patient": None, "tests": [],
                    "message": "⚠️ Patient name is required.",
                    "notification": None}
        if not selected_tests:
            return {"success": False, "patient": None, "tests": [],
                    "message": "⚠️ Please select at least one test.",
                    "notification": None}

        # Create patient record
        patient = create_patient(name.strip(), mobile, age, gender)
        if not patient:
            db_name = "Google Sheets" if USE_GOOGLE_SHEETS else "Supabase" if USE_SUPABASE else "SQLite"
            return {"success": False, "patient": None, "tests": [],
                    "message": f"❌ Failed to create patient record. Check {db_name} connection.",
                    "notification": None}

        patient_id = patient["patient_id"]

        # Create test records
        created_tests = []
        for test_name in selected_tests:
            room = ROOM_NAMES.get(test_name, f"{test_name} Room")
            test = create_test(patient_id, test_name, room)
            if test:
                created_tests.append(test)

        # Log notification message
        msg = registration_message(name, selected_tests)
        log_message(patient_id, mobile, "registration", msg, "browser", actor=self._get_actor())

        # ─── WhatsApp Registration Notifications ─────────────────────────────
        token = created_tests[0]["token_number"] if created_tests else 1
        wait_time = calculate_wait_time(selected_tests[0], 1) if selected_tests else 15
        patient_wa_msg = get_whatsapp_template(
            "registration",
            hospital=HOSPITAL_NAME,
            name=name.strip(),
            test=", ".join(selected_tests),
            token=token,
            wait=wait_time
        )
        send_whatsapp_message(mobile, patient_wa_msg)

        # 2. Doctor WhatsApp Notification
        if DOCTOR_MOBILE:
            doc_wa_msg = (
                f"🏥 *{HOSPITAL_NAME}*\n"
                f"New patient registered:\n"
                f"Name: {name.strip()}\n"
                f"Age/Gender: {age}/{gender}\n"
                f"Token: #{token}\n"
                f"Tests: {', '.join(selected_tests)}"
            )
            send_whatsapp_message(DOCTOR_MOBILE, doc_wa_msg)

        # 3. Bablu WhatsApp Notification
        if BABLU_MOBILE:
            bablu_wa_msg = (
                f"🏥 *{HOSPITAL_NAME}*\n"
                f"New patient registered:\n"
                f"Name: {name.strip()}\n"
                f"Token: #{token}\n"
                f"Tests: {', '.join(selected_tests)}"
            )
            send_whatsapp_message(BABLU_MOBILE, bablu_wa_msg)

        # ─── SMS Registration Notification ──────────────────────────────────
        patient_sms_msg = get_sms_template(
            "registration",
            hospital=HOSPITAL_NAME,
            name=name.strip(),
            test=", ".join(selected_tests),
            token=token,
            wait=wait_time,
            url=self.get_patient_status_url(patient_id)
        )
        sms_result = send_sms_message(mobile, patient_sms_msg)
        if sms_result["success"]:
            log_message(patient_id, mobile, "registration", patient_sms_msg, "sms", actor=self._get_actor())

        return {
            "success": True,
            "patient": patient,
            "tests": created_tests,
            "message": f"✅ Patient {name} registered successfully!\nID: {patient_id}",
            "notification": msg,
        }

    def bulk_register_patients(self, csv_content: str) -> dict:
        """
        Bulk register patients from a CSV string.
        CSV columns: Name, Mobile, Age, Gender, Tests
        Tests column uses '+' separator (e.g. 'ECG+Echo')

        Returns: {
            "total": int, "succeeded": int, "failed": int,
            "results": [{"row": int, "name": str, "success": bool, "message": str}]
        }
        """
        import csv
        import io

        results = []
        reader = csv.DictReader(io.StringIO(csv_content))

        for idx, row in enumerate(reader, start=2):  # row 1 = header
            name = (row.get("Name") or "").strip()
            mobile = (row.get("Mobile") or "").strip()
            age_str = (row.get("Age") or "").strip()
            gender = (row.get("Gender") or "").strip()
            tests_str = (row.get("Tests") or "").strip()

            # Parse tests
            selected_tests = [t.strip() for t in tests_str.split("+") if t.strip()]
            # Validate test names against known types
            valid_tests = [t for t in selected_tests if t in TEST_TYPES]
            if not valid_tests:
                results.append({
                    "row": idx, "name": name, "success": False,
                    "message": f"No valid tests found in '{tests_str}'. Valid: {', '.join(TEST_TYPES)}"
                })
                continue

            # Parse age
            try:
                age = int(age_str)
            except (ValueError, TypeError):
                results.append({
                    "row": idx, "name": name, "success": False,
                    "message": f"Invalid age: '{age_str}'"
                })
                continue

            # Register
            result = self.register_patient(name, mobile, age, gender, valid_tests)
            results.append({
                "row": idx,
                "name": name,
                "success": result["success"],
                "message": result["message"] if result["success"] else result["message"],
            })

        total = len(results)
        succeeded = sum(1 for r in results if r["success"])
        failed = total - succeeded
        return {
            "total": total,
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    def get_patient_details(self, identifier: str, by_mobile: bool = True) -> dict:
        """
        Get patient details and all their tests.
        identifier = mobile number (by_mobile=True) or patient_id (by_mobile=False)
        """
        if by_mobile:
            patient = get_patient_by_mobile(identifier)
        else:
            patient = get_patient_by_id(identifier)

        if not patient:
            return {"found": False, "patient": None, "tests": []}

        tests = get_tests_for_patient(patient["patient_id"])
        return {"found": True, "patient": patient, "tests": tests}

    def get_patient_visit_count(self, mobile: str) -> int:
        """Get how many times a patient with this mobile has visited."""
        from utils.db import get_patient_visit_count
        return get_patient_visit_count(mobile)

    def get_patient_visit_history(self, mobile: str) -> list[dict]:
        """
        Get ALL past visits for a patient by mobile number.
        Returns list of dicts, each with:
          { "visit": dict, "tests": list[dict], "date_str": str }
        Ordered most recent first.
        """
        from utils.db import get_patient_visits_by_mobile, get_tests_for_patient
        from datetime import datetime

        visits = get_patient_visits_by_mobile(mobile)
        result = []
        for v in visits:
            tests = get_tests_for_patient(v["patient_id"])
            # Enrich tests with display helpers
            for t in tests:
                t["status_display"] = format_status_display(t["status"])
                t["wait_time"] = calculate_wait_time(
                    t["test_name"], t.get("queue_position", 0)
                )
            # Format date for display
            try:
                dt = datetime.fromisoformat(v.get("registration_date", ""))
                date_str = dt.strftime("%d-%b-%Y")
            except Exception:
                date_str = v.get("registration_date", "Unknown")
            result.append({
                "visit": v,
                "tests": tests,
                "date_str": date_str,
            })
        return result

    # ─── QUEUE OPERATIONS ────────────────────────────────────────────────────

    def get_department_queue(self, test_name: str) -> dict:
        """
        Get the full queue state for a department.

        Returns: {
            "current": dict | None,          # Patient currently being served
            "waiting": list[dict],            # Patients waiting
            "stats": dict,                    # Counts per status
            "test_name": str,
        }
        """
        current = get_current_patient(test_name)
        waiting_list = get_queue(test_name, "waiting")
        stats = get_department_stats(test_name)

        return {
            "current": current,
            "waiting": waiting_list,
            "stats": stats,
            "test_name": test_name,
        }

    def call_patient(self, test_id: str, patient_name: str,
                     test_name: str, token: int, mobile: str, patient_id: str) -> dict:
        """
        Call a patient to the department room.
        Updates status → "called" and sends notification.
        """
        success = update_test_status(test_id, "called")
        if not success:
            return {"success": False, "message": "❌ Failed to update status."}

        room = ROOM_NAMES.get(test_name, f"{test_name} Room")
        msg = called_message(patient_name, test_name, token, room)
        log_message(patient_id, mobile, "called", msg, "browser", actor=self._get_actor())

        # ─── WhatsApp Call Notification ─────────────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "called",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            room=room,
            token=token
        )
        send_whatsapp_message(mobile, patient_wa_msg)

        # ─── SMS Call Notification ──────────────────────────────────────────
        patient_sms_msg = get_sms_template(
            "called",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            room=room,
            token=token
        )
        sms_result = send_sms_message(mobile, patient_sms_msg)
        if sms_result["success"]:
            log_message(patient_id, mobile, "called", patient_sms_msg, "sms", actor=self._get_actor())

        return {
            "success": True,
            "message": f"🔵 Called {patient_name} to {room}",
            "notification": msg,
        }

    def start_test(self, test_id: str) -> dict:
        """Mark a test as in_progress."""
        success = update_test_status(test_id, "in_progress")
        return {
            "success": success,
            "message": "🟠 Test started." if success else "❌ Failed to start test.",
        }

    def complete_test(self, test_id: str, patient_name: str,
                      test_name: str, mobile: str, patient_id: str) -> dict:
        """Mark a test as completed."""
        success = update_test_status(test_id, "completed")
        if not success:
            return {"success": False, "message": "❌ Failed to complete test."}

        msg = completed_message(patient_name, test_name)
        log_message(patient_id, mobile, "completed", msg, "browser", actor=self._get_actor())

        # ─── WhatsApp Completed Notification ─────────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "completed",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        send_whatsapp_message(mobile, patient_wa_msg)

        # ─── SMS Completed Notification ─────────────────────────────────────
        patient_sms_msg = get_sms_template(
            "completed",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        sms_result = send_sms_message(mobile, patient_sms_msg)
        if sms_result["success"]:
            log_message(patient_id, mobile, "completed", patient_sms_msg, "sms", actor=self._get_actor())

        return {
            "success": True,
            "message": f"✅ {test_name} completed for {patient_name}",
            "notification": msg,
        }

    def send_reminder(self, patient_name: str, test_name: str = "", mobile: str = "",
                      token: int = 0, patient_id: str = "") -> dict:
        """
        Send a reminder to the PATIENT's phone via DB-poll mechanism.

        Architecture fix (Brick 1):
        OLD: JS injection on staff browser — only staff sees it. Patient sees NOTHING.
        NEW: Write pending_alert=1 to DB -> Patient's 5s auto-refresh detects it
             -> Sound + Vibration + Banner on patient's own phone. ✅

        Works without WebSockets, without APIs, on free Streamlit Cloud hosting.
        """
        from utils.db import set_patient_alert

        room = ROOM_NAMES.get(test_name, "Reception")
        msg = (
            f"🔔 आपका नंबर जल्द आने वाला है! / Your turn is coming soon!\n"
            f"{patient_name} — {test_name or 'Dept'}\n"
            f"Token: #{token} | {room}\n"
            f"कृपया तैयार रहें / Please be ready!"
        )

        # ✅ Write to DB — patient's page picks this up on next 5s auto-refresh
        alert_sent = False
        if patient_id:
            alert_sent = set_patient_alert(patient_id, msg)

        return {
            "success": True,
            "message": (
                f"🔔 Reminder sent! Will appear on {patient_name}'s phone within 5 seconds."
                if alert_sent else
                f"🔔 Reminder noted for {patient_name} (pass patient_id to enable DB alert)"
            ),
            "notification": msg,
            "db_alert_set": alert_sent,
        }

    # ─── DOCTOR OPERATIONS ────────────────────────────────────────────────────

    def get_doctor_dashboard(self) -> dict:
        """Get all data for the doctor dashboard."""
        completed = get_completed_tests()
        report_ready = get_report_ready_tests()

        return {
            "pending_reports": completed,
            "reports_ready": report_ready,
        }

    def save_doctor_notes(self, test_id: str, notes: str) -> dict:
        """Save doctor's consultation notes for a completed test."""
        from utils.db import save_test_notes
        success = save_test_notes(test_id, notes)
        return {
            "success": success,
            "message": "📝 Notes saved!" if success else "❌ Failed to save notes.",
        }

    def mark_report_ready(self, test_id: str, patient_name: str,
                          test_name: str, mobile: str, patient_id: str) -> dict:
        """Mark a test report as ready."""
        success = update_test_status(test_id, "report_ready")
        if not success:
            return {"success": False, "message": "❌ Failed to mark report ready."}

        msg = report_ready_message(patient_name, test_name)
        log_message(patient_id, mobile, "report_ready", msg, "browser", actor=self._get_actor())

        # ─── WhatsApp Report Ready Notification ──────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "report_ready",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        send_whatsapp_message(mobile, patient_wa_msg)

        # ─── SMS Report Ready Notification ──────────────────────────────────
        patient_sms_msg = get_sms_template(
            "report_ready",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        sms_result = send_sms_message(mobile, patient_sms_msg)
        if sms_result["success"]:
            log_message(patient_id, mobile, "report_ready", patient_sms_msg, "sms", actor=self._get_actor())

        return {
            "success": True,
            "message": f"📋 Report ready for {patient_name} — {test_name}",
            "notification": msg,
        }

    def deliver_report(self, test_id: str) -> dict:
        """Mark a report as delivered."""
        success = update_test_status(test_id, "delivered")
        return {
            "success": success,
            "message": "📄 Report marked as delivered." if success else "❌ Failed to mark delivered.",
        }

    # ─── PATIENT STATUS ──────────────────────────────────────────────────────

    def get_patient_status(self, mobile: str) -> dict:
        """
        Get patient status display data from mobile number.
        
        Returns: {
            "found": bool,
            "patient": dict | None,
            "tests": list[dict],     # Each with status_display, wait_time
        }
        """
        result = self.get_patient_details(mobile, by_mobile=True)
        if not result["found"]:
            return {"found": False, "patient": None, "tests": []}

        tests = result["tests"]
        for test in tests:
            test["status_display"] = format_status_display(test["status"])
            test["wait_time"] = calculate_wait_time(
                test["test_name"], test.get("queue_position", 0)
            )

        return {"found": True, "patient": result["patient"], "tests": tests}

    # ─── MISS CALL ALERT ────────────────────────────────────────────────────

    def send_misscall_alert(self, patient_name: str, test_name: str = "", token: int = 0,
                            patient_pid: str = "") -> dict:
        """
        Send a "Miss Call" style alert — updates patient dashboard instantly via DB poll alert.
        """
        from utils.db import set_patient_alert

        misscall_url = f"{BASE_URL}/?misscall=1&patient={patient_pid}" if patient_pid else ""
        status_label = f"📞 Miss Call Alert: {test_name or 'Clinic'}"
        msg = (
            f"📞 Missed Call Alert! / मिस्ड कॉल अलर्ट!\n"
            f"Dear {patient_name}, you were called for {test_name or 'test'} but were not present.\n"
            f"Please proceed to the room immediately! / कृपया तुरंत रूम में संपर्क करें!"
        )

        # Write to DB alert flag so patient's page picks it up on next 5s auto-refresh
        alert_sent = False
        if patient_pid:
            alert_sent = set_patient_alert(patient_pid, msg)

        result = {
            "success": True,
            "message": (
                f"📞 Miss Call alert sent! Will appear on {patient_name}'s phone within 5 seconds."
                if alert_sent else
                f"📞 Miss Call noted for {patient_name}"
            ),
            "notification": msg,
            "patient_alert": {
                "action": "misscall_alert",
                "status_label": status_label,
            },
            "misscall_url": misscall_url,
            "db_alert_set": alert_sent
        }

        return result

    @staticmethod
    def get_misscall_script(patient_name: str, test_name: str = "") -> str:
        """Get the Miss Call Alert JS injection script (works without notif permission)."""
        return misscall_alert_script(patient_name, test_name)

    # ─── NOTIFICATION HELPERS ────────────────────────────────────────────────

    @staticmethod
    def get_notification_script(title: str, body: str, urgent: bool = False) -> str:
        """Get browser notification injection script (with sound + vibration)."""
        return browser_notification_script(title, body, urgent=urgent)

    @staticmethod
    def get_permission_script() -> str:
        """Get notification permission request script."""
        return request_notification_permission_script()

    @staticmethod
    def get_copy_link_script(url: str, label: str = "Link copied!") -> str:
        """
        Get an HTML button + JS that copies a URL to clipboard.
        Shows a toast/message when copied.
        """
        escaped_url = url.replace("'", "\\'")
        return f"""
        <div style="display:inline-block;">
            <button onclick="(function(){{
                navigator.clipboard.writeText('{escaped_url}').then(function(){{
                    var t=document.createElement('div');
                    t.style.cssText='position:fixed;bottom:20px;left:50%;transform:translateX(-50%);
                        background:#00b894;color:white;padding:10px 24px;border-radius:12px;
                        font-weight:600;z-index:9999;box-shadow:0 4px 16px rgba(0,0,0,0.2);
                        font-family:sans-serif;';
                    t.textContent='✅ {label}';
                    document.body.appendChild(t);
                    setTimeout(function(){{t.remove();}},2500);
                }});
            }})();" style="background:#00b894;color:white;border:none;padding:8px 18px;
                border-radius:8px;cursor:pointer;font-size:0.9rem;font-weight:600;
                display:inline-flex;align-items:center;gap:4px;">
                📋 Copy Link
            </button>
        </div>
        """

    # ─── TOKEN PRINTING ──────────────────────────────────────────────────────

    def generate_token_slip(self, patient_name: str, patient_id: str,
                            tests: list[dict]) -> str:
        """Generate a formatted token slip for printing."""
        return format_token_slip(patient_name, patient_id, tests)

    def get_clinic_settings(self) -> dict:
        """Get clinic branding settings from DB, falling back to config defaults."""
        from utils.db import get_clinic_settings_db
        settings = get_clinic_settings_db()
        if settings:
            return settings
        from utils.config import HOSPITAL_NAME, CLINIC_SPECIALTY, CLINIC_LOGO
        return {
            "clinic_name": HOSPITAL_NAME,
            "specialty": CLINIC_SPECIALTY,
            "logo_emoji": CLINIC_LOGO,
            "phone": "",
            "address": "",
        }

    def printable_token_slip_html(self, patient_name: str, patient_id: str,
                                   tests: list[dict]) -> str:
        """
        Generate a print-optimised HTML token slip with clinic branding,
        QR code, and estimated arrival times for each test.
        """
        settings = self.get_clinic_settings()
        qr_uri = self.generate_qr_code_base64(patient_id) or ""
        return format_html_token_slip(
            patient_name=patient_name,
            patient_id=patient_id,
            tests=tests,
            clinic_name=settings.get("clinic_name", "GIL CLINIC"),
            clinic_logo=settings.get("logo_emoji", "🏥"),
            clinic_address=settings.get("address", ""),
            clinic_phone=settings.get("phone", ""),
            qr_data_uri=qr_uri,
        )

    # ─── QR CODE GENERATION ──────────────────────────────────────────────────

    @staticmethod
    def generate_qr_code_base64(patient_id: str) -> str | None:
        """
        Generate a QR code image for a patient's status page.
        Returns a base64-encoded PNG data URI string, or None if qrcode not available.
        """
        try:
            import qrcode
            from io import BytesIO
            import base64

            url = f"{BASE_URL}/?patient={patient_id}"
            qr = qrcode.QRCode(box_size=10, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format="PNG")
            img_b64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_b64}"
        except ImportError:
            return None
        except Exception as e:
            print(f"[Harness] QR generation error: {e}")
            return None

    def get_qr_url(self, patient_id: str) -> str:
        """Get the URL encoded in the QR code for a patient."""
        return f"{BASE_URL}/?patient={patient_id}"

    def get_patient_status_url(self, patient_id: str) -> str:
        """Get the full patient status page URL for sharing."""
        return f"{BASE_URL}/?patient={patient_id}"

    # ─── DASHBOARD STATS ─────────────────────────────────────────────────────

    def get_all_dashboard_stats(self) -> dict:
        """Get aggregate stats across all departments for today."""
        stats = {}
        for test in TEST_TYPES:
            stats[test] = get_department_stats(test)
        return stats

    # ─── ANALYTICS / REPORTS ──────────────────────────────────────────────────

    def get_analytics_summary(self, start_date: str, end_date: str) -> dict:
        """
        Get aggregated KPI data for the analytics dashboard across a date range.
        Returns:
          total_patients, total_tests, avg_daily, peak_day, peak_count,
          busiest_dept, dept_stats (per-department status counts)
        """
        from utils.db import get_daily_patient_counts, get_department_stats_date_range
        from utils.queue import calculate_wait_time
        from datetime import datetime

        daily = get_daily_patient_counts(days=30)
        total_patients = sum(d["count"] for d in daily)

        # Average daily
        num_days = len(daily) if daily else 1
        avg_daily = round(total_patients / num_days, 1)

        # Peak day
        peak_day = max(daily, key=lambda d: d["count"]) if daily else {"date": "—", "count": 0}
        peak_date_str = peak_day.get("date", "—")
        try:
            peak_date_dt = datetime.fromisoformat(peak_date_str).strftime("%d-%b-%Y")
        except Exception:
            peak_date_dt = peak_date_str

        # Per-department stats in date range
        dept_stats = {}
        for test in TEST_TYPES:
            dept_stats[test] = get_department_stats_date_range(test, start_date, end_date)

        # Busiest department (most total tests)
        busiest_dept = max(dept_stats, key=lambda d: sum(dept_stats[d].values())) if dept_stats else "—"
        total_tests = sum(sum(s.values()) for s in dept_stats.values())

        return {
            "total_patients": total_patients,
            "total_tests": total_tests,
            "avg_daily": avg_daily,
            "peak_day": {"date": peak_date_dt, "count": peak_day.get("count", 0)},
            "busiest_dept": busiest_dept,
            "dept_stats": dept_stats,
        }

    def get_daily_trends(self, days: int = 30) -> dict:
        """
        Get daily patient registration counts for the last N days.
        Returns dict with 'dates' (list) and 'counts' (list) for charting.
        """
        from utils.db import get_daily_patient_counts
        data = get_daily_patient_counts(days)
        return {
            "dates": [d["date"] for d in data],
            "counts": [d["count"] for d in data],
            "raw": data,
        }

    def get_department_performance(self, start_date: str, end_date: str) -> dict:
        """
        Get performance metrics for all departments across a date range.
        Returns dict with per-dept duration stats and status breakdowns.
        """
        from utils.db import get_department_stats_date_range, get_test_duration_stats

        results = {}
        for test in TEST_TYPES:
            stats = get_department_stats_date_range(test, start_date, end_date)
            durations = get_test_duration_stats(test)
            total = sum(stats.values())
            results[test] = {
                "stats": stats,
                "durations": durations,
                "total": total,
            }
        return results

    # ─── DATA EXPORT ──────────────────────────────────────────────────────────

    def export_today_csv(self) -> str:
        """
        Export today's patient data as CSV string.
        Columns: Patient ID, Name, Mobile, Age, Gender, Test, Token, Room, Status, ETA
        """
        from utils.db import get_today_patients_with_tests
        from utils.queue import calculate_expected_time

        patients = get_today_patients_with_tests()
        if not patients:
            return ""

        import csv
        import io

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "Patient ID", "Name", "Mobile", "Age", "Gender",
            "Test", "Token #", "Room", "Status", "ETA"
        ])

        for p in patients:
            p_id = p.get("patient_id", "")
            name = p.get("name", "")
            mobile = p.get("mobile", "")
            age = p.get("age", "")
            gender = p.get("gender", "")
            tests = p.get("tests", [])
            if tests:
                for t in tests:
                    tn = t.get("test_name", "")
                    token = t.get("token_number", "")
                    room = t.get("room", "")
                    status = STATUS_LABELS.get(t.get("status", ""), t.get("status", ""))
                    eta = calculate_expected_time(tn, t.get("queue_position", 0))
                    writer.writerow([p_id, name, mobile, age, gender, tn, token, room, status, eta])
            else:
                writer.writerow([p_id, name, mobile, age, gender, "", "", "", "", ""])

        return buf.getvalue()

    # ─── ACTIVITY LOG ─────────────────────────────────────────────────────────

    def get_recent_activity(self, limit: int = 50) -> list[dict]:
        """
        Get recent activity log entries for the audit trail view.
        Returns list with keys: patient_id, patient_name, message_type,
        message_text, actor, sent_at.
        """
        from utils.db import get_recent_activity
        return get_recent_activity(limit)

    # ═══════════════════════════════════════════════════════════════════════════
    #  IPD (INPATIENT) OPERATIONS
    # ═══════════════════════════════════════════════════════════════════════════

    def admit_to_ipd(self, patient_id: str, patient_name: str, mobile: str,
                     source: str = "direct", admitting_doctor: str = "",
                     diagnosis_primary: str = "", diagnosis_secondary: str = "",
                     bed_id: str = "", notes: str = "") -> dict:
        """
        Admit a patient to the Inpatient Department.
        Returns: {"success": bool, "message": str, "admission": dict | None}
        """
        from utils.ipd import admit_patient
        return admit_patient(
            patient_id, patient_name, mobile, source, admitting_doctor,
            diagnosis_primary, diagnosis_secondary, bed_id, notes
        )

    def discharge_from_ipd(self, admission_id: str, discharge_type: str = "normal",
                           discharge_summary: str = "", follow_up_date: str = "") -> dict:
        """Discharge a patient from IPD."""
        from utils.ipd import discharge_patient
        return discharge_patient(admission_id, discharge_type, discharge_summary, follow_up_date)

    def get_ipd_ward_data(self) -> dict:
        """
        Get full IPD ward data for the dashboard.
        Returns: {
            "occupancy": list[ward_stats],
            "active_admissions": list[admission],
            "available_beds": list[bed],
        }
        """
        from utils.ipd import get_ward_occupancy, get_active_admissions, get_available_beds
        return {
            "occupancy": get_ward_occupancy(),
            "active_admissions": get_active_admissions(),
            "available_beds": get_available_beds(),
        }

    def record_ipd_vitals(self, admission_id: str, bp_systolic: int = 0,
                          bp_diastolic: int = 0, pulse: int = 0,
                          temperature: float = 0.0, spo2: int = 0,
                          weight: float = 0.0, recorded_by: str = "") -> dict:
        """Record vital signs for an admitted patient."""
        from utils.ipd import record_vitals
        return record_vitals(admission_id, bp_systolic, bp_diastolic,
                             pulse, temperature, spo2, weight, recorded_by)

    def add_ipd_note(self, admission_id: str, doctor_name: str, notes: str,
                     note_type: str = "progress") -> dict:
        """Add a clinical note for an admitted patient."""
        from utils.ipd import add_ipd_note
        return add_ipd_note(admission_id, doctor_name, notes, note_type)

    def get_ipd_patient_status(self, patient_id: str) -> dict | None:
        """Get active admission for a patient. None if not admitted."""
        from utils.ipd import get_ipd_patient_status
        return get_ipd_patient_status(patient_id)

    def update_bed_status(self, bed_id: str, new_status: str) -> bool:
        """Update a bed's status (cleaning, maintenance, available)."""
        from utils.ipd import update_bed_status
        return update_bed_status(bed_id, new_status)

    # ═══════════════════════════════════════════════════════════════════════════
    #  INVENTORY / PHARMACY METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_inventory_summary(self) -> dict:
        """Get inventory dashboard summary stats."""
        from utils.inventory import get_inventory_summary
        return get_inventory_summary()

    def get_categories(self, category_type: str = "") -> list[dict]:
        """Get inventory categories."""
        from utils.inventory import get_categories
        return get_categories(category_type)

    def create_item(self, name: str, category_id: str, unit: str = "tab",
                    generic_name: str = "", manufacturer: str = "",
                    reorder_level: float = 10.0, reorder_qty: float = 50.0,
                    sku_code: str = "", hsn_code: str = "") -> dict:
        """Create a new inventory item."""
        from utils.inventory import create_item
        return create_item(name, category_id, unit, generic_name, manufacturer,
                           reorder_level, reorder_qty, sku_code, hsn_code)

    def get_items(self, category_id: str = "", search: str = "",
                  active_only: bool = True) -> list[dict]:
        """Get inventory items with optional filters."""
        from utils.inventory import get_items
        return get_items(category_id, search, active_only)

    def add_batch(self, item_id: str, batch_no: str, quantity: float,
                  unit_rate: float, mrp: float = 0.0,
                  mfg_date: str = "", expiry_date: str = "",
                  supplier_id: str = "", grn_ref: str = "",
                  is_cold_chain: bool = False, created_by: str = "") -> dict:
        """Add stock batch (purchase receipt)."""
        from utils.inventory import add_batch
        return add_batch(item_id, batch_no, quantity, unit_rate, mrp,
                         mfg_date, expiry_date, supplier_id, grn_ref,
                         is_cold_chain, created_by)

    def get_batches(self, item_id: str = "", low_stock_only: bool = False,
                    expiring_within_days: int = 0) -> list[dict]:
        """Get inventory batches with optional filters."""
        from utils.inventory import get_batches
        return get_batches(item_id, low_stock_only, expiring_within_days)

    def get_total_stock(self, item_id: str) -> float:
        """Get total available stock for an item."""
        from utils.inventory import get_total_stock
        return get_total_stock(item_id)

    def dispense_item(self, item_id: str, quantity: float,
                      reference_type: str = "dispense",
                      reference_id: str = "", created_by: str = "",
                      notes: str = "") -> dict:
        """Dispense stock using FEFO."""
        from utils.inventory import dispense_item
        return dispense_item(item_id, quantity, reference_type,
                             reference_id, created_by, notes)

    def get_movements(self, item_id: str = "", movement_type: str = "",
                      days: int = 30) -> list[dict]:
        """Get stock movement log."""
        from utils.inventory import get_movements
        return get_movements(item_id, movement_type, days)

    def get_low_stock_items(self) -> list[dict]:
        """Get items with stock below reorder level."""
        from utils.inventory import get_low_stock_items
        return get_low_stock_items()

    def get_expiring_batches(self, days: int = 30) -> list[dict]:
        """Get batches expiring within X days."""
        from utils.inventory import get_expiring_batches
        return get_expiring_batches(days)

    def create_audit(self, audit_type: str = "full", notes: str = "",
                     created_by: str = "") -> dict:
        """Create a stock audit session."""
        from utils.inventory import create_audit
        return create_audit(audit_type, notes, created_by)

    def record_audit_item(self, audit_id: str, item_id: str, batch_id: str,
                          expected_qty: float, actual_qty: float,
                          resolution_notes: str = "") -> dict:
        """Record an audit item count."""
        from utils.inventory import record_audit_item
        return record_audit_item(audit_id, item_id, batch_id,
                                 expected_qty, actual_qty, resolution_notes)

    def complete_audit(self, audit_id: str) -> dict:
        """Mark audit as completed."""
        from utils.inventory import complete_audit
        return complete_audit(audit_id)

    def get_audits(self, limit: int = 20) -> list[dict]:
        """Get recent audits."""
        from utils.inventory import get_audits
        return get_audits(limit)

    # ═══════════════════════════════════════════════════════════════════════════
    #  FUTURE: LLM ROUTING
    # ═══════════════════════════════════════════════════════════════════════════
    #  When Phase 2+ LLM integration is enabled, user messages that are not
    #  structured "intents" will be routed here. The Harness will:
    #    1. Retrieve relevant context (chat_history, patient data from db.py)
    #    2. Inject system prompt with safety guardrails
    #    3. Call LLM API (Gemini / Claude / GPT)
    #    4. Save interaction to chat_history
    #    5. Return response to UI
    #
    #  def process_natural_language(self, user_input: str, context: dict) -> str:
    #      """Route natural language input through the LLM engine."""
    #      system_prompt = self._build_system_prompt(context)
    #      llm_response = self._call_llm_api(system_prompt, user_input)
    #      self._save_interaction(user_input, llm_response, context)
    #      return llm_response

    def _build_system_prompt(self, context: dict) -> str:
        """Build a structured natural language control prompt (OSWorld approach)."""
        return f"""
You are the AI Assistant for {self.hospital} — a cardiology department queue management system.

ROLE: Help patients and staff with queries about the queue, test status, and department workflow.

SAFETY GUARDRAILS:
- Never provide medical diagnosis or advice.
- Never share other patients' personal information.
- For medical queries, always say: "Please consult your doctor for medical advice."
- Keep responses concise and helpful in Hindi or English as the user prefers.

CONTEXT:
Today's Date: {self.today}
Available Tests: {', '.join(TEST_TYPES)}
"""

    def _call_llm_api(self, system_prompt: str, user_input: str) -> str:
        """Placeholder for actual LLM API call. Swappable engine."""
        # Phase 1: Return a rule-based fallback
        # Phase 2+: Replace with actual API call to Gemini/Claude/GPT
        return "LLM integration coming in Phase 2. Please check back later."

    def _save_interaction(self, user_input: str, response: str, context: dict):
        """Save LLM interaction to database for memory/training."""
        # Phase 2+: Log to chat_history table
        pass


# ═══════════════════════════════════════════════════════════════════════════════
#  SINGLETON INSTANCE (lazy-loaded via Streamlit session state)
# ═══════════════════════════════════════════════════════════════════════════════

def get_harness() -> Harness:
    """Get or create the singleton Harness instance."""
    if "harness" not in st.session_state:
        st.session_state.harness = Harness()
    return st.session_state.harness
