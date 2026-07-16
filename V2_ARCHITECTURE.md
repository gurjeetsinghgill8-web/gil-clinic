# GHOS Version 2 Architecture Document

*AI-First Hospital Operating System for India*
*Reference: V1 Streamlit (104 modules, 67 DB tables)*
*Date: 2026-07-12*

---

## 1. Domain Architecture

### Core Principle

Hospital is composed of **Engines**, not pages.
Each engine is an independent domain service.
Engines communicate exclusively through events.

### The 13 Engines

| Domain / Engine | Responsibility | V1 Source |
|---|---|---|
| **Identity Engine** | Users, roles, permissions, auth, staff | users, rbac_roles, hr_staff |
| **Patient Engine** | Registration, demographics, PII | patients table; encryption.py |
| **Queue Engine** | Tokens, dept queues, status transitions | tests table; queue.py |
| **Workflow Engine** | Visit lifecycle, routing, state machine | Dept flows |
| **Clinical Engine** | Results, reports, prescriptions, vitals | lab_results, prescriptions |
| **Billing Engine** | Invoices, payments, GST, discounts | bills, gst_invoices; billing.py |
| **Inventory Engine** | Items, batches, stock, purchase orders | inventory_* tables; inventory.py |
| **Appointment Engine** | Slots, scheduling, reminders | appointments, time_slots |
| **Communication Engine** | Templates, multi-channel routing | whatsapp_templates; whatsapp.py |
| **Notification Engine** | Event mapping, priority, push | push_notifications |
| **AI Engine** | LLM gateway, diet, report, triage, voice | all ai_* tables |
| **Analytics Engine** | Aggregations, reports, KPIs, ML | feedback_stats, system_metrics |
| **Audit & Security** | Audit log, encryption, consent, rights | audit_log_v2, consent_records |

### Bounded Contexts

- Patient Engine is aggregate root
- Queue Engine orchestrates Workflow + Notification
- Billing consumes Patient + Clinical + Inventory
- AI Engine is a provider facade
- Communication Engine is channel-agnostic
- Audit Engine is an observing context

---

## 2. Architecture Pattern

### Modular Monolith (V2)

GHOS V2 uses a **Modular Monolith** pattern. All code lives in a single deployable unit but is organized into strict Clean Architecture layers. Microservices are extracted only when a specific module needs independent scaling.

```
ghos-v2/
├── domain/          # Pure business logic, no framework imports
├── application/     # Use cases, DTOs, ports
├── infrastructure/  # DB, external APIs, event bus, framework code
└── presentation/    # API endpoints, WebSocket, background jobs
```

### Dependency Rules

- domain/ depends on NOTHING
- application/ depends on domain/ only
- infrastructure/ depends on application/
- presentation/ depends on application/
- NO layer may import from a higher layer
- Cross-domain communication via events ONLY
- Events published AFTER DB commit (outbox pattern)

### Future Microservice Extraction Points

| Module | Trigger | Extraction Path |
|---|---|---|
| Queue Engine | >1000 req/s throughput | Separate FastAPI service + Redis cluster |
| Notification Engine | Multi-channel at scale | Dedicated Celery workers |
| AI Engine | GPU compute needed | GPU nodes + model registry |
| Communication Engine | Carrier API rate limits | Separate Celery worker pool |
| Analytics Engine | Heavy aggregations | Read replica + OLAP store |
| Identity Engine | Multi-tenant auth | Auth0 / Keycloak |

### 14 Internal Modules (within the monolith)

| Module | Tech | DB Schema | Dependencies |
|---|---|---|---|
| api-gateway | FastAPI middleware | - | All |
| identity-mod | FastAPI | identity | None |
| patient-mod | FastAPI | patient | Identity |
| queue-mod | FastAPI+WS+Redis | queue+Redis | Patient,Workflow,Notify |
| workflow-mod | FastAPI+Celery | workflow | Queue,Patient |
| clinical-mod | FastAPI | clinical | Patient,Queue |
| billing-mod | FastAPI | billing | Patient,Clinical,Inventory |
| inventory-mod | FastAPI | inventory | None |
| appointment-mod | FastAPI | appointment | Patient,Notify |
| communication-mod | FastAPI+Celery | communication+Redis | None |
| notification-mod | FastAPI+WS | notification+Redis | Communication,Queue |
| ai-mod | FastAPI+Celery | ai | Patient,Clinical |
| analytics-mod | FastAPI+Celery | analytics | All (read replicas) |
| audit-mod | FastAPI | audit | All (via events) |

---
---

## 3. Folder Structure

Domain in domain/ package. Backend as microservices in backend/services/.
Frontend in frontend/web/ (Next.js) and frontend/mobile/ (React Native).
Services/communication/ has adapters. Services/ai-gateway/ has providers.
Database/migrations/ has Alembic. Deployment/ has k8s/docker/terraform.

---

## 4. Database Domains

Each engine owns its schema. Cross-engine references use UUIDv7.
No cross-schema foreign keys. Audit is append-only.

| Engine | Tables |
|---|---|
| identity | users, roles, permissions, staff, otp_codes |
| patient | patients, medical_history, patient_consent |
| queue | queue_entries, token_sequence, wait_time_log |
| workflow | visits, visit_states, state_transitions |
| clinical | test_results, prescriptions, vitals, lab_samples |
| billing | bills, bill_items, payments, invoices, gst_details |
| inventory | categories, items, batches, stock_movements |
| appointment | appointments, time_slots, reminders |
| communication | templates, messages, delivery_receipts |
| notification | devices, notifications, user_preferences |
| ai | ai_requests, ai_responses, diet_plans, triage |
| analytics | materialized_views, report_definitions |
| audit | audit_log, consent_records, encryption_keys |

---

## 5. API Domains

Base path: /api/v1/{engine}/{resource}

| Engine | Endpoints |
|---|---|
| Identity | POST /login, POST /verify-otp, CRUD /users, /roles |
| Patient | CRUD, POST /register, GET /{id}/history |
| Queue | POST /enqueue, POST /dequeue, GET /wait-time, WS /ws/queue/{dept} |
| Workflow | POST /visit, POST /transition, POST /escalate |
| Clinical | POST /results, CRUD /prescriptions, POST /vitals |
| Billing | POST /bills, POST /payments, GET /invoice, POST /gst-filing |
| Inventory | CRUD /items, POST /batches, POST /movement |
| Appointment | CRUD, GET /slots, POST /remind, POST /no-show |
| Communication | POST /send, CRUD /templates, GET /delivery-status |
| Notification | POST /send, POST /register-device, WS /ws/notify |
| AI | POST /diet-plan, POST /explain, POST /prescribe, POST /triage |
| Analytics | GET /dashboard, GET /reports, POST /export |
| Audit | GET /log, POST /consent, GET /chain-verify |

WS channels: /ws/queue/{dept}, /ws/notify/{user}, /ws/patient/{id}, /ws/admin

---

## 6. Event Flow

All services communicate via events on Redis pub/sub (migrating to Kafka).

- **Patient Registration**: patient-svc publishes patient.registered -> queue-svc creates token, notification-svc sends confirmation, analytics-svc counts, audit-svc logs
- **Doctor Calls**: queue-svc publishes queue.token_called -> workflow-svc updates state, notification-svc sends alert (SMS/Push/WhatsApp), WS pushes to patient and dept display
- **Report Ready**: clinical-svc publishes report.ready -> notification-svc alerts patient, communication-svc emails PDF, WS pushes to patient, billing-svc updates bill
- **Payment**: billing-svc publishes billing.payment_received -> inventory-svc finalizes stock, analytics-svc updates revenue, notification-svc sends receipt
- **AI Triage**: ai-svc publishes ai.triage_complete -> queue-svc creates priority entry, notification-svc alerts staff, workflow-svc creates visit

---

## 7. Migration Strategy (16 Weeks)

**Week 1**: Analysis - audit 104 V1 modules, map to V2 domains
**Weeks 2-3**: Domain extraction - pure dataclasses, business rules from utils/*.py
**Weeks 4-6**: Queue, Identity, Patient engines, Event Bus, PostgreSQL + Alembic
**Weeks 7-9**: Clinical, Billing, Appointment, Notification engines
**Weeks 10-12**: Communication Engine (adapters), AI Gateway (OpenAI/Gemini)
**Weeks 13-14**: Inventory, Analytics, Audit engines, Next.js frontend
**Weeks 15-16**: Data migration, parallel run, training, cutover, decommission V1

---

## 8. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Data loss during migration | High | Rehearse 3x, checksum verify |
| Event bus downtime | Medium | Redis Sentinel, RDB/AOF |
| WebSocket disconnection | Medium | Auto-reconnect, cache last state |
| AI provider failure | Medium | Circuit breaker, rule-based fallback |
| Staff resistance | Medium | 2-week parallel run, training |
| Microservice latency | Low | gRPC for critical paths |
| Connection pool exhaustion | Low | PgBouncer, 20 max per service |
| Redis message loss | Low | Kafka for critical events |

---

## 9. Technical Debt (from V1)

| Debt | Severity | V2 Fix |
|---|---|---|
| No domain models | Critical | Pure dataclasses in domain/ |
| JSON file fallback | High | PostgreSQL + S3 only |
| Streamlit state loss | Critical | WebSocket + Redis real-time |
| Scattered notifications | High | One Notification Engine |
| No audit trail | High | Immutable audit on every event |
| No test coverage | High | Unit tests, 90% min coverage |
| PII in plain text JSON | Critical | Encryption Engine + key rotation |
| No AI abstraction | Medium | AI Gateway with provider registry |
| No API versioning | Medium | /api/v1/ prefix |
| Hardcoded credentials | High | OTP auth, zero secrets in code |
| Single SQLite for all data | High | Separate PG schema per engine |

---

## 10. Phase-Wise Implementation Plan

**Weeks 1-3**: Analysis + Domain extraction. Produce CURRENT_SYSTEM_ANALYSIS.md and DOMAIN_MODEL.md.
**Weeks 4-6**: Core engines (Queue, Identity, Patient). Event bus. PostgreSQL + Alembic.
**Weeks 7-9**: Clinical + Billing + Appointment + Notification engines.
**Weeks 10-12**: Communication Engine (adapters) + AI Gateway (OpenAI, Gemini, Ollama).
**Weeks 13-14**: Inventory + Analytics + Audit engines. Frontend (Next.js).
**Weeks 15-16**: Data migration, parallel run, staff training, cutover, V1 decommission.

---

## Appendix: V1 to V2 Table Mapping

| V1 Table(s) | V2 Domain | Notes |
|---|---|---|
| users, rbac_roles, hr_staff | identity | Unified identity schema |
| patients | patient | Add medical_history, documents |
| tests | queue + workflow | Split queue/workflow |
| bills, payments, gst_invoices | billing | Normalize, add insurance |
| inventory_*, stock_* | inventory | FEFO tracking preserved |
| appointments, time_slots | appointment | Add no_show_log |
| audit_log_v2, consent_records | audit | Extend with data rights |
| all ai_* tables | ai | Unified AI request/response log |
| sms_, whatsapp_, email_* | communication | Templates vs delivery |
| push_notifications, devices | notification | Add user_preferences |
| ipd_admissions, beds, wards | clinical | IPD as clinical sub-domain |
| emergency_cases | workflow | Emergency as workflow state |
| feedback, feedback_stats | analytics | Patient satisfaction |
| purchase_orders, vendors | inventory | Procurement integrated |
| hr_*, payroll_* | identity | Staff under identity domain |

---

## Appendix B: GHOS Bible Documentation Suite

The complete system documentation is maintained in `docs/bible/` as the GHOS Bible -- 26 AI-native documents.

### Document Index

| # | Document | Purpose | Status |
|---|---|---|---|
| 000 | PROJECT_DNA | Vision, philosophy, core principles | CORE |
| 001 | GHOS_MEMORY | AI context file, project state | CORE |
| 002 | BUSINESS_RULES | 188 business rules across 13 domains | CORE |
| 003 | SYSTEM_ARCHITECTURE | Clean Architecture layers, event bus | CORE |
| 004 | DOMAIN_MODEL | 10 aggregate roots, value objects | CORE |
| 005 | DATABASE | Complete PostgreSQL schemas | CORE |
| 006 | EVENTS | 400+ domain events cataloged | CORE |
| 007 | STATE_MACHINE | Visit, token, bill state machines | CORE |
| 008 | API | Full REST + WebSocket API reference | CORE |
| 009 | DESIGN_SYSTEM | Colors, typography, components | CORE |
| 010 | UX_RULEBOOK | Mobile-first, 3-click, accessibility | CORE |
| 011 | AI_RULEBOOK | Code gen rules, prompting rules | CORE |
| 012 | MASTER_PROMPTS | 500+ AI prompts by engine | CORE |
| 013 | DECISION_LOG | 8 Architecture Decision Records | CORE |
| 014 | SECURITY | Auth, RBAC, encryption, audit | CORE |
| 015 | DEPLOYMENT | Docker, CI/CD, environments | ACTIVE |
| 016 | TESTING | Test pyramid, coverage targets | ACTIVE |
| 017 | RELEASE | Versioning, release workflow | ACTIVE |
| 018 | CHANGELOG | V1 to V2 changelog | ACTIVE |
| 019 | FUTURE | Short/medium/long-term roadmap | ACTIVE |
| 020 | ERROR_CATALOG | Standardized error codes (98 defined) | ACTIVE |
| 021 | LANGUAGE_AND_TERMINOLOGY | Vocabulary, naming, UI wording | ACTIVE |
| 022 | DEPENDENCY_GRAPH | Engine dependency map | ACTIVE |
| 023 | CAPABILITY_MATRIX | Role-permission matrix (65 features) | ACTIVE |
| 024 | CONFIGURATION | All configurable settings | ACTIVE |
| 025 | FEATURE_FLAGS | Feature tier matrix (40 flags) | ACTIVE |

**Status Legend**: CORE = Foundation documents | ACTIVE = Current development

### AI Agent Workflow

When an AI agent begins a task, it should follow this document dependency order:

1. GHOS_MEMORY (001) -> Current state and patterns
2. BUSINESS_RULES (002) -> Rules that constrain the solution
3. DOMAIN_MODEL (004) -> Entities and relationships
4. EVENTS (006) -> Events to publish/subscribe
5. STATE_MACHINE (007) -> Valid state transitions
6. DEPENDENCY_GRAPH (022) -> Which engines depend on others
7. CAPABILITY_MATRIX (023) -> Who can do what
8. SYSTEM_ARCHITECTURE (003) -> Layer structure
9. DATABASE (005) -> Schema design
10. API (008) -> Endpoint design
11. LANGUAGE (021) -> Naming conventions
12. ERROR_CATALOG (020) -> Error handling
13. DESIGN_SYSTEM (009) -> UI components
14. UX_RULEBOOK (010) -> UX patterns
15. AI_RULEBOOK (011) -> Code quality rules
16. SECURITY (014) -> Security patterns
17. IMPLEMENTATION -> Code generation
18. TESTING (016) -> Test generation
19. DEPLOYMENT (015) -> Deployment
