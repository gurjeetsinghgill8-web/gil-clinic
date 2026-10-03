"""Crawl run tracking + the doctor profile schema (BLOCK 5 · Module 6).

Why the schema lives in the app and not only in the worker
---------------------------------------------------------
The crawler runs outside this host (PythonAnywhere free has no outbound
internet, no cron, and ~100 CPU-seconds a day — see Part E). But the *shape* of
what it is allowed to send back belongs here, next to the endpoint that accepts
it. Otherwise the worker and the API drift, and the failure mode is silent:
extraction starts emitting a field nobody validates, and a wrong phone number
ends up on a public listing.

So: the worker imports this schema, and the ingest endpoint validates against
the same schema. One definition, two processes.

The model-discovery fallback in :func:`coerce_profiles` exists because LLM
extraction is not deterministic — the same instruction sometimes returns a bare
list, sometimes ``{"doctors": [...]}``, sometimes a single object. Failing on
that would make the whole pipeline flaky for no reason.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base

# ── Run outcomes ────────────────────────────────────────────────────────────

RUN_RUNNING = "RUNNING"
RUN_COMPLETED = "COMPLETED"
RUN_FAILED = "FAILED"

#: Where a profile came from, in the order we trust it.
SOURCE_CRAWL = "crawl"
SOURCE_CLAIM = "claim"
SOURCE_MANUAL = "manual"


class DoctorCrawlRunModel(Base):
    """One execution of the ingestion worker.

    Kept because "the directory has 500 clinics" is not an answer to "where did
    they come from, and is that data still fresh?". A run row records what was
    attempted, what was accepted, what was rejected and why.
    """

    __tablename__ = "doctor_crawl_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    #: Human label for the batch, e.g. "jodhpur-cardiology".
    run_label: Mapped[str] = mapped_column(
        String(120), nullable=False, default="", server_default=""
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=RUN_RUNNING, server_default="RUNNING"
    )
    #: Who or what triggered it: "github-actions" | "manual" | "cli".
    triggered_by: Mapped[str] = mapped_column(
        String(60), nullable=False, default="", server_default=""
    )

    urls_attempted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    profiles_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    profiles_created: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    profiles_updated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    #: Rejected because the clinic opted out, the row was a duplicate, or the
    #: profile failed validation. Counted separately so the reason is visible.
    profiles_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    skipped_reasons: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )
    error: Mapped[str] = mapped_column(
        Text, nullable=False, default="", server_default=""
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<DoctorCrawlRun {self.run_label} {self.status} "
            f"found={self.profiles_found} created={self.profiles_created}>"
        )


# ── The profile contract (shared with the worker) ───────────────────────────

#: Fields the worker may send, and which of them are required. Kept as plain
#: data (not a pydantic model) so the worker can import it without pulling in
#: this app's dependency tree.
REQUIRED_FIELDS: tuple[str, ...] = ("doctor_name",)
OPTIONAL_FIELDS: tuple[str, ...] = (
    "clinic_name", "specialty", "degree", "reg_no", "phone", "email",
    "address", "city", "state", "latitude", "longitude", "source_url",
    "opd_timing", "notes",
)

#: Hard caps. A crawled listing must never be able to inject a novel into the
#: directory, and an over-long field is a sign of a bad extraction, not of a
#: thorough one.
FIELD_LIMITS: dict[str, int] = {
    "doctor_name": 200, "clinic_name": 200, "specialty": 100, "degree": 500,
    "reg_no": 100, "phone": 20, "email": 200, "address": 1000, "city": 100,
    "state": 100, "source_url": 500, "opd_timing": 200, "notes": 2000,
}

#: The instruction handed to the extraction model. Lives here so the worker and
#: this module cannot disagree about what was asked for.
EXTRACTION_INSTRUCTION = (
    "Extract every doctor listed on this page as a separate object with these "
    "fields: doctor_name, clinic_name, specialty, degree, reg_no, phone, email, "
    "address, city, state, opd_timing. Use only text present on the page. Leave "
    "a field empty rather than guessing it — never invent a phone number, a "
    "registration number, or a qualification. Do not merge two doctors into one "
    "object."
)


def doctor_profile_schema() -> dict[str, Any]:
    """JSON Schema for one extracted doctor profile.

    Returned as a plain dict so both ``crawl4ai``'s ``LLMExtractionStrategy``
    and this app's validator can consume the identical definition.
    """
    properties: dict[str, Any] = {}
    for field in OPTIONAL_FIELDS + REQUIRED_FIELDS:
        if field in ("latitude", "longitude"):
            properties[field] = {"type": ["number", "null"]}
        else:
            properties[field] = {
                "type": "string",
                "maxLength": FIELD_LIMITS.get(field, 200),
            }
    return {
        "type": "object",
        "properties": properties,
        "required": list(REQUIRED_FIELDS),
        "additionalProperties": False,
    }


#: Stable reason codes for a rejected profile. The ingest endpoint buckets its
#: skip counts by these, NOT by the human message — bucketing by message text
#: produced a separate counter per distinct junk value ("'N/A'": 1, "'--'": 1),
#: which tells a worker nothing and defeats the point of tracking rejections.
REJECT_NOT_AN_OBJECT = "not_an_object"
REJECT_MISSING_NAME = "missing_name"
REJECT_NAMELESS = "nameless"
REJECT_PLACEHOLDER_NAME = "placeholder_name"
REJECT_OPTED_OUT = "opted_out"
REJECT_DUPLICATE = "duplicate_in_batch"


class ProfileValidationError(ValueError):
    """A profile that must not enter the directory, with the reason.

    ``code`` is the stable bucket the caller counts; ``reason`` is what a human
    reads. Keeping them separate is what makes the skip report aggregatable.
    """

    def __init__(self, reason: str, index: int = -1, code: str = "invalid"):
        self.reason = reason
        self.code = code
        self.index = index
        super().__init__(f"profile[{index}]: {reason}" if index >= 0 else reason)


def coerce_profiles(payload: Any) -> list[dict[str, Any]]:
    """Turn whatever the extractor returned into a list of dicts.

    LLM extraction is not deterministic: the same instruction returns a bare
    list, a ``{"doctors": [...]}`` wrapper, a single object, or occasionally a
    JSON string of any of those. Rejecting the wrappers would make the pipeline
    flaky for no reason, so unwrap them — but never invent a profile.
    """
    import json

    if payload is None:
        return []
    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return []
        try:
            return coerce_profiles(json.loads(text))
        except (ValueError, TypeError):
            return []
    if isinstance(payload, dict):
        for key in ("doctors", "profiles", "data", "results", "items", "records"):
            if isinstance(payload.get(key), list):
                return coerce_profiles(payload[key])
        # A single profile object, not a wrapper.
        if any(k in payload for k in REQUIRED_FIELDS):
            return [payload]
        return []
    if isinstance(payload, list):
        out: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, str):
                out.extend(coerce_profiles(item))
        return out
    return []


#: Field values an extractor emits when it found nothing. These are not names,
#: and a listing called "N/A (N/A Clinic)" is worse than no listing: it fills a
#: patient's search result with nothing and makes the directory look broken.
PLACEHOLDER_VALUES: frozenset[str] = frozenset(
    {
        "n/a", "na", "nil", "none", "null", "unknown", "not available",
        "not found", "tbd", "tba", "test", "testing", "sample", "demo",
        "xxx", "xxxx", "xxxxx", "doctor", "dr", "drs", "name", "doctor name",
        "-", "--", "---", ".", "..", "...", "?", "??", "0", "123", "abc",
    }
)


def _is_placeholder(value: str) -> bool:
    """Is this field really just a "nothing here" marker?"""
    text = (value or "").strip().lower()
    if not text:
        return True
    if text in PLACEHOLDER_VALUES:
        return True
    # Strip punctuation so "N / A" and "N.A." are caught too.
    squeezed = "".join(ch for ch in text if ch.isalnum())
    return squeezed in PLACEHOLDER_VALUES or squeezed == ""


def normalise_profile(raw: dict[str, Any], index: int = -1) -> dict[str, Any]:
    """Validate and clean one profile, or raise :class:`ProfileValidationError`.

    Rules, and the reason each exists:

      * ``doctor_name`` is required — a listing with no name is not a listing.
      * Unknown keys are DROPPED, not stored: an extractor that starts emitting
        a new field must not be able to write it to the database unreviewed.
      * Values are truncated to the documented limit rather than rejected, so
        one verbose address does not discard an otherwise good profile.
      * Phone numbers are reduced to digits with a 10-digit check, because a
        wrong phone number on a public listing sends a patient to a stranger.
      * Latitude/longitude are only kept when they are real coordinates; a
        ``(0, 0)`` placeholder is the classic "no fix" value and is not a place.
    """
    if not isinstance(raw, dict):
        raise ProfileValidationError("not an object", index, code=REJECT_NOT_AN_OBJECT)

    clean: dict[str, Any] = {}
    for field in OPTIONAL_FIELDS + REQUIRED_FIELDS:
        value = raw.get(field)
        if value is None:
            continue
        if field in ("latitude", "longitude"):
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if number == 0.0:
                continue  # placeholder, not a coordinate
            if field == "latitude" and not (-90 <= number <= 90):
                continue
            if field == "longitude" and not (-180 <= number <= 180):
                continue
            clean[field] = number
            continue
        text = str(value).strip()
        if not text:
            continue
        limit = FIELD_LIMITS.get(field, 200)
        clean[field] = text[:limit]

    name = clean.get("doctor_name", "")
    if not name:
        raise ProfileValidationError(
            "doctor_name is required", index, code=REJECT_MISSING_NAME
        )
    # A name with no letters is a parsing artefact ("-", "123")…
    if not any(ch.isalpha() for ch in name):
        raise ProfileValidationError(
            f"doctor_name is not a name: {name!r}", index, code=REJECT_NAMELESS
        )
    # …and "N/A" / "Not available" / "Unknown" are the extractor saying it found
    # nothing. Both must be dropped, not published as a clinic.
    if _is_placeholder(name):
        raise ProfileValidationError(
            f"doctor_name is a placeholder, not a name: {name!r}",
            index,
            code=REJECT_PLACEHOLDER_NAME,
        )

    phone = clean.get("phone")
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        if digits.startswith("91") and len(digits) == 12:
            digits = digits[2:]
        if digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        if len(digits) == 10 and digits[0] in "6789":
            clean["phone"] = digits
        else:
            # Drop a phone we cannot trust rather than publish a wrong number.
            clean.pop("phone", None)

    return clean


def profile_identity(profile: dict[str, Any]) -> str:
    """A stable key for de-duplicating a crawled profile.

    Deliberately ``name + city`` lowercased rather than the source URL: the
    same doctor is usually listed on several pages, and one page often lists
    several doctors. Name+city is what a human would use, so two crawl runs
    over overlapping sources do not create twins.
    """
    name = str(profile.get("doctor_name") or "").strip().lower()
    city = str(profile.get("city") or "").strip().lower()
    clinic = str(profile.get("clinic_name") or "").strip().lower()
    return f"{name}|{city}|{clinic}"


def new_run_id() -> str:
    """Fresh run id, as a string (the models store ids as text)."""
    return str(uuid.uuid4())
