# 020 — ERROR CATALOG

*Complete catalog of standardized error codes across all 13 domains.*
*AI agents must use these codes for all error handling, logging, and user-facing messages.*

---

## Error Code Naming Convention

Format: `{DOMAIN}_{NNN}`
Examples: `QUEUE_001`, `PATIENT_042`, `BILLING_013`

## Error Response Format

Every API error returns:
```json
{
  "error": {
    "code": "QUEUE_001",
    "title": "Patient Already Exists",
    "message": "A patient with this phone number is already registered.",
    "trace_id": "abc-123-def"
  }
}
```

## Error Record Fields

| Field | Description | Required |
|---|---|---|
| Code | Unique error identifier | Yes |
| Title | Short human-readable name | Yes |
| Severity | CRITICAL / HIGH / MEDIUM / LOW | Yes |
| HTTP Status | HTTP status code | Yes |
| User Message | Hindi + English end-user message | Yes |
| Recovery | How to resolve the error | Yes |
| Business Rule | From BUSINESS_RULES.md | Yes |

## 1. QUEUE — Queue Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| QUEUE_001 | Patient Already Exists | HIGH | 409 | Is phone se patient already registered | Use existing | PAT-003 |
| QUEUE_002 | Token Expired | MEDIUM | 410 | Token expire ho chuka | Re-register | QUEUE-009 |
| QUEUE_003 | Doctor Offline | HIGH | 503 | Doctor available nahi | Wait for doctor | QUEUE-011 |
| QUEUE_004 | Dept Unavailable | HIGH | 503 | Department band hai | Try other dept | QUEUE-014 |
| QUEUE_005 | Queue Full | MEDIUM | 429 | Waiting list full | Try later | QUEUE-020 |
| QUEUE_006 | Invalid Token Status | CRITICAL | 400 | Status action allow nahi | Check status | QUEUE-002 |
| QUEUE_007 | Cannot Call Completed | CRITICAL | 400 | Complete token call nahi kar sakte | Only waiting | QUEUE-002 |
| QUEUE_008 | Emergency Override | HIGH | 409 | Emergency priority mil rahi | Wait | QUEUE-003 |
| QUEUE_009 | Token Not Found | HIGH | 404 | Token exist nahi karta | Verify token | -- |
| QUEUE_010 | Counter Closed | MEDIUM | 503 | Counter band hai | Auto-rerouted | QUEUE-013 |
| QUEUE_011 | Skipped After 3 Attempts | MEDIUM | 200 | 3 attempts ke baad skip | Re-queue | QUEUE-009 |
| QUEUE_012 | Token Already Called | MEDIUM | 409 | Token already called | Complete or Skip | QUEUE-001 |
| QUEUE_013 | VIP Cannot Bypass Emergency | HIGH | 403 | VIP emergency bypass nahi kar sakta | Wait | QUEUE-004 |

## 2. PATIENT — Patient Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| PATIENT_001 | Invalid Patient Data | HIGH | 400 | Required fields bharein | Name+phone required | PAT-002 |
| PATIENT_002 | Duplicate Phone | HIGH | 409 | Phone already registered | Use existing patient | PAT-003 |
| PATIENT_003 | Patient Not Found | HIGH | 404 | Patient nahi mila | Verify ID | -- |
| PATIENT_004 | Encryption Failed | CRITICAL | 500 | Security error. Admin se contact | Check encryption | PAT-004 |
| PATIENT_005 | Consent Required | HIGH | 403 | Consent zaroori hai | Get consent first | PAT-006 |
| PATIENT_006 | Minor Needs Guardian | HIGH | 400 | Guardian zaroori hai | Add guardian | PAT-007 |
| PATIENT_007 | Delete Not Allowed | HIGH | 403 | Active visits. Delete nahi kar sakte | Complete visits | PAT-010 |
| PATIENT_008 | Invalid Phone Format | MEDIUM | 400 | 10-digit phone daalein | Fix phone | -- |
| PATIENT_009 | Export Failed | LOW | 500 | Export failed. Retry karein | Retry/support | PAT-009 |

## 3. IDENTITY — Identity Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| IDENTITY_001 | Invalid PIN Format | MEDIUM | 400 | PIN 4-6 digits ka hona chahiye | 4-6 digit PIN | IDN-003 |
| IDENTITY_002 | Account Locked | HIGH | 423 | 5 failures. 30 min lock | Wait 30 min | AUD-006 |
| IDENTITY_003 | Invalid Credentials | MEDIUM | 401 | Galat PIN/password | Try again | -- |
| IDENTITY_004 | OTP Expired | MEDIUM | 410 | OTP expire. Naya request | Request new OTP | IDN-001 |
| IDENTITY_005 | Max OTP Attempts | HIGH | 429 | Max attempts. 30 min wait | Wait 30 min | AUD-006 |
| IDENTITY_006 | Unauthorized Access | CRITICAL | 403 | Permission nahi hai | Contact admin | IDN-005 |
| IDENTITY_007 | Session Expired | MEDIUM | 401 | Session expire. Phir login | Re-login | AUD-007 |
| IDENTITY_008 | User Not Found | HIGH | 404 | User nahi mila | Verify ID | -- |
| IDENTITY_009 | Duplicate Username | MEDIUM | 409 | Username already exists | Different name | -- |
| IDENTITY_010 | Role Not Found | HIGH | 404 | Role exist nahi karta | Verify ID | IDN-004 |
| IDENTITY_011 | Cannot Delete Last Admin | CRITICAL | 403 | Last admin delete nahi kar sakte | Reassign role | -- |

## 4. WORKFLOW — Workflow Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| WORKFLOW_001 | Invalid State Transition | CRITICAL | 400 | Transition allowed nahi | Check state machine | WKF-001 |
| WORKFLOW_002 | Visit Already Active | HIGH | 409 | Patient ki active visit hai | Complete visit | WKF-001 |
| WORKFLOW_003 | Visit Not Found | HIGH | 404 | Visit nahi mili | Verify ID | -- |
| WORKFLOW_004 | Cannot Reopen Visit | HIGH | 403 | 30 days baad reopen nahi | New visit | WKF-005 |
| WORKFLOW_005 | Archived Visit | MEDIUM | 410 | Visit archive ho chuki | New visit | WKF-004 |
| WORKFLOW_006 | Emergency Conflict | HIGH | 409 | Already emergency active | Complete emergency | WKF-006 |

## 5. CLINICAL — Clinical Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| CLINICAL_001 | Report Not Signed | HIGH | 403 | Doctor ke signature zaroori | Doctor sign | CLN-001 |
| CLINICAL_002 | Critical Value Detected | CRITICAL | 200 | Critical values. Doctor informed | Auto-notified | CLN-002 |
| CLINICAL_003 | Invalid Doctor License | HIGH | 400 | Doctor ka license invalid | Verify license | CLN-003 |
| CLINICAL_004 | Drug Interaction Detected | HIGH | 200 | Drug interaction detected | Doctor review | CLN-005 |
| CLINICAL_005 | Lab Sample Late | MEDIUM | 400 | 2 hours mein sample nahi liya | Log delay | CLN-006 |
| CLINICAL_006 | Radiology Upload Late | MEDIUM | 400 | 24 hours mein upload nahi | Upload now | CLN-007 |
| CLINICAL_007 | Pediatric Dosage Error | HIGH | 400 | Weight se calculate karna hoga | Provide weight | CLN-004 |
| CLINICAL_008 | Reference Range Mismatch | MEDIUM | 400 | Range age/gender adjust nahi | Apply adjusted | CLN-010 |

## 6. BILLING — Billing Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| BILLING_001 | Bill Not Found | HIGH | 404 | Bill nahi mila | Verify ID | -- |
| BILLING_002 | Discount Exceeds Limit | CRITICAL | 400 | Discount 100 percent se zyada nahi | Reduce discount | BIL-003 |
| BILLING_003 | GST Calculation Error | CRITICAL | 500 | GST calculation failed | Retry | BIL-002 |
| BILLING_004 | Partial Payment Failed | MEDIUM | 400 | Partial payment failed | Check method | BIL-004 |
| BILLING_005 | Invoice Generation Failed | HIGH | 500 | Invoice generation failed | Retry | BIL-005 |
| BILLING_006 | Cannot Void Bill | HIGH | 403 | Void reason zaroori | Provide reason | BIL-008 |
| BILLING_007 | Refund Failed | HIGH | 500 | Refund failed | Retry/manual | BIL-007 |
| BILLING_008 | Pre-auth Required | MEDIUM | 400 | Pre-auth number zaroori | Provide number | BIL-009 |
| BILLING_009 | HSN Code Required | HIGH | 400 | HSN code zaroori | Add HSN | BIL-010 |
| BILLING_010 | Outstanding Balance Alert | MEDIUM | 200 | Previous outstanding Rs {amt} | Collect | BIL-012 |

## 7. INVENTORY — Inventory Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| INVENTORY_001 | Insufficient Stock | CRITICAL | 409 | Stock available nahi: {qty} | Reduce qty or order | INV-001 |
| INVENTORY_002 | Batch Expired | CRITICAL | 410 | Batch expire ho chuka | Use fresh batch | INV-003 |
| INVENTORY_003 | Batch Not Found | HIGH | 404 | Batch nahi mila | Verify ID | -- |
| INVENTORY_004 | Item Not Found | HIGH | 404 | Item nahi mili | Verify ID | -- |
| INVENTORY_005 | Low Stock Alert | MEDIUM | 200 | Stock reorder se neeche: {item} | Place order | INV-004 |
| INVENTORY_006 | Invalid Batch Date | HIGH | 400 | Manufacturing date invalid | Verify dates | INV-006 |
| INVENTORY_007 | Cold Chain Violation | MEDIUM | 400 | Temp storage chahiye | Mark cold flag | INV-007 |
| INVENTORY_008 | Audit Mismatch | HIGH | 409 | Expected {e} found {a} | Adjustment entry | INV-008 |

## 8. APPOINTMENT — Appointment Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| APP_001 | Slot Not Available | HIGH | 409 | Slot available nahi | Other slot | APP-002 |
| APP_002 | Slot Not Found | MEDIUM | 404 | Slot nahi mila | Verify ID | -- |
| APP_003 | Late Cancellation | MEDIUM | 403 | 2 hours mein cancel nahi | Visit/reschedule | APP-003 |
| APP_004 | No Show | MEDIUM | 200 | 15 min mein nahi aaye | Marked no-show | APP-004 |
| APP_005 | Max Appointments | MEDIUM | 429 | Max appointments complete | Other doctor | APP-008 |
| APP_006 | Duplicate Booking | HIGH | 409 | Already booked this slot | Other slot | APP-002 |

## 9. COMMUNICATION — Communication Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| COMM_001 | Consent Not Given | HIGH | 403 | Consent nahi di | Get consent | COM-001 |
| COMM_002 | WhatsApp Failed | MEDIUM | 502 | WhatsApp failed. SMS par switch | SMS fallback | COM-002 |
| COMM_003 | SMS Failed | MEDIUM | 502 | SMS bhejne mein failed | Email fallback | COM-003 |
| COMM_004 | Email Failed | LOW | 502 | Email failed | Retry | COM-004 |
| COMM_005 | Voice Call Failed | HIGH | 502 | Voice call failed | Use SMS | COM-005 |
| COMM_006 | Curfew Blocked | MEDIUM | 403 | Raat 9-subah 8 blocked | Schedule morning | COM-006 |
| COMM_007 | Template Not Found | HIGH | 404 | Template nahi mila | Verify ID | COM-008 |
| COMM_008 | Invalid Template Vars | MEDIUM | 400 | Template variables invalid | Check format | COM-008 |

## 10. NOTIFICATION — Notification Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| NOTIFY_001 | Device Not Registered | MEDIUM | 404 | Device registered nahi | Register device | NOT-001 |
| NOTIFY_002 | Push Failed | MEDIUM | 502 | Push notification failed | Retry or SMS | NOT-002 |
| NOTIFY_003 | Preference Blocked | LOW | 403 | User ne disable kiya | Respect preference | NOT-001 |
| NOTIFY_004 | Delivery Unconfirmed | LOW | 200 | Confirmation nahi mili | Check device | NOT-005 |

## 11. AI — AI Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| AI_001 | Provider Unavailable | HIGH | 503 | AI service unavailable. Retry | Fallback to rule | AI-008 |
| AI_002 | Response Invalid | MEDIUM | 422 | AI se invalid response | Retry | -- |
| AI_003 | Context Exceeded | MEDIUM | 413 | Request bahut badi | Reduce input | AI-010 |
| AI_004 | PII Detected | CRITICAL | 400 | Personal data. Pehle encrypt | Encrypt first | AI-009 |
| AI_005 | Diagnosis Blocked | CRITICAL | 403 | AI final diagnosis nahi de sakta | Doctor must | AI-001 |
| AI_006 | Diet Plan Pending | MEDIUM | 200 | Doctor approval required | Doctor approve | AI-003 |
| AI_007 | Voice Identity Required | HIGH | 400 | AI pehchaan-karaye | Add disclosure | AI-006 |

## 12. ANALYTICS — Analytics Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| ANALYTICS_001 | Report Failed | MEDIUM | 500 | Report generation failed | Retry | -- |
| ANALYTICS_002 | Invalid Date Range | MEDIUM | 400 | Max 365 days | Reduce range | -- |
| ANALYTICS_003 | No Data | MEDIUM | 404 | Data available nahi | Other range | -- |
| ANALYTICS_004 | Format Not Supported | LOW | 400 | Export format not supported | PDF/CSV/XLSX | -- |

## 13. AUDIT — Audit Engine

| Code | Title | Sev | HTTP | User Message | Recovery | Rule |
|---|---|---|---|---|---|---|
| AUDIT_001 | Log Append Failed | CRITICAL | 500 | Audit log failed. Blocked | Check DB | AUD-001 |
| AUDIT_002 | Chain Integrity Violation | CRITICAL | 409 | Audit chain violation! | Escalate security | AUD-003 |
| AUDIT_003 | Retention Exceeded | MEDIUM | 410 | Audit log 7 saal purana | Archive | AUD-004 |
| AUDIT_004 | Consent Revoked | HIGH | 403 | Consent wapas le li | Stop processing | AUD-005 |

---
## Severity Legend

| Severity | Meaning | SLA |
|---|---|---|
| CRITICAL | System-blocking, data corruption, security breach | < 5 minutes |
| HIGH | Feature-blocking, data inconsistency | < 1 hour |
| MEDIUM | Non-blocking, degraded experience | < 4 hours |
| LOW | Cosmetic, minor inconvenience | < 24 hours |

---
## Error Code Index

| Range | Domain | Defined |
|---|---|---|
| QUEUE_001 — QUEUE_999 | Queue Engine | 13 |
| PATIENT_001 — PATIENT_999 | Patient Engine | 9 |
| IDENTITY_001 — IDENTITY_999 | Identity Engine | 11 |
| WORKFLOW_001 — WORKFLOW_999 | Workflow Engine | 6 |
| CLINICAL_001 — CLINICAL_999 | Clinical Engine | 8 |
| BILLING_001 — BILLING_999 | Billing Engine | 10 |
| INVENTORY_001 — INVENTORY_999 | Inventory Engine | 8 |
| APPOINTMENT_001 — APPOINTMENT_999 | Appointment Engine | 6 |
| COMMUNICATION_001 — COMMUNICATION_999 | Communication Engine | 8 |
| NOTIFICATION_001 — NOTIFICATION_999 | Notification Engine | 4 |
| AI_001 — AI_999 | AI Engine | 7 |
| ANALYTICS_001 — ANALYTICS_999 | Analytics Engine | 4 |
| AUDIT_001 — AUDIT_999 | Audit Engine | 4 |
| **Total** | **13 Domains** | **98** |

> Note: Each domain has 999 code slots. Current: {total}. Extensible to 500+.

---
## Usage in Code

### Python Example
```python
from domain.errors import AppError, ErrorCode

def register_patient(name: str, phone: str):
    if not name or not phone:
        raise AppError(
            code=ErrorCode.PATIENT_001,
            message="Missing required fields: name, phone",
            http_status=400
        )
```

### API Response
```python
@router.post("/patients")
async def create_patient(req: CreatePatientRequest):
    try:
        patient = patient_service.register(req.name, req.phone)
        return {"data": patient}
    except AppError as e:
        return JSONResponse(
            status_code=e.http_status,
            content={"error": e.to_dict()}
        )
