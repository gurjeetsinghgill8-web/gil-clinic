"""FHIR R4 mapping — SQLAlchemy models → HL7 FHIR resources.

ABDM ka data-exchange standard FHIR R4 hai. Ye layer humare internal models ko
FHIR resources me convert karta hai taaki ABDM HIP/HIU ke saath interoperable
ho sakein (baad me NHA sandbox ke saath wire karenge). Pure functions — koi
network/DB dependency nahi.
"""

from __future__ import annotations

from typing import Any


def fhir_patient(p) -> dict[str, Any]:
    """PatientModel → FHIR Patient resource."""
    res: dict[str, Any] = {
        "resourceType": "Patient",
        "id": getattr(p, "patient_id", "") or "",
        "active": True,
        "name": [{"text": getattr(p, "name", "") or ""}],
        "gender": _gender(getattr(p, "gender", "")),
    }
    if getattr(p, "phone", ""):
        res["telecom"] = [{"system": "phone", "value": getattr(p, "phone")}]
    if getattr(p, "date_of_birth", ""):
        res["birthDate"] = getattr(p, "date_of_birth")
    if getattr(p, "blood_group", ""):
        res["extension"] = [
            {
                "url": "http://hl7.org/fhir/StructureDefinition/patient-bloodgroup",
                "valueString": getattr(p, "blood_group"),
            }
        ]
    return res


def fhir_practitioner(c) -> dict[str, Any]:
    """ClinicModel (doctor) → FHIR Practitioner resource."""
    return {
        "resourceType": "Practitioner",
        "id": getattr(c, "hpr_id", "") or f"doc-{str(getattr(c, 'id', ''))[:8]}",
        "name": [{"text": getattr(c, "doctor_name", "") or ""}],
        "qualification": [
            {"code": {"text": getattr(c, "doctor_degree", "") or ""}}
        ] if getattr(c, "doctor_degree", "") else [],
        "telecom": [{"system": "phone", "value": getattr(c, "doctor_phone", "")}]
        if getattr(c, "doctor_phone", "") else [],
    }


def fhir_organization(c) -> dict[str, Any]:
    """ClinicModel → FHIR Organization resource (HFR facility)."""
    addr = getattr(c, "address", "") or ""
    city = getattr(c, "city", "") or ""
    state = getattr(c, "state", "") or ""
    return {
        "resourceType": "Organization",
        "id": getattr(c, "hfr_id", "") or f"fac-{str(getattr(c, 'id', ''))[:8]}",
        "name": getattr(c, "clinic_name", "") or "",
        "address": [{"text": addr, "city": city, "state": state}],
    }


def fhir_observation(reading: dict[str, Any], patient_id: str) -> dict[str, Any]:
    """PatientReading dict → FHIR Observation resource."""
    return {
        "resourceType": "Observation",
        "status": "final",
        "subject": {"reference": f"Patient/{patient_id}"},
        "code": {"text": reading.get("label") or reading.get("code") or ""},
        "valueQuantity": {
            "value": reading.get("value"),
            "unit": reading.get("unit") or "",
        },
        "effectiveDateTime": reading.get("date_time") or "",
    }


def fhir_medication_request(p) -> dict[str, Any]:
    """OpdPrescriptionModel → FHIR MedicationRequest resource."""
    return {
        "resourceType": "MedicationRequest",
        "status": "active",
        "intent": "order",
        "subject": {"reference": f"Patient/{getattr(p, 'patient_id', '')}"},
        "note": [{"text": getattr(p, "medicines", "") or ""}],
        "reasonCode": [{"text": getattr(p, "diagnosis", "") or ""}],
    }


def fhir_diagnostic_report(p) -> dict[str, Any]:
    """OpdPrescriptionModel → FHIR DiagnosticReport resource."""
    return {
        "resourceType": "DiagnosticReport",
        "status": "final",
        "subject": {"reference": f"Patient/{getattr(p, 'patient_id', '')}"},
        "conclusion": getattr(p, "diagnosis", "") or "",
    }


def _gender(value: str) -> str:
    v = (value or "").strip().lower()
    return {"male": "male", "m": "male", "female": "female", "f": "female"}.get(v, "unknown")


# ── ABD-03 · Offline FHIR Bundle export ─────────────────────────────────────
#
# Why this exists even though ABDM linking needs credentials
# ---------------------------------------------------------
# ABD-01/02/04/05 all need ``ABDM_CLIENT_ID`` / ``ABDM_CLIENT_SECRET`` from the
# NHA sandbox, so they are genuinely blocked. Exporting a record as FHIR is not:
# the standard is public, the mapping above already exists, and a patient
# asking for "my records in a portable format" can be answered today.
#
# So this produces a **FHIR R4 collection Bundle** that:
#   * opens in any FHIR viewer,
#   * is the exact shape a HIP would later POST to an HIU, and
#   * is validated by its own tests, so the day credentials arrive the only
#     new work is the transport, not the data model.
#
# Nothing here is ABDM-specific in a way that would need rewriting later —
# that is the point of building it now rather than waiting.

#: Bundle id prefix, so an exported file is recognisable as ours.
BUNDLE_ID_PREFIX = "ghos-bundle"


def _entry(resource: dict[str, Any], index: int) -> dict[str, Any] | None:
    """Wrap one resource as a Bundle entry, or None when it is unusable.

    A resource without a ``resourceType`` is not a FHIR resource; including it
    would produce a Bundle that fails validation, so it is dropped instead.
    """
    if not isinstance(resource, dict) or not resource.get("resourceType"):
        return None
    resource = dict(resource)
    resource.setdefault("id", f"res-{index}")
    return {
        # urn:uuid is the FHIR-recommended form for a collection Bundle.
        "fullUrl": f"urn:uuid:{resource['id']}",
        "resource": resource,
    }


def fhir_bundle(
    patient: Any,
    clinic: Any = None,
    prescriptions: Any = None,
    readings: Any = None,
    bundle_id: str = "",
    generated_at: str = "",
) -> dict[str, Any]:
    """Build a FHIR R4 collection Bundle for one patient's record.

    Includes whatever exists: the Patient, the clinic as Organization and the
    doctor as Practitioner, every prescription, and every self-recorded
    reading. Missing sections are omitted rather than faked — an empty Bundle
    with a valid Patient is honest, a Bundle with invented Observations is not.

    Args:
        patient: ``PatientModel``-like object (duck-typed via ``getattr``).
        clinic: optional ``ClinicModel``-like object.
        prescriptions: iterable of prescription models.
        readings: iterable of reading dicts.
        bundle_id: override; a stable id is generated when blank.
        generated_at: ISO timestamp override (tests).

    Returns:
        A dict ready to be serialised as ``application/fhir+json``.
    """
    from datetime import datetime, timezone

    entries: list[dict[str, Any]] = []
    patient_id = getattr(patient, "patient_id", "") or ""

    def add(resource: Any) -> None:
        entry = _entry(resource, len(entries) + 1)
        if entry is not None:
            entries.append(entry)

    if patient is not None:
        add(fhir_patient(patient))
    if clinic is not None:
        add(fhir_organization(clinic))
        add(fhir_practitioner(clinic))

    for prescription in prescriptions or []:
        add(fhir_medication_request(prescription))
        # Only emit a DiagnosticReport when there is actually a diagnosis —
        # an empty conclusion is noise in a record a clinician has to read.
        if getattr(prescription, "diagnosis", ""):
            add(fhir_diagnostic_report(prescription))

    for reading in readings or []:
        if isinstance(reading, dict):
            add(fhir_observation(reading, patient_id))

    stamp = generated_at or datetime.now(timezone.utc).isoformat()
    return {
        "resourceType": "Bundle",
        "id": bundle_id or f"{BUNDLE_ID_PREFIX}-{patient_id or 'unknown'}",
        "type": "collection",
        "timestamp": stamp,
        # Provenance: every export says who produced it and when, which is what
        # makes the file usable as evidence rather than just data.
        "meta": {
            "lastUpdated": stamp,
            "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
            "tag": [
                {
                    "system": "https://ghos.clinic/fhir/export",
                    "code": "offline-export",
                    "display": "GHOS offline FHIR export (not yet ABDM-linked)",
                }
            ],
        },
        "entry": entries,
        "total": len(entries),
    }


def bundle_summary(bundle: dict[str, Any]) -> dict[str, Any]:
    """Count resources per type — what a UI or a test wants to assert on.

    Also reports the patient reference, so an export can be checked against the
    patient it claims to be for without reparsing the whole Bundle.
    """
    counts: dict[str, int] = {}
    patient_id = ""
    for entry in (bundle or {}).get("entry", []) or []:
        resource = (entry or {}).get("resource") or {}
        kind = resource.get("resourceType") or "Unknown"
        counts[kind] = counts.get(kind, 0) + 1
        if kind == "Patient" and not patient_id:
            patient_id = str(resource.get("id") or "")
    return {
        "bundle_id": (bundle or {}).get("id", ""),
        "type": (bundle or {}).get("type", ""),
        "total": int((bundle or {}).get("total") or 0),
        "counts": counts,
        "patient_id": patient_id,
    }


def validate_bundle(bundle: dict[str, Any]) -> list[str]:
    """Cheap structural checks, returning a list of problems (empty = fine).

    Deliberately NOT a FHIR validator — that needs the full specification
    package, which is too heavy for this host's 100 CPU-second budget. These
    are the mistakes that actually break an import: a wrong resourceType, a
    missing entry wrapper, a resource with no id, or a dangling subject
    reference to a patient that is not in the Bundle.
    """
    problems: list[str] = []
    if not isinstance(bundle, dict):
        return ["Bundle is not an object"]
    if bundle.get("resourceType") != "Bundle":
        problems.append(f"resourceType must be 'Bundle', got {bundle.get('resourceType')!r}")
    if bundle.get("type") not in ("collection", "document"):
        problems.append(f"unsupported Bundle type: {bundle.get('type')!r}")

    entries = bundle.get("entry")
    if not isinstance(entries, list):
        problems.append("entry must be a list")
        return problems
    if bundle.get("total") != len(entries):
        problems.append(
            f"total ({bundle.get('total')!r}) does not match entry count ({len(entries)})"
        )

    patient_ids: set[str] = set()
    subject_refs: list[str] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict) or "resource" not in entry:
            problems.append(f"entry[{index}] has no resource")
            continue
        if not entry.get("fullUrl"):
            problems.append(f"entry[{index}] has no fullUrl")
        resource = entry["resource"]
        if not resource.get("resourceType"):
            problems.append(f"entry[{index}].resource has no resourceType")
        if not resource.get("id"):
            problems.append(f"entry[{index}].resource has no id")
        if resource.get("resourceType") == "Patient":
            patient_ids.add(str(resource.get("id")))
        subject = resource.get("subject") or {}
        if isinstance(subject, dict) and subject.get("reference"):
            subject_refs.append(str(subject["reference"]))

    # Every clinical resource must point at a patient that is actually present.
    for reference in subject_refs:
        target = reference.split("/", 1)[-1]
        if target and target not in patient_ids:
            problems.append(f"dangling subject reference: {reference}")

    return problems
