# 004 — DOMAIN MODEL

*All domain entities, relationships, aggregate roots, and invariants.*

---

## Aggregate Roots

| Aggregate | Entity | Key Fields | Invariants |
|---|---|---|---|
| **Patient** | Patient | id, name, phone, dob, gender, address, createdAt | Phone unique. PII encrypted. Minor needs guardian. |
| **User** | User | id, username, role, pinHash, dept, isActive | PIN 4-6 digits. Role in allowed set. |
| **Token** | Token | id, tokenNo, patientId, dept, status, position, createdAt | Unique per dept per day. Status in valid state. |
| **Visit** | Visit | id, patientId, states[], currentState, enteredAt, completedAt | Exactly one active state. Forward transitions only. |
| **TestResult** | TestResult | id, visitId, testType, values, signedBy, signedAt | Requires doctor signature. Critical values flagged. |
| **Prescription** | Prescription | id, visitId, items[], doctorId | Doctor license required. Interaction check auto. |
| **Bill** | Bill | id, patientId, items[], total, paid, balance | Total >= 0. Discount <= 100%. Sequential invoice number. |
| **Item** | Item | id, name, category, batches[], reorderLevel | Stock >= 0. FEFO dispense. Expired blocked. |
| **Appointment** | Appointment | id, patientId, doctorId, slot, status | No double-booking. Cancel before 2h. |
| **AuditLog** | AuditLog | id, eventType, actor, target, payload, hash, prevHash | Append-only. Chain integrity via hash. |

## Key Relationships

- Patient has many Visits
- Visit has many TestResults
- Visit has one Bill
- Visit has one or many Prescriptions
- Token belongs to one Patient and one Dept
- Bill has many BillItems (line items)
- Item has many Batches (inventory)
- Batch has many StockMovements
- User has one Role (role is value object)
- Role has many Permissions
- AuditLog chains via prevHash field
- Appointment links Patient + Doctor + Slot

## Value Objects

| Value Object | Fields | Usage |
|---|---|---|
| Address | line1, line2, city, state, pincode | Patient address |
| Money | amount (Decimal), currency | Billing, inventory |
| PhoneNumber | countryCode, number | Patient, User |
| DateRange | start, end | Appointment slots, reports |
| TestValue | value, unit, referenceRange, isAbnormal | Test results |
| Dosage | medicine, amount, unit, frequency, duration | Prescription |
| Permission | resource, action | RBAC |
| TokenStatus | enum: waiting/called/in-progress/completed/skipped | Queue |
| NotificationPriority | enum: critical/high/medium/low | Notification |

## Domain Events

Each aggregate publishes events on state changes. See EVENTS.md for full catalog.
Events are named {Aggregate}.{Action} e.g. Patient.Registered, Token.Called.
