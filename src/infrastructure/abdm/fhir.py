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
