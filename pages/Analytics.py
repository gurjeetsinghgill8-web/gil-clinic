"""
Reports & Analytics Dashboard — Manager-only page
===================================================
Provides three tabs:
  1. Overview — KPI cards + daily trend chart
  2. Department Analysis — per-dept status breakdowns
  3. Timing Analysis — average wait/service/completion times

All data flows through: UI → llm_harness.py → db.py
No direct database calls from this page.
"""
import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from llm_harness import get_harness
from utils.config import TEST_TYPES, STATUS_ICONS, STATUS_LABELS

# ─── HELPERS ───────────────────────────────────────────────────────────────────

STATUS_COLORS = {
    "waiting":     "#fdcb6e",
    "called":      "#74b9ff",
    "in_progress": "#e17055",
    "completed":   "#00b894",
    "report_ready": "#6c5ce7",
    "delivered":   "#636e72",
}

def _metric_card(label: str, value: str, delta: str = "", color: str = "#667eea"):
    """Render a single metric card with gradient background."""
    return f"""
    <div style="background:linear-gradient(135deg,{color}15,{color}05);
                padding:1rem 1.2rem;border-radius:12px;border-left:4px solid {color};
                text-align:center;">
        <div style="font-size:0.8rem;color:#636e72;font-weight:500;">{label}</div>
        <div style="font-size:1.8rem;font-weight:700;color:#2d3436;margin:4px 0;">{value}</div>
        <div style="font-size:0.75rem;color:{'#00b894' if delta else '#b2bec3'};">
            {delta}</div>
    </div>
    """


def _color_badge(status: str, count: int) -> str:
    """HTML badge showing a status count with its color."""
    color = STATUS_COLORS.get(status, "#636e72")
    label = STATUS_LABELS.get(status, status)
    return f"""
    <span style="display:inline-block;background:{color}22;color:{color};
                 padding:2px 10px;border-radius:12px;font-size:0.8rem;
                 font-weight:600;margin:2px;">
        {label}: <strong>{count}</strong>
    </span>
    """


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1: OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

def _render_overview_tab(harness, start_date: str, end_date: str):
    """Render KPI cards and daily trend chart."""
    st.markdown("### 📈 Overall Performance")

    summary = harness.get_analytics_summary(start_date, end_date)
    if not summary or not summary.get("total_patients"):
        st.info("📊 No data available for the selected date range.")
        st.caption("Register some patients first and they will appear here.")
        return

    # ─── KPI Cards ─────────────────────────────────────────────────────────
    kpis = [
        ("👥 Total Patients", str(summary["total_patients"]),
         f"in selected range", "#6c5ce7"),
        ("📋 Total Tests", str(summary["total_tests"]),
         f"across {len(TEST_TYPES)} depts", "#00b894"),
        ("📊 Avg Daily", str(summary["avg_daily"]),
         f"patients per day", "#fdcb6e"),
        ("🏆 Busiest Dept", summary["busiest_dept"],
         f"most tests", "#e17055"),
    ]
    cols = st.columns(4)
    for col, (label, value, delta, color) in zip(cols, kpis):
        with col:
            st.markdown(_metric_card(label, value, delta, color),
                        unsafe_allow_html=True)

    # ─── Peak Day card inside a single-column layout ───────────────────────
    peak = summary.get("peak_day", {})
    col_p1, col_p2, _ = st.columns([1, 1, 2])
    with col_p1:
        st.metric("🏅 Peak Day", peak.get("date", "—"),
                  f"{peak.get('count', 0)} patients")
    with col_p2:
        # Completion rate
        total_done = sum(
            s.get("completed", 0) for s in summary.get("dept_stats", {}).values()
        )
        rate = round(total_done / summary["total_tests"] * 100, 1) if summary["total_tests"] else 0
        st.metric("✅ Completion Rate", f"{rate}%",
                  f"{total_done} of {summary['total_tests']} tests")

    st.divider()

    # ─── Daily Trend Chart ─────────────────────────────────────────────────
    st.markdown("### 📊 Daily Patient Registrations (Last 30 Days)")
    trends = harness.get_daily_trends(days=30)
    if trends.get("dates"):
        df = pd.DataFrame({
            "Date": pd.to_datetime(trends["dates"]),
            "Patients": trends["counts"],
        }).set_index("Date")
        st.line_chart(df, use_container_width=True, height=300)
    else:
        st.caption("No registration data for the last 30 days.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2: DEPARTMENT ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_dept_tab(harness, start_date: str, end_date: str):
    """Render per-department status breakdown with bar charts."""
    st.markdown("### 🔬 Department-wise Breakdown")

    perf = harness.get_department_performance(start_date, end_date)
    if not perf or all(d["total"] == 0 for d in perf.values()):
        st.info("📊 No department data available for the selected range.")
        return

    # Build DataFrame for bar chart
    chart_data = {}
    for dept, data in perf.items():
        for status, count in data["stats"].items():
            chart_data.setdefault(status, {})[dept] = count

    if chart_data:
        df_bars = pd.DataFrame(chart_data).fillna(0).astype(int)
        # Reorder columns to known status sequence
        status_order = [s for s in ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"] if s in df_bars.columns]
        df_bars = df_bars[status_order]
        st.bar_chart(df_bars, use_container_width=True, height=350)
        st.caption("Status distribution across departments. "
                   "Hover/tap bars for exact values.")

    st.divider()

    # ─── Per-Department Detail Cards ───────────────────────────────────────
    for dept in TEST_TYPES:
        data = perf.get(dept)
        if not data or data["total"] == 0:
            continue

        stats = data["stats"]
        durations = data["durations"]

        with st.expander(f"📊 {dept} — {data['total']} total tests", expanded=False):
            cols = st.columns(6)
            status_order_local = ["waiting", "called", "in_progress", "completed",
                                  "report_ready", "delivered"]
            for col, status in zip(cols, status_order_local):
                count = stats.get(status, 0)
                with col:
                    st.markdown(_color_badge(status, count),
                                unsafe_allow_html=True)

            # Show completion stats
            completed = stats.get("completed", 0)
            if completed > 0:
                st.markdown(f"""
                <div style="margin-top:8px;font-size:0.85rem;color:#636e72;">
                    ✅ <strong>{completed}</strong> completed tests
                    &nbsp;·&nbsp; ⏱️ Avg completion: <strong>{durations.get('avg_wait_to_complete', 0)} min</strong>
                    &nbsp;·&nbsp; 🧑‍⚕️ Called in: <strong>{durations.get('avg_wait_to_call', 0)} min</strong>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.caption("No completed tests yet.")


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3: TIMING ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _render_timing_tab(harness):
    """Render average timing metrics per department in a table."""
    st.markdown("### ⏱️ Average Service Times (All-Time)")

    from utils.db import get_test_duration_stats

    rows = []
    for test in TEST_TYPES:
        durations = get_test_duration_stats(test)
        rows.append({
            "Department": test,
            "🟡 Wait→Call (min)": durations.get("avg_wait_to_call", 0),
            "🟠 Wait→Start (min)": durations.get("avg_wait_to_start", 0),
            "✅ Wait→Complete (min)": durations.get("avg_wait_to_complete", 0),
            "📊 Completed Tests": durations.get("total_completed", 0),
        })

    if not rows or all(r["📊 Completed Tests"] == 0 for r in rows):
        st.info("⏱️ No completed tests yet. Timing data will appear here as "
                "tests are processed.")
        st.caption("Timing analysis requires tests with status='completed' "
                   "and valid timestamps (created_at, called_at, started_at, "
                   "completed_at).")
        return

    df = pd.DataFrame(rows)

    # Highlight the best (lowest) times
    def _highlight_min(s):
        is_min = s == s.min()
        return ["background-color: #00b89422; font-weight: 600;"
                if v and is_min.iloc[i] else "" for i, v in enumerate(s)]

    styled = df.style.apply(_highlight_min, subset=[
        "🟡 Wait→Call (min)", "🟠 Wait→Start (min)", "✅ Wait→Complete (min)"
    ])

    st.dataframe(
        styled,
        use_container_width=True,
        column_config={
            "Department": st.column_config.TextColumn("Department", width="small"),
            "🟡 Wait→Call (min)": st.column_config.NumberColumn(
                "Wait→Call (min)", format="%.1f", help="Avg time from registration to being called"
            ),
            "🟠 Wait→Start (min)": st.column_config.NumberColumn(
                "Wait→Start (min)", format="%.1f", help="Avg time from registration to test start"
            ),
            "✅ Wait→Complete (min)": st.column_config.NumberColumn(
                "Wait→Complete (min)", format="%.1f", help="Avg time from registration to completion"
            ),
            "📊 Completed Tests": st.column_config.NumberColumn(
                "Completed", format="%d"
            ),
        },
        hide_index=True,
    )

    st.caption("💡 Green-highlighted cells show the fastest department per metric. "
               "Lower is better.")

    # ─── Interpretation Guide ──────────────────────────────────────────────
    st.divider()
    with st.expander("📖 How to interpret timing metrics", expanded=False):
        st.markdown("""
        - **Wait→Call**: Time from patient registration to when a technician clicks "Call".  
          *Longer times suggest the queue is backed up or staff are unavailable.*
        - **Wait→Start**: Time from registration to when the test actually begins.  
          *Includes both queue wait and any delay between calling and starting.*
        - **Wait→Complete**: Total time from registration to test completion.  
          *Best measure of overall department efficiency.*
        - **Completed Tests**: Number of tests that have been fully processed.  
          *Used as a reliability indicator — small sample sizes may not be representative.*

        **Tip**: Use the Department Analysis tab to see how many tests are at each
        stage right now.
        """)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════

def show():
    """Main entry point for the Reports & Analytics page."""
    st.title("📊 Reports & Analytics")
    st.markdown(
        '<span style="background-color:#6c5ce7;color:white;padding:2px 10px;'
        'border-radius:10px;font-size:0.75rem;font-weight:bold;">'
        '📈 Manager Reports</span>',
        unsafe_allow_html=True
    )
    st.markdown("---")

    harness = get_harness()

    # ─── Date Range Picker ──────────────────────────────────────────────────
    today = date.today()
    default_start = today - timedelta(days=6)  # Last 7 days by default

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        start_date_obj = st.date_input(
            "📅 From",
            value=default_start,
            max_value=today,
            key="analytics_start_date",
        )
    with col_d2:
        end_date_obj = st.date_input(
            "📅 To",
            value=today,
            max_value=today,
            key="analytics_end_date",
        )

    start_date = start_date_obj.isoformat()
    end_date = end_date_obj.isoformat()

    if start_date > end_date:
        st.error("⚠️ Start date cannot be after end date.")
        st.stop()

    st.caption(f"Showing data from {start_date_obj.strftime('%d-%b-%Y')} "
               f"to {end_date_obj.strftime('%d-%b-%Y')}")

    # ─── Tabs ───────────────────────────────────────────────────────────────
    tab1, tab2, tab3 = st.tabs([
        "📈 Overview",
        "🔬 Department Analysis",
        "⏱️ Timing Analysis",
    ])

    with tab1:
        _render_overview_tab(harness, start_date, end_date)

    with tab2:
        _render_dept_tab(harness, start_date, end_date)

    with tab3:
        _render_timing_tab(harness)
