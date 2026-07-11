"""
Daily Patient List — Printable Today's Report
================================================
Shows all of today's registered patients in a clean table
optimised for printing (Ctrl+P). Accessible to all staff roles.

Architecture: UI → llm_harness.py → db.py
"""
import streamlit as st
from datetime import date, datetime

from llm_harness import get_harness
from utils.config import TEST_TYPES, STATUS_ICONS, STATUS_LABELS, HOSPITAL_NAME, CLINIC_LOGO


def show():
    harness = get_harness()
    now = datetime.now()
    today_str = now.strftime("%d-%b-%Y %I:%M %p")
    today_iso = date.today().isoformat()

    st.title("📄 Today's Patient List")
    st.markdown(f"### {HOSPITAL_NAME}")
    st.markdown(
        f"<span style='color:#888;font-size:0.9rem;'>🗓️ {today_str}</span>"
        f" &middot; "
        f"<span style='color:#888;font-size:0.9rem;'>"
        f"🖨️ Press <strong>Ctrl+P</strong> to print</span>",
        unsafe_allow_html=True,
    )

    # ─── Fetch data ──────────────────────────────────────────────────────────
    from utils.db import get_today_patients, get_tests_for_patient
    patients = get_today_patients()

    if not patients:
        st.info("📭 No patients registered today.")
        return

    # Stats summary
    total_patients = len(patients)
    total_tests = 0
    for p in patients:
        total_tests += len(get_tests_for_patient(p["patient_id"]))
    st.markdown(
        f"👥 **{total_patients}** patient(s), **{total_tests}** total test(s)"
    )

    # ─── Print button (opens in new tab) ────────────────────────────────────
    if st.button("🖨️ Open Printable View", type="primary", use_container_width=True):
        _show_print_view(patients, today_str)
        return

    # ─── Inline preview table ───────────────────────────────────────────────
    st.divider()
    st.markdown("### 📋 Quick Preview")

    for p in patients:
        pid = p.get("patient_id", "")
        name = p.get("name", "")
        mobile = p.get("mobile", "")
        age = p.get("age", "")
        gender = p.get("gender", "")
        tests = get_tests_for_patient(pid)

        with st.container(border=True):
            cols = st.columns([3, 1.5, 1.5, 1])
            with cols[0]:
                st.markdown(f"**{name}**")
                st.caption(f"🆔 {pid} 📱 {mobile}")
            with cols[1]:
                st.markdown(f"{age}/{gender}")
            with cols[2]:
                test_names = ", ".join(t.get("test_name", "?") for t in tests) or "—"
                st.markdown(test_names)
            with cols[3]:
                statuses = ", ".join(
                    f"{STATUS_ICONS.get(t.get('status', ''), '❓')}"
                    for t in tests
                ) or "—"
                st.markdown(statuses)

    st.caption(f"🔍 Total: {total_patients} patients")


def _show_print_view(patients: list, today_str: str):
    """Open a clean print-optimised HTML page with all today's patients."""
    from utils.db import get_tests_for_patient
    from utils.config import STATUS_ICONS, STATUS_LABELS, HOSPITAL_NAME, CLINIC_LOGO

    rows_html = ""
    for p in patients:
        pid = p.get("patient_id", "")
        name = p.get("name", "")
        mobile = p.get("mobile", "")
        age = p.get("age", "")
        gender = p.get("gender", "")
        tests = get_tests_for_patient(pid)
        test_rows = ""
        for t in tests:
            tname = t.get("test_name", "?")
            token = t.get("token_number", "?")
            status = t.get("status", "waiting")
            icon = STATUS_ICONS.get(status, "❓")
            label = STATUS_LABELS.get(status, status)
            test_rows += (
                f"<tr>"
                f"<td>{tname}</td>"
                f"<td>#{token:03d}</td>"
                f"<td>{icon} {label}</td>"
                f"</tr>"
            )
        if not test_rows:
            test_rows = "<tr><td colspan='3' style='color:#999;'>No tests</td></tr>"

        rows_html += f"""
        <div class="patient-card">
            <div class="p-header">
                <span class="p-name">{name}</span>
                <span class="p-meta">{age}/{gender} &middot; {mobile} &middot; {pid}</span>
            </div>
            <table>
                <tr><th>Test</th><th>Token</th><th>Status</th></tr>
                {test_rows}
            </table>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Patient List — {today_str}</title>
<style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{
        font-family:'Segoe UI','Arial',sans-serif;
        background:#f5f5f5; padding:20px;
    }}
    .container {{ max-width:800px; margin:0 auto; }}
    .header {{
        background:linear-gradient(135deg,#667eea,#764ba2);
        color:#fff; padding:20px 24px; border-radius:14px 14px 0 0;
        text-align:center;
    }}
    .header h1 {{ font-size:24px; }}
    .header p {{ font-size:13px; opacity:0.85; margin-top:4px; }}
    .summary {{
        background:#fff; padding:14px 24px; font-size:14px;
        border-left:1px solid #e0e0e0; border-right:1px solid #e0e0e0;
    }}
    .patient-card {{
        background:#fff; padding:16px 24px;
        border-left:1px solid #e0e0e0; border-right:1px solid #e0e0e0;
        border-bottom:1px solid #f0f0f0;
    }}
    .patient-card:last-child {{
        border-radius:0 0 14px 14px; border-bottom:1px solid #e0e0e0;
    }}
    .p-header {{ margin-bottom:8px; }}
    .p-name {{ font-size:16px; font-weight:700; color:#222; }}
    .p-meta {{ font-size:12px; color:#888; margin-left:8px; }}
    table {{ width:100%; border-collapse:collapse; margin-top:4px; }}
    th {{ text-align:left; font-size:11px; text-transform:uppercase; color:#999;
         padding:4px 8px; border-bottom:2px solid #eee; }}
    td {{ padding:6px 8px; border-bottom:1px solid #f5f5f5; font-size:14px; }}
    .footer {{ text-align:center; padding:16px; font-size:11px; color:#aaa; }}
    @media print {{
        body {{ background:#fff; padding:0; }}
        .header {{ border-radius:0; -webkit-print-color-adjust:exact; print-color-adjust:exact; }}
        .patient-card {{ break-inside:avoid; page-break-inside:avoid; }}
    }}
</style></head>
<body>
<div class="container">
    <div class="header">
        <h1>{CLINIC_LOGO} {HOSPITAL_NAME}</h1>
        <p>{today_str} &middot; Daily Patient List</p>
    </div>
    <div class="summary">
        👥 <strong>{len(patients)}</strong> patients registered today
    </div>
    {rows_html}
    <div class="footer">CardioQueue v2 &middot; Generated on {today_str}</div>
</div>
<script>window.print();</script>
</body>
</html>"""

    escaped = html.replace("`", "\\`").replace("${", "\\${")
    js = f"""
    <script>
        var w = window.open('', '_blank');
        w.document.write(`{escaped}`);
        w.document.close();
    </script>
    """
    st.components.v1.html(js, height=0, width=0)
    st.success("🖨️ Print view opened in new tab!")
