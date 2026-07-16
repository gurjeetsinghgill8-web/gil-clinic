# 🏥 GHOS (Gurjas Hospital Operating System)
# PRODUCT DEVELOPMENT BLUEPRINT — HYBRID MASTER v2.0

**Owner:** Gurjas Singh Gill (Dr. Gurjeet Singh Gill)  
**Architecture:** FastAPI + Clean Architecture + DDD + Event Driven  
**UI:** HTML + CSS + JavaScript (PWA) — ❌ No Streamlit  
**Database:** PostgreSQL (primary) / SQLite (dev) / JSON (fallback)  
**Document Date:** 2026-07-14  
**Status:** Phase 1 — Department Pilot (GHOS v1.0) 🔴 In Development  
**Previous Version:** CardioQueue V1 (Streamlit, 104 modules) — ❌ Deprecated

---

## 📋 TABLE OF CONTENTS

1. [Product Vision & Core Model](#1-product-vision--core-model)
2. [Harness Engineering — Core Architecture Concept](#2-harness-engineering--core-architecture-concept)
3. [Development Rules (Never Change)](#3-development-rules-never-change)
4. [System Architecture — Engine Stack](#4-system-architecture--engine-stack)
5. [Final Folder Structure](#5-final-folder-structure)
6. [V2 Current Build Status — What's Done](#6-v2-current-build-status--whats-done)
7. [PHASE 0 — Foundation ✅ Complete](#7-phase-0--foundation-complete)
8. [PHASE 1 — Department Pilot (GHOS v1.0)](#8-phase-1--department-pilot-ghos-v10)
9. [PHASE 2 — Clinical Engine](#9-phase-2--clinical-engine)
10. [PHASE 3 — Appointment Engine](#10-phase-3--appointment-engine)
11. [PHASE 4 — Communication Layer](#11-phase-4--communication-layer)
12. [PHASE 5 — Billing Engine](#12-phase-5--billing-engine)
13. [PHASE 6 — Inventory & Pharmacy](#13-phase-6--inventory--pharmacy)
14. [PHASE 7 — Laboratory](#14-phase-7--laboratory)
15. [PHASE 8 — HR](#15-phase-8--hr)
16. [PHASE 9 — Finance](#16-phase-9--finance)
17. [PHASE 10 — System Administration](#17-phase-10--system-administration)
18. [PHASE 11 — Analytics](#18-phase-11--analytics)
19. [PHASE 12 — AI Platform](#19-phase-12--ai-platform)
20. [Project Milestones](#20-project-milestones)
21. [Success KPIs](#21-success-kpis)
22. [V1 → V2 Feature Migration Map](#22-v1--v2-feature-migration-map)

---

## 1. PRODUCT VISION & CORE MODEL

### 🎯 What We Are Building

GHOS is **not** a traditional Hospital Management System.

GHOS is a **Patient Flow Operating System** designed to eliminate patient confusion, reduce waiting time, simplify departmental workflow and create a hospital where every patient knows exactly what is happening.

> **Core Philosophy:** Register Once → Track Everywhere → Workflows Drive Everything

### 🏆 Unique Value Proposition (from V1)

> "दवाखाने में कोई लाइन नहीं, सब कुछ mobile पर।"

- **Patients scan a QR code** at reception to open the status page on their phone.
- **Patients enter their mobile number** to search and track their active queue positions in real-time.
- **Staff can call patients** via a "Remind" button, triggering a sound/vibrate alert directly in the patient's mobile browser.
- **Free forever** — No paid third-party APIs (WhatsApp API, SMS gateways, etc.). Data stays secure on local device.
- **Local-First** — Designed to run on a local device (mobile, tablet, or laptop) without internet dependency for core operations.

### 🏗️ Architecture Principles

```
TRADITIONAL APPROACH (Wrong):
  UI Page → directly calls DB → directly calls notification
  Result: Spaghetti code, hard to maintain, bugs everywhere

OUR APPROACH (Harness Engineering):
  UI Page → Harness → DB / Local Alerts / Queue Logic
  Result: Clean separation. Modifying UI doesn't break queue logic.
```

### Primary Goal
Create a production-ready system that can run daily inside a **Cardiology Department** before expanding into a complete Hospital Operating System.

---

## 2. HARNESS ENGINEERING — CORE ARCHITECTURE CONCEPT

This is the unique architectural pattern that makes GHOS different. Every engine follows this pattern.

```
┌─────────────────────────────────────────────────────┐
│                   UI LAYER (PWA)                      │
│  HTML Templates served by FastAPI via HTMLResponse    │
│  JS fetch() calls → API endpoints → JSON responses    │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP Request
                       ▼
┌─────────────────────────────────────────────────────┐
│              HARNESS LAYER (Use Cases)                │
│  Receives Command → Authorizes → Validates → Executes │
│  Calls Domain entities → Calls Repository ports       │
│  Returns Result (Ok | Fail)                           │
└──────┬─────────────────────────────────┬────────────┘
       │                                 │
       ▼                                 ▼
┌──────────────┐              ┌──────────────────────┐
│  Domain       │              │  Infrastructure       │
│  Entities     │              │  SQLite / JSON / API  │
│  ValueObjects │              │  Repositories         │
│  Ports        │              │  Services             │
└──────────────┘              └──────────────────────┘
```

### Key Pattern: UI → Use Case → Domain → Infrastructure

```
Page → API Route → UseCase.run(Command) → Repository.save()
                                            ↓
                                     Result.ok(data)
                                            ↓
                                   HTMLResponse / JSON
```

All pages communicate through **use cases** (the harness). No page directly touches the database. This is the immutable rule.

---

## 3. DEVELOPMENT RULES (Never Change)

1. **No Streamlit.** ❌
2. **No Architecture Redesign.** What's built stays built.
3. **No New Engines** unless current phase is complete and frozen.
4. **Every phase must be tested** on real patients before moving forward.
5. **UI must be mobile-first.** All templates responsive, touch-friendly.
6. **One source of truth** for all patient workflow — the Queue Engine.
7. **Every action must be auditable.** Immutable audit log for all state changes.
8. **All modules communicate through APIs/events only.** No direct DB access across engines.
9. **Build once, scale later.** No premature optimization.
10. **Freeze architecture** after every completed phase. No changes until next phase.
11. **UI → Use Case → Infrastructure.** Never call DB from UI directly (Harness pattern).
12. **Never develop the next phase** until the current phase is:
    - Code Complete → Integrated → Tested on Real Patients → Bugs Fixed → Frozen → Released

---

## 4. SYSTEM ARCHITECTURE — ENGINE STACK

```
                    ┌──────────────────┐
                    │   PWA UI Layer   │
                    │ HTML/CSS/JS/Fetch│
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │   API Gateway    │
                    │  (FastAPI)       │
                    └────────┬─────────┘
                             │
    ┌────────────────────────┼────────────────────────┐
    │                        │                        │
    ▼                        ▼                        ▼
┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Identity     │   │   Patient        │   │   Queue          │
│  Engine       │   │   Engine         │   │   Engine Lite    │
│  ─ Auth       │   │  ─ Registration │   │  ─ Call/Start    │
│  ─ Users      │   │  ─ Demographics │   │  ─ Complete      │
│  ─ Roles      │◄──│  ─ QR Identity  │──►│  ─ Alerts        │
│  ─ Sessions   │   │  ─ History      │   │  ─ TV Display    │
│  ─ PIN/OTP    │   │  ─ Lookup/Search│   │  ─ Audit Log     │
└──────────────┘   └──────────────────┘   └────────┬─────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────┐
                    │                               │               │
                    ▼                               ▼               ▼
        ┌──────────────────┐              ┌──────────────────┐
        │  Experience      │              │  Clinical        │ [PHASE 2]
        │  Engine          │              │  Engine          │
        │  ─ PWA Templates │              │  ─ ECG Reports   │
        │  ─ Token Slip    │              │  ─ Echo Reports  │
        │  ─ Patient Status│              │  ─ TMT Reports   │
        │  ─ Alert Polling │              │  ─ Holter/ABPM   │
        └──────────────────┘              └──────────────────┘
                                                    │
                    ┌───────────────────────────────┼───────────────┐
                    │                               │               │
                    ▼                               ▼               ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │  Appointment     │  │  Communication   │  │  Billing         │
        │  Engine [PH3]    │  │  Layer [PH4]     │  │  Engine [PH5]    │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
                    │                               │               │
                    ▼                               ▼               ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │  Inventory       │  │  Laboratory      │  │  HR [PH8]        │
        │  + Pharmacy [P6] │  │  [PH7]           │  │                  │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
                    │                               │
                    ▼                               ▼
        ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
        │  Finance [PH9]   │  │  System Admin    │  │  Analytics [P11] │
        │                  │  │  [PH10]          │  │                  │
        └──────────────────┘  └──────────────────┘  └──────────────────┘
                    │
                    ▼
        ┌──────────────────┐
        │  AI Platform     │
        │  [PHASE 12]      │
        └──────────────────┘
```

### Data Flow Pattern (All Engines)
```
Client (PWA) → FastAPI Route → UseCase.run(Command)
    → Domain Entity.method() → Repository.save()
    → Audit Log Entry
    → Result.ok()
    → JSON Response → Client renders
```

---

## 5. FINAL FOLDER STRUCTURE

```
src/
├── main_v2.py                    ← FastAPI app entry point
├──
├── identity/                     ← Auth, users, roles, sessions ✅
│   ├── domain/                   ← User, Role, Session entities
│   ├── application/              ← Use cases, DTOs
│   ├── infrastructure/           ← Models, repos, services
│   └── presentation/             ← Routes, schemas, middleware
│
├── patient/                      ← Registration, QR, history ✅
│   ├── domain/                   ← Patient aggregate, value objects
│   ├── application/              ← Register, lookup, update use cases
│   ├── infrastructure/           ← Models, repos, services
│   └── presentation/             ← Routes, schemas
│
├── queue/                        ← Queue lifecycle  ✅
│   ├── domain/                   ← QueueEntry entity, QueueStatus
│   ├── application/              ← Create, list, tech actions
│   ├── infrastructure/           ← Models, repos, mappers
│   └── presentation/             ← Routes, schemas, templates
│
├── experience/                   ← PWA, token slip, patient UI ✅
│   ├── application/              ← Patient status, alerts
│   ├── presentation/             ← Routes, templates
│   └── pwa/                      ← login.html, dashboard.html
│
├── clinic/                       ← Settings, departments ✅
│   ├── domain/                   ← ClinicSettings, Department, Service
│   ├── application/              ← CRUD use cases
│   ├── infrastructure/           ← JSON providers
│   └── presentation/             ← Routes, schemas
│
├── clinical/                     ← ECG, Echo, TMT reports [PHASE 2]
├── appointment/                  ← Booking, calendar [PHASE 3]
├── communication/                ← Push, Email, SMS, WhatsApp [PHASE 4]
├── billing/                      ← Invoices, payments, GST [PHASE 5]
├── inventory/                    ← Stock, purchase, pharmacy [PHASE 6]
├── laboratory/                   ← Lab, radiology [PHASE 7]
├── hr/                           ← Employees, payroll [PHASE 8]
├── finance/                      ← P&L, expenses, dashboard [PHASE 9]
├── system/                       ← RBAC, backup, multi-branch [PHASE 10]
├── analytics/                    ← Trends, KPIs [PHASE 11]
├── ai/                           ← Dietician, voice, triage [PHASE 12]
│
└── shared/                       ← Base classes, utilities
    ├── domain/                   ← BaseEntity, BaseValueObject
    ├── application/              ← BaseUseCase, Command, Result
    └── infrastructure/           ← Database config, encryption
```

---

## 6. V2 CURRENT BUILD STATUS — WHAT'S DONE

| Layer | Files | Status |
|-------|-------|--------|
| **Identity Engine** | ~50 files | ✅ Complete — User/Role/Session entities, JWT auth, PIN/password, OTP, lockout, RBAC ports |
| **Patient Engine** | ~25 files | ✅ Complete — Patient aggregate, Demographics, Contact, QR, Device reg, Medical history |
| **Queue Engine Lite** | ~18 files | ✅ Complete — QueueEntry entity, Call→Start→Complete, Alerts, Audit, TV display, Dept queues |
| **Experience Engine** | ~10 files + 6 HTML | ✅ Complete — PWA templates, Token slip, Patient status, Hospital info |
| **Clinic Engine** | ~10 files | ✅ Complete — Clinic settings (env+JSON), Departments CRUD, Services CRUD, Dynamic lookups |
| **Persistence** | ~20 files | ✅ Complete — SQLite ORM (10 models) + JSON fallback (atomic writes, .bak recovery) |
| **Shared Layer** | ~12 files | ✅ Complete — BaseEntity, BaseUseCase, Command, Result, Database, Encryption |
| **Total V2** | **270 Python + 6 HTML** | **✅ Foundation ready for Phase 1** |

### V1 (Deprecated — Streamlit)
- **104 modules** (43 utils + 61 pages) — Fully deleted from working tree
- All functionality is being rebuilt in V2 under the clean architecture

---

## 7. PHASE 0 — FOUNDATION ✅ COMPLETE

**Status: ✅ FROZEN — No further development. No new features.**

### Modules Built

| Engine | Components | Status |
|--------|-----------|--------|
| 🔐 Identity | User, Role, Session entities; JWT service; PIN/password auth; OTP; Lockout policy; RBAC ports | ✅ |
| 👤 Patient | Patient aggregate; Demographics, Contact, QR Identity, DeviceRegistration, MedicalHistory value objects; PatientIdGenerator, QrCodeGenerator services | ✅ |
| 🏪 Experience | 6 PWA templates; Token slip; Patient status dashboard; Hospital info integration | ✅ |
| 📋 Queue Lite | QueueEntry entity (call/start/complete lifecycle); QueueStatus value object; Audit log; TV display template | ✅ |
| 🏛 Clinic | ClinicSettings (env+JSON); Department entity; Service entity; JSON file providers | ✅ |
| 💾 Persistence | SQLAlchemy ORM (10 models); JSON file storage (atomic writes); Repository pattern (both backends); Backend switching via GHOS_DB_BACKEND | ✅ |

---

## 8. PHASE 1 — DEPARTMENT PILOT (GHOS v1.0)

**Status: 🔴 CURRENT DEVELOPMENT**  
**Goal:** Production-ready system for daily Cardiology Department use

This phase produces the first production version. It includes **12 modules** that together form a complete department workflow.

### MODULE 1 — RECEPTION DASHBOARD ⭐⭐⭐⭐⭐
**Status: 🔴 NOT STARTED — Next to build**

Complete patient registration and queue creation dashboard.

| Feature | Priority | Description |
|---------|----------|-------------|
| Patient Search | 🔴 High | Phone / QR / Patient ID lookup |
| Patient Registration | 🔴 High | Walk-in registration with demographics |
| Existing Patient Lookup | 🔴 High | Quick select returning patients |
| QR Scan | 🟡 Medium | Camera-based QR code scanning |
| Service Selection | 🔴 High | ECG, Echo, TMT, Holter, ABPM multi-select |
| Generate Queue | 🔴 High | Create queue entries for selected services |
| Generate Token | 🔴 High | Display token number after registration |
| Print Token Slip | 🔴 High | Printable token slip with queue info |
| Today's Queue | 🔴 High | Live view of today's registered patients |
| Report Delivery | 🟡 Medium | Mark reports as delivered to patient |
| Patient Search History | 🟢 Low | Recent patient search results |
| Department Status | 🟡 Medium | Live cards with per-dept waiting/called counts |
| Payment Status | 🟢 Low | Placeholder UI for Phase 5 billing |
| Live Queue Counter | 🔴 High | Real-time stat counters: waiting, called, in-progress |
| Quick Registration | 🟡 Medium | Minimal fields for speed |
| Duplicate Detection | 🔴 High | Alert on same phone/name combination |
| Reception Activity Log | 🟢 Low | Audit trail of reception actions |

**Success Criteria:** Registration completed in < 30 seconds

**Old V1 Reference:** `pages/Reception.py`, `pages/Registration.py`, `pages/Receptionist.py`

---

### MODULE 2 — TECHNICIAN WORKSPACE ⭐⭐⭐⭐⭐
**Status: 🔴 NOT STARTED**

Separate workspace for every department — same template, different data.

| Department | Code |
|-----------|------|
| ECG | ECG |
| Echo | Echo |
| TMT | TMT |
| Holter | Holter |
| ABPM | ABPM |

| Action Button | Function | Status Transition |
|--------------|----------|-------------------|
| 📞 CALL | Call patient to room | WAITING → CALLED |
| ▶ START | Begin the test | CALLED → IN_PROGRESS |
| ✅ COMPLETE | Test done | IN_PROGRESS → COMPLETED |
| 📋 REPORT READY | Mark report as ready | COMPLETED → REPORT_READY |

| Feature | Description |
|---------|-------------|
| Today's Queue | Department's full queue for today |
| Waiting List | Patients waiting to be called |
| Current Patient | Currently active patient with timer |
| Department Queue | Filtered by department |
| Timer | Elapsed time since test started |
| Room Number | Room assignment display |
| Patient Timeline | Quick view of patient's journey |
| Service Notes | Free-text notes field per test |
| Reopen (Admin) | Reopen a completed entry |

**Success Criteria:** Call patient within 2 clicks

**Old V1 Reference:** `pages/_department_base.py`, `pages/ECG.py`, `pages/Echo.py`, `pages/TMT.py`, `pages/OPD.py`

---

### MODULE 3 — DOCTOR WORKSPACE ⭐⭐⭐⭐⭐
**Status: 🔴 NOT STARTED**

Single screen — doctor never changes screens during reporting.

| Feature | Description |
|---------|-------------|
| Patient Summary | Overview of selected patient |
| Today's Tests | All completed tests for current visit |
| Current Visit | Active visit details |
| Timeline | Patient's full journey: registration → delivered |
| Previous Visits | Historical visit data |
| Reports | Test reports pending review |
| Approve Report | Mark report as approved |
| Reject Report | Send back to technician with notes |
| Report Ready | Final approval → patient notified |
| Clinical Notes | Doctor's consultation notes |
| History | Past medical history |
| Vitals | Patient vitals display |
| Attachments | Upload/view attachments |
| Print | Print report summary |
| PDF | Generate PDF report |

**Success Criteria:** Doctor never changes screens during reporting workflow

**Old V1 Reference:** `pages/Doctor.py`, `pages/OPD.py`

---

### MODULE 4 — MANAGER DASHBOARD
**Status: 🔴 NOT STARTED**

Real-time department monitoring.

| KPI | Description |
|-----|-------------|
| Today's Patients | Total patients registered today |
| Current Waiting | Number of patients currently waiting |
| Average Waiting Time | Average wait across all departments |
| Completed Tests | Tests completed today |
| Pending Reports | Reports awaiting doctor approval |
| Revenue | Today's revenue (placeholder) |
| Department Load | Per-department patient count |
| Staff Performance | Per-staff productivity metrics |
| TV Status | Live TV display status |
| Alerts | System alerts and warnings |
| Export CSV | Download data as CSV |
| Export PDF | Print summary report |

**Old V1 Reference:** `pages/Manager.py`, `pages/Manager_Dashboard.py`, `pages/Reports.py`, `pages/Analytics.py`

---

### MODULE 5 — PATIENT EXPERIENCE (PWA)
**Status: ⚠️ PARTIAL — Basic exists, enhancements needed**

Current: QR login, live status, estimated waiting, basic timeline exist.  
Needs: Hindi/English, offline, report download, feedback.

| Feature | Status |
|---------|--------|
| QR Login | ✅ Basic exists |
| Live Status | ✅ Basic exists |
| Estimated Waiting | ✅ Basic exists |
| Current Test | ✅ Basic exists |
| Timeline | 🔴 Missing |
| Download Token | 🔴 Missing |
| Report Ready Animation | 🔴 Missing |
| Feedback Form | 🔴 Missing |
| Hindi + English | 🔴 Missing |
| Add To Home Screen | ⚠️ Basic PWA manifest exists |
| Offline Cache | 🔴 Missing |
| Alert Sound/Vibration | 🔴 Missing (Brick 1) |

**Old V1 Reference:** `pages/Patient_Status.py`, `pages/Patient_Portal.py`

---

### MODULE 6 — TV DISPLAY
**Status: ⚠️ PARTIAL — Basic exists, enhancements needed**

| Feature | Status |
|---------|--------|
| Queue Display | ✅ Basic exists |
| Department Rotation | ✅ Dynamic from API |
| Fullscreen | ✅ Kiosk mode exists |
| "Now Calling" Section | ✅ Exists with animation |
| Voice Calling (TTS) | 🔴 Missing |
| Emergency Alerts | 🔴 Missing |

**Old V1 Reference:** TV display was part of V1's department_base.py

---

### MODULE 7 — PATIENT TIMELINE
**Status: 🔴 NOT STARTED**

Full visual timeline of patient's journey through the hospital.

```
Registration
    ↓
Queue Generated (with token #)
    ↓
Called to Room
    ↓
Test In Progress
    ↓
Test Completed
    ↓
Doctor Review
    ↓
Report Ready
    ↓
Report Delivered
```

Visible to: Patient, Doctor, Reception, Manager

**Old V1 Reference:** `pages/Patient_Timeline.py`

---

### MODULE 8 — REPORT WORKFLOW
**Status: 🔴 NOT STARTED**

```
Technician completes test
    ↓ COMPLETED status
Doctor reviews and approves
    ↓ REPORT_READY status
Reception delivers to patient
    ↓ DELIVERED status
Patient receives report
```

**Old V1 Reference:** Report workflow was part of V1's Doctor.py

---

### MODULE 9 — SETTINGS UI
**Status: ⚠️ PARTIAL — API exists, no UI

| Setting | Backend | UI |
|---------|---------|----|
| Clinic Name/Specialty | ✅ API exists | 🔴 Missing |
| Departments | ✅ API exists | 🔴 Missing |
| Services | ✅ API exists | 🔴 Missing |
| Doctors | 🔴 Missing | 🔴 Missing |
| Rooms | 🔴 Missing | 🔴 Missing |
| Working Hours | 🔴 Missing | 🔴 Missing |
| Token Rules | 🔴 Missing | 🔴 Missing |
| Display Settings | 🔴 Missing | 🔴 Missing |
| Printer | 🔴 Missing | 🔴 Missing |
| Language | 🔴 Missing | 🔴 Missing |
| Logo/Branding | ✅ API exists | 🔴 Missing |

**Old V1 Reference:** `pages/Password_Management.py` (Admin panel)

---

### MODULE 10 — AUDIT LOG VIEWER
**Status: ⚠️ PARTIAL — Backend exists, no UI

| Feature | Status |
|---------|--------|
| Immutable Log (backend) | ✅ Exists |
| Search | 🔴 Missing |
| Filter by date/role/action | 🔴 Missing |
| Timeline View | 🔴 Missing |
| Export | 🔴 Missing |
| Verification | 🔴 Missing |

---

### MODULE 11 — ERROR RECOVERY
**Status: 🔴 NOT STARTED**

| Feature | Description |
|---------|-------------|
| Retry | Auto-retry on API failure |
| Offline Queue | Queue actions while offline |
| Auto Recovery | Recover from crash mid-action |
| Session Recovery | Restore PWA session after refresh |
| Browser Refresh Recovery | Maintain state during refresh |
| Crash Recovery | Graceful degradation |

---

### MODULE 12 — INTEGRATION TEST
**Status: 🔴 NOT STARTED**

Test with:
- 100 Real Patients
- All Departments
- Reception → Technician → Doctor → Patient → Manager
- Bug Fixes
- Performance Validation
- Freeze
- Release → **GHOS v1.0**

---

### OLD BRICK MAPPING (V1 → V2 Phase 1)

| Old Brick | V2 Equivalent | Status in V2 |
|-----------|--------------|--------------|
| Brick 1 — Alert System | Phase 1, Module 5 (Patient Alert) + Module 6 (TV Display) | 🔴 Not built |
| Brick 2 — UI Premium Redesign | All Phase 1 modules (CSS patterns) | ✅ Partial (inline CSS) |
| Brick 3 — Data Persistence | Foundation (SQLite + JSON) | ✅ Complete |
| Brick 4 — Appointment Time | Phase 1, Module 5 (wait time display) | ✅ Complete |
| Brick 5 — Clinic Settings | Clinic Engine | ✅ Complete |
| Brick 6 — Dynamic Departments | Clinic Engine (Departments + Services) | ✅ Complete |

---

## 9. PHASE 2 — CLINICAL ENGINE

**Target:** After Phase 1 is Frozen & Released

### Modules
| Module | Description |
|--------|-------------|
| ECG Structured Report | ECG-specific template, measurements, interpretation |
| Echo Structured Report | Echo report with measurements, Doppler, 2D |
| TMT Structured Report | Treadmill test report with Bruce protocol |
| Holter Report | 24-hour Holter monitoring report |
| ABPM Report | Ambulatory BP monitoring report |

### Features per Module
Draft → Final → Signature → PDF  
Measurements, Templates, Clinical Workflow, Doctor Sign-off

**Old V1 Reference:** Report generation was in V1's `Doctor.py`

---

## 10. PHASE 3 — APPOINTMENT ENGINE

**Target:** After Phase 2

### Features
| Feature | Description |
|---------|-------------|
| Booking | Patient books appointment online/at reception |
| Doctor Schedule | Per-doctor time slots |
| Calendar | Monthly/weekly/daily view |
| Follow-up | Auto-suggest follow-up dates |
| Reminder | Notification before appointment |
| Reschedule | Change appointment time |
| Cancel | Cancel with reason |
| Online Booking | Patient self-service via PWA |

**Old V1 Reference:** `pages/Appointment.py`, `pages/FollowUp.py`

---

## 11. PHASE 4 — COMMUNICATION LAYER

**Target:** After Phase 3

### Adapters (All plug into same Notification Interface)

| Adapter | Priority | Description |
|---------|----------|-------------|
| PWA Push | 1st | Browser push notifications via Service Worker |
| Email | 2nd | SMTP-based email delivery |
| SMS | 3rd | SMS gateway integration |
| WhatsApp | 4th | WhatsApp Business API |
| Voice Call | 5th | TTS-based voice calls |
| Video Consultation | 6th | Video call integration |

**Old V1 Reference:** `utils/whatsapp.py`, `utils/email.py`, `utils/sms_upgrade.py`, `utils/push_notifications.py`, `utils/voice_call.py`, `utils/video_call.py`

---

## 12. PHASE 5 — BILLING ENGINE

**Target:** After Phase 4

### Features
| Feature | Description |
|---------|-------------|
| Invoices | Generate and print invoices |
| Payments | Record payments (cash, UPI, card) |
| Discounts | Apply discounts per visit |
| Refunds | Process refunds |
| GST | GST-compliant invoices |
| Insurance | Insurance claim support |
| Reports | Daily/monthly billing reports |

**Old V1 Reference:** `utils/billing.py`, `utils/gst.py`, `pages/Billing.py`, `pages/GST.py`

---

## 13. PHASE 6 — INVENTORY & PHARMACY

**Target:** After Phase 5

### Features
| Feature | Description |
|---------|-------------|
| Medicine Master | Drug database |
| Purchase Order | Order medicines from vendors |
| Vendor Management | Vendor records |
| Stock Management | Current stock levels |
| Batch Tracking | Batch/lot number tracking |
| Expiry Management | Expiry date alerts |
| FEFO | First Expiry First Out dispensing |
| Low Stock Alerts | Auto-alert on low stock |
| Pharmacy Dispensing | Dispense medicines to patients |

**Old V1 Reference:** `utils/inventory.py`, `utils/pharmacy.py`, `pages/Inventory.py`, `pages/Pharmacy.py`, `pages/Purchase.py`, `pages/Vendor.py`

---

## 14. PHASE 7 — LABORATORY

**Target:** After Phase 6

### Features
| Feature | Description |
|---------|-------------|
| Lab | Lab test catalog and reporting |
| Radiology | Radiology workflow |
| Ultrasound | Ultrasound reporting |
| X-Ray | X-Ray workflow |
| Sample Tracking | Barcode-based sample tracking |
| Verification | Verify results before release |

**Old V1 Reference:** `utils/lab.py`, `utils/radiology.py`, `utils/sample.py`, `pages/Lab_Technician.py`, `pages/Radiology.py`, `pages/Ultrasound.py`, `pages/XRay.py`

---

## 15. PHASE 8 — HR

**Target:** After Phase 7

### Features
| Feature | Description |
|---------|-------------|
| Employees | Staff records management |
| Attendance | Daily attendance tracking |
| Leave | Leave application and approval |
| Payroll | Salary calculation |
| Salary | Salary structure management |
| Roles | Job roles and descriptions |
| Permissions | Access control |

**Old V1 Reference:** `utils/hr.py`, `pages/HR.py`, `pages/Payroll.py`

---

## 16. PHASE 9 — FINANCE

**Target:** After Phase 8

### Features
| Feature | Description |
|---------|-------------|
| P&L | Profit and Loss statement |
| Expenses | Expense tracking |
| Owner Dashboard | High-level financial overview |
| Revenue | Revenue tracking by department/doctor |
| Cash Flow | Cash flow monitoring |
| Analytics | Financial trends and forecasts |
| GST Reports | GST filing reports |

**Old V1 Reference:** `utils/finance.py`, `pages/Finance.py`, `pages/Accountant.py`, `pages/Owner_Dashboard.py`

---

## 17. PHASE 10 — SYSTEM ADMINISTRATION

**Target:** After Phase 9

### Features
| Feature | Description |
|---------|-------------|
| RBAC UI | Role-based access control management interface |
| Compliance | Regulatory compliance tracking |
| Encryption | Data encryption management |
| Backup | Automated backup to local/cloud |
| Restore | Point-in-time restore |
| Monitoring | System health monitoring |
| Logging | Centralized log management |
| Multi Branch | Multi-clinic support |
| Health Dashboard | System status overview |

**Old V1 Reference:** `utils/rbac.py`, `utils/compliance.py`, `utils/encryption.py`, `utils/backup.py`, `utils/monitoring.py`, `utils/logging.py`, `utils/multi_branch.py`, `pages/RBAC.py`, `pages/Compliance.py`, `pages/EncryptionPage.py`, `pages/Backup.py`, `pages/Monitoring.py`, `pages/Logging.py`, `pages/MultiBranch.py`

---

## 18. PHASE 11 — ANALYTICS

**Target:** After Phase 10

### Features
| Feature | Description |
|---------|-------------|
| Patient Trends | Registration and visit trends |
| Department Performance | Per-department throughput metrics |
| Waiting Time | Analysis of wait times |
| Revenue | Revenue analytics |
| Doctor Productivity | Per-doctor performance metrics |
| Operational KPIs | Day-to-day operational metrics |
| Forecasting | Predictive analytics |

**Old V1 Reference:** `pages/Reports.py`, `pages/Analytics.py`

---

## 19. PHASE 12 — AI PLATFORM

**Target:** After Phase 11 — **Absolute last priority**

### Modules (Build Order)
| # | Module | Description |
|---|--------|-------------|
| 1 | AI Dietician | Diet recommendations based on condition |
| 2 | AI Report Explainer | Patient-friendly report interpretation |
| 3 | AI Prescription Assistant | Smart prescription suggestions |
| 4 | AI Receptionist | Automated patient check-in |
| 5 | AI Triage | Priority-based patient sorting |
| 6 | AI Voice Agent | Voice-based patient interaction |
| 7 | Doctor AI Assistant | Clinical decision support |
| 8 | Clinical Decision Support | Evidence-based recommendations |
| 9 | Natural Language Search | Search reports by voice/text |

**Old V1 Reference:** `utils/ai_dietician.py`, `utils/ai_report_explainer.py`, `utils/ai_prescription.py`, `utils/ai_voice_agent.py`, `pages/AI_Dietician.py`, `pages/AI_Report_Explainer.py`, `pages/AI_Prescription.py`, `pages/AI_VoiceAgent.py`, `pages/AI_FollowUp.py`, `pages/AI_Receptionist.py`, `pages/AI_Triage.py`

---

## 20. PROJECT MILESTONES

| Milestone | Description | Phase | Status |
|-----------|-------------|-------|--------|
| M1 | Foundation (Identity, Patient, Experience, Queue, Clinic) | Phase 0 | ✅ Complete |
| M2 | **Department Pilot — GHOS v1.0** (12 Modules) | **Phase 1** | **🔴 Current** |
| M3 | Clinical Department (ECG, Echo, TMT Reports) | Phase 2 | 📅 Future |
| M4 | Complete Cardiology Hospital (all engines integrated) | Phase 3-6 | 📅 Future |
| M5 | Multi-Specialty Hospital | Phase 7-9 | 📅 Future |
| M6 | Enterprise Hospital Operating System | Phase 10-12 | 📅 Future |

---

## 21. SUCCESS KPIs

| Metric | Target |
|--------|--------|
| Registration Time | < 30 seconds |
| Patient Waiting Query | Reduced by > 70% |
| Queue Accuracy | > 99% |
| Doctor Screen Changes | Zero — single screen for reporting |
| Technician Clicks | ≤ 2 per action |
| Patient Satisfaction | > 95% |
| Department Uptime | > 99% |
| Training Time | < 15 minutes for any role |

---

## 22. V1 → V2 FEATURE MIGRATION MAP

This maps every V1 module to its V2 Phase and Status.

| V1 Module | V2 Phase | V2 Module | Status |
|-----------|----------|-----------|--------|
| `utils/config.py` | Phase 0 | Clinic/Identity config | ✅ Done |
| `utils/db.py` | Phase 0 | Persistence (SQLite + JSON) | ✅ Done |
| `utils/queue.py` | Phase 0 | Queue Engine | ✅ Done |
| `utils/notifications.py` | Phase 1, Mod 5 | Patient Alerts (Brick 1) | 🔴 |
| `utils/helpers.py` | Phase 0 | Shared utilities | ✅ Done |
| `app.py` (Login) | Phase 0 | Identity Engine | ✅ Done |
| `pages/Reception.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/Registration.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/Receptionist.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/_department_base.py` | Phase 1, Mod 2 | Technician Workspace | 🔴 |
| `pages/ECG.py` | Phase 1, Mod 2 | Technician → ECG | 🔴 |
| `pages/Echo.py` | Phase 1, Mod 2 | Technician → Echo | 🔴 |
| `pages/TMT.py` | Phase 1, Mod 2 | Technician → TMT | 🔴 |
| `pages/OPD.py` | Phase 1, Mod 3 | Doctor Workspace | 🔴 |
| `pages/Doctor.py` | Phase 1, Mod 3 | Doctor Workspace | 🔴 |
| `pages/Manager.py` | Phase 1, Mod 4 | Manager Dashboard | 🔴 |
| `pages/Password_Management.py` | Phase 1, Mod 9 | Settings UI | 🔴 |
| `pages/Admin.py` | Phase 1, Mod 9 | Settings UI | 🔴 |
| `pages/Admin_Panel.py` | Phase 1, Mod 9 | Settings UI | 🔴 |
| `pages/Patient_Status.py` | Phase 1, Mod 5 | Patient PWA | ⚠️ Partial |
| `pages/Patient_Portal.py` | Phase 1, Mod 5 | Patient PWA | 🔴 |
| `pages/Patient_Timeline.py` | Phase 1, Mod 7 | Patient Timeline | 🔴 |
| `pages/Patient_Tracking.py` | Phase 1, Mod 7 | Patient Timeline | 🔴 |
| `pages/Nurse.py` | Phase 1, Mod 2 | Technician Workspace | 🔴 |
| `pages/Checkup.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/Feedback.py` | Phase 1, Mod 5 | Patient PWA (Feedback) | 🔴 |
| `pages/DischargedPatients.py` | Phase 1, Mod 4 | Manager Dashboard | 🔴 |
| `pages/Appointment.py` | Phase 3 | Appointment Engine | 📅 |
| `pages/Appointments.py` | Phase 3 | Appointment Engine | 📅 |
| `pages/FollowUp.py` | Phase 3 | Appointment Engine | 📅 |
| `pages/Billing.py` | Phase 5 | Billing Engine | 📅 |
| `pages/GST.py` | Phase 5 | Billing Engine | 📅 |
| `pages/HR.py` | Phase 8 | HR | 📅 |
| `pages/Payroll.py` | Phase 8 | HR | 📅 |
| `pages/Finance.py` | Phase 9 | Finance | 📅 |
| `pages/Accountant.py` | Phase 9 | Finance | 📅 |
| `pages/Owner_Dashboard.py` | Phase 9 | Finance | 📅 |
| `pages/Inventory.py` | Phase 6 | Inventory | 📅 |
| `pages/Pharmacy.py` | Phase 6 | Pharmacy | 📅 |
| `pages/Pharmacist.py` | Phase 6 | Pharmacy | 📅 |
| `pages/Purchase.py` | Phase 6 | Purchase | 📅 |
| `pages/Vendor.py` | Phase 6 | Vendor | 📅 |
| `pages/Lab_Technician.py` | Phase 7 | Laboratory | 📅 |
| `pages/Lab.py` | Phase 7 | Laboratory | 📅 |
| `pages/Radiology.py` | Phase 7 | Radiology | 📅 |
| `pages/Ultrasound.py` | Phase 7 | Ultrasound | 📅 |
| `pages/XRay.py` | Phase 7 | X-Ray | 📅 |
| `pages/RBAC.py` | Phase 10 | System Admin | 📅 |
| `pages/Compliance.py` | Phase 10 | System Admin | 📅 |
| `pages/Backup.py` | Phase 10 | System Admin | 📅 |
| `pages/Monitoring.py` | Phase 10 | System Admin | 📅 |
| `pages/Logging.py` | Phase 10 | System Admin | 📅 |
| `pages/Activity_Log.py` | Phase 1, Mod 10 | Audit Log | 🔴 |
| `pages/MultiBranch.py` | Phase 10 | System Admin | 📅 |
| `pages/EncryptionPage.py` | Phase 10 | System Admin | 📅 |
| `pages/BulkImport.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/SampleTracking.py` | Phase 7 | Sample Tracking | 📅 |
| `pages/BedManager.py` | Phase 1 | IPD Ward (future) | 📅 |
| `pages/IPD_Ward.py` | Phase 1 | IPD Ward | 📅 |
| `pages/Emergency.py` | Phase 1 | Emergency | 📅 |
| `pages/Daily_List.py` | Phase 1, Mod 1 | Reception Dashboard | 🔴 |
| `pages/Email.py` | Phase 4 | Communication | 📅 |
| `pages/SMS_Upgrade.py` | Phase 4 | Communication | 📅 |
| `pages/WhatsAppUpgrade.py` | Phase 4 | Communication | 📅 |
| `pages/PushNotifications.py` | Phase 4 | Communication | 📅 |
| `pages/VoiceCall.py` | Phase 4 | Communication | 📅 |
| `pages/VideoCall.py` | Phase 4 | Communication | 📅 |
| `pages/AI_Dietician.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_Report_Explainer.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_Prescription.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_VoiceAgent.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_FollowUp.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_Receptionist.py` | Phase 12 | AI Platform | 📅 |
| `pages/AI_Triage.py` | Phase 12 | AI Platform | 📅 |

---

## 🚫 WHAT NOT TO DO

- ❌ No Streamlit — ever
- ❌ No architecture redesign
- ❌ No new engines until current phase is complete
- ❌ No framework changes
- ❌ No AI before Phase 11
- ❌ No skipping phases
- ❌ No premature optimization
- ❌ No paid third-party APIs for core functions

---

## ✅ IMMEDIATE TASK — Module 1: Reception Dashboard

**Start now.** Build the complete Reception Dashboard:

1. Patient Search (Phone / QR / Patient ID)
2. New Patient Registration
3. Existing Patient Lookup
4. Multi-test Selection (ECG, Echo, TMT, Holter, ABPM)
5. Queue Generation
6. Token Slip Printing
7. Payment Status Indicator (placeholder for Phase 5)
8. Report Delivery Panel
9. Today's Queue Summary
10. Department Status Cards

This is the **current development task**. No other module should be started until this is complete, tested, and frozen.

---

*This document is the **master development blueprint** for GHOS and remains the single source of truth for all future development. It replaces both the old CardioQueue V1 product document and the Streamlit-based architecture document.*

*Last updated: 2026-07-14*
