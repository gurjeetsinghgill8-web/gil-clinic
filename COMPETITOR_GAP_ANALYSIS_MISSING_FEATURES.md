# 🕳️ Competitor Gap Analysis — Missing Features Register (GIL CLINIC / GHOS)

> **Owner:** Gurjas Singh Gill
> **Date:** 30 Sep 2026
> **Purpose:** Competitors (EKA DOC, Tatvacare, VCDoctor) ki marketing se collect kiya gaya **poora feature set** — ab ek-ek karke compare kar ke **humare product mein kya MISSING hai** uski numbered list. **Har item alag FIR jaise tick hota jaayega (Pending → In Progress → Done).**
> **Rule (owner ka nirdesh):** Abhi **sirf list + implementation plan** banana hai. **Code tabhi** jab owner bole.

---

## 📅 Update Log

| Date | What shipped |
|------|--------------|
| **30 Sep 2026** | ✅ **GAP-01 → GAP-05 scaffold built** — `src/infrastructure/abdm/` (models: `abha_links`, `consent_artefacts`, `abdm_transactions`) + `src/presentation/abdm/routes/abdm_routes.py` (status, ABHA link, FHIR Patient/Practitioner, consent create/list/revoke, DHIS transaction log) + `clinic.hpr_id`/`hfr_id` + `/abdm` status page. **Real NHA sandbox connect ke liye sirf `ABDM_*` credentials baaki hain.** |
| **30 Sep 2026** | ✅ Find a Doctor marketplace (live queue + booking + geolocation) + Universal Health Card `/card/{uid}` + doctor dashboard "🪪 Health Card" button. |
| **30 Sep 2026** | ✅ **GAP-06 Smart Rx Pad** — `src/presentation/rx_pad/` + `templates/rx_pad.html`: clinic letterhead (name/degree/reg no/address) par print-ready prescription pad, WhatsApp share + print. Dashboard "📝 Letterhead Rx" button. **GAP-08 video consult** — free Jitsi meet room ("📹 Video" button). **GAP-07 note:** voice→text scribe pehle se maujood hai (🎙️ Record → `/opd/api/transcribe`). |
| **30 Sep 2026** | ✅ **GAP-09 External Lab Network** — `src/infrastructure/lab/` (lab_orders) + `src/presentation/lab_network/`: order → send-to-lab (stub) → result submit → patient phone result view `/lab/{token}`. Dashboard "🧪 Lab Order" button + modal. |
| **30 Sep 2026** | ✅ **Admin onboarding form wired** — `templates/admin/onboard_doctor.html` + `doctor_routes.py` ab `latitude`, `longitude` (📍 Use my location button), `hpr_id`, `hfr_id` capture karta hai. Ab Find-a-Doctor distance sorting aur ABDM registry IDs UI se populate hote hain. |

---

## 📚 Source Competitors (researched)

| Competitor | Product type | Their highlighted features |
|-----------|--------------|---------------------------|
| **EKA DOC (eka.care)** | ABDM-compliant HMIS + EMR/EHR | Google Partner · Digital Mission · ABDM Compliant · AWS Secured · FHIR Compliant · NHA Approved · 360° Practice Management · smart digital Rx · customized prescription pad · EkaScribe (AI) |
| **Tatvacare (tatvacare.in)** | Clinic practice + teleconsult + lab | Digitise Rx (30 sec) · Clinic Mgmt (online + walk-in queue) · Analytics · Tele-consultation · Lab integrations (order + results on phone) · Patient engagement (digital Rx + follow-up) · **Earn via DHIS scheme** · PubMed journals · ABHA patient IDs |
| **VCDoctor** | Telemedicine + full HMIS | Complete HMIS with **ABDM integration** · OPD & IPD · Billing & Pharmacy · EMR/EHR · Lab & Diagnostics · Telemedicine |

---

## 📋 MASTER REGISTER (number-wise, tick one-by-one)

> **Status legend:** ⬜ Pending · 🔨 In Progress · ✅ Done · 🏷️ Partial (exists but not at competitor level)

---

### 🔴 BLOCK 1 — ABDM / National Compliance (sabse bada moat, sabhi competitors ke paas hai)

| # | Feature | Source | What it is (researched) | GHOS status | Priority |
|---|---------|--------|--------------------------|-------------|----------|
| **GAP-01** | **ABDM core compliance** (ABHA + HPR + HFR + HIP/HIU + Consent Manager) | EKA DOC, VCDoctor, Tatvacare | Ayushman Bharat Digital Mission (NHA) ke building blocks par register hona. ABHA = patient ka 14-digit unique health ID; HPR = doctor registry; HFR = facility registry; HIP/HIU = data provider/user roles; Consent Manager = patient data-share consent | ⬜ Missing (humara apna schema hai, ABDM registry se linked nahi) | 🟢 P0 |
| **GAP-02** | **FHIR compliance (R4)** | EKA DOC | ABDM ka data-exchange standard HL7 FHIR R4 — resources (Patient, Practitioner, DiagnosticReport, MedicationRequest) use karke interoperable records | ⬜ Missing (humare models SQLAlchemy hai, FHIR resource mapping nahi) | 🟢 P0 |
| **GAP-03** | **NHA approval / Milestone certification** | EKA DOC, VCDoctor | National Health Authority ka official "ABDM Milestone" certificate — marketing trust + govt tender eligibility | ⬜ Missing | 🟢 P0 |
| **GAP-04** | **ABHA ID create + link (Health Locker / PHR)** | Tatvacare, EKA DOC | Patient ke ABHA number se uske records ABDM Health Locker / PHR me push — "paperless OPD" | ⬜ Missing | 🟢 P0 |
| **GAP-05** | **DHIS — Earn via Govt Scheme** | Tatvacare | Digital Health Incentive Scheme: NHA ABDM adoption ke har transaction (ABHA create, record link, token) par facility ko **reimbursement/incentive** deta hai — extra income for clinics | ⬜ Missing (yeh revenue + compliance dono angle hai) | 🟢 P0 |

---

### 🟠 BLOCK 2 — Clinical & Practice (competitor parity)

| # | Feature | Source | What it is | GHOS status | Priority |
|---|---------|--------|-----------|-------------|----------|
| **GAP-06** | **Smart digital prescription pad (customized per doctor)** | EKA DOC, Tatvacare | Har doctor ka apna **letterhead/pad** (name, reg no, degree, clinic logo) par smart Rx; write + share in 30 sec | 🏷️ Partial (drug bank + Rx hai, lekin **customized printable prescription pad** nahi) | 🟠 P1 |
| **GAP-07** | **AI Medical Scribe (voice → note)** | EKA DOC (EkaScribe) | Doctor-patient baat sun kar real-time clinical note + Rx draft banaana | 🏷️ Partial (0505 AI Rx assistant blueprint; live voice-scribe nahi) | 🟠 P1 |
| **GAP-08** | **Tele-consultation (video call)** | Tatvacare, VCDoctor | Doctor-patient live video consult + e-Rx + follow-up | 🏷️ Partial (0705 blueprint only, build nahi hua) | 🟠 P1 |
| **GAP-09** | **Lab integrations (external lab network)** | Tatvacare, VCDoctor | Platform se hi lab test **order karo** (partner labs ko), result **phone par aaye** — internal lab ke alawa | 🏷️ Partial (internal Lab module hai, external lab network nahi) | 🟠 P1 |
| **GAP-10** | **Patient engagement: digital Rx delivery + auto follow-up** | Tatvacare | Digital prescription seedha patient ko + automated follow-up reminders (adherence) | 🏷️ Partial (WhatsApp + followup engine hai) | 🟠 P1 |
| **GAP-11** | **Full EMR/EHR (FHIR-native, longitudinal)** | EKA DOC, VCDoctor | Complete electronic health record — encounters, problems, meds, allergies, labs ek interoperable chart me | 🏷️ Partial (Patient Timeline hai, FHIR-native nahi) | 🟡 P2 |
| **GAP-12** | **IPD (Inpatient) Management** | VCDoctor | Bed management, admission/discharge, nursing, inpatient records | 🏷️ Partial (0301 blueprint; roadmap P5) | 🟡 P2 |

---

### 🟡 BLOCK 3 — Growth, Education & Trust

| # | Feature | Source | What it is | GHOS status | Priority |
|---|---------|--------|-----------|-------------|----------|
| **GAP-13** | **Practice analytics dashboard** | Tatvacare, VCDoctor | Doctor/practice-level analytics — patient flow, revenue, productivity trends | 🏷️ Partial (0109 analytics engine hai) | 🟡 P2 |
| **GAP-14** | **PubMed / medical journals access (CME)** | Tatvacare | Doctor ko premium journal/PubMed access — stickiness + value | ⬜ Missing | 🟡 P2 |
| **GAP-15** | **Trust/security posture (AWS secured, Google Partner, ISO 27001)** | EKA DOC | Infra/security certifications + partner badges — enterprise trust | 🏷️ Partial (Phase 8 security hai, ISO cert nahi) | 🟡 P2 |

---

## 🧭 Implementation Sequence (kaise ek-ek karke karenge)

> Owner ka order: **compliance pehle** (kyunki wahi moat + govt incentive hai), phir clinical parity, phir growth.

```
Phase A (compliance):   GAP-01 → GAP-02 → GAP-03 → GAP-04 → GAP-05
Phase B (clinical):     GAP-06 → GAP-07 → GAP-08 → GAP-09 → GAP-10
Phase C (records):      GAP-11 → GAP-12
Phase D (growth):       GAP-13 → GAP-14 → GAP-15
```

### Per-item plan (har GAP ka "kaise karenge")

| # | Implementation approach (high level) | Effort | Dependencies |
|---|--------------------------------------|--------|--------------|
| GAP-01 | ABDM Sandbox me register → HFR (clinic) + HPR (doctor) APIs → ABHA create/link SDK → HIP/HIU role → Consent Manager artefact. Ek naya `abdm` engine/service banayenge | XL | GAP-02 |
| GAP-02 | Ek **FHIR mapping layer** (SQLAlchemy model ↔ FHIR R4 resource) — `fhir` service. Pehle Patient + Practitioner + DiagnosticReport | L | — |
| GAP-03 | NHA Milestone checklist complete karke certification apply | M | GAP-01, GAP-02 |
| GAP-04 | ABHA number ko `patients` table me add → records ko ABDM Health Locker/PHR me sync | M | GAP-01 |
| GAP-05 | DHIS transaction logging (ABHA create, link, token) → NHA se incentive claim pipeline | M | GAP-01 |
| GAP-06 | Printable Rx template engine — doctor letterhead (name/reg/logo), Hindi+EN, PDF + WhatsApp share | M | — |
| GAP-07 | ASR (speech-to-text) + LLM note gen → 3-line brief + Rx draft (doctor-in-the-loop) | L | AI infra |
| GAP-08 | WebRTC/video (existing 0705 spec) → e-Rx + recording | L | — |
| GAP-09 | External lab partner API → order + result webhook → phone delivery | M | — |
| GAP-10 | Digital Rx deep-link + follow-up cadence (existing engine) polish | S | — |
| GAP-11 | FHIR-native longitudinal EMR on top of Patient Timeline | XL | GAP-02 |
| GAP-12 | Bed/admission/discharge workflows (0301 spec) | XL | — |
| GAP-13 | Analytics dashboards surface karna (0109) | M | — |
| GAP-14 | PubMed/PMC API embed + journal search | S | — |
| GAP-15 | Cloud hardening + ISO 27001 readiness + partner badges | M | — |

---

## 📊 One-line summary (owner ke liye)

> **Sabse bada missing = ABDM/FHIR/NHA compliance (GAP-01..05)** — yehi EKA DOC, Tatvacare, VCDoctor teeno ka headline hai, aur DHIS ke through **government paisa** bhi deta hai. Baaki sab mostly humare paas **partial** hai — bas competitor-level polish chahiye. **Abhi koi code nahi; list ready hai, aap bolo to GAP-01 se shuru karte hain.**
