# 🏥 GHOS (Gurjas Hospital Operating System) / GIL CLINIC
## Technical Architecture & Code Inspection Guide for Anuj K Jain Ji

---

**Dear Anuj Ji,**

Welcome to the **GHOS (Gurjas Hospital Operating System)** codebase. Dr. Gurjeet Singh Gill has prepared this complete inspection package for you to review the architecture, technical pipelines, and system capabilities as we evaluate our 3-person partnership and private limited company incorporation.

The system is already **operational and deployed live in production**:
🔗 **Live Production URL:** `https://gillhopitalsoftware1.pythonanywhere.com`
- **Chief Doctor Portal:** PIN `5554`
- **Admin Portal:** PIN `1010`

---

## 🏗️ 1. Technical Stack Overview

| Component | Technology | Rationale |
|---|---|---|
| **Backend Core** | Python 3.12 + **FastAPI** | High-concurrency async ASGI engine with native OpenAPI documentation |
| **Architecture** | **Harness Engineering (Clean DDD)** | Strict layer decoupling: UI ➔ Use-Case Harness ➔ Domain Core ➔ DB/Infra |
| **Presentation / UI** | Jinja2 + HTML5 + CSS3 + **Vanilla JS PWA** | Zero heavy frontend frameworks (no React/Node overhead on clinic hardware), fast rendering, mobile responsive |
| **Databases** | SQLite (Local/Dev) + PostgreSQL / Supabase | Local-first resilience with cloud sync capabilities |
| **AI Vision & OCR** | Groq Llama-3.2-11b-Vision + Puter AI | Clinical prescription OCR and lab report data extraction |
| **Deployment** | PythonAnywhere ASGI Cluster + Cloudflare Tunnel | High reliability, 24/7 uptime, automated deployment pipeline (`pa_deploy.py`) |

---

## 🌟 2. Key Architectural Innovations to Inspect

### A. Zero-Cost Patient Flow OS (`CardioQueue`)
- **Problem Solved:** Traditional hospital systems rely on expensive third-party SMS or WhatsApp business API gateways (costing ₹0.30 - ₹0.80 per notification) to call patients from waiting rooms.
- **Our Solution:** 
  1. Patient scans a QR code at reception or accesses their unique tracker token (`/my/<token>`).
  2. Patient's mobile browser runs a lightweight background polling worker.
  3. When the doctor/staff clicks "Call / Remind", the patient's device browser activates the **HTML5 Web Audio synthesizer** (acoustic chime) and **Web Vibration API** (`navigator.vibrate([200, 100, 200])`).
  4. Operational Cost: **₹0.00**.

### B. The FIR (Feature & Issue Registry) Protocol
We follow a disciplined engineering protocol where clinical pain-points are logged as FIRs with owner statement, root-cause analysis, and single-brick verification:
- **FIR-01 (`FIR_PRODUCT_DEVELOPMENT.md`):** Clinical Handwriting OCR pipeline. Features client-side Canvas compression (`maxDim=1600px`, `quality=0.85`) to downsize 12MB smartphone photos to ~400KB in under 200ms before vision model inference.
- **FIR-02:** Self-learning Drug Bank. Dynamic schema (`brand_name`, `strength`, `form`, `default_dose`, `frequency`, `timing`, `salt_composition`, `use_count`). System dynamically floats most-prescribed medicines to the top of auto-complete and auto-learns new medications from completed prescriptions.
- **FIR-03:** Remote Patient Diagnostics Blueprint (`future_ideas/PATIENT_PORTAL_UPLOAD.md`) for patient-side BP, Pulse, and lab report ingestion.
- **FIR-04:** Dual-channel mobile authentication gateway.

### C. The Harness Engineering Pattern
To prevent spaghetti code in complex medical workflows, UI routes NEVER touch database entities directly:
```
[User Interface (PWA)]
         │ HTTP Request / Form Data
         ▼
[Harness Layer (llm_harness.py / opd_routes.py)]
  - Command validation
  - Role & Permission verification (Chief/Junior/Admin)
  - Business rules enforcement
         │
         ├──► [Domain Entities] (Patient, Queue, Prescription, Drug)
         │
         └──► [Infrastructure / Repositories] (SQLite, Supabase, File Storage)
```

---

## 📂 3. Codebase File & Folder Map

```
GIL CLINIC / GHOS
│
├── main_v2.py                 # FastAPI Application Gateway & Server Entrypoint
├── pa_deploy.py               # Automated Production Deployment Pipeline
├── requirements.txt           # Python Dependencies
├── llm_harness.py             # Core Orchestration Harness & AI Routing
│
├── src/                       # Clean Architecture Core
│   ├── ai_engine/             # Vision & LLM Providers (Groq, Puter, Gemini)
│   ├── domain/                # Medical & Patient Flow Domain Entities
│   ├── infrastructure/        # DB Models, Repositories, Schemas
│   └── presentation/          # FastAPI Route Handlers (OPD, Admin, Queue)
│       └── opd/routes/        # OPD Cockpit & Drug Bank Endpoints
│
├── templates/                 # Jinja2 Templates (Doctor Cockpit, Admin, Queue)
│   └── opd/dashboard.html     # Doctor Single-Screen Clinical Cockpit
│
├── static/                    # CSS, Icons, Audio Chimes & Frontend Logic
│   └── js/ai_gateway.js       # Client-side AI Vision & OCR Gateway
│
├── patient-pwa/               # Zero-app Patient Tracking Progressive Web App
│   ├── index.html             # Patient Queue Tracking UI
│   └── app.js                 # Real-time polling & audio-vibrate listeners
│
└── configs/                   # System & Environment Configurations
```

---

## 🚀 4. How to Run Locally for Inspection

### Prerequisites:
- Python 3.10+ installed.

### Steps:
1. Open terminal inside the unzipped folder:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the local FastAPI server:
   ```bash
   python main_v2.py
   ```
3. Open your browser and navigate to:
   - **Doctor Cockpit:** `http://localhost:8000/opd/dashboard` (PIN: `5554`)
   - **API Documentation:** `http://localhost:8000/docs` (Swagger UI)

---

## 🤝 5. Partnership & Co-Founding Discussion Points

Anuj Ji, Dr. Gill is eager to discuss the following with you:
1. **Infrastructure Scaling:** Transitioning the dev SQLite database to a distributed multi-tenant PostgreSQL/Supabase setup for hospital chains.
2. **Security & HIPAA/DISHA Compliance:** Hardening doctor PIN authentication and implementing role-based JWT sessions.
3. **Corporate Roadmap:** Setting up the legal entity (Private Limited Company), equity structure, and go-to-market plan for private clinics and cardiology hospitals.

*Prepared with respect for technical review by Dr. Gurjeet Singh Gill.*
