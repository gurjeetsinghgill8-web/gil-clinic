# 002 — BUSINESS RULES

*Complete catalog of business rules across all 13 domains.*
*AI agents must follow these rules during code generation.*
*Each rule has a unique ID for traceability.*

---

## QUEUE — Queue Engine

| ID | Rule | Priority |
|---|---|---|
| QUEUE-001 | Doctor can call only the next patient in queue | HIGH |
| QUEUE-002 | Doctor cannot call a completed token | CRITICAL |
| QUEUE-003 | Emergency overrides queue (goes to front) | CRITICAL |
| QUEUE-004 | VIP patient never bypasses Emergency patient | HIGH |
| QUEUE-005 | Skipped patient returns to end of queue unless recalled | HIGH |
| QUEUE-006 | Queue count never becomes negative | CRITICAL |
| QUEUE-007 | Token is auto-generated on registration | HIGH |
| QUEUE-008 | Token number format: {DeptCode}-{seq:03d} (e.g. ECG-012) | HIGH |
| QUEUE-009 | Patient must be called within 3 attempts or auto-return to queue | MEDIUM |
| QUEUE-010 | Wait time calculated from registration time, not token time | HIGH |
| QUEUE-011 | Doctor on break = queue paused | MEDIUM |
| QUEUE-012 | Doctor changed = queue continues, no reset | MEDIUM |
| QUEUE-013 | Counter closed = tokens rerouted to next available counter | HIGH |
| QUEUE-014 | Department shift change = queue preserved | MEDIUM |
| QUEUE-015 | Lab busy = clinical queue holds until lab available | MEDIUM |
| QUEUE-016 | ECG machine down = cardiology queue paused | MEDIUM |
| QUEUE-017 | Patient cancel = token removed, slot freed | HIGH |
| QUEUE-018 | Patient gone home = token marked absent, not removed | MEDIUM |
| QUEUE-019 | Patient arrived late (>15 min) = auto-skip to end | MEDIUM |
| QUEUE-020 | Max waiting patients per dept = 50, overflow redirects | LOW |
| QUEUE-021 | Priority queue exists alongside normal queue | HIGH |

## PATIENT — Patient Engine

| ID | Rule | Priority |
|---|---|---|
| PAT-001 | Patient ID is unique and auto-generated (GHOS-{seq:06d}) | CRITICAL |
| PAT-002 | Patient must have at least name and phone to register | HIGH |
| PAT-003 | Duplicate phone detection on registration | HIGH |
| PAT-004 | Patient PII encrypted at rest (AES-256-GCM) | CRITICAL |
| PAT-005 | Patient can opt out of data processing anytime | HIGH |
| PAT-006 | Patient consent recorded before any data sharing | CRITICAL |
| PAT-007 | Minor patients require guardian consent | HIGH |
| PAT-008 | Patient history accessible only on explicit consent | HIGH |
| PAT-009 | Patient data downloadable in portable format (PDF/JSON) | MEDIUM |
| PAT-010 | Patient can request data deletion (GDPR-style) | HIGH |
| PAT-011 | Emergency contact required for all patients | MEDIUM |
| PAT-012 | Patient address is optional but encouraged | LOW |

## WORKFLOW — Workflow Engine

| ID | Rule | Priority |
|---|---|---|
| WKF-001 | Patient can be at exactly one state at any time | CRITICAL |
| WKF-002 | State transitions are unidirectional (forward only) | HIGH |
| WKF-003 | Completed visit can be archived, not deleted | HIGH |
| WKF-004 | Visit archived after 90 days of inactivity | MEDIUM |
| WKF-005 | Visit cannot be reopened after 30 days of completion | HIGH |
| WKF-006 | Emergency visit follows a separate fast-track workflow | HIGH |
| WKF-007 | Follow-up visit creates linked visit record | MEDIUM |
| WKF-008 | Multi-department visit completes one dept at a time | HIGH |
| WKF-009 | Visit duration auto-calculated from first registration to discharge | MEDIUM |

## CLINICAL — Clinical Engine

| ID | Rule | Priority |
|---|---|---|
| CLN-001 | Test result must be signed by doctor before release | CRITICAL |
| CLN-002 | Critical (panic) values immediately notified to doctor | CRITICAL |
| CLN-003 | Prescription requires valid doctor license number | HIGH |
| CLN-004 | Medicine dosage calculated on weight (pediatric) | HIGH |
| CLN-005 | Drug interaction check auto-triggered on multi-prescription | HIGH |
| CLN-006 | Lab sample must be collected within 2 hours of order | MEDIUM |
| CLN-007 | Radiology report must be uploaded within 24 hours | MEDIUM |
| CLN-008 | Vital signs recorded at every visit | MEDIUM |
| CLN-009 | Previous reports visible for comparison | MEDIUM |
| CLN-010 | Test reference ranges age/gender-adjusted | HIGH |

## BILLING — Billing Engine

| ID | Rule | Priority |
|---|---|---|
| BIL-001 | Bill generated after service, never before | HIGH |
| BIL-002 | GST calculated at line-item level | CRITICAL |
| BIL-003 | Discount cannot exceed 100% of bill amount | CRITICAL |
| BIL-004 | Partial payment allowed, balance tracked | HIGH |
| BIL-005 | Invoice number is auto-generated and sequential | HIGH |
| BIL-006 | Cash discount (if offered) applied before card payment | MEDIUM |
| BIL-007 | Refund only on original payment method | HIGH |
| BIL-008 | Bill cannot be deleted, only voided with reason | HIGH |
| BIL-009 | Insurance claim requires pre-authorization number | MEDIUM |
| BIL-010 | HSN code required for GST invoices | HIGH |
| BIL-011 | Zero-value bills allowed (free checkup, company-sponsored) | MEDIUM |
| BIL-012 | Outstanding balance alerts on patient registration | MEDIUM |

## INVENTORY — Inventory Engine

| ID | Rule | Priority |
|---|---|---|
| INV-001 | Stock never goes negative (check before dispense) | CRITICAL |
| INV-002 | FEFO dispense: soonest expiry dispensed first | HIGH |
| INV-003 | Expired batch blocked from dispense | CRITICAL |
| INV-004 | Low stock alert at reorder_level threshold | HIGH |
| INV-005 | Batch received before reference date blocked | HIGH |
| INV-006 | Each movement logged against specific batch | HIGH |
| INV-007 | Cold chain items flagged on receipt | MEDIUM |
| INV-008 | Stock audit reconciliation creates adjustment entry | HIGH |
| INV-009 | Purchase order required for stock receipt | MEDIUM |
| INV-010 | Returned stock goes back to original batch | MEDIUM |

## APPOINTMENT — Appointment Engine

| ID | Rule | Priority |
|---|---|---|
| APP-001 | Slot duration configurable per doctor/dept | HIGH |
| APP-002 | No double-booking on same slot | CRITICAL |
| APP-003 | Cancel allowed up to 2 hours before slot | MEDIUM |
| APP-004 | No-show marked after 15 min of slot time | MEDIUM |
| APP-005 | Reminder sent 24h and 2h before appointment | MEDIUM |
| APP-006 | Walk-in patient assigned next available slot | HIGH |
| APP-007 | Doctor can block slots for breaks | MEDIUM |
| APP-008 | Max appointments per day configurable per doctor | HIGH |

## COMMUNICATION — Communication Engine

| ID | Rule | Priority |
|---|---|---|
| COM-001 | Patient consent required before any communication | CRITICAL |
| COM-002 | WhatsApp is primary channel (if available) | HIGH |
| COM-003 | SMS is fallback when WhatsApp fails | HIGH |
| COM-004 | Email used for reports and invoices only | MEDIUM |
| COM-005 | Voice call for critical results only | HIGH |
| COM-006 | No communication between 9 PM and 8 AM | MEDIUM |
| COM-007 | All outbound messages logged with delivery status | HIGH |
| COM-008 | Template-based messages (no custom text to patient) | HIGH |

## NOTIFICATION — Notification Engine

| ID | Rule | Priority |
|---|---|---|
| NOT-001 | Push notification requires user opt-in | HIGH |
| NOT-002 | Browser notification supported as secondary channel | MEDIUM |
| NOT-003 | Notification priority: Critical > High > Medium > Low | HIGH |
| NOT-004 | Critical notifications bypass all user preferences | CRITICAL |
| NOT-005 | Notification delivery confirmed via receipt | MEDIUM |
| NOT-006 | Unread notifications badge on dashboard | LOW |

## AI — AI Engine

| ID | Rule | Priority |
|---|---|---|
| AI-001 | AI never makes final diagnosis — doctor always signs | CRITICAL |
| AI-002 | AI suggestions labeled as AI-generated | HIGH |
| AI-003 | Diet plan requires doctor approval before sharing | HIGH |
| AI-004 | Report explanation uses patient-friendly language (target: 5th grade level) | HIGH |
| AI-005 | AI triage is advisory, not authoritative | CRITICAL |
| AI-006 | Voice agent must identify as AI at start of call | HIGH |
| AI-007 | All AI interactions logged for audit | HIGH |
| AI-008 | AI provider circuit breaker on repeated failures | MEDIUM |
| AI-009 | Patient data never sent to AI for training | CRITICAL |
| AI-010 | Context window limit enforced per request | MEDIUM |

## AUDIT & SECURITY — Audit Engine

| ID | Rule | Priority |
|---|---|---|
| AUD-001 | Every data mutation logged with timestamp and actor | CRITICAL |
| AUD-002 | Audit log is append-only, never modified | CRITICAL |
| AUD-003 | Chain integrity verified via hash chaining | HIGH |
| AUD-004 | Audit logs retained for 7 years (regulatory) | HIGH |
| AUD-005 | Access to PII logged separately | HIGH |
| AUD-006 | Failed login attempts > 5 = account lockout 30 min | HIGH |
| AUD-007 | Session timeout after 15 min of inactivity | MEDIUM |
| AUD-008 | All API requests logged (method, path, status, latency) | HIGH |

## IDENTITY — Identity Engine

| ID | Rule | Priority |
|---|---|---|
| IDN-001 | Staff login via OTP or PIN (no passwords) | HIGH |
| IDN-002 | Admin login via OTP + password (backward compatible) | HIGH |
| IDN-003 | PIN must be 4-6 numeric digits | MEDIUM |
| IDN-004 | Roles: Admin, Doctor, Receptionist, Technician, Nurse, Manager, Pharmacist, Lab Tech | HIGH |
| IDN-005 | Permission check on every API call | CRITICAL |
| IDN-006 | Role hierarchy: Admin > Manager > Doctor > Staff | HIGH |
| IDN-007 | Staff can access only assigned departments | HIGH |
| IDN-008 | Default seed users created when table empty | MEDIUM |
