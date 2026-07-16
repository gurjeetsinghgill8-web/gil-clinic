#!/usr/bin/env python3
"""
CardioQueue / GIL Clinic — Complete User Manual PDF Generator
43 Utilities + 61 Pages = 104 Modules
"""
import os, sys
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, ListFlowable, ListItem, HRFlowable
)
from reportlab.lib import colors
import textwrap, inspect

# ━━ Color Palette ━━
ACCENT       = HexColor('#4e2eac')
ACCENT_LIGHT = HexColor('#7c5cbf')
TEXT_PRIMARY  = HexColor('#252321')
TEXT_MUTED    = HexColor('#837f76')
BG_SURFACE   = HexColor('#e7e4e0')
BG_PAGE      = HexColor('#f1efec')
WHITE        = colors.white
TABLE_HEADER_COLOR = ACCENT
TABLE_HEADER_TEXT  = WHITE
TABLE_ROW_EVEN     = WHITE
TABLE_ROW_ODD      = BG_SURFACE

W, H = A4  # 595.27, 841.89

# ━━ Styles ━━
styles = getSampleStyleSheet()

s_cover_title = ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=36, leading=44,
                                textColor=WHITE, alignment=TA_CENTER, spaceAfter=12)
s_cover_sub = ParagraphStyle('CoverSub', parent=styles['Normal'], fontSize=16, leading=22,
                              textColor=HexColor('#d4ccf0'), alignment=TA_CENTER, spaceAfter=6)
s_h1 = ParagraphStyle('H1', parent=styles['Heading1'], fontSize=20, leading=26,
                       textColor=ACCENT, spaceBefore=20, spaceAfter=8)
s_h2 = ParagraphStyle('H2', parent=styles['Heading2'], fontSize=15, leading=20,
                       textColor=ACCENT_LIGHT, spaceBefore=14, spaceAfter=6)
s_h3 = ParagraphStyle('H3', parent=styles['Heading3'], fontSize=12, leading=16,
                       textColor=TEXT_PRIMARY, spaceBefore=10, spaceAfter=4)
s_body = ParagraphStyle('Body', parent=styles['Normal'], fontSize=9.5, leading=13.5,
                         textColor=TEXT_PRIMARY, alignment=TA_JUSTIFY, spaceAfter=4)
s_body_small = ParagraphStyle('BodySmall', parent=s_body, fontSize=8.5, leading=11.5)
s_code = ParagraphStyle('Code', parent=styles['Code'], fontSize=7.5, leading=10,
                         fontName='Courier', textColor=HexColor('#1a1a2e'), spaceAfter=3,
                         leftIndent=8, backColor=HexColor('#f5f5ff'))
s_bullet = ParagraphStyle('Bullet', parent=s_body, leftIndent=16, bulletIndent=4, spaceAfter=2)
s_table_header = ParagraphStyle('TH', fontSize=8.5, leading=11, textColor=WHITE, fontName='Helvetica-Bold')
s_table_cell = ParagraphStyle('TC', fontSize=7.8, leading=10.5, textColor=TEXT_PRIMARY)

OUTPUT = "CardioQueue_User_Manual.pdf"

story = []

def add_hr():
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BG_SURFACE))
    story.append(Spacer(1, 4))

def add_bullet(text, style=s_bullet):
    story.append(Paragraph(f"<bullet>&bull;</bullet> {text}", style))

def make_table(data, col_widths=None):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0,0), (-1,0), TABLE_HEADER_COLOR),
        ('TEXTCOLOR', (0,0), (-1,0), TABLE_HEADER_TEXT),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8.5),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.4, HexColor('#cccccc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [TABLE_ROW_EVEN, TABLE_ROW_ODD]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
    ]
    t.setStyle(TableStyle(style_cmds))
    return t

# ══════════════════════════════════════════════════════════════
# COVER PAGE
# ══════════════════════════════════════════════════════════════
story.append(Spacer(1, 80))
story.append(HRFlowable(width="60%", thickness=3, color=ACCENT))
story.append(Spacer(1, 30))
story.append(Paragraph("CardioQueue", s_cover_title))
story.append(Paragraph("GIL Clinic — Complete System", s_cover_sub))
story.append(Spacer(1, 12))
story.append(Paragraph("User Manual & Module Guide", s_cover_sub))
story.append(Spacer(1, 40))
story.append(HRFlowable(width="60%", thickness=1, color=HexColor('#d4ccf0')))
story.append(Spacer(1, 20))
story.append(Paragraph("43 Utility Modules + 61 Page Modules = 104 Total Modules", s_cover_sub))
story.append(Spacer(1, 10))
story.append(Paragraph(f"Generated: {datetime.now().strftime('%d-%b-%Y')}", s_cover_sub))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# TABLE OF CONTENTS
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("TABLE OF CONTENTS", s_h1))
add_hr()
toc_items = [
    "1. System Overview",
    "2. Login & Access Control",
    "3. Role-Based Modules",
    "    3.1 Admin Dashboard",
    "    3.2 Reception / Registration",
    "    3.3 Doctor / OPD",
    "    3.4 Department Staff (ECG, Echo, TMT)",
    "    3.5 Nurse Station",
    "    3.6 Pharmacist & Pharmacy",
    "    3.7 Lab Technician & Radiology",
    "    3.8 Billing & Accountant",
    "    3.9 HR & Payroll",
    "    3.10 Manager / Owner Dashboard",
    "4. Patient Modules",
    "    4.1 Patient Status (Self-Service PWA)",
    "    4.2 Patient Portal",
    "    4.3 Patient Timeline & Tracking",
    "5. Communication Modules",
    "    5.1 Email",
    "    5.2 SMS Manager",
    "    5.3 WhatsApp Business",
    "    5.4 Push Notifications",
    "    5.5 Voice Call & Video Call",
    "6. AI Modules",
    "    6.1 AI Dietician",
    "    6.2 AI Report Explainer",
    "    6.3 AI Prescription",
    "    6.4 AI Voice Agent",
    "    6.5 AI Triage & AI Receptionist",
    "7. System & Admin Tools",
    "    7.1 Backup & Restore",
    "    7.2 Encryption & Audit",
    "    7.3 RBAC & Compliance",
    "    7.4 Monitoring & Logging",
    "    7.5 Multi-Branch",
    "8. Finance & Inventory",
    "    8.1 Finance (P&L)",
    "    8.2 GST Compliance",
    "    8.3 Inventory & Purchase",
    "    8.4 Vendor Management",
    "9. IPD & Emergency",
    "10. Quick Reference — Default Credentials",
]
for item in toc_items:
    story.append(Paragraph(item, s_body if not item.startswith("    ") else s_body_small))
story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 1. SYSTEM OVERVIEW
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("1. System Overview", s_h1))
add_hr()
story.append(Paragraph(
    "CardioQueue is a comprehensive hospital management system designed for GIL Clinic. "
    "It handles patient registration, department queue management, billing, pharmacy, "
    "inventory, HR, finance, AI-assisted tools, and multi-channel communication — all "
    "in one Streamlit web application.", s_body))
story.append(Spacer(1, 6))

story.append(Paragraph("Architecture", s_h2))
story.append(Paragraph("UI Pages → llm_harness.py → db.py (SQLite + Google Sheets + Local JSON)", s_code))
story.append(Spacer(1, 2))
add_bullet("Frontend: Streamlit (multi-page, role-based navigation)")
add_bullet("Orchestration: <b>llm_harness.py</b> — central action router")
add_bullet("Database: SQLite primary, Google Sheets fallback, local JSON cache")
add_bullet("PWA: manifest.json + service-worker.js for Add-to-Home-Screen")
add_bullet("Notifications: Browser push, WhatsApp (Meta Cloud API), SMS, Email")

story.append(Paragraph("How to Start", s_h2))
story.append(Paragraph(
    "Run: <b>streamlit run app.py</b> from the project root. "
    "Open the URL shown in terminal (default http://localhost:8501).", s_body))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 2. LOGIN & ACCESS
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("2. Login & Access Control", s_h1))
add_hr()
story.append(Paragraph("Login Flow", s_h2))
add_bullet("On first load, you see a gradient card grid of staff members grouped by role.")
add_bullet("Click your name → enter your PIN (4-6 digits).")
add_bullet("Admin: click name → enter password <b>gurjas@123</b>.")
add_bullet('Patients: click "Patient" button at bottom → goes to self-service status page.')
add_bullet('Admin toggle link at bottom switches to "Password Login" mode (for keyboard entry).')

story.append(Paragraph("Role-Based Access (RBAC)", s_h2))
story.append(Paragraph(
    "Every page is protected by role. The system has 12 roles with granular permissions. "
    "See <i>pages/RBAC.py</i> for the permission matrix viewer.", s_body))

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 3. ROLE-BASED MODULES
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("3. Role-Based Modules", s_h1))
add_hr()

# 3.1 Admin
story.append(Paragraph("3.1 Admin Dashboard", s_h2))
add_bullet("<b>Page:</b> Admin / Admin_Panel")
add_bullet("Full system KPIs: total patients today, revenue, pending reports")
add_bullet("User management: add/edit staff, reset PINs")
add_bullet("System-wide settings and configuration")
add_bullet("Access all modules across all departments")

# 3.2 Reception
story.append(Paragraph("3.2 Reception / Registration", s_h2))
add_bullet("<b>Pages:</b> Registration, Reception, Appointments")
add_bullet("Register new patients: name, mobile, age, gender, address, doctor reference")
add_bullet("Book appointments (walk-in or scheduled)")
add_bullet("Assign tests (ECG, Echo, TMT, OPD, Lab, X-Ray, Ultrasound)")
add_bullet("Print token slip with department, test name, token number, wait time")
add_bullet("Bulk import patients from CSV via <i>pages/BulkImport.py</i>")

# 3.3 Doctor
story.append(Paragraph("3.3 Doctor / OPD", s_h2))
add_bullet("<b>Pages:</b> Doctor, OPD, FollowUp")
add_bullet("View all patients assigned for consultation")
add_bullet("Add OPD consultation notes per test")
add_bullet("Prescribe medicines → flows to Pharmacy/Billing")
add_bullet("View patient history, past reports, timeline")
add_bullet("Mark consultation complete → patient moves to next stage")

# 3.4 Department Staff
story.append(Paragraph("3.4 Department Staff (ECG, Echo, TMT)", s_h2))
add_bullet("<b>Pages:</b> ECG, Echo, TMT")
add_bullet("Live queue of patients waiting for that test")
add_bullet("Call next patient (triggers WhatsApp notification + beep)")
add_bullet("Mark test in progress / complete")
add_bullet("Auto-refresh every 5 seconds")
add_bullet("Room assignments per technician")

# 3.5 Nurse
story.append(Paragraph("3.5 Nurse Station", s_h2))
add_bullet("<b>Page:</b> Nurse")
add_bullet("View all today's patients across all departments")
add_bullet("Record vitals (BP, pulse, temperature, SpO2, weight)")
add_bullet("Filter patients by waiting/called/in-progress status")

# 3.6 Pharmacy
story.append(Paragraph("3.6 Pharmacist & Pharmacy", s_h2))
add_bullet("<b>Pages:</b> Pharmacist, Pharmacy")
add_bullet("View pending prescriptions from doctors")
add_bullet("Dispense medicines (auto-deduct from inventory)")
add_bullet("Low stock alerts and expiring batch warnings")
add_bullet("Medicine master: add/edit medicines with batch tracking")

# 3.7 Lab
story.append(Paragraph("3.7 Lab Technician & Radiology", s_h2))
add_bullet("<b>Pages:</b> Lab_Technician, Lab, Radiology, XRay, Ultrasound")
add_bullet("Sample collection workflow: collect → process → verify → report")
add_bullet("Upload test results / reports (PDF, images)")
add_bullet("Mark report ready → notifies patient via WhatsApp/SMS")

# 3.8 Billing
story.append(Paragraph("3.8 Billing & Accountant", s_h2))
add_bullet("<b>Pages:</b> Billing, Accountant, Finance")
add_bullet("Create bills with test items, medicines, discounts")
add_bullet("Auto-GST calculation (HSN/SAC codes)")
add_bullet("Payment modes: Cash, Card, UPI, Insurance")
add_bullet("View today's billing summary, pending payments")
add_bullet("P&L dashboard, expense tracking, monthly summaries")

# 3.9 HR
story.append(Paragraph("3.9 HR & Payroll", s_h2))
add_bullet("<b>Pages:</b> HR, Payroll")
add_bullet("Staff directory: all employees with roles, contact, salary")
add_bullet("Attendance tracking (present/absent/leave)")
add_bullet("Leave request management (apply/approve/reject)")
add_bullet("Monthly payroll: calculate salary, deductions, net pay")
add_bullet("Payslip generation")

# 3.10 Manager
story.append(Paragraph("3.10 Manager / Owner Dashboard", s_h2))
add_bullet("<b>Pages:</b> Manager_Dashboard, Owner_Dashboard, Reports, Analytics")
add_bullet("Daily, weekly, monthly revenue charts")
add_bullet("Patient volume trends, department-wise load")
add_bullet("Top tests performed, doctor referral analysis")
add_bullet("Export reports as CSV/PDF")
add_bullet("Owner dashboard: full business KPIs at a glance")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 4. PATIENT MODULES
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("4. Patient Modules", s_h1))
add_hr()

story.append(Paragraph("4.1 Patient Status (Self-Service PWA)", s_h2))
add_bullet("<b>Page:</b> Patient_Status")
add_bullet("Mobile-first PWA: Add to Home Screen on phone")
add_bullet("Auto-load via QR scan: <i>?patient=ID</i>")
add_bullet("Or enter mobile number: <i>?mobile=NUMBER</i>")
add_bullet("Live status bar showing journey progress")
add_bullet("Sound + vibration when called or report ready")
add_bullet("Auto-refresh every 5 seconds")
add_bullet("Missed call alert detection")
add_bullet("Bilingual: Hindi + English")

story.append(Paragraph("4.2 Patient Portal", s_h2))
add_bullet("<b>Page:</b> Patient_Portal")
add_bullet("Self-service appointment booking (date, time, test type)")
add_bullet("View past appointments and test history")
add_bullet("Download reports")
add_bullet("Submit feedback")

story.append(Paragraph("4.3 Patient Timeline & Tracking", s_h2))
add_bullet("<b>Pages:</b> Patient_Timeline, Patient_Tracking")
add_bullet("Timeline: full journey from registration to report delivery")
add_bullet("Tracking: live flow monitor across all departments")
add_bullet("Search by Patient ID or mobile number")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 5. COMMUNICATION
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("5. Communication Modules", s_h1))
add_hr()

story.append(Paragraph("5.1 Email", s_h2))
add_bullet("<b>Page:</b> Email | <b>Utils:</b> utils/email.py")
add_bullet("Configure SMTP settings in the page")
add_bullet("Send single or bulk emails")
add_bullet("Report email templates (test results in HTML)")
add_bullet("Email log viewer with sent/failed status")

story.append(Paragraph("5.2 SMS Manager", s_h2))
add_bullet("<b>Page:</b> SMS_Upgrade | <b>Utils:</b> utils/sms_upgrade.py")
add_bullet("Create and manage SMS templates (DLT-compliant)")
add_bullet("Send appointment reminders, report alerts, promotional SMS")
add_bullet("Template variables: {patient_name}, {doctor}, {time}, etc.")

story.append(Paragraph("5.3 WhatsApp Business", s_h2))
add_bullet("<b>Page:</b> WhatsAppUpgrade | <b>Utils:</b> utils/whatsapp_upgrade.py")
add_bullet("Meta Cloud API integration (send template messages)")
add_bullet("Send appointment confirmations, call alerts, report ready notifications")
add_bullet("Configure PHONE_NUMBER_ID and ACCESS_TOKEN")
add_bullet("Legacy WhatsApp also available via utils/whatsapp.py")

story.append(Paragraph("5.4 Push Notifications", s_h2))
add_bullet("<b>Page:</b> PushNotifications | <b>Utils:</b> utils/push_notifications.py")
add_bullet("Register devices for browser push")
add_bullet("Send targeted or broadcast notifications")
add_bullet("Notification categories: appointment, report, promotion, alert")

story.append(Paragraph("5.5 Voice Call & Video Call", s_h2))
add_bullet("<b>Pages:</b> VoiceCall, VideoCall")
add_bullet("Voice: initiate calls, view call history, call logs")
add_bullet("Video: create telemedicine rooms, start/end sessions")
add_bullet("Room management for doctor-patient video consultations")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 6. AI MODULES
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("6. AI Modules", s_h1))
add_hr()

story.append(Paragraph("6.1 AI Dietician", s_h2))
add_bullet("<b>Page:</b> AI_Dietician | <b>Utils:</b> utils/ai_dietician.py")
add_bullet("Generate personalized meal plans based on:")
add_bullet("  - Disease/condition (diabetes, hypertension, heart disease, etc.)", s_body_small)
add_bullet("  - Dietary preference (vegetarian, vegan, non-veg)", s_body_small)
add_bullet("  - Calorie target", s_body_small)
add_bullet("Pre-defined diet plans for common conditions")
add_bullet("Custom meal plan generation")

story.append(Paragraph("6.2 AI Report Explainer", s_h2))
add_bullet("<b>Page:</b> AI_Report_Explainer | <b>Utils:</b> utils/ai_report_explainer.py")
add_bullet("Enter test name + value → get plain-English explanation")
add_bullet("Shows reference ranges, flag (normal/high/low)")
add_bullet("Contextual advice based on deviation")
add_bullet("Covers 50+ medical tests with REFERENCE_RANGES")

story.append(Paragraph("6.3 AI Prescription", s_h2))
add_bullet("<b>Page:</b> AI_Prescription | <b>Utils:</b> utils/ai_prescription.py")
add_bullet("Medicine database with dosages, contraindications")
add_bullet("Drug-drug interaction checker")
add_bullet("Suggest medicines for common conditions")
add_bullet("Generate formatted prescription with doctor info")

story.append(Paragraph("6.4 AI Voice Agent", s_h2))
add_bullet("<b>Page:</b> AI_VoiceAgent | <b>Utils:</b> utils/ai_voice_agent.py")
add_bullet("Voice agent session management")
add_bullet("Agent types: appointment booking, general inquiry, prescription refill")
add_bullet("Create and monitor voice agent sessions")

story.append(Paragraph("6.5 AI Triage & AI Receptionist", s_h2))
add_bullet("<b>Pages:</b> AI_Triage, AI_Receptionist")
add_bullet("AI Triage: symptom assessment → recommend department priority")
add_bullet("AI Receptionist: automated patient check-in and guidance")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 7. SYSTEM & ADMIN
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("7. System & Admin Tools", s_h1))
add_hr()

story.append(Paragraph("7.1 Backup & Restore", s_h2))
add_bullet("<b>Page:</b> Backup | <b>Utils:</b> utils/backup.py")
add_bullet("Create database backups on demand")
add_bullet("View backup history with timestamps and sizes")
add_bullet("Backup stats: total size, count, last backup")

story.append(Paragraph("7.2 Encryption & Audit", s_h2))
add_bullet("<b>Page:</b> EncryptionPage | <b>Utils:</b> utils/encryption.py, utils/audit.py")
add_bullet("Encryption: AES-256-GCM via Fernet, encrypt/decrypt text, PII protection")
add_bullet("Audit: SHA-256 chained audit log, verify chain integrity")
add_bullet("Every action logged immutably")

story.append(Paragraph("7.3 RBAC & Compliance", s_h2))
add_bullet("<b>Pages:</b> RBAC, Compliance")
add_bullet("RBAC: 12-role permission matrix viewer, check permissions")
add_bullet("Compliance: patient consent management, data rights requests")
add_bullet("Consent types: treatment, data sharing, research, billing")

story.append(Paragraph("7.4 Monitoring & Logging", s_h2))
add_bullet("<b>Pages:</b> Monitoring, Logging")
add_bullet("Monitoring: system health dashboard, DB size, page count, metrics")
add_bullet("Logging: centralized log viewer with search, filter by level")
add_bullet("Record and review all system events")

story.append(Paragraph("7.5 Multi-Branch", s_h2))
add_bullet("<b>Page:</b> MultiBranch | <b>Utils:</b> utils/multi_branch.py")
add_bullet("Add and manage multiple clinic branches")
add_bullet("View all branches in the network")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 8. FINANCE & INVENTORY
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("8. Finance & Inventory", s_h1))
add_hr()

story.append(Paragraph("8.1 Finance (P&L)", s_h2))
add_bullet("<b>Page:</b> Finance, Accountant, Owner_Dashboard | <b>Utils:</b> utils/finance.py")
add_bullet("Profit & Loss dashboard with revenue vs expenses")
add_bullet("Add expenses (rent, salary, utilities, supplies)")
add_bullet("Monthly summary with category breakdown")
add_bullet("Expense categories: 10+ predefined")

story.append(Paragraph("8.2 GST Compliance", s_h2))
add_bullet("<b>Page:</b> GST | <b>Utils:</b> utils/gst.py")
add_bullet("HSN/SAC code maps for medical services and products")
add_bullet("Auto-GST calculation (5%, 12%, 18%, 28%)")
add_bullet("GST invoice generation")
add_bullet("Tax summary reports")

story.append(Paragraph("8.3 Inventory & Purchase", s_h2))
add_bullet("<b>Page:</b> Inventory, Purchase | <b>Utils:</b> utils/inventory.py, utils/purchase.py")
add_bullet("Inventory categories, items, batch tracking (FEFO)")
add_bullet("Stock movements: in/out/transfer/adjustment")
add_bullet("Low stock alerts, expiring batch warnings")
add_bullet("Purchase orders with approval workflow")
add_bullet("Stock audit: create audit session → count → resolve variances")

story.append(Paragraph("8.4 Vendor Management", s_h2))
add_bullet("<b>Page:</b> Vendor | <b>Utils:</b> utils/vendor.py")
add_bullet("Vendor registry with GST, contact, ratings")
add_bullet("Track purchases by vendor")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 9. IPD & EMERGENCY
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("9. IPD & Emergency", s_h1))
add_hr()

story.append(Paragraph("IPD (In-Patient Department)", s_h2))
add_bullet("<b>Page:</b> IPD_Ward | <b>Utils:</b> utils/ipd.py")
add_bullet("Admit patients to wards/beds")
add_bullet("Bed management: view occupied/available beds")
add_bullet("Discharge summary generation")
add_bullet("Track IPD billing (room rent, procedures, medicines)")

story.append(Paragraph("Emergency", s_h2))
add_bullet("<b>Page:</b> Emergency | <b>Utils:</b> utils/emergency.py")
add_bullet("Rapid patient registration in emergency mode")
add_bullet("Priority-based queue (critical → serious → stable)")
add_bullet("Quick vitals recording")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# 10. DEFAULT CREDENTIALS
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("10. Quick Reference — Default Credentials", s_h1))
add_hr()

cred_data = [
    [Paragraph("Role", s_table_header), Paragraph("Name", s_table_header), Paragraph("PIN / Password", s_table_header)],
    ["Admin", "Admin", "gurjas@123"],
    ["Reception", "Receptionist", "1234"],
    ["ECG", "ECG Technician", "1234"],
    ["Echo", "Echo Technician", "1234"],
    ["TMT", "TMT Technician", "1234"],
    ["OPD", "OPD Staff", "1234"],
    ["Manager", "Manager", "1234"],
]
cred_table = Table(cred_data, colWidths=[120, 180, 180])
cred_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), ACCENT),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,0), 10),
    ('GRID', (0,0), (-1,-1), 0.5, HexColor('#cccccc')),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [WHITE, BG_SURFACE]),
    ('TOPPADDING', (0,0), (-1,-1), 6),
    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
]))
story.append(cred_table)
story.append(Spacer(1, 12))
add_bullet("PIN is 4-6 digit numeric (new users). Legacy text passwords also supported.")
add_bullet("Auto-seed: 7 default users created when database is empty.")
add_bullet("Change passwords/PINs from Admin panel.")

story.append(PageBreak())

# ══════════════════════════════════════════════════════════════
# COMPLETE MODULE LIST
# ══════════════════════════════════════════════════════════════
story.append(Paragraph("Appendix A: Complete Module List", s_h1))
add_hr()
story.append(Paragraph("43 Utility Modules + 61 Page Modules = 104 Modules", s_body))
story.append(Spacer(1, 6))

utils_list = sorted([f.replace('.py','') for f in os.listdir('utils') if f.endswith('.py') and f != '__init__.py'])
pages_list = sorted([f.replace('.py','') for f in os.listdir('pages') if f.endswith('.py') and f not in ('__init__', '_department_base')])

# Utility modules in 3 columns
utils_cols = [[''] * 15 for _ in range(3)]
for i, u in enumerate(utils_list):
    utils_cols[i % 3][i // 3] = u

util_table_data = [[Paragraph(h, s_table_header) for h in ["Utility Modules (43)"]]]
# Split into chunks of 15 per column
for row_idx in range(15):
    row = []
    for col_idx in range(1):
        row.append(Paragraph(utils_list[row_idx] if row_idx < len(utils_list) else "", s_table_cell))
    util_table_data.append(row)

util_table = Table([[Paragraph(f"<b>Utility Modules — {len(utils_list)} total</b>", s_body)]])
story.append(util_table)
story.append(Spacer(1, 4))

# Write as 3-column grid
utils_per_col = (len(utils_list) + 2) // 3
cols_data = []
for c in range(3):
    start = c * utils_per_col
    end = min(start + utils_per_col, len(utils_list))
    col = "<br/>".join(utils_list[start:end]) if start < end else ""
    cols_data.append(Paragraph(col, s_code))
col_grid = Table([cols_data], colWidths=[170, 170, 170])
col_grid.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
]))
story.append(col_grid)

story.append(Spacer(1, 12))

# Page modules in 3 columns
pages_per_col = (len(pages_list) + 2) // 3
pcols_data = []
for c in range(3):
    start = c * pages_per_col
    end = min(start + pages_per_col, len(pages_list))
    col = "<br/>".join(pages_list[start:end]) if start < end else ""
    pcols_data.append(Paragraph(col, s_code))
pcol_grid = Table([pcols_data], colWidths=[170, 170, 170])
pcol_grid.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('RIGHTPADDING', (0,0), (-1,-1), 8),
]))
story.append(Paragraph(f"<b>Page Modules — {len(pages_list)} total</b>", s_body))
story.append(Spacer(1, 4))
story.append(pcol_grid)

# ══════════════════════════════════════════════════════════════
# BUILD
# ══════════════════════════════════════════════════════════════
doc = SimpleDocTemplate(
    OUTPUT, pagesize=A4,
    leftMargin=20*mm, rightMargin=20*mm,
    topMargin=20*mm, bottomMargin=20*mm,
    title="CardioQueue GIL Clinic User Manual",
    author="GIL Clinic",
    subject="Complete System User Manual — 104 Modules"
)

doc.build(story)
print(f"✅ PDF generated: {OUTPUT}")
print(f"   Pages: ~{len(story)} story elements")
print(f"   File size: {os.path.getsize(OUTPUT) / 1024:.1f} KB")
