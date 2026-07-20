# 🧠 SMART OPD — Master Reference Memory File

> ⚠️ Yeh memory file **master source file** par based hai:
> `C:\Users\pc\.zcode\tmp\paste-attachments\2026-07-20\pasted-text-20260720-214546-b395e2de.txt`
>
> **Kabhi bhi is source file ko change mat karna.** Sirf isko reference ki tarah use karo
> aur FastAPI/HTML system me rebuild karo.

---

## 📋 File Inventory

### Master File: `bharat_ai_clinic_master.py` (3366+ lines)
- Streamlit monolith app — saara logic ek hi file mein
- **Do NOT modify** — sirf reference ke liye

### Lab Scanner Module: `lab_scanner.py`
- Standalone lab report batch scanner
- Groq Vision + PDF + WhatsApp
- Can be used as standalone or imported

---

## 🏗️ Architecture (Master File)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BHARAT AI CLINIC — ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     LAYER 1: LOGIN                           │   │
│  │  PIN: 5554=Chief | 1234=Junior | 1010=Admin | License Pins  │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    LAYER 2: ROUTING                         │   │
│  │  role=admin  →  Admin Portal (5 tabs)                       │   │
│  │  role=chief  →  Doctor Portal (New Rx, Batch, Starred,      │   │
│  │  role=junior     Roster, Settings)                           │   │
│  │  role=licensed → Same Doctor Portal (isolated doctor_id)    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER 3: DATA PERSISTENCE                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────┐           │   │
│  │  │ SQLite   │←→│ Supabase │←→│ Google Sheet   │           │   │
│  │  │ (Local   │  │ (Cloud   │  │ (Webhook/CSV)  │           │   │
│  │  │  Cache)  │  │  Source  │  │ (Legacy)       │           │   │
│  │  └──────────┘  └──────────┘  └────────────────┘           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              LAYER 4: AI ENGINE (Groq)                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐   │   │
│  │  │ call_groq()  │  │call_groq_scan│  │ call_whisper()  │   │   │
│  │  │ (Text+Image) │  │ (Vision OCR) │  │ (Voice→Text)    │   │   │
│  │  └──────────────┘  └──────────────┘  └─────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Tables (ALL 7)

### 1. `patients` — Main patient records
```sql
id              BIGSERIAL PRIMARY KEY
doctor_id       TEXT NOT NULL DEFAULT 'chief'
date            TEXT
patient_name    TEXT
phone           TEXT
vitals          TEXT
fee             TEXT DEFAULT '0'
complaints      TEXT
medicines       TEXT
investigations  TEXT DEFAULT ''
specialty       TEXT DEFAULT 'General Physician'
```

### 2. `drug_history` — Drug autocomplete data
```sql
id              BIGSERIAL PRIMARY KEY
doctor_id       TEXT NOT NULL
drug_name       TEXT
dose            TEXT
use_count       INTEGER DEFAULT 1
last_used       TEXT
```

### 3. `specialty_upgrades` — AI specialist consultations
```sql
id              BIGSERIAL PRIMARY KEY
doctor_id       TEXT NOT NULL DEFAULT 'chief'
date            TEXT
patient_name    TEXT
vitals          TEXT
original_rx     TEXT
specialty       TEXT
upgraded_rx     TEXT
evidence        TEXT
is_starred      INTEGER DEFAULT 0
star_note       TEXT DEFAULT ''
```

### 4. `templates` — Rx and Lab templates
```sql
id              BIGSERIAL PRIMARY KEY
doctor_id       TEXT NOT NULL DEFAULT 'chief'
category        TEXT
name            TEXT
content         TEXT
UNIQUE(doctor_id, name)
```

### 5. `licenses` — Multi-doctor license system
```sql
id              BIGSERIAL PRIMARY KEY
doctor_id       TEXT UNIQUE NOT NULL
doctor_name     TEXT
doctor_email    TEXT
doctor_phone    TEXT
pin             TEXT UNIQUE NOT NULL
clinic_name     TEXT
specialty       TEXT
expiry_date     TEXT
is_active       INTEGER DEFAULT 1
created_date    TEXT
notes           TEXT DEFAULT ''
```

### 6. `settings` — Doctor/clinic settings
```sql
doctor_id       TEXT PRIMARY KEY
clinic_name     TEXT DEFAULT 'My Clinic'
doc_name        TEXT DEFAULT 'Doctor'
doc_subtitle    TEXT DEFAULT 'MBBS'
doc_degree      TEXT DEFAULT ''
doc_reg_no      TEXT DEFAULT ''
doc_email       TEXT DEFAULT ''
doc_phone       TEXT DEFAULT ''
clinic_address  TEXT DEFAULT ''
doc_extra_quals TEXT DEFAULT ''
```

### 7. `pending_scans` — Batch prescription scan queue
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
doctor_id       TEXT NOT NULL DEFAULT 'chief'
uploaded_at     TEXT
image_b64       TEXT
patient_name    TEXT DEFAULT ''
phone           TEXT DEFAULT ''
vitals          TEXT DEFAULT ''
fee             TEXT DEFAULT '0'
complaints      TEXT DEFAULT ''
medicines       TEXT DEFAULT ''
investigations  TEXT DEFAULT ''
status          TEXT DEFAULT 'pending'
```

---

## 🔑 PIN-Based Authentication

### Built-in Roles
| Role   | PIN  | doctor_id       | Access                      |
|--------|------|-----------------|-----------------------------|
| Chief  | 5554 | clinic_default  | Full doctor portal          |
| Junior | 1234 | clinic_default  | Doctor portal (no research) |
| Admin  | 1010 | admin           | Admin portal only           |

### License System (Multi-Doctor)
- Doctor-specific PIN stored in `licenses` table
- doctor_id unique per licensed doctor
- Isolated data (each licensed doctor sees only their patients)
- Expiry date enforcement
- Settings auto-initialized on license creation

### Login Flow
```
1. User enters PIN
2. Check built-in roles (chief/junior/admin)
3. If not found → check licenses table (pin + is_active + expiry)
4. On success → set session_state: role, doctor_id, lic info
5. On fail → show error
```

---

## 💾 Data Persistence (3-Layer Strategy)

### Layer 1: SQLite (Local Cache)
- Location: `/tmp/gill_opd_cache.db`
- WAL mode for performance
- All tables created on startup via `init_db()`
- Fast reads, instant writes
- **Resets on server restart** (it's in /tmp/)

### Layer 2: Supabase (Cloud Source of Truth)
- REST API via `requests`
- No Supabase SDK needed
- Tables: patients, drug_history, specialty_upgrades, templates, licenses, settings
- Patient save: `db_save_patient()` → SQLite + Supabase + Google Sheet
- Sync on login: `sync_from_supabase()` → pull last 30 days
- Auto-restore: `_check_and_restore()` → if local empty, offer restore

### Layer 3: Google Sheet (Legacy Backup)
- Webhook URL hardcoded
- On patient save → POST to webhook
- CSV export for patient search and roster

### Sync Flow
```
On Login:
  sync_from_supabase()
    1. Pull settings from Supabase → cache in SQLite
    2. Pull patients (last 1000) → merge into SQLite (dedup by name+date)
    3. Pull licenses → INSERT OR REPLACE
    4. Pull templates → INSERT OR REPLACE

On Patient Save:
  db_save_patient()
    1. INSERT into SQLite (always)
    2. INSERT into Supabase (if configured)
    3. POST to Google Sheet webhook (if URL configured)
    4. Learn drug names from Rx text → drug_history
```

---

## 🤖 AI Engine

### `call_groq(msgs, model, temp)`
- Multi-modal (text + image)
- Model: llama-3.3-70b-versatile (text) / llama-4-scout-17b (vision)
- Rate limit handling
- Returns: response text or None

### `call_whisper(audio_bytes, fname)`
- Audio transcription via Groq Whisper API
- Returns: transcribed text

### `call_groq_scan(img, extra)`
- Vision OCR for handwritten prescriptions
- Returns: structured JSON (patient_name, phone, vitals, complaints, medicines, etc.)

### API Key Resolution
```
1. st.secrets["GROQ_API_KEY"]
2. st.session_state.groq_key
3. os.getenv("GROQ_API_KEY")
```

---

## 📄 PDF Generator

### `make_rx_pdf(pt_name, vitals, rx_text, investigations, specialty_label)`
- Professional Indian prescription format
- Letterhead: Doctor (left) + Clinic (right)
- Patient info row: Name, Date, Vitals
- Prescription body
- Investigations section
- Returns: PDF bytes

### `make_cme_pdf(topic, content)`
- CME study material PDF
- Returns: PDF bytes

### `show_pdf(pdf_bytes)`
- Display PDF in Streamlit via base64 iframe

---

## 🧩 Features List (Complete)

### Doctor Portal (Chief/Junior/Licensed)
```
┌─────────────────────────────────────────────────────────────────┐
│ TAB 1: NEW Rx (Patient Form + AI Prescription)                 │
├─────────────────────────────────────────────────────────────────┤
│  • New Patient / Old Patient toggle                             │
│  • Old patient search (name/phone → SQLite + Supabase + Sheet)  │
│  • Follow-up: load past vitals + Rx, compare vitals            │
│  • Patient details: name, age, gender, phone                    │
│  • Vitals: BP, Pulse, Sugar, Weight, SpO2, Temp                │
│  • Complaints: text input + voice scribe (Whisper)             │
│  • Quick investigations: CBC, ECG, X-Ray, etc. (18 buttons)    │
│  • Template selector: Rx templates + Lab templates              │
│  • Drug autocomplete from drug_history                          │
│  • AI Generate Prescription button                              │
│  • Manual edit Rx output                                        │
│  • Save as template                                             │
│  • PDF preview + download                                       │
│  • Save patient (3-layer: SQLite + Supabase + Sheet)            │
│  • WhatsApp share                                               │
│  • Specialty Upgrade section: select 1-3 specialties → AI      │
│    comparison → side-by-side GP vs Specialist → Star → Save    │
│  • Drug Review (chief only): AI interaction/dose/cost check    │
│  • CME Study (chief only): AI generates study material         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TAB 2: BATCH SCAN (Upload + AI OCR)                            │
├─────────────────────────────────────────────────────────────────┤
│  • Upload photos (multi-file + camera)                         │
│  • Preview thumbnails                                          │
│  • Process All → AI reads each Rx via Groq Vision              │
│  • Saves to pending_scans table                                │
│  • Review tab: edit fields, approve/skip/draft                 │
│  • Approve → finalize_pending() → saves to patients table      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TAB 3: STARRED (Saved Comparisons)                             │
├─────────────────────────────────────────────────────────────────┤
│  • List all starred specialty upgrades                         │
│  • View GP Rx vs Specialist Rx side-by-side                    │
│  • PDF download per starred case                               │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TAB 4: OPD ROSTER (Patient List)                               │
├─────────────────────────────────────────────────────────────────┤
│  • Filter: Today / Yesterday / Last 5 Days / All Time          │
│  • Search bar                                                  │
│  • Patient cards: name, date, vitals, fee, medicines           │
│  • Actions: Follow-up, Reprint PDF, Old PDF download           │
│  • Revenue summary: total patients, total fees, average        │
│  • CSV export                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TAB 5: SETTINGS (Doctor/Clinic Configuration)                  │
├─────────────────────────────────────────────────────────────────┤
│  • Clinic Name, Address                                        │
│  • Doctor Name, Degree, Subtitle, Reg No                       │
│  • Doctor Email, Phone                                         │
│  • Extra Qualifications                                        │
│  • Save to: SQLite + Supabase + Session Cache                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ TAB 6: RESEARCH (Chief Only)                                   │
├─────────────────────────────────────────────────────────────────┤
│  • Analyze up to 150 patient records                           │
│  • Quick buttons: Disease Distribution, Top Medications,       │
│    Revenue Summary                                             │
│  • AI generates analytics with practice context                │
│  • PDF export                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Admin Portal (PIN: 1010)
```
┌─────────────────────────────────────────────────────────────────┐
│ ADMIN TABS                                                     │
├─────────────────────────────────────────────────────────────────┤
│ TAB 1: API & System                                            │
│  • Groq API Key management                                     │
│  • Supabase status + table setup SQL                           │
│  • System stats (total patients local + cloud)                 │
├─────────────────────────────────────────────────────────────────┤
│ TAB 2: Doctor Licenses                                         │
│  • Create license: ID, Name, Email, Phone, PIN, Clinic,        │
│    Specialty, Expiry Date                                      │
│  • List all licenses with active/expired status                │
│  • Delete license                                              │
├─────────────────────────────────────────────────────────────────┤
│ TAB 3: All Doctors Data                                        │
│  • View patient lists per doctor                               │
│  • Analytics per doctor                                        │
├─────────────────────────────────────────────────────────────────┤
│ TAB 4: Import Old Data                                         │
│  • Paste CSV/JSON text                                         │
│  • Flexible column mapping                                     │
│  • Import to any doctor                                        │
├─────────────────────────────────────────────────────────────────┤
│ TAB 5: Waiting Room                                            │
│  • In-memory queue (session_state)                             │
│  • Add patient + ticket number                                 │
│  • Mark as seen → remove                                       │
└─────────────────────────────────────────────────────────────────┘
```

### Lab Scanner Module (Separate)
```
• Upload 1-30 lab report images
• AI reads each via Groq Vision
• Structured output: test name, value, unit, reference, flag
• Clinical interpretation generation
• PDF download
• WhatsApp share
• Add to OPD notes
```

---

## 📊 Function Map (Master File → FastAPI Target)

### Database Functions (to recreate as SQLAlchemy models + repos)
```
Master File Function             →  FastAPI Target
──────────────────────────────────────────────────────────────────
init_db()                        →  SQLAlchemy Base.metadata.create_all
_supa_creds() / _supa_available() → src/infrastructure/backup/supabase_client.py
supa_insert / supa_select        →  same
db_save_patient()                →  src/application/opd/use_cases/save_patient_use_case.py
db_search_patients()             →  src/application/opd/use_cases/search_patient_use_case.py
db_get_patients_filter()         →  src/application/opd/use_cases/list_patients_use_case.py
_get_drug_suggestions()          →  src/application/opd/use_cases/drug_suggestions_use_case.py
_learn_drugs()                   →  src/application/opd/use_cases/learn_drugs_use_case.py
db_get_templates()               →  src/application/opd/use_cases/template_use_case.py
db_save_template()               →  same
db_delete_template()             →  same
check_pin()                      →  src/presentation/opd/routes/auth_routes.py
db_get_settings()                →  src/application/opd/use_cases/settings_use_case.py
db_save_settings()               →  same
db_save_upgrade()                →  src/application/opd/use_cases/specialty_upgrade_use_case.py
db_get_starred()                 →  same
db_save_scan()                   →  src/application/opd/use_cases/scan_use_case.py
db_get_pending_scans()           →  same
db_approve_scan()                →  same
```

### AI Functions (to copy as-is)
```
Master File Function             →  FastAPI Target
──────────────────────────────────────────────────────────────────
call_groq()                      →  src/ai_engine/groq_client.py (already copied)
call_whisper()                   →  src/ai_engine/groq_client.py (already has it)
call_groq_scan()                 →  src/ai_engine/groq_client.py (add vision)
_api_key()                       →  src/ai_engine/groq_client.py (add key resolution)
```

### PDF Functions (to copy as-is)
```
Master File Function             →  FastAPI Target
──────────────────────────────────────────────────────────────────
make_rx_pdf()                    →  src/utils/pdf_generator.py (rewrite for FastAPI)
make_cme_pdf()                   →  src/utils/pdf_generator.py
show_pdf()                       →  Return PDF as HTTP response
_s() (safe string)               →  src/utils/helpers.py
```

---

## 🚀 Migration Phases (GIL Clinic FastAPI)

### Phase 0: Memory + Reference ✅ (DONE)
```
✅ Master file documented and saved as memory
✅ Database schema documented
✅ All functions mapped
✅ Architecture documented
✅ This memory file created
```

### Phase 1: Database Models
```
Create SQLAlchemy models for ALL 7 tables:
  ├── PatientModel (extend existing — add opd fields or create OPD-specific)
  ├── DrugHistoryModel
  ├── SpecialtyUpgradeModel
  ├── TemplateModel
  ├── LicenseModel
  ├── SettingsModel (doctor-specific settings)
  └── PendingScanModel
```

### Phase 2: AI Engine
```
Already copied:
  ├── src/ai_engine/groq_client.py
  ├── src/ai_engine/prompts.py
  └── src/utils/helpers.py

Still needed:
  ├── Add call_groq_scan() vision function
  ├── Add API key resolution (env → session → db)
  └── Add specialty prompts
```

### Phase 3: Doctor Endpoints
```
Create:
  ├── POST /api/v1/opd/generate-prescription
  ├── POST /api/v1/opd/generate-pdf
  ├── POST /api/v1/opd/save-prescription
  ├── GET  /api/v1/opd/search-patients
  ├── GET  /api/v1/opd/drug-suggestions
  ├── GET  /api/v1/opd/templates
  ├── POST /api/v1/opd/templates
  ├── GET  /api/v1/opd/settings
  ├── POST /api/v1/opd/settings
  ├── POST /api/v1/opd/batch-scan
  ├── POST /api/v1/opd/specialty-upgrade
  └── POST /api/v1/opd/license/create
```

### Phase 4: Doctor Dashboard Template
```
Create Jinja2 templates:
  ├── templates/opd/doctor_dashboard.html
  ├── templates/opd/prescription_form.html
  ├── templates/opd/patient_search.html
  ├── templates/opd/settings.html
  ├── templates/opd/batch_scan.html
  └── templates/opd/admin_portal.html
```

### Phase 5: Backup Integration
```
Create:
  ├── src/infrastructure/backup/supabase_client.py
  ├── src/infrastructure/backup/sync_manager.py
  └── Sync hooks in save_patient, save_settings, etc.
```

---

## 🔐 PINs for Testing (Master File)

| Role   | PIN  | doctor_id       |
|--------|------|-----------------|
| Chief  | 5554 | clinic_default  |
| Junior | 1234 | clinic_default  |
| Admin  | 1010 | admin           |

---

## ⚠️ Critical Rules

1. **NEVER modify the master file** — sirf reference hai
2. **NEVER delete the master file** — wahi source of truth hai
3. **Har feature rebuild karo FastAPI/HTML mein** — copy-paste nahi
4. **AI Engine + PDF generator** direct copy ho sakte hain (no Streamlit dependency)
5. **Database schema ka exact match karo** — 7 tables jaise master file mein hain
6. **Supabase integration master file jaisa hi rakhna** — REST API via requests
7. **Data persistence 3-layer** rakhna: SQLite + Supabase + optional Sheet

---

> **Last Updated:** 2026-07-20
> **Reference Source:** Bharat AI Clinic Master File (paste-attachments)
> **Target System:** GIL Clinic FastAPI + HTML
> **Created by:** ZCode Agent
