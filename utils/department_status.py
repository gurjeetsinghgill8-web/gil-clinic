"""
Department Status — Working / Under Construction Tracker
=========================================================
Defines which departments are fully functional and which are under construction.
Home page shows Green for working, Red for under-construction with popup.
"""
from typing import Dict, Tuple

# ─── Department Status ──────────────────────────────────────────────────────
# True  = ✅ Working (fully functional / LIVE)
# False = ❌ Under Construction (shows popup/banner)
DEPARTMENT_STATUS: Dict[str, bool] = {
    # ── Core Clinical Departments ──
    "ECG":          True,    # ✅ Working via _department_base
    "Echo":         True,    # ✅ Working via _department_base
    "TMT":          True,    # ✅ Working via _department_base
    "OPD":          True,    # ✅ Working via _department_base
    "X-Ray":        True,    # ✅ Working via _department_base
    "Ultrasound":   True,    # ✅ Working via _department_base
    "Lab":          True,    # ✅ Working (Lab.py)

    # ── Patient Flow ──
    "Reception":    True,    # ✅ Working
    "Doctor":       True,    # ✅ Working
    "Nurse":        True,    # ✅ Working
    "Patient Status": True,  # ✅ Working
    "Patient Timeline": False,# ❌ Under Construction (Skeleton)
    "Patient Tracking": True, # ✅ Working

    # ── Management ──
    "Manager":      True,    # ✅ Working
    "Admin":        True,    # ✅ Working
    "Owner Dashboard": True, # ✅ Working

    # ── Pharmacy & Inventory ──
    "Pharmacy":     True,    # ✅ Working
    "Pharmacist":   True,    # ✅ Working
    "Inventory":    True,    # ✅ Working
    "Purchase Orders": True, # ✅ Working
    "Vendors":      True,    # ✅ Working

    # ── Billing & Finance ──
    "Billing":      True,    # ✅ Working
    "Accountant":   True,    # ✅ Working
    "Finance":      True,    # ✅ Working
    "GST":          True,    # ✅ Working

    # ── Appointments & Scheduling ──
    "Appointments": True,    # ✅ Working
    "Daily List":   True,    # ✅ Working
    "Follow-up":    True,    # ✅ Working

    # ── HR & Payroll ──
    "HR":           True,    # ✅ Working
    "Payroll":      True,    # ✅ Working

    # ── AI Features ──
    "AI Triage":        True,  # ✅ Working
    "AI Follow-up":     True,  # ✅ Working
    "AI Receptionist":  True,  # ✅ Working
    "AI Dietician":     True,  # ✅ Working
    "AI Report Explainer": True,# ✅ Working
    "AI Prescription":  True,  # ✅ Working
    "AI Voice Agent":   True,  # ✅ Working

    # ── Communication ──
    "Email":            True,  # ✅ Working
    "SMS":              True,  # ✅ Working
    "WhatsApp":         True,  # ✅ Working
    "Push Notifications": True,# ✅ Working
    "Voice Calls":      True,  # ✅ Working
    "Telemedicine":     True,  # ✅ Working

    # ── Security & Compliance ──
    "RBAC":             True,  # ✅ Working
    "Compliance":       True,  # ✅ Working
    "Encryption":       True,  # ✅ Working
    "Password Management": True,# ✅ Working
    "Activity Log":     True,  # ✅ Working
    "System Logs":      True,  # ✅ Working
    "System Monitoring": True, # ✅ Working
    "Backup":           True,  # ✅ Working

    # ── Multi-Branch ──
    "Multi-Branch":     False, # ❌ Under Construction
    "Reports & Analytics": True, # ✅ Working
    "Feedback":         True,  # ✅ Working

    # ── Additional ──
    "Lab Technician":   True,  # ✅ Working
    "SMS Manager":      True,  # ✅ Working
    "WhatsApp Business": True, # ✅ Working
}

# ── Department Categories for Home Page Display ────────────────────────────
DEPARTMENT_CATEGORIES: Dict[str, Dict[str, Tuple[str, bool]]] = {
    "🩺 Clinical & Diagnostic": {
        "ECG":        ("📊", DEPARTMENT_STATUS.get("ECG", False)),
        "Echo":       ("📊", DEPARTMENT_STATUS.get("Echo", False)),
        "TMT":        ("📊", DEPARTMENT_STATUS.get("TMT", False)),
        "OPD":        ("🩺", DEPARTMENT_STATUS.get("OPD", False)),
        "X-Ray":      ("🩻", DEPARTMENT_STATUS.get("X-Ray", False)),
        "Ultrasound": ("📡", DEPARTMENT_STATUS.get("Ultrasound", False)),
        "Lab":        ("🧪", DEPARTMENT_STATUS.get("Lab", False)),
    },
    "📋 Operations": {
        "Reception":   ("📋", DEPARTMENT_STATUS.get("Reception", False)),
        "Doctor":      ("🩺", DEPARTMENT_STATUS.get("Doctor", False)),
        "Nurse":       ("👩‍⚕️", DEPARTMENT_STATUS.get("Nurse", False)),
        "Appointments":("📅", DEPARTMENT_STATUS.get("Appointments", False)),
        "Billing":     ("💳", DEPARTMENT_STATUS.get("Billing", False)),
        "Pharmacy":    ("💊", DEPARTMENT_STATUS.get("Pharmacy", False)),
    },
    "🏥 Patient Services": {
        "Patient Status":  ("🔍", DEPARTMENT_STATUS.get("Patient Status", False)),
        "Patient Portal":  ("🏥", DEPARTMENT_STATUS.get("Patient Portal", False)),
        "Patient History": ("📋", DEPARTMENT_STATUS.get("Patient History", False)),
        "Patient Timeline":("🕐", DEPARTMENT_STATUS.get("Patient Timeline", False)),
        "Patient Tracking":("📍", DEPARTMENT_STATUS.get("Patient Tracking", False)),
        "Emergency":       ("🚑", DEPARTMENT_STATUS.get("Emergency", False)),
        "IPD Ward":        ("🏥", DEPARTMENT_STATUS.get("IPD Ward", False)),
        "Follow-up":       ("📅", DEPARTMENT_STATUS.get("Follow-up", False)),
    },
    "📈 Management & Finance": {
        "Manager Dashboard": ("📈", DEPARTMENT_STATUS.get("Manager", False)),
        "Admin Panel":       ("👑", DEPARTMENT_STATUS.get("Admin", False)),
        "Owner Dashboard":   ("👑", DEPARTMENT_STATUS.get("Owner Dashboard", False)),
        "Reports & Analytics":("📊", DEPARTMENT_STATUS.get("Reports & Analytics", False)),
        "Inventory":         ("📦", DEPARTMENT_STATUS.get("Inventory", False)),
        "HR":                ("👥", DEPARTMENT_STATUS.get("HR", False)),
        "Payroll":           ("💰", DEPARTMENT_STATUS.get("Payroll", False)),
        "Finance":           ("📊", DEPARTMENT_STATUS.get("Finance", False)),
        "GST":               ("🧾", DEPARTMENT_STATUS.get("GST", False)),
    },
    "🤖 AI Features": {
        "AI Triage":         ("🤖", DEPARTMENT_STATUS.get("AI Triage", False)),
        "AI Follow-up":      ("🤖", DEPARTMENT_STATUS.get("AI Follow-up", False)),
        "AI Receptionist":   ("🤖", DEPARTMENT_STATUS.get("AI Receptionist", False)),
        "AI Dietician":      ("🥗", DEPARTMENT_STATUS.get("AI Dietician", False)),
        "AI Report Explainer":("📄", DEPARTMENT_STATUS.get("AI Report Explainer", False)),
        "AI Prescription":   ("💊", DEPARTMENT_STATUS.get("AI Prescription", False)),
        "AI Voice Agent":    ("🎙️", DEPARTMENT_STATUS.get("AI Voice Agent", False)),
    },
    "🔧 System Administration": {
        "Password Management":("🔐", DEPARTMENT_STATUS.get("Password Management", False)),
        "Activity Log":      ("📋", DEPARTMENT_STATUS.get("Activity Log", False)),
        "Backup":            ("💾", DEPARTMENT_STATUS.get("Backup", False)),
        "Multi-Branch":      ("🏢", DEPARTMENT_STATUS.get("Multi-Branch", False)),
        "System Monitoring": ("📊", DEPARTMENT_STATUS.get("System Monitoring", False)),
        "Compliance":        ("📋", DEPARTMENT_STATUS.get("Compliance", False)),
        "RBAC":              ("🔐", DEPARTMENT_STATUS.get("RBAC", False)),
    },
}


def get_status_icon(module_name: str) -> str:
    """Return ✅ if module is working, ❌ if under construction."""
    return "✅" if DEPARTMENT_STATUS.get(module_name, False) else "❌"


def get_status_badge(module_name: str) -> str:
    """Return HTML badge for module status."""
    working = DEPARTMENT_STATUS.get(module_name, False)
    if working:
        return '<span style="background:linear-gradient(135deg,#00b894,#00d2d3);color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:bold;box-shadow:0 2px 6px rgba(0,184,148,0.2);">✅ LIVE</span>'
    else:
        return '<span style="background:linear-gradient(135deg,#ff7675,#d63031);color:white;padding:2px 8px;border-radius:10px;font-size:0.7rem;font-weight:bold;box-shadow:0 2px 6px rgba(214,48,49,0.25);">🚧 Building</span>'


UNDER_CONSTRUCTION_SCRIPT = """
<script>
function showUnderConstruction(name) {
    const overlay = document.createElement('div');
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(10,14,26,0.8); z-index: 99999;
        display: flex; align-items: center; justify-content: center;
        backdrop-filter: blur(8px);
    `;
    overlay.innerHTML = `
        <div style="background: #ffffff; border-radius: 24px; padding: 3rem 2rem;
                    max-width: 420px; width: 90%; text-align: center;
                    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);
                    border: 1px solid rgba(255,255,255,0.1);
                    animation: cardSlideIn 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);">
            <div style="font-size: 4.5rem; margin-bottom: 1rem; filter: drop-shadow(0 10px 15px rgba(230,126,34,0.3));">🚧</div>
            <h2 style="color: #d63031; margin-bottom: 0.5rem; font-size: 1.6rem; font-weight:800; font-family: system-ui, sans-serif;">Under Construction</h2>
            <p style="color: #636e72; margin-bottom: 1.75rem; font-size: 0.95rem; line-height:1.5; font-family: system-ui, sans-serif;">
                <strong style="color:#2d3436; font-size: 1.05rem;">${name}</strong> module abhi develop ho raha hai.<br>
                Jald hi available hoga!
            </p>
            <div style="background: #ffeaa7; padding: 0.8rem; border-radius: 12px; margin-bottom: 2rem; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);">
                <span style="color: #d63031; font-weight: 700; font-size: 0.9rem;">⏳ Coming Soon</span>
            </div>
            <button onclick="this.closest('div[style*=\\'fixed\\']').remove()"
                    style="background: linear-gradient(135deg, #667eea, #764ba2); color: white;
                           border: none; padding: 0.8rem 2.5rem; border-radius: 12px;
                           font-size: 1rem; cursor: pointer; font-weight: 700;
                           box-shadow: 0 4px 15px rgba(102,126,234,0.4);
                           transition: all 0.2s ease;">
                ✕ Close
            </button>
        </div>
        <style>
            @keyframes cardSlideIn {
                from { opacity: 0; transform: scale(0.8) translateY(30px); }
                to { opacity: 1; transform: scale(1) translateY(0); }
            }
            button:active {
                transform: scale(0.97) !important;
            }
        </style>
    `;
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) {
        if (e.target === this) this.remove();
    });
}
</script>
"""
