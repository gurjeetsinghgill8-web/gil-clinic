# 012 — MASTER PROMPTS

*500+ AI prompts organized by engine.*
*Each prompt references relevant Bible documents.*

---

## How to Use These Prompts

Each prompt follows this pattern:
- **Engine**: Which domain this belongs to
- **Files**: What files to generate/modify
- **References**: Which Bible docs to read first
- **Rules**: Which BUSINESS_RULES apply
- **Events**: Which EVENTS to publish
- **Prompt**: The actual instruction

---

## IDENTITY ENGINE (30 prompts)

### ID-001: Create User Registration Module
- **Files**: domain/identity/entities.py, domain/identity/use_cases.py
- **References**: 003_SYSTEM_ARCHITECTURE.md, 005_DATABASE.md
- **Rules**: IDN-001 to IDN-008
- **Prompt**: Create the Identity domain module with User entity, Role value object, and Permission value object. User must have: id (UUIDv7), username, full_name, role, department, pin_hash, phone, is_active. Implement PIN validation (4-6 digits). Include factory method User.create() with validation. Use dataclasses. No framework imports.

### ID-002: Implement OTP Login Flow
- **Files**: infrastructure/auth/otp_service.py, application/auth/login_usecase.py
- **References**: 003_SYSTEM_ARCHITECTURE.md, 008_API.md
- **Rules**: IDN-001, IDN-002
- **Events**: AUDIT.SECURITY_ALERT (on failed attempts)
- **Prompt**: Implement OTP-based login: generate 6-digit OTP, store with 5-min expiry, max 5 attempts then 30-min lockout. Return JWT on success. Hash OTP in DB.

### ID-003: Role-Based Access Middleware
- **Files**: infrastructure/auth/rbac_middleware.py
- **References**: 003_SYSTEM_ARCHITECTURE.md
- **Rules**: IDN-004 to IDN-007
- **Prompt**: Create FastAPI middleware that checks JWT, extracts role, validates permission for requested resource+action. Return 403 if unauthorized. Log all access attempts.

### ID-004 to ID-030: Staff management, role CRUD, permission matrix, seed data, etc.

---

## PATIENT ENGINE (35 prompts)

### PAT-001: Patient Registration Module
- **Files**: domain/patient/entities.py, application/patient/register_usecase.py
- **References**: 003_SYSTEM_ARCHITECTURE.md, 004_DOMAIN_MODEL.md, 005_DATABASE.md
- **Rules**: PAT-001 to PAT-012
- **Events**: PATIENT.REGISTERED
- **Prompt**: Create Patient aggregate root. Fields: patient_id (GHOS-XXXXXX), name, phone, dob, gender, address (value object), emergency_contact, blood_group, consent_given. Validate phone uniqueness. Encrypt PII fields before storage. Generate sequential patient ID.

### PAT-002: Patient Search & Duplicate Detection
- **Files**: infrastructure/patient/patient_repository.py
- **References**: 005_DATABASE.md
- **Rules**: PAT-003
- **Prompt**: Implement patient search by name (partial match), phone (exact), and patient_id. On registration, check phone duplicates and show matching patients. Return max 20 results. Index on phone and name.

### PAT-003 to PAT-035: Patient update, history, consent management, data export, GDPR deletion, etc.

---

## QUEUE ENGINE (40 prompts)

### QUE-001: Queue Token Generator
- **Files**: domain/queue/entities.py, domain/queue/services.py
- **References**: 003_SYSTEM_ARCHITECTURE.md, 004_DOMAIN_MODEL.md, 007_STATE_MACHINE.md
- **Rules**: QUEUE-007, QUEUE-008
- **Prompt**: Create Token aggregate. Token format: {DeptCode}-{seq:04d}. Daily sequence per department. Status enum: waiting/called/in-progress/completed/skipped/absent. Auto-increment sequence from token_sequence table. Validate max 50 tokens per dept.

### QUE-002: Call Next Patient
- **Files**: application/queue/call_next_usecase.py
- **References**: 007_STATE_MACHINE.md
- **Rules**: QUEUE-001 to QUEUE-006
- **Events**: QUEUE.TOKEN_CALLED
- **Prompt**: Implement call-next logic: get highest priority waiting token, validate doctor is available, validate dept is not paused, transition state to 'called', mark called_at timestamp, increment called_count. Return token and patient info. If no tokens, return empty.

### QUE-003: Skip Patient
- **Files**: application/queue/skip_usecase.py
- **Rules**: QUEUE-005, QUEUE-009
- **Events**: QUEUE.TOKEN_SKIPPED
- **Prompt**: Skip current called patient. Re-queue to end unless recalled within 3 attempts. Log skip reason. Notify display system.

### QUE-004 to QUE-040: Wait time calculation, emergency override, VIP handling, doctor break, counter close, display board, WebSocket channel, etc.

---

## WORKFLOW ENGINE (30 prompts)

### WKF-001: Visit State Machine
- **Files**: domain/workflow/state_machine.py
- **References**: 004_DOMAIN_MODEL.md, 007_STATE_MACHINE.md
- **Rules**: WKF-001 to WKF-009
- **Events**: WORKFLOW.VISIT_TRANSITIONED
- **Prompt**: Implement state machine with all valid transitions from STATE_MACHINE.md. Guard conditions on each transition. Publish event on each transition. Reject invalid transitions with meaningful error. Track transition history.

### WKF-002 to WKF-030: Visit creation, emergency workflow, multi-dept routing, archiving, etc.

---

## CLINICAL ENGINE (40 prompts)

### CLN-001: Test Results Module
- **Files**: domain/clinical/test_result.py, application/clinical/record_result_usecase.py
- **References**: 005_DATABASE.md
- **Rules**: CLN-001, CLN-002, CLN-010
- **Events**: CLINICAL.REPORT_READY, CLINICAL.CRITICAL_VALUE_ALERT
- **Prompt**: Implement test result recording. Support multiple values per test. Check reference ranges, flag abnormal values. If critical (panic) value detected, immediately publish CRITICAL_VALUE_ALERT. Require doctor signature before final release.

### CLN-002: Prescription Writer
- **Files**: domain/clinical/prescription.py
- **Rules**: CLN-003, CLN-004, CLN-005
- **Prompt**: Prescription entity with items array (medicine, dosage, duration, instructions). Validate doctor license number. Auto-calculate pediatric dosage from weight. Trigger drug interaction check if 3+ medicines.

### CLN-003 to CLN-040: Vital signs, lab sample tracking, radiology upload, report PDF generation, etc.

---

## BILLING ENGINE (50 prompts)

### BIL-001: Bill Creation & GST Calculation
- **Files**: domain/billing/bill.py, domain/billing/gst.py
- **References**: 005_DATABASE.md
- **Rules**: BIL-001 to BIL-012
- **Events**: BILLING.BILL_CREATED, BILLING.GST_INVOICE_GENERATED
- **Prompt**: Bill aggregate with line items, subtotal, discount (max 100%), tax, total, paid, balance. Calculate GST at line-item level using HSN codes. Generate sequential invoice number (INV-YYYYMMDD-XXXXX). Support partial payments and balance tracking.

### BIL-002 to BIL-050: Payment processing, refund, void, GST filing, insurance claim, daily summary, etc.

---

## INVENTORY ENGINE (50 prompts)

### INV-001: Stock Receipt (Purchase Order)
- **Files**: domain/inventory/batch.py, application/inventory/receive_stock_usecase.py
- **References**: 005_DATABASE.md
- **Rules**: INV-001 to INV-010
- **Events**: INVENTORY.STOCK_RECEIVED
- **Prompt**: Implement stock receipt: create batch with expiry date, validate batch not already received, set unit rate and MRP, validate mfg_date before expiry_date. Cold chain flag. Auto-increment total quantity on item.

### INV-002: FEFO Dispense
- **Files**: application/inventory/dispense_usecase.py
- **Rules**: INV-001, INV-002, INV-003
- **Events**: INVENTORY.STOCK_DISPENSED
- **Prompt**: Dispense using FEFO (First Expiry First Out). Find batches with quantity > 0, sort by expiry_date ASC. Deduct from earliest expiring batch first. If insufficient stock, reject with message showing available qty. Never let stock go negative.

### INV-003 to INV-050: Stock audit, low stock alerts, expiry alerts, batch report, stock transfer, return, etc.

---

## APPOINTMENT ENGINE (30 prompts)

### APP-001: Slot Management
- **Files**: domain/appointment/slot.py
- **Rules**: APP-001, APP-002, APP-007, APP-008
- **Prompt**: Slot entity with doctor_id, date, start_time, end_time, is_blocked. Configurable duration per doctor. Validate no double-booking. Max appointments per day configurable. Block slots for breaks.

### APP-002 to APP-030: Booking, cancellation, reminder, no-show, calendar view, etc.

---

## NOTIFICATION ENGINE (40 prompts)

### NOT-001: Push Notification Service
- **Files**: infrastructure/notifications/push_service.py
- **Rules**: NOT-001 to NOT-006
- **Prompt**: Web push notification service using browser Push API. Register device endpoint. Send notification with title, body, icon, click URL. Track delivery receipts. Respect user preferences (opt-in/out per category).

### NOT-002 to NOT-040: In-app notification, email notification, SMS notification, notification preferences, broadcast, etc.

---

## AI ENGINE (60 prompts)

### AI-001: AI Gateway — Multi-Provider Router
- **Files**: infrastructure/ai/gateway.py
- **Rules**: AI-001 to AI-010
- **Prompt**: Create AI Gateway with provider abstraction. Support OpenAI, Gemini, Ollama. Circuit breaker on repeated failures. Auto-fallback to next provider. Log all requests and responses. Never send PII to AI. Enforce context window limits.

### AI-002: Diet Plan Generator
- **Files**: application/ai/diet_plan_usecase.py
- **Rules**: AI-003
- **Events**: AI.DIET_PLAN_GENERATED
- **Prompt**: Generate diet plan from patient condition, age, gender, weight. Detect condition from vitals/test results. Use AI Gateway. Require doctor approval before returning to patient.

### AI-003 to AI-060: Report explainer, prescription suggestion, triage, voice agent, transcription, etc.

---

## ANALYTICS ENGINE (40 prompts)

### ANA-001: Operations Dashboard
- **Files**: application/analytics/ops_dashboard_usecase.py
- **Rules**: (none specific)
- **Prompt**: Show real-time metrics: patients today, avg wait time, avg consultation time, patients by dept, tokens by status. Use read replica. Cache for 30 seconds.

### ANA-002 to ANA-040: Financial dashboard, clinical analytics, custom reports, export, alerting, etc.

---

## AUDIT ENGINE (30 prompts)

### AUD-001: Immutable Audit Logger
- **Files**: infrastructure/audit/audit_logger.py
- **References**: 005_DATABASE.md
- **Rules**: AUD-001 to AUD-008
- **Events**: AUDIT.CHAIN_VERIFIED
- **Prompt**: Append-only audit log with hash chaining. Each entry: id, event_type, actor_id, actor_type, target_type, target_id, payload (JSONB), hash (SHA-256 of prev_hash + payload), prev_hash. Verify chain integrity on demand. Never allow UPDATE or DELETE.

### AUD-002 to AUD-030: Consent management, data rights processing, chain verification, security alerts, etc.

---

## COMMUNICATION ENGINE (40 prompts)

### COM-001: Multi-Channel Message Router
- **Files**: infrastructure/communication/router.py
- **Rules**: COM-001 to COM-008
- **Prompt**: Route messages: WhatsApp primary, SMS fallback, email for reports, voice for critical. Check consent before sending. Template-based only. Log delivery status. No communication 9PM-8AM. Respect patient timezone.

### COM-002 to COM-040: Template management, delivery receipts, WhatsApp integration, SMS gateway, email service, voice call integration, etc.

---

## CROSS-CUTTING PROMPTS (60 prompts)

### X-001: Error Handling Middleware
- **Files**: infrastructure/errors/error_handler.py
- **Prompt**: Global error handler. Map domain exceptions to HTTP status codes. Log errors with stack trace. Return consistent JSON error format: {error: {code, message, details}}. Never expose internal details in production.

### X-002 to X-060: Database migrations, Docker setup, CI/CD pipeline, logging config, monitoring, health checks, rate limiting, etc.
