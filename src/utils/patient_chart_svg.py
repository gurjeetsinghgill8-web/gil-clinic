"""
Server-side SVG trend chart for the Patient Portal (Smart OPD).

**Ek hi chart engine, teen jagah** (is liye "download me graph nahi aata" jaisi
shikayat dobara nahi ho sakti):
  1. Patient portal ki screen  → `GET /my/<token>/chart.svg?code=...`
  2. HTML report (inline SVG)  → `patient_report.build_report_html()`
  3. PDF report (vector draw)  → `patient_report.build_report_pdf()` (isi geometry se)

Design (CLINICITY v0.8.0 me doctor-approved):
  * default canvas 320×160 (≈2:1) — phone par full card width, labels bina zoom
    padhne layak (12–15px rendered)
  * normal-range ka **green band**, y-axis min/max, first/middle/last date labels,
    2+ readings hone par value labels
"""

from __future__ import annotations

from html import escape as _esc
from typing import Any, Optional, Sequence

from src.utils.patient_metrics import short_stamp


def _fmt_axis(v: float) -> str:
    f = float(v)
    if abs(f) >= 100:
        return str(int(round(f)))
    return f"{f:g}"


def trend_point_count(values: Sequence[Any]) -> int:
    n = 0
    for v in values:
        if v is None:
            continue
        try:
            float(v)
        except (TypeError, ValueError):
            continue
        n += 1
    return n


def trend_chart_svg(
    values: Sequence[Any],
    dates: Optional[Sequence[str]] = None,
    color: str = "#0d9488",
    unit: str = "",
    normal_min: Optional[float] = None,
    normal_max: Optional[float] = None,
    width: int = 320,
    height: int = 160,
    class_name: str = "trend-chart",
) -> str:
    """Trend chart ka SVG **string** ('' jab 2 se kam readings hon).

    Text XML-escaped hota hai aur koi `id`/external reference nahi hota — is liye
    ek hi HTML file me 10 graphs bina takraav ke reh sakte hain.
    """
    nums = []
    for v in values:
        if v is None:
            continue
        try:
            nums.append(float(v))
        except (TypeError, ValueError):
            continue
    if len(nums) < 2:
        return ""

    w, h = int(width), int(height)
    pad_top = round(h * 0.115)
    pad_right = 12
    pad_bottom = round(h * 0.155)
    pad_left = 42
    iw = w - pad_left - pad_right
    ih = h - pad_top - pad_bottom

    fs_axis = max(9, round(h * 0.068))
    fs_value = max(10, round(h * 0.076))
    r_dot = max(2.6, h * 0.02)
    stroke = max(1.8, h * 0.014)

    lo = min(nums + ([normal_min] if normal_min is not None else []))
    hi = max(nums + ([normal_max] if normal_max is not None else []))
    span = (hi - lo) or 1.0
    y_lo = lo - span * 0.12
    y_hi = hi + span * 0.12
    span = (y_hi - y_lo) or 1.0

    n = len(values)

    def x(i: int) -> float:
        if n <= 1:
            return pad_left + iw / 2
        return pad_left + (i / (n - 1)) * iw

    def y(v: float) -> float:
        return pad_top + ih - ((float(v) - y_lo) / span) * ih

    coords = []
    for i, v in enumerate(values):
        if v is None:
            coords.append(None)
            continue
        try:
            coords.append((x(i), y(float(v))))
        except (TypeError, ValueError):
            coords.append(None)

    pts = [c for c in coords if c is not None]
    line = " ".join(f"{px:.1f},{py:.1f}" for px, py in pts)

    band_top = band_h = 0.0
    show_band = normal_min is not None and normal_max is not None
    if show_band:
        b1, b2 = y(normal_max), y(normal_min)
        band_top, band_h = min(b1, b2), abs(b2 - b1)

    show_values = len(nums) <= 10

    def date_at(i: int) -> str:
        if dates and i < len(dates) and dates[i]:
            return short_stamp(str(dates[i]))
        return ""

    first_date = date_at(0)
    last_date = date_at(n - 1) if n > 1 else ""
    mid_idx = (n - 1) // 2
    mid_date = date_at(mid_idx) if n >= 6 else ""

    p = []
    p.append(
        f'<svg class="{_esc(class_name)}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="vitals trend{(" in " + _esc(unit)) if unit else ""}" '
        f'style="display:block;width:100%;height:auto;max-width:100%">'
    )

    font = "system-ui,Segoe UI,Roboto,Arial,sans-serif"
    if unit:
        p.append(
            f'<text x="2" y="{round(fs_axis + 1)}" font-size="{fs_axis}" fill="#94a3b8" '
            f'font-family="{font}">{_esc(unit)}</text>'
        )

    if show_band and band_h > 0:
        p.append(
            f'<rect x="{pad_left}" y="{band_top:.1f}" width="{iw}" height="{band_h:.1f}" '
            f'fill="#10b981" fill-opacity="0.12" stroke="#10b981" stroke-opacity="0.35" '
            f'stroke-width="0.8" rx="2"/>'
        )
        if band_h >= fs_axis + 4:
            p.append(
                f'<text x="{w - pad_right - 3}" y="{band_top + band_h - 3:.1f}" '
                f'font-size="{max(8, fs_axis - 1)}" fill="#059669" fill-opacity="0.85" '
                f'text-anchor="end" font-family="{font}">normal</text>'
            )

    for frac in (0.25, 0.5, 0.75):
        gy = pad_top + ih * frac
        p.append(
            f'<line x1="{pad_left}" x2="{w - pad_right}" y1="{gy:.1f}" y2="{gy:.1f}" '
            f'stroke="#e2e8f0" stroke-width="1"/>'
        )

    p.append(
        f'<line x1="{pad_left}" x2="{pad_left}" y1="{pad_top}" y2="{pad_top + ih}" '
        f'stroke="#cbd5e1" stroke-width="1"/>'
    )
    p.append(
        f'<line x1="{pad_left}" x2="{w - pad_right}" y1="{pad_top + ih}" y2="{pad_top + ih}" '
        f'stroke="#cbd5e1" stroke-width="1"/>'
    )

    p.append(
        f'<text x="{pad_left - 5}" y="{pad_top + fs_axis * 0.75:.1f}" font-size="{fs_axis}" '
        f'fill="#94a3b8" text-anchor="end" font-family="{font}">{_fmt_axis(y_hi)}</text>'
    )
    p.append(
        f'<text x="{pad_left - 5}" y="{pad_top + ih:.1f}" font-size="{fs_axis}" '
        f'fill="#94a3b8" text-anchor="end" font-family="{font}">{_fmt_axis(y_lo)}</text>'
    )

    if line:
        p.append(
            f'<polyline points="{line}" fill="none" stroke="#ffffff" '
            f'stroke-width="{stroke + 1.6:.1f}" stroke-linecap="round" stroke-linejoin="round" '
            f'opacity="0.9"/>'
        )
        p.append(
            f'<polyline points="{line}" fill="none" stroke="{_esc(color)}" '
            f'stroke-width="{stroke:.1f}" stroke-linecap="round" stroke-linejoin="round" '
            f'opacity="0.95"/>'
        )

    for i, c in enumerate(coords):
        if c is None:
            continue
        px, py = c
        is_last = i == len(coords) - 1
        p.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{(r_dot * 1.35 if is_last else r_dot):.1f}" '
            f'fill="{_esc(color)}" stroke="#ffffff" stroke-width="1.2"/>'
        )
        if show_values:
            above = py - 7 >= pad_top + fs_value * 0.6
            ly = py - 7 if above else py + fs_value + 4
            p.append(
                f'<text x="{px:.1f}" y="{ly:.1f}" font-size="{fs_value}" fill="#334155" '
                f'text-anchor="middle" font-weight="600" font-family="{font}">'
                f"{_fmt_axis(values[i])}</text>"
            )

    if first_date:
        p.append(
            f'<text x="{pad_left}" y="{h - 4}" font-size="{fs_axis}" fill="#94a3b8" '
            f'text-anchor="start" font-family="{font}">{_esc(first_date)}</text>'
        )
    if mid_date:
        p.append(
            f'<text x="{pad_left + iw / 2:.1f}" y="{h - 4}" font-size="{fs_axis}" fill="#94a3b8" '
            f'text-anchor="middle" font-family="{font}">{_esc(mid_date)}</text>'
        )
    if last_date:
        p.append(
            f'<text x="{w - pad_right}" y="{h - 4}" font-size="{fs_axis}" fill="#94a3b8" '
            f'text-anchor="end" font-family="{font}">{_esc(last_date)}</text>'
        )

    p.append("</svg>")
    return "".join(p)
