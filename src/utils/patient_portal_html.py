"""
Portal ke HTML fragments (server-rendered) — trends/graphs, Excel-style table,
red-flag banners aur summary chips.

Kyun server-side? Kyunki **ek hi chart engine** rahe: yahi `trends_html()` portal
ki screen par dikhta hai, save ke baad `/my/<token>/content` se refresh hota hai,
aur HTML report (`patient_report`) me bhi wahi SVG jata hai — is liye screen aur
download ki file hamesha ek jaisi rehti hai.
"""

from __future__ import annotations

from html import escape as _esc
from typing import Any, Dict, List, Sequence

from src.utils.patient_chart_svg import trend_chart_svg, trend_point_count
from src.utils.patient_metrics import (
    STATUS_COLOR,
    STATUS_LABEL,
    format_dt,
    latest_reading_by_key,
    metric_by_code,
    normal_range_text,
)


def _num(v: Any) -> str:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return _esc(str(v))
    return str(int(f)) if f == int(f) else f"{f:g}"


def trends_html(series: Sequence[Dict[str, Any]]) -> str:
    """Har metric ka trend card (bade graph, green normal band)."""
    if not series:
        return '<p class="pp-empty">Abhi koi reading nahi hai — pehli reading bharne par graph yahan aa jayega.</p>'

    cards: List[str] = []
    for s in series:
        values = s.get("values") or []
        unit = _esc(str(s.get("unit") or ""))
        n = trend_point_count(values)
        latest = _num(values[-1]) if values else "—"
        rng = ""
        if s.get("normal_min") is not None and s.get("normal_max") is not None:
            rng = f'{_num(s["normal_min"])}–{_num(s["normal_max"])} {unit}'.strip()
        if n >= 2:
            svg = trend_chart_svg(
                values,
                s.get("dates"),
                unit=s.get("unit") or "",
                normal_min=s.get("normal_min"),
                normal_max=s.get("normal_max"),
            )
            chart = svg
        else:
            chart = (
                '<div class="pp-hint">Trend line ke liye kam se kam 2 readings chahiye '
                f"(abhi {n}).</div>"
            )
        cards.append(
            f'<div class="pp-trend">'
            f'<div class="pp-trend-head"><b>{_esc(str(s.get("label") or s.get("code")))}</b>'
            f'<span>latest <b>{latest} {unit}</b>{(" · normal " + rng) if rng else ""}</span></div>'
            f"{chart}</div>"
        )
    return f'<div class="pp-trends">{"".join(cards)}</div>'


def table_html(pivot: Dict[str, Any]) -> str:
    """Excel-style matrix (rows = date-time, BP ek column me 135/85)."""
    columns = pivot.get("columns") or []
    rows = pivot.get("rows") or []
    if not columns or not rows:
        return '<p class="pp-empty">Abhi koi reading nahi hai.</p>'

    head = "".join(
        f'<th>{_esc(str(c["label"]))}<div class="pp-th-unit">{_esc(str(c["unit"]))}</div></th>'
        for c in columns
    )
    body: List[str] = []
    for row in rows[:60]:
        tds: List[str] = []
        for cell in row.get("cells") or []:
            if not cell:
                tds.append('<td class="pp-muted">—</td>')
                continue
            st = cell.get("status") or "ok"
            color = STATUS_COLOR.get(st, "#0f172a")
            weight = "700" if st != "ok" else "400"
            tag = f' <small>({STATUS_LABEL.get(st, st)})</small>' if st != "ok" else ""
            tds.append(
                f'<td style="color:{color};font-weight:{weight}">{_esc(str(cell["text"]))}{tag}</td>'
            )
        body.append(
            f'<tr><td class="pp-nowrap">{_esc(format_dt(row.get("date_time")))}</td>{"".join(tds)}</tr>'
        )
    more = (
        f'<p class="pp-hint">… sirf pichhli 60 entries dikhayi gayi hain — poore record ke liye '
        f"PDF/HTML/CSV download karein.</p>"
        if len(rows) > 60
        else ""
    )
    return (
        '<div class="pp-table-wrap"><table class="pp-table">'
        f"<thead><tr><th>Date &amp; time</th>{head}</tr></thead>"
        f'<tbody>{"".join(body)}</tbody></table></div>{more}'
    )


def flags_html(flags: Sequence[Dict[str, Any]]) -> str:
    """Red-flag banner — latest out-of-range readings + Hinglish guidance."""
    if not flags:
        return ""
    rows = "".join(
        f'<div class="pp-flag-row"><b>{_esc(str(f.get("label")))}: {_num(f.get("value"))} '
        f'{_esc(str(f.get("unit") or ""))}</b> '
        f'<span style="color:{STATUS_COLOR.get(str(f.get("status")), "#dc2626")}">'
        f'({STATUS_LABEL.get(str(f.get("status")), f.get("status"))})</span>'
        f'<div class="pp-flag-guide">{_esc(str(f.get("guidance") or ""))}</div></div>'
        for f in flags
    )
    return f'<div class="pp-alert">{rows}</div>'


def summary_html(readings: Sequence[Dict[str, Any]]) -> str:
    """Latest value + normal range chips (report ke summary jaisa)."""
    latest = latest_reading_by_key(readings)
    if not latest:
        return ""
    chips: List[str] = []
    for key, r in latest.items():
        metric = metric_by_code(str(r.get("code") or ""))
        status = str(r.get("status") or "ok")
        color = STATUS_COLOR.get(status, "#047857")
        rng = normal_range_text(metric) or "—"
        chips.append(
            f'<div class="pp-chip" style="border-color:{color}44">'
            f'<b>{_esc(str(r.get("label") or key))}</b> {_num(r.get("value"))} '
            f'{_esc(str(r.get("unit") or ""))}'
            f'<span>normal: {_esc(rng)}</span></div>'
        )
    return f'<div class="pp-chips">{"".join(chips)}</div>'
