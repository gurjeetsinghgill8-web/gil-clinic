"""
Patient record reports — HTML (inline SVG graphs), CSV, aur PDF (vector graphs).

Smart OPD me teen jagah se yahi report banti hai:
  * Patient:  `GET /my/<token>/export?fmt=pdf|html|csv`
  * Doctor:   `GET /opd/api/patient-report?patient_id=...&fmt=...`
  * Share:    `GET /s/<token>/export?fmt=...`   (read-only snapshot)

Graphs **file ke andar** aate hain (HTML me inline SVG, PDF me vector lines) —
is liye patient ka download kisi bhi phone par, bina internet, theek dikhta hai.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
from html import escape as _esc
from typing import Any, Dict, List, Optional, Sequence

from fpdf import FPDF

from src.utils.patient_chart_svg import trend_chart_svg, trend_point_count
from src.utils.patient_metrics import (
    STATUS_COLOR,
    STATUS_LABEL,
    METRICS,
    build_series,
    format_dt,
    latest_reading_by_key,
    metric_by_code,
    normal_range_text,
    pivot_readings,
)
from src.utils.pdf_generator import safe_str

DEFAULT_CLINIC = "GIL CLINIC"

DISCLAIMER = (
    "Ye self-reported readings sirf home tracking aur doctor review ke liye hain — "
    "final diagnosis nahi. Emergency me turant doctor ya nearest emergency se sampark karein."
)


def _ctx(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Context ko safe defaults ke saath normalise karo."""
    out = dict(ctx or {})
    out.setdefault("clinic_name", DEFAULT_CLINIC)
    out.setdefault("patient_name", "Patient")
    out.setdefault("patient_id", "")
    out.setdefault("readings", [])
    out.setdefault("mode", "patient")  # 'patient' | 'shared'
    out.setdefault("note", "")
    out.setdefault("valid_till", "")
    out.setdefault("doctor_name", "")
    return out


def _num(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


# ─────────────────────────────────────────────────────────────────────────────
# HTML
# ─────────────────────────────────────────────────────────────────────────────
def build_report_html(ctx: Dict[str, Any]) -> str:
    c = _ctx(ctx)
    readings: List[Dict[str, Any]] = list(c["readings"])
    shared = c["mode"] == "shared"
    pivot = pivot_readings(readings)
    series = build_series(readings)
    trending = [s for s in series if trend_point_count(s["values"]) >= 2]

    # summary chips (latest value + normal range)
    seen: set = set()
    chips: List[str] = []
    latest_by_key = latest_reading_by_key(readings)
    for key, r in latest_by_key.items():
        code = r.get("code") or "custom"
        if code in seen:
            continue
        seen.add(code)
        metric = metric_by_code(code)
        rng = normal_range_text(metric) or "—"
        chips.append(
            f'<div class="chip"><b>{_esc(str(r.get("label") or code))}</b> {_num(r.get("value"))} '
            f'{_esc(str(r.get("unit") or ""))}<span class="rng">normal: {_esc(rng)}</span></div>'
        )

    # charts — sirf 2+ readings wale metrics (1 reading se line nahi banti)
    boxes: List[str] = []
    for s in trending:
        svg = trend_chart_svg(
            s["values"],
            s["dates"],
            unit=s["unit"],
            normal_min=s.get("normal_min"),
            normal_max=s.get("normal_max"),
        )
        rng = (
            f'{_num(s.get("normal_min"))}–{_num(s.get("normal_max"))} {_esc(s["unit"])}'.strip()
            if s.get("normal_min") is not None and s.get("normal_max") is not None
            else ""
        )
        boxes.append(
            f'<div class="chart-box"><div class="chart-head"><b>{_esc(s["label"])}</b>'
            f'<span>latest <b>{_num(s["values"][-1])} {_esc(s["unit"])}</b>'
            f'{(" · normal " + rng) if rng else ""}</span></div>{svg}</div>'
        )

    cols = "".join(
        f'<th>{_esc(col["label"])}<br><small>{_esc(col["unit"])}</small></th>' for col in pivot["columns"]
    )
    rows_html: List[str] = []
    for row in pivot["rows"][:150]:
        tds = []
        for cell in row["cells"]:
            if not cell:
                tds.append('<td class="muted">—</td>')
                continue
            st = cell.get("status") or "ok"
            bg = f' style="background:{STATUS_COLOR.get(st, "#fff")}22"' if st != "ok" else ""
            tag = f' <small>({STATUS_LABEL.get(st, st)})</small>' if st != "ok" else ""
            tds.append(f"<td{bg}>{_esc(str(cell['text']))}{tag}</td>")
        rows_html.append(
            f'<tr><td class="nowrap">{_esc(format_dt(row["date_time"]))}</td>{"".join(tds)}</tr>'
        )

    generated = format_dt(_dt.datetime.now())
    note_html = (
        f'<div class="note"><b>Patient ka message:</b><br>{_esc(c["note"]).replace(chr(10), "<br>")}</div>'
        if c["note"]
        else ""
    )
    valid_html = (
        f'<p>Link valid till: <b>{_esc(format_dt(c["valid_till"]))}</b></p>' if c["valid_till"] else ""
    )
    charts_html = (
        f'<div class="charts">{"".join(boxes)}</div>'
        if boxes
        else '<p class="muted" style="font-size:13px">Graph ke liye kam se kam 2 readings chahiye '
        "(ek hi reading se line nahi banti). Neeche table me saari values hain.</p>"
    )

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(c['patient_name'])} — Health Records</title>
<style>
  body{{font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;margin:0;background:#f1f5f9;color:#0f172a}}
  .head{{background:linear-gradient(135deg,#0d9488,#047857);color:#fff;padding:20px 18px}}
  .head h1{{margin:0 0 4px;font-size:20px}} .head p{{margin:2px 0;font-size:13px;opacity:.95}}
  .wrap{{max-width:900px;margin:0 auto;padding:16px}}
  .card{{background:#fff;border-radius:12px;padding:14px 16px;margin-bottom:14px;box-shadow:0 1px 3px rgba(15,23,42,.08)}}
  .card h2{{margin:0 0 10px;font-size:15px}}
  .chips{{display:flex;flex-wrap:wrap;gap:8px}}
  .chip{{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:999px;padding:6px 12px;font-size:13px}}
  .chip .rng{{color:#64748b;font-size:11px;display:block;text-align:center}}
  .note{{background:#eff6ff;border:1px solid #bfdbfe;border-left:4px solid #2563eb;border-radius:10px;padding:10px 14px;font-size:13px;line-height:1.6;margin-bottom:12px}}
  .charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}}
  .chart-box{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:10px 12px;break-inside:avoid;page-break-inside:avoid}}
  .chart-head{{display:flex;flex-wrap:wrap;justify-content:space-between;gap:6px;font-size:13px;margin-bottom:6px}}
  .chart-head span{{color:#64748b;font-size:12px}}
  table{{border-collapse:collapse;width:100%;font-size:13px}}
  th,td{{border:1px solid #e2e8f0;padding:7px 9px;text-align:left;vertical-align:top}}
  th{{background:#f8fafc;font-size:12px}}
  .muted{{color:#94a3b8}} .nowrap{{white-space:nowrap}}
  .foot{{color:#64748b;font-size:12px;text-align:center;padding:10px}}
  .printbar{{position:sticky;top:0;background:#0f172a;color:#fff;padding:10px 14px;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:10px}}
  .printbar button{{background:#0d9488;color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:13px;font-weight:600;cursor:pointer}}
  @media print{{
    body{{background:#fff}} .printbar{{display:none}}
    .card{{box-shadow:none;border:1px solid #e2e8f0}}
    .head{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
    .charts{{grid-template-columns:repeat(2,1fr)}} .card,table{{break-inside:auto}}
  }}
</style></head>
<body>
<div class="printbar">
  <span>🖨️ Print ya "Save as PDF" ke liye button dabayein</span>
  <button onclick="window.print()">Print / PDF</button>
</div>
<div class="head">
  <h1>🏥 {_esc(c['clinic_name'])} — {'Shared Health Record' if shared else 'Patient Health Record'}</h1>
  <p>Patient: <b>{_esc(c['patient_name'])}</b> &nbsp;·&nbsp; ID: {_esc(c['patient_id'])}</p>
  <p>Generated: {_esc(generated)}{' &nbsp;·&nbsp; Patient ne khud share kiya (read-only)' if shared else ''}</p>
  {valid_html}
</div>
<div class="wrap">
  {note_html}
  <div class="card"><h2>📊 Summary</h2><div class="chips">{''.join(chips) or '<span class="muted">No readings yet</span>'}</div>
  <p class="muted" style="font-size:12px">{_esc(DISCLAIMER)}</p></div>
  <div class="card"><h2>📈 Graphs — trend</h2>{charts_html}
  <p class="muted" style="font-size:12px">Green patti = normal range. Har graph par latest value, normal range aur date labels diye gaye hain.</p></div>
  <div class="card"><h2>📋 Sabhi readings — Excel-style (ek jagah)</h2>
  <p class="muted" style="font-size:12px">Har line = ek baar ki entry (same date &amp; time par bhari gayi values). BP dono (systolic/diastolic) ek hi column me dikhte hain.</p>
  <div style="overflow-x:auto"><table><thead><tr><th>Date &amp; time</th>{cols}</tr></thead>
  <tbody>{''.join(rows_html) or '<tr><td colspan="10" class="muted">—</td></tr>'}</tbody></table></div></div>
</div>
<div class="foot">{_esc(c['clinic_name'])} · Self-monitoring record · {_esc(c['patient_name'])} ({_esc(c['patient_id'])})</div>
</body></html>"""


# ─────────────────────────────────────────────────────────────────────────────
# CSV
# ─────────────────────────────────────────────────────────────────────────────
def build_report_csv(readings: Sequence[Dict[str, Any]]) -> str:
    pivot = pivot_readings(readings)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["Date & time"] + [col["label"] for col in pivot["columns"]])
    for row in pivot["rows"]:
        writer.writerow([format_dt(row["date_time"])] + [c["text"] if c else "" for c in row["cells"]])
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# PDF (fpdf2 — vector graphs, koi image nahi)
# ─────────────────────────────────────────────────────────────────────────────
TEAL = (13, 148, 136)
DARK = (20, 25, 32)
SLATE = (70, 78, 90)
GRAY = (130, 138, 150)
LINE = (226, 232, 240)
BAND = (209, 250, 229)
MAROON = (190, 30, 45)

PAGE_W = 210.0
M = 14.0
CW = PAGE_W - 2 * M


class _Report:
    def __init__(self) -> None:
        self.pdf = FPDF(orientation="P", unit="mm", format="A4")
        self.pdf.set_auto_page_break(False)
        self.y = 0.0

    # -- primitives -----------------------------------------------------------
    def ensure_room(self, needed: float) -> None:
        if self.y + needed > 280:
            self.pdf.add_page()
            self.y = 18.0

    def text(self, s: str, x: float, y: float, size: float, style: str = "", color=DARK) -> None:
        self.pdf.set_font("Helvetica", style, size)
        self.pdf.set_text_color(*color)
        self.pdf.text(x, y, safe_str(s))

    def text_right(self, s: str, x_right: float, y: float, size: float, style: str = "", color=DARK) -> None:
        self.pdf.set_font("Helvetica", style, size)
        self.pdf.set_text_color(*color)
        self.pdf.text(x_right - self.pdf.get_string_width(safe_str(s)), y, safe_str(s))

    def section(self, title: str) -> None:
        self.ensure_room(13)
        self.text(title, M, self.y, 11, "B", TEAL)
        self.y += 2.4
        self.pdf.set_draw_color(*TEAL)
        self.pdf.set_line_width(0.4)
        self.pdf.line(M, self.y, PAGE_W - M, self.y)
        self.y += 5

    def paragraph(self, s: str, size: float = 9, color=SLATE) -> None:
        self.pdf.set_font("Helvetica", "", size)
        self.pdf.set_text_color(*color)
        lines = self.pdf.multi_cell(CW, size * 0.46, safe_str(s), dry_run=True, output="LINES")
        for ln in lines:
            self.ensure_room(5)
            self.pdf.text(M, self.y, ln)
            self.y += size * 0.46


def _draw_chart(pdf: FPDF, series: Dict[str, Any], x: float, y_top: float, w: float, h: float) -> None:
    """Ek trend chart (vector) — SVG wale chart ki hi geometry."""
    pad_l, pad_r, pad_t, pad_b = 12.0, 4.0, 4.5, 7.0
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b

    values = series["values"]
    dates = series["dates"]
    lo_v = min(values)
    hi_v = max(values)
    if series.get("normal_min") is not None:
        lo_v = min(lo_v, float(series["normal_min"]))
    if series.get("normal_max") is not None:
        hi_v = max(hi_v, float(series["normal_max"]))
    span = (hi_v - lo_v) or 1.0
    y_lo = lo_v - span * 0.12
    y_hi = hi_v + span * 0.12
    span = (y_hi - y_lo) or 1.0

    n = len(values)

    def px(i: int) -> float:
        return x + pad_l + (iw / 2 if n <= 1 else (i / (n - 1)) * iw)

    def py(v: float) -> float:
        return y_top + pad_t + ih - ((float(v) - y_lo) / span) * ih

    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.2)
    pdf.rect(x, y_top, w, h, "D")

    if series.get("normal_min") is not None and series.get("normal_max") is not None:
        try:
            b1, b2 = py(float(series["normal_max"])), py(float(series["normal_min"]))
            top, bh = min(b1, b2), abs(b2 - b1)
            if bh > 0.4:
                pdf.set_fill_color(*BAND)
                pdf.rect(x + pad_l, top, iw, bh, "F")
                if bh >= 5:
                    pdf.set_font("Helvetica", "", 6)
                    pdf.set_text_color(5, 150, 105)
                    tw = pdf.get_string_width("normal")
                    pdf.text(x + pad_l + iw - tw - 1.5, top + bh - 1.4, "normal")
        except (TypeError, ValueError):
            pass

    pdf.set_draw_color(*LINE)
    pdf.set_line_width(0.15)
    for frac in (0.25, 0.5, 0.75):
        gy = y_top + pad_t + ih * frac
        pdf.line(x + pad_l, gy, x + pad_l + iw, gy)

    pdf.set_draw_color(203, 213, 225)
    pdf.set_line_width(0.25)
    pdf.line(x + pad_l, y_top + pad_t, x + pad_l, y_top + pad_t + ih)
    pdf.line(x + pad_l, y_top + pad_t + ih, x + pad_l + iw, y_top + pad_t + ih)

    pdf.set_font("Helvetica", "", 6.4)
    pdf.set_text_color(*GRAY)
    pdf.text(x + pad_l - 1.5 - pdf.get_string_width(_num(y_hi)), y_top + pad_t + 2.2, _num(y_hi))
    pdf.text(x + pad_l - 1.5 - pdf.get_string_width(_num(y_lo)), y_top + pad_t + ih, _num(y_lo))

    pts = [(px(i), py(v)) for i, v in enumerate(values)]
    for i in range(1, len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(1.5)
        pdf.line(x1, y1, x2, y2)
        pdf.set_draw_color(*TEAL)
        pdf.set_line_width(0.6)
        pdf.line(x1, y1, x2, y2)

    show_values = len(values) <= 10
    for i, (cx, cy) in enumerate(pts):
        r = 1.05 if i == len(pts) - 1 else 0.8
        pdf.set_fill_color(*TEAL)
        pdf.set_draw_color(255, 255, 255)
        pdf.set_line_width(0.4)
        pdf.ellipse(cx - r, cy - r, 2 * r, 2 * r, "DF")
        if show_values:
            pdf.set_font("Helvetica", "B", 6.6)
            pdf.set_text_color(51, 65, 85)
            label = _num(values[i])
            tw = pdf.get_string_width(label)
            above = cy - 2.6 > y_top + pad_t
            pdf.text(cx - tw / 2, (cy - 1.9) if above else (cy + 4), label)

    pdf.set_font("Helvetica", "", 6.4)
    pdf.set_text_color(*GRAY)
    from src.utils.patient_metrics import short_stamp

    first = short_stamp(dates[0]) if dates else ""
    last = short_stamp(dates[-1]) if dates and len(dates) > 1 else ""
    mid = short_stamp(dates[(n - 1) // 2]) if dates and n >= 6 else ""
    if first:
        pdf.text(x + pad_l, y_top + h - 2.2, first)
    if mid:
        pdf.text(x + pad_l + iw / 2 - pdf.get_string_width(mid) / 2, y_top + h - 2.2, mid)
    if last:
        pdf.text(x + pad_l + iw - pdf.get_string_width(last), y_top + h - 2.2, last)


def build_report_pdf(ctx: Dict[str, Any]) -> bytes:
    c = _ctx(ctx)
    readings: List[Dict[str, Any]] = list(c["readings"])
    shared = c["mode"] == "shared"
    r = _Report()
    pdf = r.pdf
    pdf.add_page()

    # ---- header band ----
    pdf.set_fill_color(*TEAL)
    pdf.rect(0, 0, PAGE_W, 24, "F")
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.text(M, 10, safe_str(f"{c['clinic_name']} — {'Shared Health Record' if shared else 'Patient Health Record'}"))
    pdf.set_font("Helvetica", "", 9)
    pdf.text(M, 16, safe_str(f"Patient: {c['patient_name']}   ·   ID: {c['patient_id']}"))
    line3 = f"Generated: {format_dt(_dt.datetime.now())}"
    if shared:
        line3 += "   ·   Patient ne khud share kiya (read-only)"
    pdf.text(M, 21, safe_str(line3))
    r.y = 31

    # ---- patient ka message ----
    if c["note"]:
        pdf.set_font("Helvetica", "", 8.5)
        lines = pdf.multi_cell(CW - 8, 3.9, safe_str(c["note"]), dry_run=True, output="LINES")
        box_h = len(lines) * 3.9 + 8
        r.ensure_room(box_h + 4)
        pdf.set_fill_color(239, 246, 255)
        pdf.set_draw_color(37, 99, 235)
        pdf.set_line_width(0.4)
        pdf.rect(M, r.y - 3.5, CW, box_h, "DF")
        r.text("Patient ka message:", M + 3, r.y + 1.4, 8.5, "B", (30, 64, 175))
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(30, 41, 59)
        for i, ln in enumerate(lines):
            pdf.text(M + 3, r.y + 5.6 + i * 3.9, ln)
        r.y += box_h + 3

    # ---- summary: latest value + normal range + status ----
    series = build_series(readings)
    latest_by_key = latest_reading_by_key(readings)
    rows = [s for s in series if s["code"] != "custom"]
    if rows:
        r.section("Summary — latest values")
        col_w = [58.0, 34.0, 46.0, 44.0]
        pdf.set_fill_color(248, 250, 252)
        pdf.rect(M, r.y - 3.6, CW, 6, "F")
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*DARK)
        cx = M + 2
        for head, wcol in zip(["Metric", "Latest", "Normal range", "Status"], col_w):
            pdf.text(cx, r.y, head)
            cx += wcol
        r.y += 4.5
        for s in rows:
            r.ensure_room(7)
            metric = metric_by_code(s["code"])
            status = (latest_by_key.get(s["code"]) or {}).get("status") or "ok"
            rng = (
                f'{_num(s["normal_min"])}–{_num(s["normal_max"])} {s["unit"]}'.strip()
                if s.get("normal_min") is not None and s.get("normal_max") is not None
                else (normal_range_text(metric) or "—")
            )
            cx = M + 2
            r.text(s["label"], cx, r.y, 8.4, "", (30, 41, 59))
            cx += col_w[0]
            r.text(f'{_num(s["values"][-1])} {s["unit"]}'.strip(), cx, r.y, 8.4, "B", (30, 41, 59))
            cx += col_w[1]
            r.text(rng or "—", cx, r.y, 8.4, "", (30, 41, 59))
            cx += col_w[2]
            color = (5, 150, 105) if status == "ok" else (MAROON if status == "critical" else (217, 119, 6))
            r.text(STATUS_LABEL.get(status, status), cx, r.y, 8.4, "", color)
            r.y += 5
            pdf.set_draw_color(*LINE)
            pdf.set_line_width(0.15)
            pdf.line(M, r.y - 3.4, PAGE_W - M, r.y - 3.4)
        r.y += 3

    # ---- graphs ----
    trending = [s for s in series if trend_point_count(s["values"]) >= 2]
    r.section("Graphs — trend")
    if not trending:
        r.paragraph("Graph ke liye kam se kam 2 readings chahiye. Neeche table me saari values di gayi hain.", 8.6, GRAY)
    else:
        for s in trending[:12]:
            r.ensure_room(62)
            r.text(s["label"], M, r.y, 9.2, "B", DARK)
            rng = (
                f'{_num(s["normal_min"])}–{_num(s["normal_max"])} {s["unit"]}'.strip()
                if s.get("normal_min") is not None and s.get("normal_max") is not None
                else ""
            )
            r.text_right(
                f'latest {_num(s["values"][-1])} {s["unit"]}' + (f'   ·   normal {rng}' if rng else ""),
                PAGE_W - M,
                r.y,
                8,
                "",
                GRAY,
            )
            r.y += 2.2
            _draw_chart(pdf, s, M, r.y, CW, 46)
            r.y += 52
        r.paragraph("Green patti = normal range. Har graph par latest value aur date labels diye gaye hain.", 8, GRAY)
        r.y += 2

    # ---- Excel-style readings table ----
    pivot = pivot_readings(readings)
    if pivot["columns"] and pivot["rows"]:
        r.section("All readings — Excel style (ek jagah)")
        n_cols = min(len(pivot["columns"]), 8) + 1
        first_w = 34.0
        colw = (CW - first_w) / (n_cols - 1)

        def table_head() -> None:
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(M, r.y - 3.6, CW, 6.4, "F")
            r.text("Date & time", M + 1.5, r.y, 7, "B", DARK)
            for i, col in enumerate(pivot["columns"][: n_cols - 1]):
                r.text(col["label"][:18], M + first_w + i * colw + 1.5, r.y, 7, "B", DARK)
            r.y += 5.6

        r.ensure_room(14)
        table_head()
        for row in pivot["rows"][:80]:
            if r.y > 282:
                pdf.add_page()
                r.y = 18.0
                table_head()
            r.text(format_dt(row["date_time"]), M + 1.5, r.y, 7.4, "", (30, 41, 59))
            for i, cell in enumerate(row["cells"][: n_cols - 1]):
                cx = M + first_w + i * colw + 1.5
                if not cell:
                    r.text("—", cx, r.y, 7.4, "", (148, 163, 184))
                    continue
                st = cell.get("status") or "ok"
                color = (
                    (30, 41, 59)
                    if st == "ok"
                    else (MAROON if st == "critical" else ((37, 99, 235) if st == "low" else (194, 65, 12)))
                )
                r.text(str(cell["text"]), cx, r.y, 7.4, "B" if st != "ok" else "", color)
            r.y += 4.6
            pdf.set_draw_color(*LINE)
            pdf.set_line_width(0.12)
            pdf.line(M, r.y - 3, PAGE_W - M, r.y - 3)
        if len(pivot["rows"]) > 80:
            r.y += 2
            r.paragraph(f"… aur {len(pivot['rows']) - 80} purani entries (poora record HTML/CSV file me hai).", 7.6, GRAY)
        r.y += 4

    # ---- disclaimer ----
    r.ensure_room(18)
    pdf.set_draw_color(253, 230, 138)
    pdf.set_fill_color(255, 251, 235)
    pdf.set_line_width(0.4)
    pdf.set_font("Helvetica", "", 7.8)
    dlines = pdf.multi_cell(CW - 6, 3.6, safe_str(DISCLAIMER), dry_run=True, output="LINES")
    pdf.rect(M, r.y - 3.6, CW, len(dlines) * 3.6 + 6, "DF")
    pdf.set_text_color(120, 53, 15)
    for i, ln in enumerate(dlines):
        pdf.text(M + 3, r.y + 0.8 + i * 3.6, ln)

    # ---- footers ----
    total = pdf.pages_count if hasattr(pdf, "pages_count") else None
    try:
        total = pdf.pages_count  # fpdf2 ≥ 2.7.6
    except Exception:
        total = None
    if total is None:
        total = len(getattr(pdf, "pages", {}) or {}) or 1
    for page_no in range(1, int(total) + 1):
        pdf.page = page_no
        pdf.set_font("Helvetica", "", 7.2)
        pdf.set_text_color(150, 155, 160)
        foot = f"{c['clinic_name']} · self-monitoring record · {c['patient_name']} ({c['patient_id']})"
        pdf.text((PAGE_W - pdf.get_string_width(safe_str(foot))) / 2, 291, safe_str(foot))
        r.text_right(f"Page {page_no} / {int(total)}", PAGE_W - M, 291, 7.2, "", (150, 155, 160))

    out = pdf.output()
    return bytes(out)
