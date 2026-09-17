"""Quick manual check for the patient report engine (Phase 1) — temp file."""
from __future__ import annotations

import datetime as dt
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.patient_chart_svg import trend_chart_svg, trend_point_count  # noqa: E402
from src.utils.patient_metrics import (  # noqa: E402
    build_series,
    flag_reading,
    metric_by_code,
    pivot_readings,
)
from src.utils.patient_report import build_report_csv, build_report_html, build_report_pdf  # noqa: E402


def mk(code, label, unit, value, day, status="ok"):
    return {
        "reading_id": f"{code}-{day}",
        "patient_id": "GIL-000123",
        "code": code,
        "label": label,
        "unit": unit,
        "value": value,
        "date_time": dt.datetime(2026, 9, day, 8, 0).isoformat(),
        "source": "patient",
        "status": status,
    }


readings = [
    mk("bp-systolic", "BP Systolic", "mmHg", 138, 1),
    mk("bp-diastolic", "BP Diastolic", "mmHg", 88, 1),
    mk("bp-systolic", "BP Systolic", "mmHg", 152, 3, "high"),
    mk("bp-diastolic", "BP Diastolic", "mmHg", 96, 3, "high"),
    mk("bp-systolic", "BP Systolic", "mmHg", 146, 6, "high"),
    mk("bp-diastolic", "BP Diastolic", "mmHg", 92, 6, "high"),
    mk("pulse", "Pulse", "bpm", 82, 1),
    mk("pulse", "Pulse", "bpm", 76, 3),
    mk("pulse", "Pulse", "bpm", 88, 6),
    mk("rbs", "Blood Sugar (RBS)", "mg/dL", 148, 1, "high"),
    mk("rbs", "Blood Sugar (RBS)", "mg/dL", 126, 6),
    mk("weight", "Weight", "kg", 78, 6),
    mk("custom", "Hemoglobin", "g/dL", 12.4, 1),
    mk("custom", "Hemoglobin", "g/dL", 12.9, 6),
    mk("custom", "CBC Platelets", "lakh/uL", 2.1, 6),
]

print("flag bp-systolic 160 →", flag_reading(metric_by_code("bp-systolic"), 160))
print("flag bp-systolic 190 →", flag_reading(metric_by_code("bp-systolic"), 190))
series = build_series(readings)
print("series:", [(s["code"], s["values"]) for s in series])
svg = trend_chart_svg(
    series[0]["values"], series[0]["dates"], unit="mmHg", normal_min=90, normal_max=140
)
print("chart svg length:", len(svg), "| polylines:", svg.count("<polyline"), "| band:", 'fill="#10b981"' in svg)
print("1-point chart (should be ''):", repr(trend_chart_svg([120], ["2026-09-01T08:00:00"])))
print("point count:", trend_point_count([1, None, 3]))

pivot = pivot_readings(readings)
print("pivot columns:", [c["label"] for c in pivot["columns"]])
print("pivot first row:", pivot["rows"][0]["date_time"], [c["text"] if c else "—" for c in pivot["rows"][0]["cells"]])

ctx = {
    "patient_name": "Raj Kumar",
    "patient_id": "GIL-000123",
    "readings": readings,
    "clinic_name": "GIL CLINIC",
    "mode": "shared",
    "note": "BP 3 din se high aa raha hai",
    "valid_till": dt.datetime(2026, 9, 24).isoformat(),
}
html = build_report_html(ctx)
print("html charts:", html.count('class="trend-chart"'), "| chart boxes:", html.count('class="chart-box"'))
csv_text = build_report_csv(readings)
print("csv header:", csv_text.splitlines()[0])
pdf_bytes = build_report_pdf(ctx)
print("pdf magic:", pdf_bytes[:5], "| size:", len(pdf_bytes))

out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preview")
os.makedirs(out_dir, exist_ok=True)
for name, data, mode in (
    ("report.html", html.encode("utf-8"), "wb"),
    ("report.csv", csv_text.encode("utf-8"), "wb"),
    ("report.pdf", pdf_bytes, "wb"),
):
    with open(os.path.join(out_dir, name), mode) as fh:
        fh.write(data)
print("written to:", out_dir)
