"""Token labels — ``C-14`` / ``G-14`` / ``E-1``.

Why this file exists
--------------------
Two doctors sit in the same clinic. Dr. Gill (Cardiology) and Dr. Sharma
(General) each call out "token 14". Both patients stand up. The *data* was
already correct — ``queue_entries`` has been partitioned by
``(clinic_id, doctor_id, service_code)`` since Part D · E-04 — but the number
the patient HEARS was ambiguous.

So the display gets a prefix taken from the specialty, and an emergency case
gets its own ``E`` sequence so it can never be mistaken for a routine token:

    C-14   → Cardiology
    G-14   → General / General Physician
    E-1    → Emergency (Code Red)

Design rules:
  * PURE FUNCTIONS ONLY — no DB, no ORM, no FastAPI. Same contract as
    ``ewt.py``, so the label rule is unit-testable and safe anywhere.
  * The prefix is **display sugar only**. Uniqueness still comes from the
    ``(clinic, doctor, service, token)`` partition, so a prefix collision
    (two specialties both starting with "P") can never merge two queues.
    That is why the fallback is a plain first letter instead of a lookup that
    could fail.
"""

from __future__ import annotations

from typing import Any

#: Emergency tokens get their own sequence and the ``E`` prefix.
EMERGENCY_PREFIX = "E"

#: Specialty → prefix. Only the ones where the first letter would be
#: misleading (or collide with a much more common specialty) are pinned.
SPECIALTY_PREFIX: dict[str, str] = {
    "cardiology": "C",
    "general physician": "G",
    "general": "G",
    "general medicine": "G",
    "medicine": "G",
    "orthopedics": "O",
    "orthopaedics": "O",
    "pediatrics": "P",
    "paediatrics": "P",
    "dermatology": "D",
    "gynecology": "N",
    "gynaecology": "N",
    "ent": "T",
    "ophthalmology": "Y",
    "dental": "M",
    "dentistry": "M",
    "gastroenterology": "S",
}

#: Fallback when a clinic has no specialty configured at all.
DEFAULT_PREFIX = "T"  # "Token"


def specialty_prefix(specialty: Any) -> str:
    """``"Cardiology"`` → ``"C"`` · ``"General Physician"`` → ``"G"``.

    Falls back to the first alphabetic character of the specialty, and to
    :data:`DEFAULT_PREFIX` when there is nothing usable — a label must never
    be empty, because an empty label reads as a bug to the patient.
    """
    text = str(specialty or "").strip().lower()
    if not text:
        return DEFAULT_PREFIX
    if text in SPECIALTY_PREFIX:
        return SPECIALTY_PREFIX[text]
    # Try the leading word too: "Cardiology (Interventional)" → "cardiology".
    head = text.replace("(", " ").replace("-", " ").split()
    if head and head[0] in SPECIALTY_PREFIX:
        return SPECIALTY_PREFIX[head[0]]
    for char in text:
        if char.isalpha():
            return char.upper()
    return DEFAULT_PREFIX


def is_emergency(entry: Any) -> bool:
    """Is this queue entry an emergency (Code Red) case?

    Recognised from the ``visit_type`` the queue engine already writes, so no
    new boolean column is needed and QE 0-3 keep working.
    """
    if entry is None:
        return False
    visit_type = ""
    if isinstance(entry, dict):
        visit_type = str(entry.get("visit_type") or "")
    else:
        visit_type = str(getattr(entry, "visit_type", "") or "")
    return visit_type.strip().lower() == "emergency"


def token_label(
    token_number: Any,
    prefix: str = "",
    emergency: bool = False,
) -> str:
    """Build the label a patient hears: ``"C-14"`` · ``"E-1"`` · ``"14"``.

    With no prefix it degrades to the bare number, which is exactly what the
    app showed before this module existed — so an unconfigured clinic loses
    nothing.
    """
    try:
        number = int(token_number or 0)
    except (TypeError, ValueError):
        number = 0
    if number <= 0:
        return ""
    mark = (EMERGENCY_PREFIX if emergency else str(prefix or "")).strip().upper()
    return f"{mark}-{number}" if mark else str(number)


def entry_label(
    entry: Any,
    specialty: Any = "",
    prefix: Any = "",
) -> str:
    """Label one queue entry, deciding emergency vs specialty prefix itself.

    ``prefix`` may be passed explicitly (a caller that already resolved the
    clinic's specialty); otherwise it is derived from ``specialty``.
    """
    if entry is None:
        return ""
    if isinstance(entry, dict):
        token = entry.get("token_number")
    else:
        token = getattr(entry, "token_number", None)
    if is_emergency(entry):
        return token_label(token, emergency=True)
    return token_label(token, prefix=str(prefix or "") or specialty_prefix(specialty))


def next_emergency_token(existing_tokens: Any) -> int:
    """Next ``E`` number from today's emergency tokens.

    Kept separate from the routine ``MAX(token_number)`` counter on purpose:
    an emergency must never consume a routine number, because the routine
    patients would then see a gap and assume someone was skipped.
    """
    highest = 0
    for value in existing_tokens or []:
        try:
            number = int(value or 0)
        except (TypeError, ValueError):
            continue
        highest = max(highest, number)
    return highest + 1
