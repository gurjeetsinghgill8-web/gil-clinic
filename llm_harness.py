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
    get_available_actions, format_token_slip
)
from utils.notifications import (
    registration_message, called_message, completed_message,
    report_ready_message, browser_notification_script,
    request_notification_permission_script
)
from utils.whatsapp import send_whatsapp_message, get_whatsapp_template


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
        log_message(patient_id, mobile, "registration", msg, "browser")

        # ─── WhatsApp Registration Notifications ─────────────────────────────
        # 1. Patient Notification
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

        # 2. Doctor Notification
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

        # 3. Bablu Notification
        if BABLU_MOBILE:
            bablu_wa_msg = (
                f"🏥 *{HOSPITAL_NAME}*\n"
                f"New patient registered:\n"
                f"Name: {name.strip()}\n"
                f"Token: #{token}\n"
                f"Tests: {', '.join(selected_tests)}"
            )
            send_whatsapp_message(BABLU_MOBILE, bablu_wa_msg)

        return {
            "success": True,
            "patient": patient,
            "tests": created_tests,
            "message": f"✅ Patient {name} registered successfully!\nID: {patient_id}",
            "notification": msg,
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
        log_message(patient_id, mobile, "called", msg, "browser")

        # ─── WhatsApp Call Notification ─────────────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "called",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            room=room,
            token=token
        )
        send_whatsapp_message(mobile, patient_wa_msg)

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
        log_message(patient_id, mobile, "completed", msg, "browser")

        # ─── WhatsApp Completed Notification ─────────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "completed",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        send_whatsapp_message(mobile, patient_wa_msg)

        return {
            "success": True,
            "message": f"✅ {test_name} completed for {patient_name}",
            "notification": msg,
        }

    def send_reminder(self, patient_name: str, test_name: str = "", mobile: str = "", token: int = 0) -> dict:
        """
        Send a reminder notification (sound + vibration) to a patient.
        Does NOT change any status — just pushes notification.
        Staff can click this button repeatedly.
        """
        room = ROOM_NAMES.get(test_name, "Cardiology Department")
        msg = (
            f"🔔 Reminder!\n"
            f"{patient_name}, please check your status.\n"
            f"Department: {test_name or 'Cardiology'}\n"
            f"Token: #{token}"
        )

        # ─── WhatsApp Reminder (if mobile available) ─────────────────────────
        if mobile:
            wa_msg = (
                f"🏥 *{HOSPITAL_NAME}*\n"
                f"🔔 *Reminder*\n"
                f"Dear {patient_name}, your test ({test_name}) is pending.\n"
                f"Token #{token} • Room: {room}\n"
                f"Please check your status."
            )
            send_whatsapp_message(mobile, wa_msg)

        return {
            "success": True,
            "message": f"🔔 Reminder sent to {patient_name}",
            "notification": msg,
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

    def mark_report_ready(self, test_id: str, patient_name: str,
                          test_name: str, mobile: str, patient_id: str) -> dict:
        """Mark a test report as ready."""
        success = update_test_status(test_id, "report_ready")
        if not success:
            return {"success": False, "message": "❌ Failed to mark report ready."}

        msg = report_ready_message(patient_name, test_name)
        log_message(patient_id, mobile, "report_ready", msg, "browser")

        # ─── WhatsApp Report Ready Notification ──────────────────────────────
        patient_wa_msg = get_whatsapp_template(
            "report_ready",
            hospital=HOSPITAL_NAME,
            name=patient_name,
            test=test_name
        )
        send_whatsapp_message(mobile, patient_wa_msg)

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

    # ─── NOTIFICATION HELPERS ────────────────────────────────────────────────

    @staticmethod
    def get_notification_script(title: str, body: str, urgent: bool = False) -> str:
        """Get browser notification injection script (with sound + vibration)."""
        return browser_notification_script(title, body, urgent=urgent)

    @staticmethod
    def get_permission_script() -> str:
        """Get notification permission request script."""
        return request_notification_permission_script()

    # ─── TOKEN PRINTING ──────────────────────────────────────────────────────

    def generate_token_slip(self, patient_name: str, patient_id: str,
                            tests: list[dict]) -> str:
        """Generate a formatted token slip for printing."""
        return format_token_slip(patient_name, patient_id, tests)

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

    # ─── DASHBOARD STATS ─────────────────────────────────────────────────────

    def get_all_dashboard_stats(self) -> dict:
        """Get aggregate stats across all departments for today."""
        stats = {}
        for test in TEST_TYPES:
            stats[test] = get_department_stats(test)
        return stats

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
