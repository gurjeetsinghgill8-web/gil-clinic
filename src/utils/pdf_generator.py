"""
PDF Generator for OPD — Professional Indian prescription PDF and CME PDF.
Uses fpdf2 library. Mirrors the master file's make_rx_pdf() but returns
PDF bytes suitable for FastAPI HTTP responses (no Streamlit dependency).
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from fpdf import FPDF

logger = logging.getLogger(__name__)


def safe_str(text) -> str:
    """FPDF latin-1 safe: emoji/symbols hatao (koi '?' nahi bachega)."""
    try:
        s = str(text)
        out = []
        for ch in s:
            cp = ord(ch)
            if cp == 0x20B9:  # ₹
                out.append("Rs ")
            elif cp in (0x2013, 0x2014):  # en/em dash
                out.append("-")
            elif cp in (0x2018, 0x2019):  # single quotes
                out.append("'")
            elif cp in (0x201C, 0x201D):  # double quotes
                out.append('"')
            elif cp == 0x2022:  # bullet
                out.append("-")
            elif cp < 256:
                out.append(ch)
            # baaki (emoji, Hindi etc.) — drop, '?' kabhi nahi
        return "".join(out)
    except Exception:
        return str(text)


def make_rx_pdf(
    pt_name: str,
    vitals: str,
    rx_text: str,
    investigations: str = "",
    specialty_label: str = "",
    clinic_name: str = "My Clinic",
    doc_name: str = "Doctor",
    doc_degree: str = "MBBS",
    doc_subtitle: str = "",
    doc_reg_no: str = "",
    doc_phone: str = "",
    doc_email: str = "",
    clinic_address: str = "",
    doc_extra_quals: str = "",
) -> bytes:
    """
    Generate professional prescription PDF with Indian letterhead format.

    Args:
        pt_name: Patient name
        vitals: Vitals string (BP/HR/Sugar/Weight)
        rx_text: Prescription text (AI generated or edited)
        investigations: Additional investigations
        specialty_label: If specialty consult, show specialty name
        clinic_name: Clinic name for letterhead
        doc_name: Doctor name for letterhead
        doc_degree: Doctor degrees
        doc_subtitle: Doctor subtitle/specialty
        doc_reg_no: Registration number
        doc_phone: Doctor phone
        doc_email: Doctor email
        clinic_address: Clinic address
        doc_extra_quals: Extra qualifications

    Returns:
        PDF bytes
    """
    pdf = FPDF()
    pdf.add_page()

    # ── Letterhead Background ─────────────────────────────────────────
    # Full-width light blue background
    pdf.set_fill_color(235, 245, 255)
    pdf.rect(0, 0, 210, 58, "F")
    # Dark blue accent line
    pdf.set_draw_color(0, 51, 102)
    pdf.set_line_width(0.8)
    pdf.line(0, 58, 210, 58)
    pdf.set_line_width(0.2)

    # ── LEFT COLUMN: Doctor Info ─────────────────────────────────────
    # Doctor Name (larger, bold)
    pdf.set_xy(8, 4)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(100, 7, safe_str(doc_name), ln=False)

    # Degrees (below name)
    pdf.set_xy(8, 12)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 30, 120)
    pdf.cell(100, 5, safe_str(doc_degree), ln=False)

    # Specialty/Subtitle (below degrees)
    if doc_subtitle:
        pdf.set_xy(8, 18)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(60, 60, 120)
        pdf.cell(100, 5, safe_str(doc_subtitle), ln=False)

    # Extra Qualifications (below subtitle, up to 4 lines)
    if doc_extra_quals:
        extra_lines = [l.strip() for l in doc_extra_quals.split("\n") if l.strip()]
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(80, 80, 100)
        for i, eq in enumerate(extra_lines[:4]):
            pdf.set_xy(8, 24 + i * 4)
            pdf.cell(100, 4, safe_str(eq), ln=False)

    # ── RIGHT COLUMN: Clinic Info ────────────────────────────────────
    # Clinic Name
    pdf.set_xy(105, 4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(0, 51, 102)
    pdf.cell(97, 7, safe_str(clinic_name), ln=False, align="R")

    # Address lines
    addr_lines = []
    if clinic_address:
        addr_lines = [l.strip() for l in clinic_address.split("\n") if l.strip()]

    y_right = 12
    if addr_lines:
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(60, 60, 60)
        for al in addr_lines[:3]:
            pdf.set_xy(105, y_right)
            pdf.cell(97, 4.5, safe_str(al), ln=False, align="R")
            y_right += 4.5

    # Phone & Email on right
    contact_parts = []
    if doc_phone:
        contact_parts.append(f"📞 {doc_phone}")
    if doc_email:
        contact_parts.append(f"✉ {doc_email}")
    if contact_parts:
        pdf.set_xy(105, y_right)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(70, 70, 70)
        pdf.cell(97, 4.5, safe_str(" | ".join(contact_parts)), ln=False, align="R")
        y_right += 5

    # Registration Number
    if doc_reg_no:
        pdf.set_xy(105, y_right)
        pdf.set_font("Helvetica", "", 7.5)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(97, 4.5, safe_str(f"Reg No: {doc_reg_no}"), ln=False, align="R")

    # ── Patient Info Row ────────────────────────────────────────────
    y_info = 62
    pdf.set_xy(8, y_info)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(60, 6, f"Patient: {safe_str(pt_name)}", ln=False)

    # Date
    pdf.set_font("Helvetica", "", 9)
    pdf.set_xy(110, y_info)
    date_str = datetime.datetime.now().strftime("%d-%b-%Y %I:%M %p")
    pdf.cell(92, 6, f"Date: {date_str}", ln=False, align="R")

    # Vitals
    if vitals:
        pdf.set_xy(8, y_info + 7)
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(194, 6, safe_str(f"Vitals: {vitals}"), ln=False)

    # Specialty label (if upgrade)
    if specialty_label:
        pdf.set_xy(8, y_info + 14)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(180, 50, 50)
        pdf.cell(100, 6, safe_str(f"⚕️ {specialty_label} Consult"), ln=False)

    # ── Divider ─────────────────────────────────────────────────────
    y_pos = y_info + 20
    pdf.set_draw_color(200, 200, 200)
    pdf.line(8, y_pos, 202, y_pos)
    y_pos += 4

    # ── Prescription Body ───────────────────────────────────────────
    pdf.set_xy(8, y_pos)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.set_fill_color(250, 250, 250)

    # Split text into lines and write
    rx_lines = rx_text.split("\n") if rx_text else ["No prescription data."]
    line_height = 5
    for line in rx_lines:
        if y_pos > 270:  # Page bottom
            pdf.add_page()
            y_pos = 10

        line = line.strip()
        if not line:
            y_pos += 3
            continue

        # Bold for section headers (e.g. "Diagnosis:", "Drugs:")
        if any(line.startswith(h) for h in ["Diagnosis", "Drugs", "Advice", "Follow-up",
                                              "Investigations", "Rx", "Prescription"]):
            pdf.set_font("Helvetica", "B", 10)
            # Background tint for headers
            pdf.set_fill_color(240, 248, 255)
            pdf.set_xy(8, y_pos)
            pdf.cell(194, 6, safe_str(line), fill=True)
            y_pos += 7
            pdf.set_font("Helvetica", "", 10)
        else:
            pdf.set_xy(12, y_pos)
            # Check if it's a numbered item
            if line[:1].isdigit() and "." in line[:3]:
                pdf.set_x(12)
            else:
                pdf.set_x(12)
            pdf.multi_cell(186, line_height, safe_str(line))
            y_pos = pdf.get_y() + 1

        pdf.set_text_color(30, 30, 30)

    # ── Investigations Section ──────────────────────────────────────
    if investigations and investigations.strip():
        y_pos = max(y_pos, pdf.get_y()) + 4
        if y_pos > 260:
            pdf.add_page()
            y_pos = 10
        pdf.set_xy(8, y_pos)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(255, 245, 235)
        pdf.cell(194, 6, "Investigations:", fill=True)
        y_pos += 8
        pdf.set_xy(12, y_pos)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(186, 5, safe_str(investigations))

    # ── Footer ──────────────────────────────────────────────────────
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "This is a computer-generated prescription. Valid without signature.", align="C")

    result = pdf.output(dest="S")
    if isinstance(result, bytearray):
        return bytes(result)
    if isinstance(result, bytes):
        return result
    return result.encode("latin-1")


def make_cme_pdf(topic: str, content: str) -> bytes:
    """
    Generate CME study material PDF.

    Args:
        topic: CME topic title
        content: CME content (plain text with sections)

    Returns:
        PDF bytes
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(0, 51, 102)
    pdf.rect(0, 0, 210, 25, "F")
    pdf.set_xy(10, 5)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 10, safe_str(f"CME: {topic}"), align="C")
    pdf.set_xy(10, 15)
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(200, 220, 255)
    pdf.cell(190, 6, f"Generated: {datetime.datetime.now().strftime('%d-%b-%Y')}", align="C")

    y_pos = 30
    lines = content.split("\n") if content else ["No content."]
    for line in lines:
        line = line.strip()
        if not line:
            y_pos += 3
            continue
        if y_pos > 270:
            pdf.add_page()
            y_pos = 10
        pdf.set_xy(10, y_pos)
        pdf.set_text_color(30, 30, 30)

        # Section headers
        if line.endswith(":") or line.isupper():
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(240, 245, 255)
            pdf.cell(190, 6, safe_str(line), fill=True)
            y_pos += 7
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_x(14)
            pdf.multi_cell(182, 5, safe_str(line))
            y_pos = pdf.get_y() + 1

    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, safe_str("Bharat AI Clinic — CME Study Material"), align="C")

    result = pdf.output(dest="S")
    if isinstance(result, bytearray):
        return bytes(result)
    if isinstance(result, bytes):
        return result
    return result.encode("latin-1")


def make_diet_pdf(
    patient_name: str,
    age: str = "",
    gender: str = "",
    weight: str = "",
    height: str = "",
    bmi: str = "",
    conditions: str = "",
    goal: str = "",
    diet_type: str = "",
    target_calories: str = "",
    diet_plan: str = "",
    clinic_name: str = "",
    doc_name: str = "Dietitian",
    phone: str = "",
) -> bytes:
    """
    Generate a professional Clinical Diet Plan PDF following international standards.

    Features:
    - Clinic letterhead with green theme
    - Patient info box
    - Prescribed macro-nutrient targets table
    - Per-meal nutritional breakdown (Protein | Fiber | Calories per food item)
    - Daily nutrition summary
    - Foods to include/avoid sections
    - Professional footer
    """
    pdf = FPDF()
    pdf.add_page()

    # ── Letterhead ──────────────────────────────────────────────
    pdf.set_fill_color(0, 100, 50)
    pdf.rect(0, 0, 210, 38, "F")
    pdf.set_xy(10, 5)
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(190, 10, safe_str("Clinical Dietary Prescription"), align="C")
    header_y = 17
    if clinic_name:
        pdf.set_xy(10, header_y)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(200, 255, 220)
        pdf.cell(190, 5, safe_str(clinic_name), align="C")
        header_y = 23
    pdf.set_xy(10, header_y)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(180, 240, 200)
    pdf.cell(190, 5, "Prepared by AI - Reconfirm by Dietitian", align="C")
    pdf.set_xy(10, header_y + 6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.cell(190, 5, f"Date: {datetime.datetime.now().strftime('%d-%b-%Y')} | IFCT/NIN/ICMR Compliant", align="C")

    y_pos = 44

    # ── Patient Info Box ────────────────────────────────────────
    pdf.set_fill_color(235, 250, 240)
    pdf.set_draw_color(0, 150, 80)
    pdf.rect(10, y_pos, 190, 32, "DF")
    pdf.set_xy(14, y_pos + 3)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(0, 80, 40)
    pdf.cell(90, 5, f"Patient: {safe_str(patient_name)}", ln=False)

    pdf.set_xy(110, y_pos + 3)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 80, 40)
    info_parts = []
    if age: info_parts.append(f"Age: {age}")
    if gender: info_parts.append(f"Gender: {gender}")
    pdf.cell(86, 5, " | ".join(info_parts), ln=False, align="R")

    pdf.set_xy(14, y_pos + 11)
    pdf.set_font("Helvetica", "", 8.5)
    details = []
    if weight: details.append(f"Wt: {weight} kg")
    if height: details.append(f"Ht: {height} cm")
    if bmi: details.append(f"BMI: {bmi}")
    if phone: details.append(f"Ph: {phone}")
    pdf.multi_cell(182, 4.5, " | ".join(details))

    pdf.set_xy(14, y_pos + 18)
    pdf.set_font("Helvetica", "", 8.5)
    meta = []
    if conditions: meta.append(f"Conditions: {conditions}")
    if goal: meta.append(f"Goal: {goal}")
    if diet_type: meta.append(f"Diet: {diet_type}")
    if target_calories: meta.append(f"Target: {target_calories} kcal")
    pdf.multi_cell(182, 4.5, " | ".join(meta))

    y_pos += 38

    # ── Divider ─────────────────────────────────────────────────
    pdf.set_draw_color(0, 150, 80)
    pdf.set_line_width(0.5)
    pdf.line(10, y_pos, 200, y_pos)
    y_pos += 5

    # ── Diet Plan Content ───────────────────────────────────────
    if diet_plan:
        lines = diet_plan.split("\n")
        pdf.set_text_color(30, 30, 30)

        # Track if we're inside a table-like section
        in_table = False

        for line in lines:
            line_stripped = line.strip()
            line_display = line  # keep original indentation for display
            if not line_stripped:
                y_pos += 2
                continue

            # Page overflow check
            if y_pos > 265:
                pdf.add_page()
                y_pos = 10

            # Detect section headers
            is_section_header = (
                line_stripped.startswith("CLINICAL DIETARY")
                or line_stripped.startswith("PRESCRIBED NUTRITION")
                or line_stripped.startswith("DAILY MEAL PLAN")
                or line_stripped.startswith("DAILY NUTRITION SUMMARY")
                or line_stripped.startswith("PROTEIN SOURCES")
                or line_stripped.startswith("FIBER SOURCES")
                or line_stripped.startswith("FOODS TO INCLUDE")
                or line_stripped.startswith("FOODS TO LIMIT")
                or line_stripped.startswith("LIFESTYLE")
                or line_stripped.startswith("INDIAN HEALTHY")
                or line_stripped.startswith("WEEK 1 SAMPLE")
                or line_stripped.startswith("Follow-up")
            )

            # Detect macro targets line
            is_macro_line = (
                line_stripped.startswith("CALORIES:")
                or line_stripped.startswith("PROTEIN:")
                or line_stripped.startswith("CARBOHYDRATES:")
                or line_stripped.startswith("FAT:")
                or line_stripped.startswith("FIBER:")
                or line_stripped.startswith("WATER:")
            )

            # Detect food item with → Protein/Fiber/Calories
            is_food_detail = "→ Protein:" in line_stripped or "Protein:" in line_stripped

            # Detect summary totals
            is_summary = line_stripped.startswith("TOTAL PROTEIN") or line_stripped.startswith("TOTAL FIBER") or line_stripped.startswith("TOTAL CALORIES")

            # Detect PATIENT / WEIGHT / CONDITIONS info line
            is_info_line = (
                line_stripped.startswith("PATIENT:")
                or line_stripped.startswith("WEIGHT:")
                or line_stripped.startswith("CONDITIONS:")
                or line_stripped.startswith("DIET TYPE:")
            )

            if is_section_header:
                # Section header — green background
                pdf.set_fill_color(220, 245, 230)
                pdf.set_font("Helvetica", "B", 9.5)
                if y_pos > 10:
                    y_pos += 3
                pdf.set_xy(10, y_pos)
                pdf.cell(190, 6, safe_str(line_stripped), fill=True)
                y_pos += 7
                in_table = True

            elif is_macro_line:
                # Macro target — bold with highlight
                pdf.set_fill_color(240, 250, 242)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_xy(14, y_pos)
                pdf.cell(182, 5.5, safe_str(line_stripped), fill=True)
                y_pos += 6.5

            elif is_food_detail:
                # Food protein/fiber/calories detail — monospace style, indented
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(60, 60, 60)
                pdf.set_xy(18, y_pos)
                pdf.multi_cell(178, 4.5, safe_str(line_stripped))
                y_pos = pdf.get_y() + 1

            elif is_summary:
                # Summary line — bold, blue-ish
                pdf.set_fill_color(235, 245, 255)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_xy(14, y_pos)
                pdf.cell(182, 5.5, safe_str(line_stripped), fill=True)
                y_pos += 6.5

            elif is_info_line:
                # Info line — smaller, muted
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(80, 80, 80)
                pdf.set_xy(14, y_pos)
                pdf.cell(182, 4.5, safe_str(line_stripped))
                y_pos += 5

            elif line_stripped.startswith("•") or line_stripped.startswith("-"):
                # Meal item bullet
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.set_xy(14, y_pos)
                pdf.multi_cell(182, 4.5, safe_str(line_stripped))
                y_pos = pdf.get_y() + 1

            elif line_stripped.startswith("GIL CLINIC"):
                # Clinic line — center
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(0, 100, 50)
                pdf.set_xy(10, y_pos)
                pdf.cell(190, 4.5, safe_str(line_stripped), align="C")
                y_pos += 5

            else:
                # Regular body text
                pdf.set_font("Helvetica", "", 9)
                pdf.set_text_color(40, 40, 40)
                pdf.set_xy(14, y_pos)
                pdf.multi_cell(182, 4.5, safe_str(line_stripped))
                y_pos = pdf.get_y() + 1.5

    # ── Footer ──────────────────────────────────────────────────
    pdf.set_y(-15)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 10, "This diet plan is AI-generated using IFCT/NIN/ICMR guidelines. Should be reviewed by a qualified dietitian.", align="C")

    result = pdf.output(dest="S")
    if isinstance(result, bytearray):
        return bytes(result)
    if isinstance(result, bytes):
        return result
    return result.encode("latin-1")
