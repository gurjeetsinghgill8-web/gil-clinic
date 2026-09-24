# 🏥 GHOS & GIL CLINIC — SYSTEM SPECIFICATION & FIR DISCLOSURE
## TECHNICAL ARCHITECTURE, ENGINE PIPELINES & FEATURE REGISTRY RECORD

---

### 🕒 TIMESTAMP & METADATA RECORD
- **Date:** 24 September 2026 (24-09-2026)
- **Time:** 17:35:00 IST (UTC +05:30)
- **Author & System Architect:** Dr. Gurjeet Singh Gill (Gurjas Singh Gill)
- **Registered Ownership Emails:** `gurjeetsinghgill8@gmail.com` | `mcgillpharma@gmail.com`
- **System Names:** GHOS (Gurjas Hospital Operating System) / GIL CLINIC Smart OPD / CardioQueue
- **Production URL:** `https://gillhopitalsoftware1.pythonanywhere.com`
- **Document Intent:** Comprehensive disclosure of technical inner workings, algorithmic pipelines, and the **FIR Protocol** for indisputable prior art and legal protection before source code evaluation by prospective technical partners.

---

## 1. EXECUTIVE OVERVIEW: THE PATIENT FLOW OPERATING SYSTEM

Traditional Hospital Management Systems (HMS) are glorified billing databases with clunky forms. **GHOS (Gurjas Hospital Operating System)** was conceptualized and built by Dr. Gurjeet Singh Gill to operate as a real-time **Patient Flow Operating System**.

### Core Value Propositions:
1. **"दवाखाने में कोई लाइन नहीं, सब कुछ mobile पर" (Zero-Queue Hospital):**
   - Patients arrive, scan a zero-app QR code at reception, and receive a secure tracker token.
   - Live queue status updates dynamically on the patient's phone.
   - When their turn arrives, staff trigger a browser-native acoustic chime and vibration alert directly in the patient's device browser without expensive third-party SMS or WhatsApp API aggregators.
2. **Local-First & Resilient:**
   - Designed to run seamlessly in low-connectivity hospital corridors, with zero dependence on costly external cloud runtimes.
3. **AI-Assisted Clinical Cockpit:**
   - Single-screen doctor cockpit with handwritten prescription OCR, dynamic drug database, and automated prescription generation.

---

## 2. THE FIR (FEATURE & ISSUE REGISTRY) SYSTEM EXPLAINED

The **FIR (Feature & Issue Registry)** is a proprietary clinical engineering methodology developed by Dr. Gurjeet Singh Gill. Instead of haphazard bug-fixing, every major challenge, architectural gap, or clinical workflow hurdle is logged as an **FIR** with:
- **Owner Statement:** The clinical doctor's direct problem statement.
- **Evidence & Code Lines:** Exact files and code locations responsible.
- **Root Cause Analysis (RCA):** Deep architectural explanation.
- **Strict One-by-One Engineering:** Sequential resolution, verification, and live deployment.

Below is the comprehensive technical breakdown of the 4 foundational FIR units:

---

### 🔴 FIR-01: CLINICAL HANDWRITTEN PRESCRIPTION & REPORT OCR ENGINE

#### A. Clinical Problem:
Doctors frequently write prescriptions by hand or receive complex external paper reports. The system required an automated mechanism where a doctor can take a photograph of a prescription from a smartphone or upload an image and have all patient details, symptoms, and medications automatically extracted into structured digital records. In early iterations, cloud endpoints failed on large mobile camera photographs.

#### B. The 4 Root Causes Uncovered & Solved:
1. **Data URL vs. File Object Serialization:** The browser AI gateway (`static/js/ai_gateway.js`) was improperly transforming raw base64 data into binary `File` objects when the downstream runtime required pure base64 Data URLs.
2. **Client-Side Image Compression Ceiling:** High-resolution modern mobile cameras produce images exceeding 10 MB - 15 MB. AI vision inference pipelines silently drop or fail on inputs above 10 MB. An in-browser Canvas-based compression algorithm was integrated (`maxDim=1600px`, `quality=0.85`), compressing 12MB photos down to ~400KB in under 200ms without loss of clinical legibility.
3. **Array-Form Markdown Content Parsing:** The AI vision runtime returns text across structured message content arrays. The parser was upgraded to iteratively concatenate and clean segmented tokens into cohesive markdown.
4. **Guest Account & Authentication Bypasses:** Automated fallback to temporary guest sessions was identified and replaced with verified authentication wrappers.

#### C. Request & Data Pipeline:
```
[Doctor Takes Photo]
         │
         ▼
[Browser Canvas Compression: max 1600px, 0.85 Quality] (< 500 KB)
         │
         ▼
[Browser AI Gateway: static/js/ai_gateway.js]
         │
         ├──► (Primary): Puter AI Browser-Native Vision Gateway
         │
         └──► (Fallback): FastAPI Backend (/opd/api/scan-ai) -> Groq Llama-3.2-11b-Vision
         │
         ▼
[Structured Extraction: Patient Name, Age, Symptoms, Medicines, Dosages]
         │
         ▼
[Auto-Population of OPD Cockpit & Prescription Rows]
```

---

### 🔴 FIR-02: SELF-LEARNING CLINICAL DRUG BANK & AUTO-POPULATION

#### A. Clinical Problem:
In standard clinical practice, a doctor cannot afford to manually type drug names, strengths, forms (Tablet/Syrup/Injection), dosage instructions, meal timings, and salt compositions repeatedly for hundreds of patients daily. Legacy systems lacked memory of how a doctor prescribes.

#### B. Technical Solution Implemented:
1. **Full-Spectrum Structured Medication Schema:**
   - `brand_name` (e.g., Augmentin)
   - `strength` (e.g., 625 mg)
   - `form` (Tablet, Syrup, Injection, Capsule, Drops, Ointment)
   - `default_dose` (e.g., 1 tablet, 5 ml)
   - `default_frequency` (1-0-1, 1-1-1, 0-0-1, SOS, BD, TDS)
   - `default_timing` (After food, Before food, At bedtime)
   - `salt_composition` (e.g., Amoxicillin + Potassium Clavulanate)
   - `use_count` (Dynamic integer tracking usage frequency)
2. **Dynamic Ranking by Frequency (`use_count DESC`):**
   - The most frequently prescribed medicines dynamically float to the top of auto-complete recommendations.
3. **Form-Prefix Normalization:**
   - Cleans input variants like "Tab. Paracetamol", "Tab Paracetamol", "Syp Paracetamol" into canonical entities while preserving proper form tags.
4. **Prescription-to-Library Auto-Seeding (`_learn_drugs`):**
   - When a consultation is completed, the system parses the structured prescription rows and automatically updates/creates entries in `opd_drug_history`, ensuring the drug bank continuously expands without manual administrative entry.

---

### 🟢 FIR-03: REMOTE PATIENT PORTAL & AT-HOME DIAGNOSTICS BLUEPRINT

#### A. Clinical Innovation:
A groundbreaking bidirectional patient engagement portal where patients are not just passive queue-viewers, but can remotely submit:
1. Prior medical history PDFs and external diagnostic lab scans.
2. Home-monitored vital signs (Blood Pressure: Systolic/Diastolic, Resting Heart Rate / Pulse, Blood Glucose).
3. Chief complaints before entering the consultation cabin.

#### B. System Status:
Blueprint finalized under `future_ideas/PATIENT_PORTAL_UPLOAD.md`. Preserved as proprietary trade-secret intellectual property slated for Phase 2 integration.

---

### 🟠 FIR-04: DUAL-CHANNEL POPULATION & BROWSER AUTHENTICATION GATEWAY

#### A. Technical Problem:
On mobile devices, progressive web apps (PWAs), and cross-origin iframe contexts, standard OAuth popups frequently fail, open blank screens, or detach from `window.opener`, leaving doctors stranded with an inoperable AI interface.

#### B. Architectural Solution:
1. Implemented **dual-channel authentication handling**:
   - Primary: Modal popup with explicit authentication handshake and strict timeout fallbacks.
   - Secondary: Full-tab redirect authentication with `localStorage` state reconciliation and automatic session restoration.
2. Strict rejection of unverified temporary guest accounts to protect clinical data integrity.

---

## 3. HARNESS ENGINEERING ARCHITECTURE

The GHOS architecture strictly enforces the **Harness Engineering Pattern**, preventing cross-layer coupling:

```
┌───────────────────────────────────────────────────────────────────┐
│                     1. UI PRESENTATION LAYER                       │
│    FastAPI Jinja2 Templates (HTML5 + CSS + PWA Vanilla JS)        │
│    No bloated heavy frameworks; fast, zero-dependency rendering   │
│    Routes: templates/opd/dashboard.html, patient-pwa/             │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ HTTP JSON API / Form Post
                                  ▼
┌───────────────────────────────────────────────────────────────────┐
│                     2. HARNESS LAYER (USE CASES)                  │
│    Command Orchestration, Permission Verification, Sanitization   │
│    Business Rules Execution, Audit Event Triggering               │
│    Routes: src/presentation/opd/routes/opd_routes.py              │
│    Harness: llm_harness.py, main_v2.py                            │
└──────────────────┬───────────────────────────────┬────────────────┘
                   │                               │
                   ▼                               ▼
┌───────────────────────────────────┐ ┌─────────────────────────────┐
│       3. DOMAIN CORE ENTITIES     │ │ 4. INFRASTRUCTURE & STORAGE │
│  Patient, Queue, Prescription,    │ │  SQLite (Local dev/offline) │
│  Drug, Clinical Consultation      │ │  PostgreSQL / Supabase      │
│  src/domain/                      │ │  PythonAnywhere ASGI / File │
└───────────────────────────────────┘ └─────────────────────────────┘
```

---

## 4. ZERO-COST REAL-TIME PATIENT QUEUE ENGINE

1. **Reception Entry:** Receptionist registers patient in `CardioQueue` via rapid form.
2. **Access Token Generation:** A unique URL slug (`/my/<token>`) is generated.
3. **QR Code Display:** A dynamic QR code is rendered on screen or printed on a receipt slip.
4. **Live Polling & Event Listeners:**
   - Patient opens URL on mobile browser (no app download required).
   - Phone screen displays real-time estimated wait time, queue index, and doctor consultation state.
5. **Staff Acoustic Buzzer:**
   - When doctor is ready, staff clicks "Call / Remind".
   - Patient's browser catches the state transition via lightweight fetch polling and activates the Web Audio API synthesizer (audible alert) and the Web Vibration API (`navigator.vibrate([200, 100, 200])`).
   - Cost: **₹0.00** (Zero SMS or WhatsApp gateway charges).

---

## 5. LIVE PRODUCTION DEPLOYMENT TOPOLOGY

- **Production Server:** PythonAnywhere ASGI Production Cluster
- **Base Domain:** `https://gillhopitalsoftware1.pythonanywhere.com`
- **Deployment Engine:** `pa_deploy.py` (Custom idempotent automated deployment pipeline with git hash tagging, automatic table migration, and rollback protection).
- **Core Endpoints:**
  - `/opd/dashboard` — Doctor & Staff Consultation Cockpit.
  - `/api/drugs` — Dynamic medication search and auto-complete API.
  - `/api/drugs/backfill` — Idempotent drug bank seeding and normalization.
  - `/opd/api/scan-ai` — AI Vision transcription gateway.
  - `/my/<token>` — Mobile patient queue status portal.
  - `/s/<token>` — Secure read-only doctor consultation sharing token.

---

## 6. PROPRIETARY VALUE & PRIOR ART DISCLOSURE

The architectural combination of:
- Zero-cost acoustic web-polling patient queue management,
- Client-side image-compressed handwriting OCR vision routing,
- Self-learning clinical drug database with frequency ranking and form normalization, and
- The decoupled Harness Engineering FastAPI pattern,

represents proprietary trade secrets and original intellectual property developed exclusively by **Dr. Gurjeet Singh Gill**. Any unauthorized use, reproduction, translation, derivation, or implementation by third parties without formal written license is strictly prohibited by law.

---

**Certified & Recorded on this 24th Day of September, 2026:**

**Dr. Gurjeet Singh Gill (Gurjas Singh Gill)**  
*Sole Author, Creator & System Architect*  
*Registered Contact:* `gurjeetsinghgill8@gmail.com` | `mcgillpharma@gmail.com`
