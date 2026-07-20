# 🏥 GIL Clinic — OPD Extended Integration Plan

> ⚠️ **Product Development File** — Yeh file track karti hai ki OPD Extended system se
> kya lena hai, kahan lagana hai, kaise karna hai. Agar beech mein kaam band ho jaye
> to ye file padhke dubara shuru kar sakte hain bina confusion ke.

---

## 📌 Table of Contents

1. [System Overview](#1-system-overview)
2. [Source Analysis (OPD Extended)](#2-source-analysis-opd-extended)
3. [Target Architecture (GIL Clinic)](#3-target-architecture-gil-clinic)
4. [Feature Migration — Priority Wise](#4-feature-migration--priority-wise)
5. [Phase 1: AI Prescription + PDF](#5-phase-1-ai-prescription--pdf)
6. [Phase 2: Doctor Workflow Upgrade](#6-phase-2-doctor-workflow-upgrade)
7. [Phase 3: Templates + Drug Autocomplete](#7-phase-3-templates--drug-autocomplete)
8. [Phase 4: Cloud Backup (Supabase)](#8-phase-4-cloud-backup-supabase)
9. [Phase 5: Advanced Features](#9-phase-5-advanced-features)
10. [File Reference: OPD → GIL Mapping](#10-file-reference-opd--gil-mapping)
11. [Recovery Plan (Agar Beech Mein Ruk Jaye)](#11-recovery-plan-agar-beech-mein-ruk-jaye)
12. [Testing Checklist](#12-testing-checklist)
13. [Deployment Checklist](#13-deployment-checklist)

---

## 1. System Overview

### 🟢 Current System (GIL Clinic — FastAPI + HTML)
```
Frontend:  Jinja2 HTML templates + CSS + JavaScript
Backend:   FastAPI (Python 3.12)
Database:  SQLAlchemy + SQLite (async)
Auth:      PIN-based (staff_routes.py mein hardcoded)
Queue:     QueueEntryModel — Cardiology department, service_code based
Patients:  PatientModel — basic demographics
Deploy:    Railway (Docker + SQLite)
URL:       https://cardioqueue-production.up.railway.app
```

### 🟠 Source System (OPD Extended — Streamlit)
```
Frontend:  Streamlit (Python — event-driven)
Backend:   Streamlit (same process)
Database:  SQLite (direct sqlite3, no ORM)
Auth:      PIN-based (chief=5555, junior=1234, admin=9999)
AI:        Groq API (Llama 3.3) — prescription generation, OCR, voice
Backup:    Supabase (optional) + Google Sheets webhook
PDF:       fpdf2 — professional Indian prescription format
Files:     27 Python files, 7 database tables
URL:       https://github.com/gurjeetsinghgill8-web/new-opd-EXTENDED-B
```

### 🔵 Migration Strategy
```
❌ Direct copy-paste nahi karna (Streamlit → FastAPI incompatible)
✅ Features uthao, GIL Clinic FastAPI system me rebuild karo
✅ AI engine, prompts, PDF generator — yeh directly reuse ho sakte hain
✅ Database schema se inspiration lo, lekin apne existing models me merge karo
```

---

## 2. Source Analysis (OPD Extended)

### 2.1 OPD Database Tables (7 tables)
```
┌──────────────────┐
│    patients      │  ← Main patient records with prescriptions
├──────────────────┤
│   pending_rx     │  ← Batch scan pending prescriptions (OCR queue)
├──────────────────┤
│ specialty_upgrades│  ← AI specialty comparison records
├──────────────────┤
│  drug_history    │  ← Drug names for autocomplete
├──────────────────┤
│   templates      │  ← Rx templates + Lab templates
├──────────────────┤
│   licenses       │  ← Doctor licenses (multi-doctor support)
├──────────────────┤
│  app_settings    │  ← Key-value settings store
└──────────────────┘
```

### 2.2 OPD Features List
```
╔══════════════════════════════════╦════════════╦══════════════════╗
║           Feature                ║  Priority  ║  Migration Cost  ║
╠══════════════════════════════════╬════════════╬══════════════════╣
║ AI Prescription Generation       ║  🔥 HIGH   ║  1 day           ║
║ PDF Prescription Download        ║  🔥 HIGH   ║  1 day           ║
║ Drug Autocomplete                ║  🔥 HIGH   ║  4 hours         ║
║ Rx / Lab Templates               ║  🔥 HIGH   ║  4 hours         ║
║ Doctor Login (License system)    ║  🔥 HIGH   ║  2 days          ║
╠══════════════════════════════════╬════════════╬══════════════════╣
║ Supabase Cloud Backup            ║  ⚡ MEDIUM ║  1 day           ║
║ Follow-up Progress Tracking      ║  ⚡ MEDIUM ║  1 day           ║
║ Patient Search (old)             ║  ⚡ MEDIUM ║  4 hours         ║
║ QR-based Patient Identity        ║  ⚡ MEDIUM ║  1 day           ║
╠══════════════════════════════════╬════════════╬══════════════════╣
║ Batch Scan (OCR)                 ║  🟢 LOW    ║  2 days          ║
║ Specialty Upgrade (AI Consult)   ║  🟢 LOW    ║  2 days          ║
║ Voice Scribe (Whisper)           ║  🟢 LOW    ║  1 day           ║
║ CME Study Generator              ║  🟢 LOW    ║  1 day           ║
║ Research Agent (Analytics)       ║  🟢 LOW    ║  2 days          ║
║ Starred Cases                    ║  🟢 LOW    ║  4 hours         ║
╚══════════════════════════════════╩════════════╩══════════════════╝
```

---

## 3. Target Architecture (GIL Clinic)

### 3.1 Current Files Structure
```
gil-clinic/
├── src/
│   ├── application/          ← Use cases
│   │   └── queue/use_cases/  ← Queue business logic
│   ├── domain/               ← Entities, Value Objects
│   │   └── queue/entities/   ← QueueEntry, etc.
│   ├── infrastructure/       ← Database, external services
│   │   ├── patient/models/   ← PatientModel
│   │   ├── queue/models/     ← QueueEntryModel
│   │   └── persistence/      ← Repositories
│   ├── presentation/         ← Routes (FastAPI)
│   │   ├── queue/routes/     ← Queue API (/api/v1/queue/*)
│   │   ├── patient/routes/   ← Patient API (/api/v1/patient/*)
│   │   └── staff/routes/     ← Staff Dashboard (HTML)
│   └── shared/               ← Database, base classes
├── templates/dashboard/       ← Jinja2 HTML templates
├── static/dashboard/          ← CSS, JS
└── main.py                    ← FastAPI app entry
```

### 3.2 Target Files Structure (After Integration)
```
gil-clinic/
├── src/
│   ├── application/
│   │   ├── queue/use_cases/  ← Existing (unchanged)
│   │   └── opd/              ← 🆕 OPD use cases
│   │       ├── __init__.py
│   │       ├── ai_prescription_use_case.py
│   │       ├── pdf_generation_use_case.py
│   │       ├── template_use_case.py
│   │       └── drug_history_use_case.py
│   ├── domain/
│   │   ├── queue/entities/   ← Existing
│   │   └── opd/              ← 🆕 OPD domain entities
│   │       ├── __init__.py
│   │       ├── prescription.py
│   │       └── template.py
│   ├── infrastructure/
│   │   ├── patient/models/   ← Existing + extend
│   │   ├── queue/models/     ← Existing
│   │   └── opd/              ← 🆕 OPD models + repos
│   │       ├── models/
│   │       │   ├── prescription_model.py
│   │       │   ├── drug_history_model.py
│   │       │   └── template_model.py
│   │       └── repositories/
│   │           ├── prescription_repository.py
│   │           ├── drug_history_repository.py
│   │           └── template_repository.py
│   ├── ai_engine/            ← 🆕 Copied from OPD Extended
│   │       ├── groq_client.py
│   │       └── prompts.py
│   ├── presentation/
│   │   ├── queue/routes/     ← Existing
│   │   ├── patient/routes/   ← Existing
│   │   ├── staff/routes/     ← Existing + extend
│   │   └── opd/              ← 🆕 OPD routes
│   │       └── routes/
│   │           └── opd_routes.py
├── templates/
│   ├── dashboard/            ← Existing
│   └── opd/                  ← 🆕 OPD templates
│       ├── doctor_dashboard.html
│       ├── prescription_form.html
│       ├── patient_search.html
│       └── settings.html
├── static/dashboard/         ← Existing (will add CSS)
└── utils/                    ← 🆕 Copied from OPD Extended
    ├── helpers.py
    └── validators.py
```

---

## 4. Feature Migration — Priority Wise

```
📊 MIGRATION ROADMAP
═══════════════════════════════════════════════════════════════════
PHASE 1 (Week 1) — AI Prescription + PDF           🔥 HIGH
───────────────────────────────────────────────────────────────────
  Day 1:  ai_engine/ — Copy groq_client.py + prompts.py
  Day 2:  AI Prescription API endpoint
  Day 3:  Doctor dashboard template (prescription form)
  Day 4:  PDF Generator integration
  Day 5:  Testing + Deploy

PHASE 2 (Week 2) — Doctor Workflow                  🔥 HIGH
───────────────────────────────────────────────────────────────────
  Day 1:  Patient search (old patient lookup)
  Day 2:  Follow-up tracking
  Day 3:  Drug autocomplete
  Day 4:  Doctor settings page
  Day 5:  Testing + Deploy

PHASE 3 (Week 3) — Templates + Backup               ⚡ MEDIUM
───────────────────────────────────────────────────────────────────
  Day 1:  Rx / Lab templates CRUD
  Day 2:  Supabase backup integration
  Day 3:  Auto-restore on deploy
  Day 4:  Queue → cloud sync
  Day 5:  Testing + Deploy

PHASE 4 (Week 4) — Advanced Features                🟢 LOW
───────────────────────────────────────────────────────────────────
  Day 1:  Batch Scan (OCR for handwritten Rx)
  Day 2:  Specialty Upgrade (AI specialist consult)
  Day 3:  Voice Scribe (Whisper)
  Day 4:  Research Agent
  Day 5:  Final Testing + Deploy
═══════════════════════════════════════════════════════════════════
```

---

## 5. Phase 1: AI Prescription + PDF

### 5.1 Files to Copy from OPD Extended
```
Source (OPD Extended)              →  Target (GIL Clinic)
──────────────────────────────────────────────────────────────
ai_engine/groq_client.py           →  src/ai_engine/groq_client.py
ai_engine/prompts.py               →  src/ai_engine/prompts.py
features/pdf_generator.py          →  src/utils/pdf_generator.py
config/settings.py (SPECIALTIES)   →  src/shared/opd_specialties.py
requirements.txt (add groq)        →  requirements.txt (update)
```

### 5.2 New Files to Create in GIL Clinic
```
┌─────────────────────────────────────────────────────────────────┐
│  src/presentation/opd/routes/opd_routes.py                      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ POST /api/v1/opd/generate-prescription  → AI generate Rx   ││
│  │ POST /api/v1/opd/generate-pdf           → Download PDF     ││
│  │ POST /api/v1/opd/save-prescription      → Save to DB       ││
│  │ GET  /staff/doctor                      → Doctor page (upd)││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  src/application/opd/use_cases/ai_prescription_use_case.py      │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Input: patient_name, age, gender, complaints, vitals,       ││
│  │        investigations, doctor_id                            ││
│  │ Process: call_groq() with gp_prompt()                       ││
│  │ Output: Diagnosis, Medicines, Advice, Follow-up             ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  templates/opd/doctor_dashboard.html                            │
│  templates/opd/prescription_form.html                           │
└─────────────────────────────────────────────────────────────────┘
```

### 5.3 Doctor Page Flow
```
┌──────────────────────────────────────────────────────────────┐
│                    DOCTOR DASHBOARD                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │   LEFT: Patient Form │  │   RIGHT: Prescription Output │  │
│  │                      │  │                              │  │
│  │  Patient Name: [___] │  │  🏥 AI Generated Prescription│  │
│  │  Age:          [___] │  │  ┌──────────────────────────┐│  │
│  │  Phone:        [___] │  │  │ Diagnosis: ___________  ││  │
│  │  Vitals BP:    [___] │  │  │                         ││  │
│  │  Complaints:   [___] │  │  │ 1. Tab. __________     ││  │
│  │                      │  │  │ 2. Tab. __________     ││  │
│  │  [ 🔍 Search Old ]   │  │  │                         ││  │
│  │                      │  │  │ Follow-up: _________   ││  │
│  │  [ 🤖 Generate Rx ]  │  │  └──────────────────────────┘│  │
│  │                      │  │                              │  │
│  │  Quick Invest:       │  │  [✏️ Edit] [📄 PDF] [💾 Save]│  │
│  │  [CBC][ECG][X-Ray]   │  │                              │  │
│  └──────────────────────┘  └──────────────────────────────┘  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 5.4 API Endpoints (Phase 1)
```
POST /api/v1/opd/generate-prescription
  Body: {
    "patient_name": "Amar Singh",
    "age": 45,
    "gender": "Male",
    "complaints": "Sardar dard, bukhar 2 din se",
    "vitals": "BP 130/80, Pulse 78",
    "investigations": "CBC, ECG"
  }
  Response: {
    "diagnosis": "Hypertension, Viral Fever",
    "medicines": "1. Tab. Paracetamol 500mg - TDS - 3 days\n2. Tab. Telmisartan 40mg - OD - 30 days",
    "advice": "Rest, plenty of fluids",
    "follow_up": "7 days"
  }

POST /api/v1/opd/generate-pdf
  Body: {
    "patient_name": "Amar Singh",
    "vitals": "BP 130/80",
    "prescription": "...",
    "doctor_id": "chief"
  }
  Response: PDF bytes (application/pdf)

POST /api/v1/opd/save-prescription
  Body: {
    "patient_name": "...",
    "phone": "...",
    "vitals": "...",
    "complaints": "...",
    "medicines": "...",
    "investigations": "..."
  }
  Response: { "ok": true, "patient_id": "CQ-..." }
```

### 5.5 Dependencies to Add
```
# requirements.txt me ye add karo:
groq>=0.8.0            # AI client (already OPD Extended me hai)
fpdf2>=2.7.6           # PDF generator (already in requirements)
Pillow>=10.0.0         # Image processing for Groq vision
```

---

## 6. Phase 2: Doctor Workflow Upgrade

### 6.1 Patient Search (Old Patient Lookup)
```
┌─────────────────────────────────────────────────────────────┐
│                    PATIENT SEARCH                           │
├─────────────────────────────────────────────────────────────┤
│  🔎 Search: [________________]  Name ya Phone              │
├─────────────────────────────────────────────────────────────┤
│  Results:                                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 👤 Amar Singh | 2026-07-20 | 📞 9876543210             ││
│  │    Vitals: BP 130/80 | Fee: ₹300                       ││
│  │    [📝 Follow-Up]  [✏️ Reprint]  [📄 Old PDF]          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 👤 Baldev Kaur | 2026-07-20 | 📞 9876543211            ││
│  │    Vitals: BP 120/80 | Fee: ₹300                       ││
│  │    [📝 Follow-Up]  [✏️ Reprint]  [📄 Old PDF]          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Follow-up Tracking
```
┌─────────────────────────────────────────────────────────────┐
│  🔄 FOLLOW-UP: Amar Singh (Last: 2026-07-10)               │
│                                                             │
│  Past Vitals: BP 150/90  ──→  Today: BP 130/80  ✅ IMPROVED │
│  Past Rx: Telmisartan 40mg → Same (continuing)              │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Load past data → Pre-fill form                          ││
│  │ Adjust → Generate new Rx → Save                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Drug Autocomplete
```
Database Table: drug_history
  id        INTEGER PRIMARY KEY
  doctor_id TEXT NOT NULL
  drug_name TEXT NOT NULL
  date      TEXT DEFAULT current_timestamp

Flow:
  Save Prescription → Extract drug names (regex)
                    → INSERT INTO drug_history
                    → Next time: SELECT DISTINCT drug_name WHERE LIKE '%query%'

API:
  GET /api/v1/opd/drug-suggestions?q=telmi
  → ["Telmisartan 40mg", "Telmisartan 20mg", "Telmisartan+HCZ"]
```

---

## 7. Phase 3: Templates + Drug Autocomplete

### 7.1 Templates System
```
Database Table: templates
  id       INTEGER PRIMARY KEY
  category TEXT NOT NULL ('Rx' or 'Lab')
  name     TEXT NOT NULL UNIQUE
  content  TEXT NOT NULL
  created_at TEXT DEFAULT current_timestamp

API:
  GET  /api/v1/opd/templates?category=Rx
  POST /api/v1/opd/templates  {"category":"Rx","name":"HTN","content":"..."}
  DELETE /api/v1/opd/templates/{name}

Sample Templates:
  Rx: {
    "HTN Standard": "1. Tab. Telmisartan 40mg OD\n2. Tab. Amlodipine 5mg OD",
    "Diabetes": "1. Tab. Metformin 500mg BD\n2. Tab. Glimepiride 2mg OD",
    "Viral Fever": "1. Tab. Paracetamol 650mg TDS\n2. Syp. Ascoril 2tsp TDS"
  }
  Lab: {
    "Routine Cardiac": "ECG, Lipid Profile, FBS, HbA1c, RFT",
    "Annual Checkup": "CBC, LFT, RFT, Lipid, TSH, Vit D, Vit B12"
  }
```

### 7.2 Doctor-Specific Settings
```
API:
  GET  /api/v1/opd/settings
  POST /api/v1/opd/settings  {"key":"clinic_name","value":"GIL Clinic"}

Settings Keys:
  clinic_name, clinic_address, doc_name, doc_degree,
  doc_reg_no, doc_phone, doc_email, groq_api_key
```

---

## 8. Phase 4: Cloud Backup (Supabase)

### 8.1 Supabase Schema
```
Table: queue_entries (mirror of local SQLite)
  id UUID PRIMARY KEY
  patient_id TEXT
  patient_name TEXT
  service_code TEXT
  token_number INT
  status TEXT
  created_at TIMESTAMPTZ
  doctor_id TEXT

Table: patients (cloud copy)
  patient_id TEXT PRIMARY KEY
  patient_name TEXT
  phone TEXT
  vitals TEXT
  medicines TEXT
  created_at TIMESTAMPTZ
  doctor_id TEXT
```

### 8.2 Backup Flow
```
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKUP PIPELINE                                │
│                                                                     │
│  ┌──────────┐     ┌─────────────┐     ┌──────────────┐             │
│  │  Local    │────→│  Sync Agent │────→│  Supabase    │             │
│  │  SQLite   │     │ (background) │     │  (Cloud DB)  │             │
│  └──────────┘     └─────────────┘     └──────────────┘             │
│       │                                       │                     │
│       │  On app start: check if empty          │  On login: pull    │
│       │  → offer restore from cloud            │  last 30 days      │
│       └─────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────┘

Files to create:
  src/infrastructure/backup/supabase_client.py
  src/infrastructure/backup/sync_manager.py
```

---

## 9. Phase 5: Advanced Features

### 9.1 Batch Scan (OCR for Handwritten Rx)
```
Flow:
  1. Doctor uploads photo of handwritten prescription
  2. Call groq vision API with prompt to extract text
  3. Show extracted text in review form
  4. Doctor edits + approves → saves to patients table

Files:
  templates/opd/batch_scan.html
  src/presentation/opd/routes/opd_routes.py (add /batch-scan endpoint)
  Uses: ai_engine/groq_client.py → call_groq_vision()
```

### 9.2 Specialty Upgrade (AI Consult)
```
Flow:
  1. Doctor enters patient data + current prescription
  2. Selects specialty (Cardiology, Neuro, etc.)
  3. AI generates specialist's opinion with evidence
  4. Compare GP vs Specialist side-by-side
  5. Star for later reference

API:
  POST /api/v1/opd/specialty-upgrade
  Body: { "patient_data": {...}, "specialty": "Cardiology" }
  Response: { "gp_rx": "...", "specialist_rx": "...", "evidence": "..." }
```

### 9.3 Voice Scribe
```
Flow:
  1. Doctor clicks mic button
  2. Records audio (browser Web API or file upload)
  3. Sends to Whisper API (Groq)
  4. Transcribed text fills complaints/notes field

Uses: ai_engine/groq_client.py → call_whisper()
```

---

## 10. File Reference: OPD → GIL Mapping

### 10.1 Files to Copy Directly (with minor edits)
```
OPD Extended File              →  GIL Clinic Target File             Changes Needed
──────────────────────────────────────────────────────────────────────────────────────
ai_engine/groq_client.py       →  src/ai_engine/groq_client.py       Change imports
ai_engine/prompts.py           →  src/ai_engine/prompts.py           No change
features/pdf_generator.py      →  src/utils/pdf_generator.py         Change imports
utils/helpers.py               →  src/utils/helpers.py               Change imports
config/settings.py (partial)   →  src/shared/opd_specialties.py      Extract only SPECIALTIES
```

### 10.2 Files to Create New (GIL Clinic specific)
```
New File                                   Purpose
──────────────────────────────────────────────────────────────────────
src/application/opd/use_cases/             OPD use cases package
├── ai_prescription_use_case.py            AI Rx generation logic
├── pdf_generation_use_case.py            PDF creation logic
├── template_use_case.py                   Template CRUD logic
└── drug_history_use_case.py              Drug autocomplete logic

src/domain/opd/                            OPD domain entities
├── prescription.py                        Prescription value object
└── template.py                            Template entity

src/infrastructure/opd/models/             OPD SQLAlchemy models
├── prescription_model.py
├── drug_history_model.py
└── template_model.py

src/infrastructure/opd/repositories/       OPD repositories
├── prescription_repository.py
├── drug_history_repository.py
└── template_repository.py

src/presentation/opd/routes/opd_routes.py  OPD API routes

templates/opd/                             OPD Jinja2 templates
├── doctor_dashboard.html
├── prescription_form.html
├── patient_search.html
├── settings.html
└── batch_scan.html
```

### 10.3 Files to Modify (Existing GIL Clinic files)
```
Existing File                         Changes
──────────────────────────────────────────────────────────────────────
src/presentation/staff/routes/        Add OPD-related routes:
  staff_routes.py                       /staff/doctor → full doctor flow
                                       /staff/opd-settings

main.py                               Register new routers:
                                       app.include_router(opd_router)

requirements.txt                      Add: groq>=0.8.0, fpdf2>=2.7.6,
                                       Pillow>=10.0.0

templates/dashboard/base.html         Add OPD nav link if not present
                                       Add OPD CSS if needed

static/dashboard/style.css            Add OPD-specific styles
static/dashboard/app.js               Add OPD-specific JS handlers
```

---

## 11. Recovery Plan (Agar Beech Mein Ruk Jaye)

### 11.1 If Agent Gets Confused
```
Step 1:  Yeh file padho → OPD_INTEGRATION_PLAN.md
Step 2:  Check current status from TodoWrite
Step 3:  Check Phase → Day → Task from roadmap above
Step 4:  Check Files section → kya bana chuke ho, kya nahi
Step 5:  Continue from where you left off
```

### 11.2 If Deployment Breaks
```
Rollback:
  railway rollback  ← last working deployment

Common Issues:
  - Missing dependency: Check requirements.txt
  - Import error: Check file paths match exactly
  - DB error: Railway SQLite resets on deploy (seed again)
```

### 11.3 If Railway Resets (Data Loss)
```
1. Railway pe SQLite ephemeral hai — redeploy pe data loss
2. Isliye Phase 4 (Cloud Backup) IMPORTANT hai
3. Tab tak: /staff/seed se dubara seed data banao
4. Ya /staff/api/register se patients register karo
```

### 11.4 Git Commands for Checkpoint
```bash
# Before starting a new phase, commit:
git add -A
git commit -m "checkpoint: before Phase N"

# If something breaks:
git checkout -- .   # Discard all changes

# To see what changed:
git diff --name-only
```

---

## 12. Testing Checklist

### Phase 1 — AI Prescription + PDF
```
[  ] POST /api/v1/opd/generate-prescription → 200 with AI Rx
[  ] POST /api/v1/opd/generate-pdf → 200 with PDF bytes
[  ] POST /api/v1/opd/save-prescription → 200 with patient_id
[  ] Doctor page loads with form
[  ] "Generate Rx" button works
[  ] "Download PDF" button works
[  ] "Save" button saves to DB
[  ] Template dropdown shows templates
[  ] Quick investigation buttons work
```

### Phase 2 — Doctor Workflow
```
[  ] Patient search by name works
[  ] Patient search by phone works
[  ] Follow-up loads past data
[  ] Follow-up shows vitals comparison
[  ] Drug autocomplete shows suggestions
[  ] Drug autocomplete learns new drugs
[  ] Doctor settings page saves/loads
```

### Phase 3 — Templates + Backup
```
[  ] Template CRUD works (create/read/update/delete)
[  ] Template loads into prescription form
[  ] Supabase connection works
[  ] Data syncs to cloud on save
[  ] Data restores from cloud on deploy
```

### General
```
[  ] All pages load without 500 errors
[  ] Login/logout works
[  ] Mobile responsive
[  ] Railway deploy succeeds
[  ] Railway health check passes
[  ] Seed data creates properly
```

---

## 13. Deployment Checklist

### Before Railway Deploy
```
[  ] requirements.txt updated with all new deps
[  ] No syntax errors (python -c "compile")
[  ] All imports resolve correctly
[  ] Templates use correct variable names
[  ] Static files referenced with correct paths
[  ] Railway domain is active
```

### After Railway Deploy
```
[  ] railway logs → no errors
[  ] curl https://domain/staff/login → 200
[  ] Login works with test PIN
[  ] All pages render (check 2-3 pages)
[  ] Seed data created if needed
[  ] DNS resolving (or hosts file entry)
```

---

## 📝 Memory File Location

```
Yeh file yahan save hai:
  C:\Users\pc\Desktop\gurjas ai\GIL CLINIC\OPD_INTEGRATION_PLAN.md

Memory topic entry:
  C:\Users\pc\.zcode\cli\memories\projects\gil-clinic-634ed77773d1c9bd\topics\project_opd-integration-plan.md

Agent ko batana:
  "Read OPD_INTEGRATION_PLAN.md — wahan sab likha hai"
```

---

> **Last Updated:** 2026-07-20  
> **Source Repo:** https://github.com/gurjeetsinghgill8-web/new-opd-EXTENDED-B  
> **Target App:** https://cardioqueue-production.up.railway.app  
> **Created by:** ZCode Agent — GIL Clinic Development
