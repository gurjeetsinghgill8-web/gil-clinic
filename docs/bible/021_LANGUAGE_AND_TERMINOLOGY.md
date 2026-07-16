# 021 — LANGUAGE AND TERMINOLOGY

*Complete vocabulary, naming conventions, and terminology rules.*
*AI agents must use these terms consistently in all generated code, UI, API, and documentation.*

---

## Standard Terms

| Correct Term | Never Use | Domain | Rationale |
|---|---|---|---|
| Patient | Customer, Client, User | All | Healthcare domain standard |
| Doctor | Provider, Physician (avoid when possible) | Clinical | Indian hospital convention |
| Receptionist | Operator, Front Desk Staff | Identity | Role-based clarity |
| Token | Ticket, Queue Number, Chit | Queue | Hospital industry standard |
| Clinic | Branch, Store, Outlet | All | Indian healthcare term |
| Test | Procedure, Exam, Investigation | Clinical | Patient-friendly |
| Report | Result Document, Output | Clinical | Short and standard |
| Visit | Encounter, Session, Episode | Workflow | Clinical terminology |
| Bill | Invoice (for legal), Receipt | Billing | Indian hospital usage |
| Medicine | Drug, Medication (use Medicine) | Clinical | Patient-friendly |
| Prescription | Rx, Script (avoid) | Clinical | Standard term |
| Sample | Specimen, Collection | Clinical | Lab standard |
| Department | Ward, Unit, Section | All | Hospital structure |
| Counter | Window, Station | Queue | Clinic operations |
| Shift | Duty (avoid) | Identity | Time-based scheduling |

## Naming Patterns

### Python Code
- Classes: PascalCase (`PatientRegistration`, `TokenGenerator`)
- Functions: snake_case (`register_patient()`, `call_next_token()`)
- Variables: snake_case (`patient_id`, `token_status`)
- Constants: UPPER_SNAKE (`MAX_QUEUE_LENGTH`, `OTP_EXPIRY_SECONDS`)
- Private: prefix with `_` (`_validate_token`, `_encrypt_pii`)
- Type hints: Required for all public functions

### Database
- Tables: snake_case plural (`patients`, `queue_entries`, `visit_states`)
- Columns: snake_case singular (`patient_id`, `token_number`, `created_at`)
- Primary keys: `id` (UUIDv7 stored as `uuid` type)
- Foreign keys: `{referenced_table}_id` (`patient_id`, `doctor_id`)
- Indexes: `idx_{table}_{column}` (`idx_patients_phone`)
- Unique constraints: `uq_{table}_{column}` (`uq_patients_phone`)
- Timestamps: `created_at`, `updated_at`

### API
- Base path: `/api/v1/{engine}/{resource}`
- Resource names: plural nouns (`/patients`, `/tokens`, `/bills`)
- Actions: HTTP verbs (POST for create, GET for read, etc.)
- Query params: snake_case (`?patient_id=abc&date_from=2026-01-01`)
- Response envelope: `{"data": ..., "meta": {...}}` for lists
- Error envelope: `{"error": {"code": "...", "message": "..."}}`

### Events (Event Bus)
- Naming: `{DOMAIN}.{ENTITY}.{ACTION}`
- Examples: `PATIENT.REGISTERED`, `QUEUE.TOKEN_CALLED`, `BILLING.PAYMENT_SUCCESS`
- Past tense for action (already happened)
- No underscores in event names (dots only)

### File Structure
- Domain layer: `domain/{engine}/entities.py`, `domain/{engine}/value_objects.py`
- Application layer: `application/{engine}/use_cases.py`, `application/{engine}/dtos.py`
- Infrastructure: `infrastructure/{engine}/repositories.py`, `infrastructure/{engine}/services.py`
- Presentation: `presentation/{engine}/routes.py`, `presentation/{engine}/schemas.py`

---

## Domain-Specific Terminology

### Patient Engine
- `patient_id`: Format `GHOS-{seq:06d}` (e.g., `GHOS-000042`)
- `phone`: 10-digit Indian mobile number
- `consent`: Boolean, recorded with timestamp
- `emergency_contact`: Name + phone

### Queue Engine
- `token`: Format `{DeptCode}-{seq:04d}` (e.g., `ECG-0012`)
- `DeptCode`: ECG, ECHO, TMT, OPD, IPD, LAB, PHARM
- `status`: waiting / called / in_progress / completed / skipped / absent
- `priority`: normal / emergency / vip

### Workflow Engine
- `visit_id`: UUIDv7, primary identifier for a patient visit
- `state`: Registered > Waiting > Called > InConsultation > ...
- `transition`: Unidirectional, forward-only state change

### Clinical Engine
- `test_type`: ecg, echo, tmt, opd, blood_test, xray, mri, ct_scan
- `result_status`: pending / processing / completed / signed / delivered
- `reference_range`: Age/gender adjusted normal values

### Billing Engine
- `invoice_number`: Format `INV-YYYYMMDD-XXXXX`
- `gst_type`: CGST + SGST (intra-state) or IGST (inter-state)
- `payment_status`: unpaid / partial / paid / refunded

### Inventory Engine
- `batch_number`: Supplier-provided or auto-generated
- `dispense_method`: FEFO (First Expiry First Out)
- `stock_movement`: received / dispensed / returned / adjusted / expired

---

## UI Wording Rules

1. **Buttons**: Verb-first ("Register Patient", not "Patient Registration")
2. **Errors**: Hindi + English ("Patient nahi mila / Patient not found")
3. **Success**: Brief confirmation ("Patient registered successfully")
4. **Labels**: Short, descriptive ("Phone", not "Phone Number")
5. **Placeholders**: Example-driven ("eg: 9876543210")
6. **Empty states**: Action-oriented ("No patients yet. Register your first patient.")
7. **Confirmations**: Specify what will happen ("Are you sure you want to discharge this patient?")
8. **Tooltips**: Optional, for non-obvious fields only

---

## API Naming Quick Reference

| Action | HTTP Method | URL Pattern |
|---|---|---|
| List | GET | /api/v1/{engine}s |
| Get | GET | /api/v1/{engine}s/{id} |
| Create | POST | /api/v1/{engine}s |
| Update | PUT | /api/v1/{engine}s/{id} |
| Patch | PATCH | /api/v1/{engine}s/{id} |
| Delete | DELETE | /api/v1/{engine}s/{id} |

---

## Database Naming

### Schema Names
- `identity`, `patient`, `queue`, `workflow`, `clinical`
- `billing`, `inventory`, `appointment`, `communication`
- `notification`, `ai`, `analytics`, `audit`

### Common Columns
| Column | Type | Purpose |
|---|---|---|
| `id` | UUIDv7 | Primary key |
| `created_at` | TIMESTAMPTZ | Row creation |
| `updated_at` | TIMESTAMPTZ | Last update |
| `created_by` | UUID | Actor reference |
| `is_active` | BOOLEAN | Soft delete flag |
| `version` | INTEGER | Optimistic locking |

---

## Event Naming Quick Reference

| Domain | Event Pattern | Examples |
|---|---|---|
| Patient | PATIENT.{ACTION} | REGISTERED, UPDATED, CONSENT_CHANGED |
| Queue | QUEUE.{ACTION} | TOKEN_CREATED, TOKEN_CALLED, TOKEN_COMPLETED |
| Workflow | WORKFLOW.{ACTION} | VISIT_STARTED, VISIT_TRANSITIONED |
| Clinical | CLINICAL.{ACTION} | REPORT_READY, CRITICAL_VALUE_ALERT |
| Billing | BILLING.{ACTION} | BILL_CREATED, PAYMENT_SUCCESS, BILL_VOIDED |
| Inventory | INVENTORY.{ACTION} | STOCK_RECEIVED, STOCK_DISPENSED, LOW_STOCK_ALERT |
| Appointment | APPOINTMENT.{ACTION} | BOOKED, CANCELLED, NO_SHOW |
| Communication | COMMUNICATION.{ACTION} | MESSAGE_SENT, DELIVERY_FAILED, DELIVERY_CONFIRMED |
| Notification | NOTIFY.{ACTION} | PUSH_SENT, PREFERENCE_CHANGED |
| AI | AI.{ACTION} | DIET_PLAN_GENERATED, TRIAGE_COMPLETED |
| Analytics | ANALYTICS.{ACTION} | REPORT_GENERATED, EXPORT_COMPLETED |
| Audit | AUDIT.{ACTION} | SECURITY_ALERT, CONSENT_CHANGED |

---

## Never Use List

These terms MUST NEVER appear in GHOS code, UI, or documentation:

| Never Use | Use Instead |
|---|---|
| Customer | Patient |
| Client | Patient |
| User (for patients) | Patient |
| Provider | Doctor |
| Operator | Receptionist |
| Agent | Staff |
| Ticket | Token |
| Chit | Token |
| Store/Branch | Clinic |
| Procedure | Test |
| Exam | Test |
| Rx | Prescription |
| Episode | Visit |
| Encounter | Visit |
| Drug | Medicine |
| Specimen | Sample |
| Script | Prescription |
| Window | Counter (queue) |
| Ward | Department |
| Section | Department |
