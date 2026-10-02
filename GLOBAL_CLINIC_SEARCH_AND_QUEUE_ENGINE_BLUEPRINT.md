# 🌐 GLOBAL CLINIC SEARCH & QUEUE ENGINE — Master Architecture Blueprint

> **Owner:** Gurjas Singh Gill (Dr. G. S. Gill)
> **Product:** GHOS — GIL CLINIC (`gillhopitalsoftware1.pythonanywhere.com`)
> **Version:** 1.0 · **Date:** 02 Oct 2026
> **One-liner:** *"Practo ek directory dikhata hai. GHOS ek ZINDA queue dikhata hai."*
> **Mantra:** 🟢 **Live queue > khaali appointment slot.**

> **Ye file kya hai:** poore "Global Clinic Search + Queue Engine" module ka **master architecture blueprint**.
> Do hisse hain — **Part A: Global Clinic Search** (patient doctor dhoondhta hai) aur
> **Part B: Queue Engine** (doctor patient bulata hai). Dono ko **Part C** jodta hai (booking bridge).
>
> **Har section me saaf likha hai:** ✅ kya ban chuka · 📐 kya banana hai · 📁 kis file me.

---

## 0. TL;DR — 30 second me poora module

```
Patient phone par search karta hai  →  zinda queue dikhti hai  →  1 tap booking  →  token  →
"3 patient bache, ab niklo"  →  doctor ke screen par live  →  consult  →  Health Card share  →  naya patient
```

| # | Layer | Kaam | Status |
|---|-------|------|--------|
| 1 | **Global Search** | City + specialty + "seene me dard" (plain Hindi) se doctor dhoondho | ✅ **LIVE** |
| 2 | **Two-tier ranking** | Partner clinic (live queue) upar · baaki directory niche | ✅ **LIVE** |
| 3 | **Live Queue Engine** | Asli `queue_entries` se token, patients-ahead, serving token | ✅ **LIVE** |
| 4 | **1-tap Booking** | Search se seedha asli OPD token + tracking link | ✅ **LIVE** |
| 5 | **EWT Engine** | Complexity-weighted wait time (6/15 min, delay-aware) | 📐 **BANANA HAI** |
| 6 | **Availability + Geofence** | Open/close time, "open now", distance sort, leave-now alert | 🏷️ **PARTIAL** |
| 7 | **Slot Booking** | `appointment_slots` + Doctor Live View slot grid | 📐 **BANANA HAI** |
| 8 | **ABDM/FHIR** | ABHA + HPR/HFR + FHIR R4 + DHIS incentive | 🏷️ **SCAFFOLD READY** |

---

## 1. Vision — yeh module kyun hai

Do bilkul alag dard, ek hi engine se theek hote hain:

**Patient ka dard** — *"4 baje ka appointment liya, 5:30 par bhi waiting room me hoon."*
Appointment slot **jhooth** hai, kyunki wo maanta hai ki har patient 20 min lega.
Naya case 20 min, follow-up 6 min — slot system ise ignore karta hai.

**Doctor ka dard** — *"Queue bahar chalti hai, andar ka pata nahi."* No-show, bheed, chaos.

**GHOS ka jawaab:** time **book** mat karo — **queue dikhao**.

```
"Dr. G.S. Gill IN CHAMBER hai (Room 2).
 Token #14 andar hai. Aapse 3 patient aage hain.
 Aapka wait: ~18 minute."
```

Aur jab 3 patient bachein: 📲 *"Ab niklo — 15 min ka rasta, zero wait."*

> **Yeh booking app nahi hai. Yeh OPD ka live marketplace hai — "Uber/Ola of OPD".**

---

## 2. System Map — poora module ek nazar me

```
┌──────────────────────────── PATIENT SIDE ────────────────────────────┐
│  WhatsApp link ─┐                                                     │
│  QR code ───────┼──►  /find-doctor   (templates/marketplace.html)      │
│  Google search ─┘            │                                        │
│                              ▼                                        │
│                   GET /api/v1/marketplace/meta      ← city + specialty│
│                   GET /api/v1/marketplace/doctors   ← directory+live  │
│                              │                                        │
│                              ▼                                        │
│            ┌──────────── TIER 1: PARTNER CLINIC ────────────┐          │
│            │ 🟢 LIVE QUEUE ACTIVE · token #14 · 3 ahead      │          │
│            └────────────────────────────────────────────────┘          │
│            ┌──────────── TIER 2: DIRECTORY ONLY ────────────┐          │
│            │ ☎️ Call clinic · 📍 Directions · 📢 Invite       │          │
│            └────────────────────────────────────────────────┘          │
│                              │                                        │
│                    POST /api/v1/marketplace/book                       │
│                              ▼                                        │
│              Token #17 + /track/<token>  (PWA, no install)             │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────── QUEUE ENGINE ──────────────────┐
│  queue_entries  (per-clinic, service_code='OPD')                       │
│  WAITING → CALLED → IN_CONSULT → COMPLETED → DELIVERED                 │
│  priority score = token_number − (priority × 1000)   ← senior/emergency│
│  delay engine: elapsed − avg_service_time  → warning 5min / crit 10min │
│  EWT: complexity_weight × avg_service_time + live delay                │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────── DOCTOR SIDE ───────────────────┐
│  /opd/dashboard   Live queue · Call next · ECG dispatch · Rx          │
│  📱 Patient link  · 🩺 Patient Monitor · 🪪 Health Card · 📝 Rx Pad    │
│  🧪 Lab Order  · 📹 Jitsi video  · 🏥 ABDM status                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
                    /card/<uid>  (Universal Health Card)
                               ▼
                 Share → naya patient → wapas Search par 🔁 (flywheel)
```

---

# PART A — GLOBAL CLINIC SEARCH

> **Kaam:** patient ko *apne shehar ka sahi doctor* dikhana — aur yeh bhi batana ki **abhi kitni der lagegi**.

## A1. Jo ban chuka hai (✅ LIVE)

| Cheez | File | Detail |
|-------|------|--------|
| Marketplace page | `templates/marketplace.html` (22 KB) | Mobile-first, city/specialty/problem filter |
| Page route | `src/presentation/marketplace/routes/marketplace_routes.py` | `GET /find-doctor`, `GET /doctors` (alias) |
| Meta API | same file | `GET /api/v1/marketplace/meta` → distinct cities + specialties |
| Search API | same file | `GET /api/v1/marketplace/doctors?city=&specialty=&problem=&lat=&lon=` |
| Booking API | same file | `POST /api/v1/marketplace/book` → asli token + tracking link |
| Demo seed | same file | `POST /api/v1/marketplace/seed?token=GIL-DEMO-SEED-2026` (8 demo clinics, idempotent) |
| Router wiring | `main_v2.py` line 532 | `app.include_router(marketplace_router)` |
| Landing entry | `templates/landing.html` | Public landing page → "Find a Doctor" button |

## A2. Plain-language problem → specialty (real code)

`PROBLEM_TO_SPECIALTY` dict (marketplace_routes.py, line 46) — patient **Hindi** me likhta hai, hum specialty nikalte hain:

```
"seene me dard" / "dil" / "bp" / "ghabrahat"  → Cardiology
"bukhar" / "khansi" / "sugar" / "sir dard"    → General Physician
"ghutna" / "kamardard" / "haddi"              → Orthopedics
"bachcha" / "baby"                            → Pediatrics
"daant" / "kaan" / "aankh" / "twacha"         → Dental / ENT / Ophthalmology / Dermatology
"pet" / "gas" / "acidity"                     → Gastroenterology
```

> **Rule:** naya keyword add karna ho to **sirf yahi dict** chhedni hai — UI aur API dono apne aap sync rehte hain.

## A3. Ranking algorithm (business moat)

```
STEP 1  FILTER : city (lower=) + specialty (lower=) + problem→specialty map
STEP 2  RANK   : is_license_active DESC  (partner pehle)  →  doctor_name ASC
STEP 3  LIVE   : partner ke liye _queue_map() se REAL numbers
                 serving_token · patients_ahead · wait_minutes · chamber
STEP 4  DISTANCE: lat/lon diya to haversine (km, 1 decimal)
```

| Tier | Kaun | Cost | Revenue lever |
|------|------|------|---------------|
| **Tier 1** | Paying GHOS clinics (active license) | ~₹0 — data queue engine me pehle se hai | Renewal + upgrade |
| **Tier 2** | Non-network doctors (public info) | ~₹0 | **Growth loop** — patient demand unhe SaaS khareedne par majboor karti hai |

> 🔁 **Flywheel:** free listing → demand data → listing paying partner banti hai → zyada live data → zyada patient.

## A4. Live queue signal — asli hai, demo nahi

```python
# marketplace_routes.py → _queue_map()
SELECT clinic_id, COUNT(id), MAX(token_number)
FROM queue_entries
WHERE clinic_id IN (...) AND completed_at IS NULL AND delivered_at IS NULL
  AND service_code = 'OPD'
GROUP BY clinic_id
```

- `patients_ahead` = is clinic ke **asli** active OPD entries
- `serving_token` = sabse ooncha active token (jo abhi andar hai)
- ⚠️ **Purana `_live_signal()` demo (stable hash) hata diya gaya hai** — ab koi fake number nahi.
- ⚠️ `MINUTES_PER_PATIENT = 7` **hardcoded** hai → yahi **Part B ka EWT Engine** replace karega.

## A5. 📐 Jo Part A me banana hai

| # | Kaam | Kahan | Kaise |
|---|------|-------|-------|
| A-1 | **Availability (Open Now)** | `ClinicModel` + `marketplace_routes.py` | `open_time`/`close_time` columns + `availability` ko `OPEN`/`CLOSED`/`DIRECTORY` banao + "🟢 Abhi khula" filter |
| A-2 | **Rating** | `ClinicModel.rating` | Patient feedback se average (0109 analytics) — ranking me tie-breaker |
| A-3 | **Department search** | meta API | City + specialty ke saath "Cardiology / ECG / Echo / Lab" facility filter |
| A-4 | **City landing pages** | naya route `/doctors/<city>` | SEO — "Jodhpur me heart doctor" Google se traffic (static, cacheable) |
| A-5 | **Tier-2 Growth Loop** | naya button + table | "📢 Is doctor ko GHOS Live Queue me invite karo" → `clinic_leads` table → Admin pipeline |
| A-6 | **Departure Alert** | naya — EWT ke saath | 3 patient bache → WhatsApp deep link: "15 min drive, ab niklo" |

---

# PART B — QUEUE ENGINE

> **Kaam:** ek token ka poora jeevan — banna, chalna, bulaya jaana, khatam hona — aur uska **sahi wait time**.

## B1. Token lifecycle (state machine) — jo live hai

```
                    POST /api/v1/marketplace/book   (patient)
                    POST /api/register              (reception)
                              │
                              ▼
                        ┌──────────┐
                        │ WAITING  │◄──────── HOLD ────────┐
                        └────┬─────┘                       │
                   called_at │  ← "▶ CALL NEXT"            │
                             ▼                             │
                        ┌──────────┐                       │
                        │  CALLED  │───────────────────────┘
                        └────┬─────┘
                   started_at│  ← doctor ne andar bulaya
                             ▼
                      ┌─────────────┐
                      │ IN_CONSULT  │──► SENT_TO_DEPT (ECG/Echo/TMT/Lab)
                      └──────┬──────┘         │
                 completed_at│                │ report_ready_at
                             ▼                ▼
                       ┌───────────┐    ┌──────────────┐
                       │ COMPLETED │    │ REPORT_READY │
                       └─────┬─────┘    └──────┬───────┘
                    delivered_at│             │
                                ▼             ▼
                          ┌──────────────────────┐
                          │      DELIVERED       │  ← queue se bahar
                          └──────────────────────┘
```

**Asli columns jo pehle se maujood hain** (`queue_entries`) — yeh sab **timestamped** hain, isliye EWT
aur analytics **koi naya data** maange bina ban sakta hai:

`called_at` · `started_at` · `completed_at` · `report_ready_at` · `delivered_at` · `priority` · `display_order` · `status`

> ✅ Iska matlab: **service time ka asli data hum already collect kar rahe hain** — bas use padhna baaki hai.

## B2. Priority Engine (Code Red / Senior / Emergency)

Do jagah maujood hai:

**(a) Live app** — `queue_entries.priority` (int) + `display_order`

**(b) Blueprint microservice** — `ghos/services/queue-engine/app/engine/priority.py`:

```python
score = token_number − (priority × 1000)      # chhota score = pehle
# 0 Normal · 1 Senior (60+) · 2 Emergency · 3 VIP   ·  Staff family = −100 offset
```

Fayda: `#14` (normal) se `#E-2` (emergency) **aage** nikal jata hai — badalna sirf ek number hai.

| Level | Score | Kab |
|-------|-------|-----|
| 0 Normal | token | Aam patient |
| 1 Senior | token − 1000 | 60+ |
| 2 Emergency | token − 2000 | Chest pain / SpO₂ < 90% → **Code Red** (`#E-1`) + siren |
| 3 VIP | token − 3000 | Owner/trustee referral |

## B3. Delay Detection (live hai blueprint me)

`ghos/services/queue-engine/app/engine/delay.py`:

```
delay = (abhi ka samay − called_at) − avg_service_time

  < 0        → koi delay nahi
  ≥ 5 min    → 🟡 warning
  ≥ 10 min   → 🔴 critical  (staff screens par alert)
```

> Live app me abhi **delay alert wire nahi hua** — yeh Part C ka kaam hai.

## B4. 📐 EWT Engine — "Uber ETA for OPD" (BANANA HAI)

**Problem:** `wait_minutes = patients_ahead × 7` — har patient ko 7 min maan leta hai. **Galat.**
Naya case 20 min leta hai, follow-up 6 min.

### B4.1 Formula (banane wala)

```
AVG = EWMA(completed_at − started_at)            ← is doctor ka ASLI average (rolling)
      (kam se kam 20 samples, warna default 7 min)

EWT(mere liye) =
      Σ  ( complexity_weight_i × AVG × 1.0 )      ← mere aage ke har patient ka
   +  DELAY_PENALTY                               ← agar current patient AVG se zyada le raha hai
                                                  (max +15 min cap)
   −  ELAPSED_SINCE_CALLED                        ← agar main already CALLED hoon

clamp: 0 se 180 min · aur 2 min se kam kabhi na dikhao
```

### B4.2 Complexity weights (owner ke research se)

| Visit type | Weight | Est. time | Kaise pata chalega |
|------------|--------|-----------|--------------------|
| Follow-up | 1× | 6–8 min | `visit_type='followup'` ya patient history me 30 din me visit |
| Report review | 1× | 5–7 min | Lab/ECG report attach hai, naya diagnosis nahi |
| New visit | 2× | 15–20 min | Pehli visit (`total_visits <= 1`) |
| Procedure/ECG | 2× | 15–20 min | `service_code != 'OPD'` dispatched |

### B4.3 Naye columns (additive — purana kuch nahi tootega)

```sql
ALTER TABLE queue_entries ADD COLUMN complexity_weight  INT DEFAULT 1;   -- 1 / 2 / 3
ALTER TABLE queue_entries ADD COLUMN estimated_minutes  INT;             -- snapshot
ALTER TABLE queue_entries ADD COLUMN visit_type         VARCHAR(20);     -- new|followup|report
-- started_at / completed_at ABHI SE MAUJOOD HAIN — naya nahi chahiye
```

### B4.4 Nayi file

```
src/domain/queue/ewt.py          ← pure functions (koi DB/network nahi, aise test karna aasan)
    avg_service_minutes(entries)         → EWMA
    complexity_weight(entry, history)    → 1 | 2 | 3
    estimate_wait(entry, ahead, avg)     → int (minutes)
    eta_confidence(ahead, samples)       → "high" | "medium" | "low"
```

Phir `marketplace_routes._queue_map()` me `MINUTES_PER_PATIENT` ki jagah `estimate_wait()` lagega —
**UI ko chhune ki zaroorat nahi**, kyunki wahi `wait_minutes` key return hoti rahegi.

## B5. 📐 Slot Booking (BANANA HAI)

```sql
CREATE TABLE appointment_slots (
    id          UUID PRIMARY KEY,
    clinic_id   VARCHAR(36) NOT NULL,
    doctor_id   VARCHAR(50),
    slot_date   DATE      NOT NULL,
    start_time  TIME      NOT NULL,
    end_time    TIME      NOT NULL,
    capacity    INT       NOT NULL DEFAULT 1,
    booked      INT       NOT NULL DEFAULT 0,
    is_active   BOOLEAN   NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT now(),
    UNIQUE (clinic_id, doctor_id, slot_date, start_time)
);
```

**Rule (non-negotiable):** slot **booking ka jhooth nahi** — slot sirf **EWT ke saath** dikhega:

> *"2:30 PM slot · us waqt tak queue clear hone ka anumaan 🟢 high"*

Slot khali dikhane se zyada imaandar hai slot + **asli queue** dono dikhana.

---

# PART C — BRIDGE: Search → Booking → Live Queue → Health Card

> Yeh **loop** poore module ki jaan hai. Har step ka asli code path neeche hai.

```
[1] PATIENT SEARCH
    /find-doctor  →  GET /api/v1/marketplace/doctors?problem=seene%20me%20dard
                     ↓  _detect_specialty() → "Cardiology"
                     ↓  ClinicModel filter (city/specialty, is_active)
                     ↓  _queue_map() → REAL live queue
    ✅ Result: 🟢 "Gill Heart Clinic · Token #14 andar · 3 aage · ~18 min"
    📐 Naya  : wait_minutes = ewt estimate (7-min hardcode hat jayega)

[2] BOOKING (1 TAP)
    POST /api/v1/marketplace/book {clinic_id, name, phone, problem}
      → PatientModel: phone_hash se reuse, warna naya (CQ-YYYYMMDD-###)
      → QueueEntryModel: service_code='OPD', status='WAITING', created_by='marketplace'
      → token = MAX(token_number)+1 (us din ke VIS- prefix par)
      → tracking_url = /track/<tracking_token>
    ✅ Result: "Token #17 booked · 3 patient aage · ~21 min"

[3] WAIT AT HOME (Virtual Waiting Room)
    Patient /track/<token> par baitha rehta hai — lobby me nahi
    📐 Naya: 3 patient bache → WhatsApp: "ab niklo, 15 min ka rasta"
             (distance = haversine(patient lat/lon, clinic lat/lon))

[4] DOCTOR'S LIVE VIEW
    /opd/dashboard → ▶ CALL NEXT → called_at set → patient ko chime + slip
    📐 Naya: complexity-weighted EWT + slot grid + delay badge 🟡/🔴

[5] CONSULT → DISPATCH
    started_at → ECG/Echo/TMT/Lab order → SENT_TO_DEPT → completed_at
    ✅ Multi-department routing maujood hai (staff routes: /ecg /echo /tmt /lab /
       live-board /tv) — reception par dobara queue nahi lagti

[6] HEALTH CARD (retention + virality)
    POST /opd/api/health-card → /card/<uid>
    Card = identity (masked phone) + latest vitals + 8 latest prescriptions
    ✅ Read-only · expiry 30 din · view_count track
    📐 Naya: health_card_access audit + "🔒 revoke link" (DPDP Act 2023)

[7] NEXT PATIENT (flywheel)
    Shared card / WhatsApp → naya patient search par aata hai → wapas [1] 🔁
```

---

## 3. Data Model — poora module ek schema me

### 3.1 ✅ Jo maujood hai (chhedna nahi, sirf padhna)

| Table | Kaam | File |
|-------|------|------|
| `clinics` | Multi-tenant registry + **lat/long + hpr_id + hfr_id** already hai | `src/infrastructure/clinic/models/clinic_model.py` |
| `queue_entries` | Token + status + **saare timestamps** | `src/infrastructure/queue/models/queue_entry_model.py` |
| `patients` | Patient master (`phone_hash` se dedupe) | `src/infrastructure/patient/models/patient_model.py` |
| `opd_prescriptions` | Rx history (Health Card ka source) | `src/infrastructure/opd/models/opd_models.py` |
| `patient_readings` | Patient self-filled BP/sugar/weight | `src/infrastructure/opd/models/patient_portal_models.py` |
| `patient_portal_links` / `patient_shares` | `/my/<token>` + `/s/<token>` | same |
| `health_cards` | Universal Health Card (`uid`, `expires_at`, `view_count`, `active`) | same |
| `abha_links` | Patient ↔ 14-digit ABHA | `src/infrastructure/abdm/models.py` |
| `consent_artefacts` | Data-share consent (DPDP + ABDM) | same |
| `abdm_transactions` | DHIS incentive claim ka audit trail | same |
| `lab_orders` | External lab network | `src/infrastructure/lab/models.py` |
| `opd_drug_history` | 50,000+ drug bank (auto-learn) | OPD engine |

### 3.2 📐 Jo add karna hai (sirf **additive** — purana kuch nahi tootega)

```sql
-- (1) Availability + rating  → "Open now" filter, distance sort
ALTER TABLE clinics ADD COLUMN open_time  VARCHAR(5);    -- "09:00"
ALTER TABLE clinics ADD COLUMN close_time VARCHAR(5);    -- "20:00"
ALTER TABLE clinics ADD COLUMN rating     FLOAT DEFAULT 0;

-- (2) EWT engine  → complexity-weighted wait
ALTER TABLE queue_entries ADD COLUMN complexity_weight INT DEFAULT 1;
ALTER TABLE queue_entries ADD COLUMN estimated_minutes INT;
ALTER TABLE queue_entries ADD COLUMN visit_type        VARCHAR(20);

-- (3) Slot booking
CREATE TABLE appointment_slots (...);        -- poora SQL Part B5 me

-- (4) Health Card audit + revoke (DPDP Act 2023)
CREATE TABLE health_card_access (
    id            UUID PRIMARY KEY,
    card_id       UUID NOT NULL,
    accessed_by   VARCHAR(200),      -- doctor name / phone hash
    ip_hash       VARCHAR(64),
    accessed_at   TIMESTAMP DEFAULT now()
);

-- (5) Growth loop (Tier-2 → Tier-1 conversion)
CREATE TABLE clinic_leads (
    id            UUID PRIMARY KEY,
    clinic_name   VARCHAR(200),
    doctor_name   VARCHAR(200),
    phone         VARCHAR(20),
    city          VARCHAR(100),
    source        VARCHAR(50) DEFAULT 'marketplace_invite',
    status        VARCHAR(30) DEFAULT 'new',   -- new | contacted | onboarded | rejected
    created_at    TIMESTAMP DEFAULT now()
);
```

> **Migration rule:** har schema change ke saath `alembic/versions/` me ek migration file,
> aur `main_v2.py` ka `Base.metadata.create_all()` naye tables khud bana deta hai (SQLite par yahi chalta hai).

---

## 4. API Contract — ek jagah saare endpoints

### 4.1 ✅ LIVE (aaj kaam kar rahe hain)

| Method | Path | Kaam |
|--------|------|------|
| GET | `/find-doctor` | Patient marketplace page (HTML) |
| GET | `/api/v1/marketplace/meta` | Cities + specialties list |
| GET | `/api/v1/marketplace/doctors` | Directory + **asli live queue** |
| POST | `/api/v1/marketplace/book` | 1-tap booking → token + tracking link |
| POST | `/api/v1/marketplace/seed` | Demo clinics (token-gated) |
| GET | `/track/<token>` | Patient live tracking (PWA, no install) |
| GET | `/my/<token>` | Patient self-portal (BP/sugar/graphs/PDF) |
| GET | `/s/<token>` | Doctor read-only share (7 din) |
| GET | `/card/<uid>` | 🪪 Universal Health Card |
| POST | `/opd/api/health-card` | Doctor: card banao + WhatsApp link |
| GET | `/rx-pad` | 📝 Letterhead prescription pad |
| POST | `/opd/api/lab-order` | 🧪 External lab order |
| GET | `/lab/<token>` | Patient: lab result phone par |
| GET | `/abdm` | 🏥 ABDM compliance status page |
| GET | `/abdm/status` · `/abdm/fhir/Patient/{id}` · `/abdm/consent/{patient_id}` · `/abdm/dhis/transactions` | ABDM registry + FHIR + consent + DHIS |

### 4.2 📐 BANANE HAIN

| Method | Path | Kaam | Kahan |
|--------|------|------|-------|
| GET | `/api/v1/marketplace/doctors?open_now=1` | Sirf khuli clinics | `marketplace_routes.py` |
| GET | `/api/v1/marketplace/ewt?clinic_id=` | EWT breakdown (patient ko transparency) | naya `ewt_routes.py` |
| GET | `/api/v1/slots?clinic_id=&date=` | Free slots + confidence | naya `slots_routes.py` |
| POST | `/api/v1/slots/book` | Slot → queue entry | same |
| POST | `/opd/api/notify-leave-now` | Departure alert (3 ahead) | `opd_routes.py` helper |
| POST | `/opd/api/alert/leave-now` | Patient ko WhatsApp "ab niklo" | naya |
| POST | `/card/{uid}/revoke` | 🔒 Link band karo (DPDP right-to-revoke) | `health_card_routes.py` |
| GET | `/opd/api/queue-ewt` | Doctor Live View ka EWT feed | `opd_routes.py` |
| POST | `/api/v1/marketplace/invite` | Tier-2 → `clinic_leads` | `marketplace_routes.py` |
| GET | `/abdm/fhir/Bundle/{patient_id}` | Poora record ek FHIR bundle me | `abdm_routes.py` |
| GET | `/abdm/dhis/claim-export` | DHIS incentive claim file | same |

---

## 5. 🔒 Guardrails — jo kabhi nahi todenge

| # | Rule | Kyun |
|---|------|------|
| 1 | **Sirf additive schema** — koi column rename/drop nahi | Live production SQLite par purana data bacha rahe |
| 2 | **`opd_routes.py` (3650+ lines) chhedne se bacho** | Sabse nazuk file — naya kaam naye module me |
| 3 | **Naya code live = `python pa_deploy.py ship --since <commit>`** | PA par files-API upload + reload + health |
| 4 | **Har deploy par BUILD stamp badle** | `/health` + dashboard footer se naya/purana turant pata chale |
| 5 | **PA free ki limit yaad rakho** — 100 CPU-sec/din · no scheduled tasks · outbound sirf whitelist | Bhaari loop/background job PA par nahi chalega |
| 6 | **AI browser-side BYOK** — server se provider call PA par block hai | Har doctor apni key, owner ka ₹0 |
| 7 | **Patient data public nahi** — phone masked, uid unguessable, read-only share | DPDP Act 2023 |
| 8 | **Koi fake number nahi** — `_live_signal()` demo hata diya gaya hai | Bharosa = product |
| 9 | **Naya keyword/specialty = sirf `PROBLEM_TO_SPECIALTY` dict** | UI + API sync rahe |
| 10 | **Har feature ke saath ek test** (`tests/`, `scripts/integration_smoke_test.py`) | Live par todo mat |

---

## 6. Build Order — ek-ek karke tick hoga

> Owner ka nirdesh: **queue/EWT pehle** (yahi asli moat hai), phir slots, phir growth, phir compliance wiring.

### 🔴 BLOCK 1 — EWT Engine (P0) — *"Uber ETA for OPD"*

| # | Item | File | Effort |
|---|------|------|--------|
| EWT-01 | `src/domain/queue/ewt.py` — avg service time + complexity weight + estimate | **naya** | M |
| EWT-02 | `queue_entries` me `complexity_weight`, `estimated_minutes`, `visit_type` | model + migration | S |
| EWT-03 | `MINUTES_PER_PATIENT` hardcode → `estimate_wait()` | `marketplace_routes.py` | S |
| EWT-04 | Booking API me booking ke waqt hi EWT snapshot save | `marketplace_routes.py` | S |
| EWT-05 | Doctor Live View me EWT + delay badge 🟡/🔴 | `templates/opd/dashboard.html` | M |
| EWT-06 | Patient page par EWT breakdown (imaandari se "3 aage × ~6 min") | `marketplace.html` + `/track` | S |

### 🟠 BLOCK 2 — Availability + Geofence (P1)

| # | Item | File | Effort |
|---|------|------|--------|
| AVL-01 | `open_time`/`close_time`/`rating` columns + admin form | clinic model + `onboard_doctor.html` | M |
| AVL-02 | "🟢 Abhi khula hai" filter + `availability: OPEN/CLOSED` | `marketplace_routes.py` | S |
| AVL-03 | Distance sort (haversine already hai) + "mere paas" button | `marketplace.html` | S |
| AVL-04 | **Departure Alert** — 3 patient bache → WhatsApp "ab niklo" | naya notifier + `patient_tokens` | M |

### 🟡 BLOCK 3 — Slots + Doctor Live View (P1)

| # | Item | File | Effort |
|---|------|------|--------|
| SLT-01 | `appointment_slots` table + CRUD | model + migration | M |
| SLT-02 | Slot booking API (slot → queue entry, capacity check) | naya `slots_routes.py` | M |
| SLT-03 | Doctor dashboard me slot grid + "EWT confidence" | `dashboard.html` | M |

### 🔵 BLOCK 4 — Retention + Growth (P2)

| # | Item | File | Effort |
|---|------|------|--------|
| GRW-01 | `health_card_access` audit + `/card/{uid}/revoke` (DPDP) | `health_card_routes.py` | S |
| GRW-02 | `clinic_leads` + Tier-2 "📢 Invite" button + Admin pipeline | marketplace + admin | M |
| GRW-03 | City SEO pages `/doctors/<city>` | naya route | S |
| GRW-04 | Family Health Locker (1 mobile → N profiles) | portal | L |

### 🟣 BLOCK 5 — Compliance wiring (P0, par credentials ka intezaar)

| # | Item | File | Effort |
|---|------|------|--------|
| ABD-01 | ABDM sandbox se HFR (clinic) + HPR (doctor) register | `abdm_routes.py` | M |
| ABD-02 | ABHA create + link live (`/abdm/abha/link` pehle se ready) | same | M |
| ABD-03 | FHIR Bundle export (Patient+Observation+MedicationRequest+DiagnosticReport) | `fhir.py` + routes | M |
| ABD-04 | DHIS claim export (incentive 💰) | `abdm_routes.py` | S |
| ABD-05 | NHA Milestone certification apply | docs | M |

> ⚠️ **ABD-01 se aage credentials ke bina nahi badh sakte** — `ABDM_CLIENT_ID` / `ABDM_CLIENT_SECRET`
> (NHA sandbox) chahiye. Tab tak ABD-03 (offline FHIR export) ban sakta hai.

---

## 7. Success Metrics (North Star)

| Metric | Aaj | 90-din target |
|--------|-----|---------------|
| Doctor search → booking conversion | — | ≥ 15% |
| Partner clinics with live feed | 1 (GIL CLINIC) | 100% |
| Average patient wait (partner) | ~60 min (industry) | **< 15 min** |
| EWT accuracy (actual vs predicted) | — | ± 5 min |
| Health Card share rate | — | ≥ 20% visits |
| Tier-2 → Tier-1 upgrade | 0 | ≥ 5% / month |
| No-show rate | — | < 10% |

---

## 8. Ek line me

> **Part A patient ko sahi doctor dikhata hai. Part B doctor ko sahi patient deta hai.
> Part C dono ko jodta hai — aur wahi loop GHOS ko "Uber of OPD" banata hai.** 🟢

---

*Files referenced in this blueprint (verified 02-Oct-2026):*
`marketplace_routes.py` · `health_card_routes.py` · `abdm_routes.py` · `fhir.py` · `lab_network_routes.py` ·
`rx_pad_routes.py` · `queue_entry_model.py` · `clinic_model.py` · `ghos/services/queue-engine/app/engine/{priority,delay,queue_engine}.py` ·
`main_v2.py` · `templates/{marketplace,health_card,landing,opd/dashboard}.html` · `DEEP_RESEARCH_PRODUCT_DEVELOPMENT.md` ·
`PRODUCT_UPGRADATION_UBER_HEALTHCARE.md` · `COMPETITOR_GAP_ANALYSIS_MISSING_FEATURES.md`
