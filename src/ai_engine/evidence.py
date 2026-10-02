"""
evidence.py — Evidence Source Library + Master Clinical Rules + verification helpers.

Three-engine architecture (clinical decision support):
    1. Clinical Reasoning Engine — patient data → safety assessment → differential
    2. Evidence Retrieval Engine — clinical question → relevant guideline → verified evidence
    3. Prescription Engine      — assessment + verified evidence → draft prescription

The specialty button changes the clinical reasoning framework AND the evidence
retrieval strategy — not merely the wording of the prescription.
"""

import re
from typing import Dict, List, Optional

# ════════════════════════════════════════════════════════════════════════════
# MASTER CLINICAL RULES — injected into every clinical AI prompt
# ════════════════════════════════════════════════════════════════════════════

MASTER_CLINICAL_RULES = """
MASTER CLINICAL RULES (non-negotiable — apply to EVERY response):
1. Do not generate a prescription from memory. First establish the clinical problem, then retrieve and verify the relevant current evidence, then draft the prescription.
2. Never invent a diagnosis from your own memory. Work ONLY from the patient data actually provided (vitals, symptoms, examination, history, doctor's own diagnosis/medicines).
3. Never silently modify, rewrite, or overwrite the doctor's diagnosis, medicines, or prescription. Every change must be a clearly labelled suggestion (ADD / MODIFY / REMOVE) for physician review.
4. SAFETY FIRST: any high-risk finding (e.g. BP >= 180/120, chest pain, SpO2 < 90, altered sensorium, focal deficit, red-flag symptoms) triggers a SAFETY ASSESSMENT before any prescription content. Hypertensive emergency is NOT defined by the BP number alone — advise repeat measurement and assess for symptoms / target-organ injury.
5. Every recommendation must cite its source as [Guideline/Society name, year]. If you cannot verify the exact guideline name and year, mark that recommendation "Evidence not verified" — never present an unverified statement as guideline-based.
6. Use CURRENT guideline versions when they exist (e.g. 2025 AHA/ACC and 2024 ESC hypertension guidelines). Never silently default to an outdated guideline version.
7. A specialty change means changing the clinical reasoning framework and evidence sources — not just re-wording the prescription.
8. Final diagnosis, prescription, and treatment decisions remain with the treating physician. This is clinical decision support — not a substitute for physician judgment.
9. Never add chronic conditions (diabetes, hypertension, CKD…) unless stated in the patient data or clearly abnormal vitals/values support them.
10. If information is insufficient for a firm statement, say what is needed instead of guessing.
""".strip()


# ════════════════════════════════════════════════════════════════════════════
# EVIDENCE SOURCE LIBRARY — specialty → verified primary sources
# NOTE: this is a source list only. The relevant guideline must still be
# retrieved and verified for each clinical question.
# ════════════════════════════════════════════════════════════════════════════

EVIDENCE_LIBRARY: Dict[str, dict] = {
    "🩺 General Medicine": {
        "label": "General Medicine",
        "sources": ["ACP", "NICE", "WHO", "ICMR", "Harrison", "Goldman-Cecil"],
        "guidelines": [
            "ACP Clinical Guidelines (current version)",
            "NICE Clinical Guidelines (current version)",
            "WHO Essential Medicines / clinical guidance",
            "Harrison's Principles of Internal Medicine (latest edition)",
            "Goldman-Cecil Medicine (latest edition)",
        ],
    },
    "❤️ Cardiology": {
        "label": "Cardiology",
        "sources": ["ACC", "AHA", "ESC", "ESH"],
        "guidelines": [
            "ACC/AHA 2025 Hypertension Guideline",
            "ESC 2024 Hypertension Guidelines",
            "ESC 2024 Atrial Fibrillation Guidelines (AF-CARE pathway)",
            "ACC/AHA 2023 Chronic Coronary Disease Guideline",
            "ESC 2026 Heart Failure Guidelines",
            "ACC/AHA Guideline Methodology (Class of Recommendation / Level of Evidence)",
        ],
    },
    "💓 Echocardiography": {
        "label": "Echocardiography",
        "sources": ["ASE", "EACVI"],
        "guidelines": [
            "ASE/EACVI Chamber Quantification Recommendations (latest revision)",
            "ASE Standards for Adult Echocardiography Reporting",
            "ASE/EACVI Diastolic Function Assessment (latest revision)",
            "ASE/EACVI Valvular Regurgitation & Stenosis Recommendations (latest revision)",
        ],
    },
    "🦠 Infectious Diseases": {
        "label": "Infectious Diseases",
        "sources": ["IDSA", "ICMR", "WHO", "CDC"],
        "guidelines": [
            "IDSA Clinical Practice Guidelines (current version)",
            "ICMR Treatment Guidelines (India)",
            "WHO clinical guidance (current version)",
        ],
    },
    "🩸 Diabetology": {
        "label": "Diabetes",
        "sources": ["ADA", "RSSDI"],
        "guidelines": [
            "ADA Standards of Care 2025/2026",
            "RSSDI Clinical Practice Guidelines (current version)",
        ],
    },
    "🩺 Nephrology": {
        "label": "Nephrology",
        "sources": ["KDIGO", "ISN", "RSI"],
        "guidelines": [
            "KDIGO 2024 Clinical Practice Guidelines",
            "ISN / RSI (India) guidance (current version)",
        ],
    },
    "🫁 Pulmonology": {
        "label": "Pulmonology",
        "sources": ["GOLD", "GINA", "ATS", "ERS", "BTS", "IDSA"],
        "guidelines": [
            "GOLD 2025 COPD Strategy",
            "GINA Asthma Guidelines (current version)",
            "ATS/ERS Technical Standards (current version)",
            "ATS/IDSA CAP Guidelines (current version)",
        ],
    },
    "🩺 Gastroenterology": {
        "label": "Gastroenterology",
        "sources": ["ACG", "AGA", "AASLD", "EASL", "ISG", "INASL"],
        "guidelines": [
            "ACG Clinical Guidelines (current version)",
            "AGA Clinical Practice Updates (current version)",
            "AASLD / EASL Liver Disease & MASLD Guidelines (current version)",
            "ISG / INASL (India) Guidelines (current version)",
        ],
    },
    "🧪 Endocrinology": {
        "label": "Endocrinology",
        "sources": ["Endocrine Society", "AACE", "ATA", "ISE"],
        "guidelines": [
            "Endocrine Society Clinical Practice Guidelines (current version)",
            "ATA Thyroid Guidelines (current version)",
            "AACE Clinical Practice Guidelines (current version)",
        ],
    },
    "🧠 Neurology": {
        "label": "Neurology",
        "sources": ["AAN", "ESO", "IHS", "ILAE", "IAN"],
        "guidelines": [
            "AAN Clinical Practice Guidelines (current version)",
            "ESO Stroke Guidelines 2024",
            "IHS ICHD-3 Migraine Classification",
            "ILAE Epilepsy Guidelines (current version)",
        ],
    },
    "🦴 Orthopedics": {
        "label": "Orthopedics",
        "sources": ["AAOS", "NICE", "IOA"],
        "guidelines": [
            "AAOS Clinical Practice Guidelines (current version)",
            "NICE Musculoskeletal Guidelines (current version)",
            "IOA (India) Guidelines (current version)",
        ],
    },
    "👶 Pediatrics": {
        "label": "Pediatrics",
        "sources": ["IAP", "WHO", "AAP", "NNF"],
        "guidelines": [
            "IAP Immunization Schedule (current version)",
            "WHO IMCI Guidelines",
            "AAP Clinical Practice Guidelines (current version)",
        ],
    },
    "👩‍⚕️ Gynecology": {
        "label": "Gynecology",
        "sources": ["FOGSI", "RCOG", "ACOG", "WHO"],
        "guidelines": [
            "FOGSI Clinical Protocols (current version)",
            "RCOG Green-top Guidelines (current version)",
            "ACOG Practice Bulletins (current version)",
        ],
    },
    "👁️ Ophthalmology": {
        "label": "Ophthalmology",
        "sources": ["AAO", "ICO", "AIOS"],
        "guidelines": [
            "AAO Preferred Practice Patterns (current version)",
            "ICO / AIOS (India) Guidelines (current version)",
        ],
    },
    "👂 ENT": {
        "label": "ENT",
        "sources": ["AAO-HNS", "AOI"],
        "guidelines": [
            "AAO-HNS Clinical Practice Guidelines (current version)",
            "AOI (India) Protocols (current version)",
        ],
    },
    "🧬 Dermatology": {
        "label": "Dermatology",
        "sources": ["IADVL", "AAD", "BAD"],
        "guidelines": [
            "IADVL Clinical Guidelines (current version)",
            "AAD Clinical Guidelines (current version)",
            "BAD Guidelines (current version)",
        ],
    },
    "🫀 Rheumatology": {
        "label": "Rheumatology",
        "sources": ["ACR", "EULAR", "IRA"],
        "guidelines": [
            "ACR Clinical Practice Guidelines (current version)",
            "EULAR Recommendations (current version)",
            "IRA (India) Guidelines (current version)",
        ],
    },
    "🧠 Psychiatry": {
        "label": "Psychiatry",
        "sources": ["APA", "IPS", "WHO", "NICE"],
        "guidelines": [
            "APA Practice Guidelines (current version)",
            "IPS (India) Clinical Guidelines (current version)",
            "WHO mhGAP 2.0",
        ],
    },
    "🩺 Urology": {
        "label": "Urology",
        "sources": ["AUA", "EAU", "USI"],
        "guidelines": [
            "AUA Clinical Guidelines (current version)",
            "EAU Guidelines (current version)",
            "USI (India) Protocols (current version)",
        ],
    },
    "🩺 Oncology": {
        "label": "Oncology",
        "sources": ["NCCN", "ASCO", "ICMR"],
        "guidelines": [
            "NCCN Clinical Practice Guidelines (current version)",
            "ASCO Guidelines (current version)",
            "ICMR Cancer Guidelines (India)",
        ],
    },
    "🩺 General Surgery": {
        "label": "General Surgery",
        "sources": ["ACS", "AMASI", "IAGES"],
        "guidelines": [
            "ACS Surgery Guidelines (current version)",
            "AMASI / IAGES (India) Protocols (current version)",
        ],
    },
}


def library_for(specialty_key: str) -> Optional[dict]:
    """Return the evidence library entry for a specialty key (emoji key or plain name)."""
    if not specialty_key:
        return None
    entry = EVIDENCE_LIBRARY.get(specialty_key)
    if entry is not None:
        return entry
    for key, val in EVIDENCE_LIBRARY.items():
        if key.replace(" ", "") == specialty_key.replace(" ", ""):
            return val
        if val.get("label", "").strip().lower() == specialty_key.strip().lower():
            return val
    return None


def sources_for_prompt(specialty_key: str) -> str:
    """Text block listing a specialty's verified sources + allowed guidelines, for prompts."""
    entry = library_for(specialty_key)
    if not entry:
        return (
            "PRIMARY SOURCES: None pre-verified for this specialty.\n"
            "ALLOWED GUIDELINES: NONE pre-verified — every recommendation MUST be marked "
            "\"Evidence not verified\" unless the exact guideline name and year can be confirmed."
        )
    sources = ", ".join(entry["sources"])
    guidelines = "\n".join(f"- {g}" for g in entry["guidelines"])
    return (
        f"PRIMARY SOURCES (verified library): {sources}\n"
        f"ALLOWED GUIDELINES (cite ONLY from this list, with name + year):\n{guidelines}\n"
        "If the exact guideline name and year for a recommendation cannot be confirmed from this "
        "list, mark that recommendation \"Evidence not verified\"."
    )


def evidence_status(text: str, specialty_key: str) -> str:
    """
    Badge check: does the output actually cite a verified source with a year?
    Returns "verified" or "not_verified". Conservative by design — no citation,
    no verified badge.
    """
    if not text or not text.strip():
        return "not_verified"
    entry = library_for(specialty_key)
    if not entry:
        return "not_verified"
    lowered = text.lower()
    has_source = any(tok.lower() in lowered for tok in entry["sources"])
    has_year = bool(re.search(r"\b(19|20)\d{2}\b", text))
    return "verified" if (has_source and has_year) else "not_verified"


def evidence_badge_html(status: str) -> str:
    """Small HTML badge for verified / not-verified status (frontend helper)."""
    if status == "verified":
        return ('<span class="ev-badge ev-verified" title="Official guideline or authoritative '
                'source verified.">✅ Evidence verified</span>')
    return ('<span class="ev-badge ev-unverified" title="Do not treat as a confirmed '
            'guideline-based recommendation.">⚠️ Evidence not verified</span>')
