"""
Patient self-monitoring metric catalog + clinical flagging (Smart OPD).

Yeh module **pure Python** hai (koi DB / FastAPI / SQLAlchemy import nahi) —
is liye tests turant chalte hain aur yahi logic teen jagah use hota hai:
  1. Patient portal (screen par normal range + red-flag guidance)
  2. Reports (HTML / PDF / CSV)
  3. Doctor ke Patient Monitor tab me trends

Ranges sirf **flag** karne ke liye hain (clinic protocol), diagnosis nahi.
Ranges CLINICITY OPD v0.8.0 ke catalog se hi rakhe gaye hain + kuch common
Indian OPD lab metrics jode gaye hain (Hb, Creatinine, LDL, PPBS).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ReadingStatus = str  # 'ok' | 'low' | 'high' | 'critical'


@dataclass(frozen=True)
class MetricDef:
    code: str
    label: str
    unit: str
    loinc: str = ""
    min: Optional[float] = None
    max: Optional[float] = None
    critical_min: Optional[float] = None
    critical_max: Optional[float] = None
    #: Patient portal ke default form me dikhega?
    in_form: bool = False


#: Catalog — order matter karta hai (pivot table aur graphs isi order me lagte hain)
METRICS: List[MetricDef] = [
    MetricDef("bp-systolic", "BP Systolic", "mmHg", "8480-6", 90, 140, 80, 180, True),
    MetricDef("bp-diastolic", "BP Diastolic", "mmHg", "8462-4", 60, 90, 50, 120, True),
    MetricDef("pulse", "Pulse", "bpm", "8867-4", 60, 100, 40, 130, True),
    MetricDef("spo2", "SpO2", "%", "2708-6", 95, 100, 90, 100, True),
    MetricDef("temperature", "Temperature", "°F", "8310-5", 97, 99.5, 95, 103, True),
    MetricDef("weight", "Weight", "kg", "29463-7", None, None, None, None, True),
    MetricDef("rbs", "Blood Sugar (RBS)", "mg/dL", "2339-0", 70, 140, 50, 300, True),
    MetricDef("fbs", "Fasting Sugar (FBS)", "mg/dL", "1558-6", 70, 100, 50, 250),
    MetricDef("ppbs", "Sugar (PPBS)", "mg/dL", "1521-4", 70, 140, 50, 300),
    MetricDef("hba1c", "HbA1c", "%", "4548-4", 4, 6.5, 4, 10),
    MetricDef("tsh", "TSH", "mIU/L", "3016-3", 0.4, 4.0, 0.1, 10),
    MetricDef("hb", "Hemoglobin", "g/dL", "718-7", 12, 17, 7, 20),
    MetricDef("creatinine", "Creatinine", "mg/dL", "2160-0", 0.6, 1.3, 0.3, 4),
    MetricDef("ldl", "LDL Cholesterol", "mg/dL", "13457-7", 50, 100, 30, 250),
]

#: BP systolic + diastolic jodi — pivot table aur report me ek hi column (135/85)
BP_PAIR_CODE = "bp"

STATUS_LABEL: Dict[ReadingStatus, str] = {
    "ok": "Normal",
    "high": "High",
    "low": "Low",
    "critical": "Critical",
}

STATUS_COLOR: Dict[ReadingStatus, str] = {
    "ok": "#047857",
    "high": "#b45309",
    "low": "#2563eb",
    "critical": "#dc2626",
}

_BY_CODE: Dict[str, MetricDef] = {m.code: m for m in METRICS}

#: Portal ke "Aaj ki readings" form me default fields
FORM_CODES: List[str] = [m.code for m in METRICS if m.in_form]


def metric_by_code(code: str) -> Optional[MetricDef]:
    return _BY_CODE.get(code or "")


def flag_reading(metric: Optional[MetricDef], value: float) -> ReadingStatus:
    """Sirf flag — koi diagnosis nahi. Critical pehle check hota hai."""
    if metric is None or value is None:
        return "ok"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "ok"
    if metric.critical_min is not None and v < metric.critical_min:
        return "critical"
    if metric.critical_max is not None and v > metric.critical_max:
        return "critical"
    if metric.min is not None and v < metric.min:
        return "low"
    if metric.max is not None and v > metric.max:
        return "high"
    return "ok"


def worst_of(statuses: Iterable[Optional[str]]) -> ReadingStatus:
    vals = [s for s in statuses if s]
    for want in ("critical", "high", "low"):
        if want in vals:
            return want
    return "ok"


def guidance_for(metric: Optional[MetricDef], status: ReadingStatus) -> str:
    """Patient ke liye Hinglish guidance (red-flag banner me dikhta hai)."""
    if status == "critical":
        return (
            "Khatarnak range — turant doctor se sampark karein ya nearest emergency "
            "me jaayein. Ye self-reading hai, intezaar na karein."
        )
    if status == "high":
        if metric and metric.code in ("bp-systolic", "bp-diastolic"):
            return (
                "Aapka BP badha hua hai (140/90 ya upar) — jaldi doctor se consult karein "
                "aur dawa apne aap na badlein."
            )
        if metric and metric.code in ("rbs", "fbs", "ppbs", "hba1c"):
            return "Sugar normal se zyada hai — khaana-dawa par dhyan dein aur doctor ko dikhayein."
        return "Ye value normal se zyada hai — doctor se consult karein."
    if status == "low":
        return "Ye value normal se kam hai — doctor se consult karein (dawa ki dose apne aap na badlein)."
    return ""


def normal_range_text(metric: Optional[MetricDef]) -> str:
    if metric is None or metric.min is None or metric.max is None:
        return ""
    return f"{_fmt_num(metric.min)}–{_fmt_num(metric.max)} {metric.unit}".strip()


def _fmt_num(v: float) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


# ─────────────────────────────────────────────────────────────────────────────
# Reading dict helpers
# ─────────────────────────────────────────────────────────────────────────────
#: Ek reading ka shape (DB row se dict me map hota hai):
#:   {"reading_id","patient_id","code","label","unit","value","date_time",
#:    "source","status","note"}


def reading_public(row: Dict[str, Any]) -> Dict[str, Any]:
    """DB row (ya dict) → sirf wahi fields jo patient/doctor ko dikhte hain.
    created_at/updated_at jaisi internal cheezein bahar nahi bhejte."""
    dt = row.get("date_time")
    if isinstance(dt, _dt.datetime):
        dt = dt.isoformat()
    out = {
        "reading_id": str(row.get("reading_id") or row.get("id") or ""),
        "code": row.get("code") or "custom",
        "label": row.get("label") or "Custom",
        "unit": row.get("unit") or "",
        "value": float(row.get("value") or 0),
        "date_time": dt or "",
        "source": row.get("source") or "patient",
        "status": row.get("status") or "ok",
    }
    if row.get("note"):
        out["note"] = row["note"]
    return out


def series_key(reading: Dict[str, Any]) -> str:
    """Custom fields label-wise alag rehte hain (Hemoglobin aur CBC mix na hon)."""
    if (reading.get("code") or "") == "custom":
        return f"custom:{reading.get('label') or 'Custom'}"
    return reading.get("code") or "custom"


def build_series(readings: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per-metric chronological series — har graph isi se banta hai.

    Returns: [{code, label, unit, values:[..], dates:[iso..], normal_min, normal_max}]
    """
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for r in readings:
        groups.setdefault(series_key(r), []).append(r)

    order = {m.code: i for i, m in enumerate(METRICS)}
    out: List[Dict[str, Any]] = []
    for key, rows in groups.items():
        rows = sorted(rows, key=lambda r: str(r.get("date_time") or ""))
        first = rows[0]
        metric = metric_by_code(key)
        series: Dict[str, Any] = {
            "code": key,
            "label": first.get("label") or key,
            "unit": first.get("unit") or "",
            "values": [float(r.get("value") or 0) for r in rows],
            "dates": [str(r.get("date_time") or "") for r in rows],
        }
        if metric is not None:
            series["normal_min"] = metric.min
            series["normal_max"] = metric.max
        out.append(series)

    out.sort(key=lambda s: order.get(s["code"], 900))
    return out


def pivot_readings(readings: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """Excel-style matrix: har date-time ek row, metrics columns.

    BP systolic + diastolic (same save) → ek hi "BP" column me "135/85".
    Returns {"columns":[{key,label,unit}], "rows":[{date_time, cells:[cell|null]}]}
    """
    used = {r.get("code") for r in readings}
    columns: List[Dict[str, str]] = []
    code_cols: List[str] = []

    if "bp-systolic" in used or "bp-diastolic" in used:
        columns.append({"key": BP_PAIR_CODE, "label": "BP", "unit": "mmHg"})
        code_cols.append(BP_PAIR_CODE)
    for m in METRICS:
        if m.code in ("bp-systolic", "bp-diastolic"):
            continue
        if m.code in used:
            columns.append({"key": m.code, "label": m.label, "unit": m.unit})
            code_cols.append(m.code)

    custom_cols: List[Tuple[str, str]] = []
    seen_custom: set = set()
    for r in readings:
        if r.get("code") != "custom":
            continue
        label = r.get("label") or "Custom"
        if label in seen_custom:
            continue
        seen_custom.add(label)
        custom_cols.append((label, r.get("unit") or ""))
    for label, unit in custom_cols:
        columns.append({"key": f"custom:{label}", "label": label, "unit": unit})
        code_cols.append(f"custom:{label}")

    by_time: Dict[str, List[Dict[str, Any]]] = {}
    for r in readings:
        by_time.setdefault(str(r.get("date_time") or ""), []).append(r)
    times = sorted(by_time.keys(), reverse=True)

    rows: List[Dict[str, Any]] = []
    for t in times:
        group = by_time[t]

        def at(code: str) -> Optional[Dict[str, Any]]:
            for r in group:
                if r.get("code") == code:
                    return r
            return None

        cells: List[Optional[Dict[str, Any]]] = []
        for col in code_cols:
            if col == BP_PAIR_CODE:
                s = at("bp-systolic")
                d = at("bp-diastolic")
                if not s and not d:
                    cells.append(None)
                    continue
                text = f"{_fmt_num(s['value']) if s else '—'}/{_fmt_num(d['value']) if d else '—'}"
                cells.append({"text": text, "status": worst_of([s and s.get("status"), d and d.get("status")])})
            elif col.startswith("custom:"):
                label = col.split(":", 1)[1]
                r = None
                for x in group:
                    if x.get("code") == "custom" and (x.get("label") or "Custom") == label:
                        r = x
                        break
                if not r:
                    cells.append(None)
                    continue
                unit = r.get("unit") or ""
                cells.append({"text": f"{_fmt_num(r['value'])}{(' ' + unit) if unit else ''}", "status": r.get("status")})
            else:
                r = at(col)
                cells.append({"text": _fmt_num(r["value"]), "status": r.get("status")} if r else None)
        rows.append({"date_time": t, "cells": cells})

    return {"columns": columns, "rows": rows}


def latest_reading_by_key(readings: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for r in readings:
        k = series_key(r)
        prev = out.get(k)
        if prev is None or str(r.get("date_time") or "") > str(prev.get("date_time") or ""):
            out[k] = r
    return out


MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def short_stamp(iso: str) -> str:
    """'2026-09-17T08:30:00' → '17 Sep' (graph ke x-axis labels ke liye)."""
    d = parse_iso(iso)
    if d is None:
        return ""
    return f"{d.day} {MONTHS_SHORT[d.month - 1]}"


def parse_iso(value: Any) -> Optional[_dt.datetime]:
    if isinstance(value, _dt.datetime):
        return value
    if not value:
        return None
    try:
        s = str(value).replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(s)
    except ValueError:
        return None


def format_dt(value: Any) -> str:
    """Report/table ke liye: '17 Sep 2026, 8:30 AM'."""
    d = parse_iso(value)
    if d is None:
        return str(value or "")
    hour = d.hour % 12 or 12
    ampm = "AM" if d.hour < 12 else "PM"
    return f"{d.day} {MONTHS_SHORT[d.month - 1]} {d.year}, {hour}:{d.minute:02d} {ampm}"
