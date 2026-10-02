# 🌐 GLOBAL CLINIC SEARCH & QUEUE ENGINE — Master Architecture Blueprint

> **Owner:** Gurjas Singh Gill (Dr. G. S. Gill)
> **Product:** GHOS — GIL CLINIC (`gillhopitalsoftware1.pythonanywhere.com`)
> **Version:** **1.1** · **Date:** 02 Oct 2026
> **One-liner:** *"Practo ek directory dikhata hai. GHOS ek ZINDA queue dikhata hai."*
> **Mantra:** 🟢 **Live queue > khaali appointment slot.**

> **Ye file kya hai:** poore "Global Clinic Search + Queue Engine" module ka **master architecture blueprint**.
> **Part A** Search · **Part B** Queue Engine · **Part C** Bridge · **Part D** Real-world edge cases ·
> **Part E** Module 6 (external doctor data ingestion).
>
> **Har section me saaf likha hai:** ✅ kya ban chuka · 📐 kya banana hai · 📁 kis file me.

### 📝 Changelog

| Ver | Kya badla |
|-----|-----------|
| 1.0 | Part A/B/C + data model + build order |
| **1.1** | ➕ **Part D** — 9 real-world edge cases (doctor late arrival, token skip/HOLD, no-cron alert, multi-doctor collision) · ➕ **Part E** — Module 6 Crawl4AI ingestion (PA-free-safe architecture) · 🐞 **BUG-01** booking token counter · ✅ status vocabulary corrected (`IN_PROGRESS`, not `IN_CONSULT`) |

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
| 8 | **Edge Cases (Part D)** | Doctor late, token skip, multi-doctor, no-cron alert | 📐 **BANANA HAI** |
| 9 | **ABDM/FHIR** | ABHA + HPR/HFR + FHIR R4 + DHIS incentive | 🏷️ **SCAFFOLD READY** |
| 10 | **Module 6 Ingestion** | Crawl4AI se Tier-2 doctor data (GH Actions worker) | 📐 **NAYA MODULE** |

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
│              📱 8s polling → Web Audio chime (cron-free alert!)        │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────── QUEUE ENGINE ──────────────────┐
│  queue_entries  (per-clinic · per-doctor · service_code='OPD')         │
│  WAITING → CALLED → IN_PROGRESS → COMPLETED → REPORT_READY → DELIVERED │
│  side: HOLD (naya) · CANCELLED · NO_SHOW                               │
│  priority score = token_number − (priority × 1000)   ← senior/emergency│
│  chamber gate: doctor ▶ START OPD tak EWT countdown band               │
│  delay engine: elapsed − avg_service_time → 🟡 5min / 🔴 10min         │
│  EWT: complexity_weight × avg_service_time + live delay                │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────── DOCTOR SIDE ───────────────────┐
│  /opd/dashboard   Live queue · Call next · ECG dispatch · Rx          │
│  📱 Patient link · 🩺 Patient Monitor · 🪪 Health Card · 📝 Rx Pad     │
│  🧪 Lab Order · 📹 Jitsi video · 🏥 ABDM status · ▶️ START OPD        │
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
| A-6 | **Departure Alert** | Part D · E-03 | 3 patient bache → **client-side** chime (server cron nahi chahiye) |

---

# PART B — QUEUE ENGINE

> **Kaam:** ek token ka poora jeevan — banna, chalna, bulaya jaana, khatam hona — aur uska **sahi wait time**.

## B1. Token lifecycle — **asli status vocabulary**

Source of truth: `src/domain/queue/value_objects/queue_status.py` (✅ pehle se maujood)

```
WAITING  →  CALLED  →  IN_PROGRESS  →  COMPLETED  →  REPORT_READY  →  DELIVERED
   │           │            │
   └───────────┴────────────┴──►  CANCELLED  |  NO_SHOW   (terminal)

Valid transitions (code me defined):
  WAITING      → CALLED · CANCELLED · NO_SHOW
  CALLED       → IN_PROGRESS · WAITING · CANCELLED · NO_SHOW
  IN_PROGRESS  → COMPLETED · CANCELLED
  COMPLETED    → REPORT_READY · IN_PROGRESS
  REPORT_READY → DELIVERED
```

| Icon | Status | Matlab |
|------|--------|--------|
| 🟡 | `WAITING` | Line me khada hai |
| 🔵 | `CALLED` | Naam pukara gaya (`called_at`) |
| 🟠 | `IN_PROGRESS` | Andar hai (`started_at`) |
| ✅ | `COMPLETED` | Consult khatam (`completed_at`) |
| 📋 | `REPORT_READY` | Report taiyar |
| 📄 | `DELIVERED` | Report mil gaya — queue se bahar (`delivered_at`) |
| ❌🚫 | `CANCELLED` / `NO_SHOW` | Terminal — band |

> ⚠️ **Correction (v1.0 → v1.1):** pehle is blueprint me `IN_CONSULT` likha tha — **galat**.
> Asli naam **`IN_PROGRESS`** hai. Aur **`HOLD` abhi maujood NAHI hai** → Part D · E-02 me banana hai.

## B2. Priority Engine (Code Red / Senior / Emergency)

Do jagah maujood hai:

**(a) Live app** — `queue_entries.priority` (int) + `display_order`

**(b) Blueprint microservice** — `ghos/services/queue-engine/app/engine/priority.py`:

```python
score = token_number − (priority × 1000)      # chhota score = pehle
# 0 Normal · 1 Senior (60+) · 2 Emergency · 3 VIP   ·  Staff family = −100 offset
```

| Level | Score | Kab |
|-------|-------|-----|
| 0 Normal | token | Aam patient |
| 1 Senior | token − 1000 | 60+ |
| 2 Emergency | token − 2000 | Chest pain / SpO₂ < 90% → **Code Red** (`#E-1`) + siren |
| 3 VIP | token − 3000 | Owner/trustee referral |

## B3. Delay Detection

`ghos/services/queue-engine/app/engine/delay.py`:

```
delay = (abhi ka samay − called_at) − avg_service_time

  < 0        → koi delay nahi
  ≥ 5 min    → 🟡 warning
  ≥ 10 min   → 🔴 critical  (staff screens par alert)
```

> Live app me abhi **delay alert wire nahi hua** — Part C ka kaam hai.

## B4. 📐 EWT Engine — "Uber ETA for OPD" (BANANA HAI)

**Problem:** `wait_minutes = patients_ahead × 7` — har patient ko 7 min maan leta hai. **Galat.**

### B4.1 Formula (banane wala)

```
AVG = EWMA(completed_at − started_at)            ← is DOCTOR ka ASLI average (rolling)
      (kam se kam 20 samples, warna default 7 min)

EWT(mere liye) =
      Σ  ( complexity_weight_i × AVG )            ← mere aage ke har patient ka
   +  DELAY_PENALTY                               ← current patient AVG se zyada le raha hai
                                                  (max +15 min cap)
   −  ELAPSED_SINCE_CALLED                        ← agar main already CALLED hoon

clamp: 0 se 180 min · 2 min se kam kabhi na dikhao
GUARD: chamber band hai (doctor nahi aaya) → EWT = 0 · "Arrival Pending" dikhao (Part D · E-01)
```

### B4.2 Complexity weights (owner ke research se)

| Visit type | Weight | Est. time | Kaise pata chalega |
|------------|--------|-----------|--------------------|
| Follow-up | 1× | 6–8 min | `visit_type='followup'` ya 30 din me visit |
| Report review | 1× | 5–7 min | Lab/ECG report attach hai, naya diagnosis nahi |
| New visit | 2× | 15–20 min | Pehli visit (`total_visits <= 1`) |
| Procedure/ECG | 2× | 15–20 min | `service_code != 'OPD'` dispatched |

### B4.3 Naye columns (additive)

```sql
ALTER TABLE queue_entries ADD COLUMN complexity_weight INT DEFAULT 1;   -- 1 / 2 / 3
ALTER TABLE queue_entries ADD COLUMN estimated_minutes INT;             -- snapshot
ALTER TABLE queue_entries ADD COLUMN visit_type        VARCHAR(20);     -- new|followup|report
ALTER TABLE queue_entries ADD COLUMN doctor_id         VARCHAR(100);    -- ⚠️ Part D · E-04
ALTER TABLE queue_entries ADD COLUMN sort_key          FLOAT;           -- ⚠️ Part D · E-02
ALTER TABLE queue_entries ADD COLUMN requeue_count     INT DEFAULT 0;   -- ⚠️ Part D · E-02
-- started_at / completed_at ABHI SE MAUJOOD HAIN — naya nahi chahiye
```

### B4.4 Nayi file

```
src/domain/queue/ewt.py          ← pure functions (koi DB/network nahi → test karna aasan)
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
    doctor_id   VARCHAR(100),
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

**Rule:** slot **akela kabhi nahi** dikhega — saath me **live queue + EWT confidence** bhi:

> *"2:30 PM slot · us waqt tak queue clear hone ka anumaan 🟢 high"*

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
      → token = MAX(token_number)+1     ⚠️ BUG-01 (Part D) — clinic filter chahiye
      → tracking_url = /track/<tracking_token>
    ✅ Result: "Token #17 booked · 3 patient aage · ~21 min"

[3] WAIT AT HOME (Virtual Waiting Room)
    Patient /track/<token> par baitha rehta hai — lobby me nahi
    ✅ Ye page already /track/{token}/status ko har 8 second poll karta hai
    📐 Naya: patients_ahead ≤ 3 → browser me chime + "🏃 AB NIKLO" (no server cron!)

[4] DOCTOR'S LIVE VIEW
    /opd/dashboard → ▶ START OPD (chamber gate) → ▶ CALL NEXT → called_at
    📐 Naya: complexity-weighted EWT + slot grid + delay badge 🟡/🔴 + HOLD button

[5] CONSULT → DISPATCH
    started_at → ECG/Echo/TMT/Lab order → IN_PROGRESS → completed_at
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

# PART D — 🚨 REAL-WORLD EDGE CASES

> **Kyun ye section hai:** blueprint 95% sahi tha, par **asli clinic chalte waqt** yeh 9 cheezein
> system ko phasa sakti hain. Sab **code me verify** ki gayi hain (02-Oct-2026).

---

## E-01 🔴 Doctor "Late Arrival" — EWT ka sabse bada bug

**Problem:** Clinic ka time 9:00 AM likha hai, doctor traffic/ward round se **9:40** par aaya.
Agar 9:00–9:40 ke beech patient app kholega to system bolega *"Wait: 15 min"* — jabki
**doctor room me hai hi nahi.** Patient gussa, trust khatam.

**✅ Rule (Chamber Gate):**
1. EWT countdown **tab tak shuru nahi hoga** jab tak doctor ne ▶️ **START OPD** na dabaya ho.
2. Jab tak chamber band hai, patient ko dikhega:

```
⏳ Doctor Arrival Pending  (Scheduled: 9:00 AM)
   Chamber abhi khula nahi hai — aapka number safe hai, wait count nahi ho raha.
```

3. Doctor login + START karte hi countdown **live** ho jayega — aur 9:00 se 9:40 ka
   **intezaar EWT me count nahi** hoga (warna jhoota number banega).

**📁 Implement:**
```sql
CREATE TABLE chamber_sessions (
    id          UUID PRIMARY KEY,
    clinic_id   VARCHAR(36) NOT NULL,
    doctor_id   VARCHAR(100) NOT NULL,
    session_date DATE       NOT NULL,
    opened_at   TIMESTAMP   NOT NULL,      -- ▶️ START OPD
    closed_at   TIMESTAMP,                 -- ⏹ END OPD
    UNIQUE (clinic_id, doctor_id, session_date)
);
```
- `GET /api/v1/marketplace/doctors` → `chamber_open: true|false` + `opened_at`
- **Bonus:** `opened_at − scheduled_time` = **doctor ka average late-arrival** (owner ka analytics)

---

## E-02 🔴 Token Skip & Return — "washroom problem"

**Problem:** Token #14 bulaya, patient washroom gaya tha. Doctor ne #15 bula liya.
Ab #14 wapas aaya — to **sabse aakhir (#35)** me chala jayega? **Mareez jhagda karega!**

**✅ Rule (Next + 1):**
1. Bulane par patient na mile → **`HOLD`** (aakhir me nahi bhejna).
2. Wapas aane par position = **jo abhi `IN_PROGRESS` hai uske theek agle number par** (Next + 1).
3. **Abuse guard:** ek patient ko sirf **1 baar** free re-queue — doosri baar aakhir me.
4. Agar `IN_PROGRESS` koi nahi, to `CALLED` ke baad, warna queue ke **shuru** me.

**📁 Implement (O(1) insertion trick):**
```python
# sort_key FLOAT use karo (naya additive column)
cur  = in_progress_entry.sort_key          # e.g. 14.0
nxt  = next_waiting_sort_key(after=cur)    # e.g. 15.0
entry.sort_key = (cur + nxt) / 2           # 14.5  ← beech me ghus gaya, koi shifting nahi
entry.status = "WAITING"
entry.requeue_count += 1
```
- `QueueStatus` me **`HOLD`** add karo (`waITING`/`CALLED` se `HOLD` allowed, `HOLD → WAITING` allowed)
- ✅ Lucky baat: `CALLED → WAITING` transition **pehle se allowed** hai — base taiyar hai.

---

## E-03 🟠 Departure Alert — **server cron ke bina** (PA free ki majboori)

**Problem:** Guardrail kehta hai *"PA free: no scheduled tasks (403) · 100 CPU-sec/din"* —
par C4 kehta hai *"WhatsApp: ab niklo"*. **Server par cron/WhatsApp API chalega hi nahi.** Contradiction.

**✅ Fix (dono raste, dono free):**

**(1) Client-side trigger — sabse sahi:**
```
Patient ka /track/<token> page ALREADY har 8 second /track/<token>/status poll karta hai
      ↓
patients_ahead ≤ 3  →  browser khud:
      🔊 Web Audio chime  (koi gateway cost nahi)
      🏃 full-screen "AB NIKLO — 15 min ka rasta"
      🔔 Notification API (agar permission di ho) + phone vibrate
```
> **Kuch bhi server par nahi chalta** — patient ka apna phone hisaab karta hai. PA ke 100 CPU-sec bhi safe.

**(2) Reception 1-click WhatsApp:**
- Reception screen par chhota icon — jab kisi patient ke `patients_ahead ≤ 3` ho to **green** ho jaye
- Receptionist 1 tap → `https://wa.me/91<phone>?text=<ready message>` deep link
- ✅ Koi paid gateway nahi, koi cron nahi — **insaan hi trigger hai**, system sirf signal deta hai

**📁 Implement:** `templates/patient_track.html` (already 8s polling) + `staff_routes.py` public status me
`patients_ahead` field + reception dashboard ka green icon.

---

## E-04 🔴 Multi-Doctor Chamber Collision

**Problem:** GIL CLINIC me 2 doctor baithe hain (Dr. Gill – Cardiology, Dr. Sharma – General).
Agar dono ka **Token #14** ho gaya to EWT mix ho jayega — Cardiology ka 20-min case
General ke patient ko "20 min wait" dikhayega. **Galat.**

**✅ Rule:** har token `(clinic_id, doctor_id, service_code)` teeno par partition ho.

```
C-14   → Cardiology (Dr. Gill)
G-14   → General    (Dr. Sharma)
E-01   → Emergency / Code Red
```

**🐞 Verified gap:** `doctor_id` **`queue_entries` me hai HI NAHI** —
jabki OPD layer me har jagah maujood hai (`opd_settings.doctor_id`, `opd_prescriptions.doctor_id`,
`opd_drug_history.doctor_id`, `lab_orders.doctor_id`).

**📁 Implement:**
```sql
ALTER TABLE queue_entries ADD COLUMN doctor_id VARCHAR(100) DEFAULT 'chief';
CREATE INDEX ix_queue_clinic_doctor_status ON queue_entries (clinic_id, doctor_id, status);
```
- Token generator: `MAX(token_number) WHERE clinic_id = ? AND doctor_id = ? AND service_code='OPD' AND date = today`
- Display: `<specialty_prefix>-<token>` (C-14 / G-14)
- EWT: strictly `(clinic_id, doctor_id)` — **doctors ka queue kabhi mix nahi**

---

## E-05 🐞 BUG-01 — Booking token counter **global** hai (naya bug mila)

**Problem (code me mila):** `marketplace_routes.py` → `marketplace_book()`:

```python
token_row = await session.execute(
    sa.select(sa.func.coalesce(sa.func.max(QueueEntryModel.token_number), 0)).where(
        QueueEntryModel.service_code == "OPD",
        QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
        # ❌ clinic_id filter NAHI hai!
    )
)
```

**Result:** do alag clinics ek hi din me **ek hi token sequence** share kar rahi hain.
Clinic A ko #17, Clinic B ko #18 — jabki B ka ye pehla patient hai. **Ye production bug hai.**

**✅ Fix:**
```python
.where(
    QueueEntryModel.clinic_id == str(clinic.id),       # ✅ per-clinic
    QueueEntryModel.doctor_id == (doctor_id or "chief"),# ✅ per-doctor (E-04)
    QueueEntryModel.service_code == "OPD",
    QueueEntryModel.visit_id.like(f"VIS-{date_prefix}-%"),
)
```
**Saath me:** `department="OPD"` hardcoded aur `room=""` chhoot gaya hai — ye clinic/doctor ke
asli room se aana chahiye (warna doctor screen par galat chamber dikhega).

---

## E-06 🟡 Clinic Holiday / Band din

**Rule:** `clinics.is_open_today` (ya `holidays` table) → listing par **"🔴 Aaj band hai"**,
booking **band**, aur `availability = CLOSED`. Patient ka time barbaad nahi hona chahiye.

---

## E-07 🟡 No-Show / Cancel — ghost entry se EWT kharab na ho

**Rule:** `CALLED` ke baad **X min (default 8)** tak patient na aaye → auto **`NO_SHOW`** + EWT **turant recompute**.
Warna ek bhoot entry poori line ka wait jhoota badha deti hai. (Status pehle se maujood hai: `NO_SHOW`.)

---

## E-08 🟡 Emergency Override (Code Red)

**Rule:** Chest pain / SpO₂ < 90% → token **`#E-1`** + staff screens par **siren**
+ waiting patients ko ek tap me *"emergency case, 10 min extra"* message.
(Product file me innovation #10 — ab EWT ke saath wire hoga.)

---

## E-09 🟡 Non-OPD services ka alag EWT

**Rule:** ECG / Echo / TMT / Lab ka **apna** average hai (`service_code` partition).
Unka wait OPD ke average se nahi nikalna — warna report-review patient ka number galat aayega.

---

### 📊 Part D summary register

| # | Edge case | Severity | Status |
|---|-----------|----------|--------|
| E-01 | Doctor late arrival (chamber gate) | 🔴 Critical | 📐 |
| E-02 | Token skip & return (HOLD → Next+1) | 🔴 Critical | 📐 |
| E-03 | Departure alert **bina cron** | 🟠 High | 📐 |
| E-04 | Multi-doctor collision (`doctor_id`) | 🔴 Critical | 📐 |
| **E-05** | **BUG-01: global token counter** | 🔴 **Bug (live)** | 📐 |
| E-06 | Holiday / closed day | 🟡 Medium | 📐 |
| E-07 | No-show auto-detect | 🟡 Medium | 📐 |
| E-08 | Emergency override | 🟡 Medium | 📐 |
| E-09 | Non-OPD alag EWT | 🟡 Medium | 📐 |

---

# PART E — MODULE 6: AUTONOMOUS EXTERNAL DOCTOR DATA INGESTION

> **Maqsad:** Tier-2 (non-network) doctors ka data **khud** bhar jaye — hazaron ghante manual
> scraping ke bina. Crawler public hospital/clinic pages padhta hai, LLM usko structured
> **doctor profile** me badalta hai, aur hamara marketplace use dikhata hai.

## E1. Architecture — par ⚠️ pehle ek zaroori sachchai

> ### 🚫 Crawl4AI **PythonAnywhere free par NAHI chal sakta** — 4 verified wajah:
> | # | Rok | Kyun |
> |---|-----|------|
> | 1 | **Outbound internet sirf whitelist** | PA free ka server kisi bhi random hospital site par request nahi kar sakta (MEMORY §2) |
> | 2 | **Scheduled tasks band (403)** | Crawl worker ko cron chahiye — PA free me nahi milta |
> | 3 | **100 CPU-second / din** | Ek headless-browser crawl hi poora quota kha jayega |
> | 4 | **Disk/RAM** | Playwright + Chromium ~400 MB — app ke saath fit nahi hoga |
>
> **Isliye Module 6 app ke andar nahi chalega — usko ek alag "worker" me chalana hoga.** ✅ Neeche 2 raste hain.

### E1.1 Sahi architecture (2 raste — dono free)

```
┌─────────── WORKER (app ke bahar) ───────────┐        ┌──── GHOS APP (PA par) ────┐
│                                             │        │                           │
│  Option 1: GitHub Actions (cron)  ⭐        │        │  POST /api/v1/ingest/     │
│    ├─ crawl4ai (headless Chromium)          │        │       doctors  (token)    │
│    ├─ Gemini/LLM schema extraction          │───────►│        ↓                  │
│    └─ normalize → JSON                      │  HTTPS │  clinics (Tier-2,          │
│                                             │        │   source='crawl',         │
│  Option 2: Clinic PC (3-din me 1 baar)      │        │   verified=0)             │
│    └─ same script, `python ingest.py`       │        │        ↓                  │
│                                             │        │  /find-doctor (Tier-2)    │
└─────────────────────────────────────────────┘        │        ↓                  │
                                                        │  📢 "Invite this doctor"  │
                                                        │        ↓                  │
                                                        │  claim → Tier-1 onboard   │
                                                        └───────────────────────────┘
```

- ✅ **Option 1 (recommended):** aapka account **already GitHub Actions cron use karta hai**
  (`auto-social-agent` repo) — wahi pattern yahan reuse hoga. **App par zero load, zero cost.**
- ✅ **Option 2 (fallback):** clinic ka PC 3 din me 1 baar khulta hai — tab yeh script chal jaye.
  Koi external dependency nahi.

> **Rule:** app **sirf data leta hai** (ingest API), crawl **kabhi** app ke andar nahi.

## E2. Ingest API (naya — app ke andar)

| Method | Path | Kaam |
|--------|------|------|
| POST | `/api/v1/ingest/doctors` | Token-gated (`INGEST_TOKEN`) — crawl ka JSON push |
| GET | `/api/v1/ingest/sources` | Kitne sources, kab crawl hua, kitne profile |
| POST | `/api/v1/ingest/claim/{clinic_id}` | Doctor "ye mera profile hai" → claim → Tier-1 pipeline |
| DELETE | `/api/v1/ingest/profile/{clinic_id}` | 🚫 **Opt-out** — doctor kehta hai hata do → turant delete |

## E3. Schema (additive)

```sql
-- clinics par crawler ka meta
ALTER TABLE clinics ADD COLUMN source        VARCHAR(30) DEFAULT 'manual';  -- manual | crawl | referral
ALTER TABLE clinics ADD COLUMN source_url    VARCHAR(500) DEFAULT '';       -- kaunse page se aaya
ALTER TABLE clinics ADD COLUMN verified      BOOLEAN DEFAULT TRUE;          -- crawl = FALSE
ALTER TABLE clinics ADD COLUMN claim_status  VARCHAR(30) DEFAULT 'n/a';     -- unclaimed | claimed | opted_out
ALTER TABLE clinics ADD COLUMN last_crawled_at TIMESTAMP;

-- raw crawl audit (kya padha tha — proof)
CREATE TABLE doctor_crawl_runs (
    id           UUID PRIMARY KEY,
    source_url   VARCHAR(500),
    hospital_name VARCHAR(200),
    raw_hash     VARCHAR(64),
    profiles_found INT DEFAULT 0,
    status       VARCHAR(20),      -- success | failed | blocked
    error        TEXT,
    created_at   TIMESTAMP DEFAULT now()
);
```

## E4. Data contract (worker → app)

```python
class DoctorProfileSchema(BaseModel):          # ⚠️ aapke snippet me yeh DEFINE hi nahi tha
    doctor_name: str
    degree: str = ""
    specialty: str = "General Physician"
    reg_no: str = ""
    clinic_name: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    phone: str = ""                # sirf PUBLIC clinic/business number
    opd_days: str = ""             # "Mon-Sat"
    opd_start: str = ""            # "09:00"
    opd_end: str = ""              # "14:00"
    source_url: str
    confidence: float = 0.0        # LLM ka apna bharosa — 0.7 se kam = review queue
```

## E5. 🔧 Aapke code snippet me 6 technical corrections

| # | Aapka code | Sahi | Kyun |
|---|-----------|------|------|
| 1 | `provider="google/gemini-2.0-flash"` | `provider="gemini/gemini-2.5-flash"` | litellm me `google/` = **Vertex AI** (service-account chahiye). Google AI Studio key ke liye prefix **`gemini/`** |
| 2 | `DoctorProfileSchema` **undefined** | Class define karo (E4) | Warna `model_json_schema()` par `NameError` |
| 3 | schema = ek single object | List chahiye → wrapper: `{"type":"array","items": DoctorProfileSchema.model_json_schema()}` | Page par **kai** doctor hain |
| 4 | `wait_for="css:.doctor-list, .team-member, .profile-card"` | ek reliable selector + fallback (`delay_before_return_html`) | `wait_for` ek selector leta hai, "kya mila to chalega" nahi |
| 5 | model hardcoded = `2.0-flash` | **model discovery fallback** (jaise `ai_gateway.js` me pehle se hai) | Purane model retire hote hain → 404 (yeh dard aap already jhel chuke ho) |
| 6 | `headless=True` (seedha) | Pehle `playwright install chromium` + retry/backoff | CI par Chromium pre-install zaroori |

**Plus:** `robots.txt` respect · per-host **rate limit (1 req/sec)** · saaf User-Agent
(`GHOS-Crawler/1.0 (+contact)`) · retry 3 baar · `bypass_cache=True` rakho.

## E6. ⚖️ Legal / DPDP guardrails (non-negotiable)

1. **Sirf public professional info** — naam, degree, specialty, clinic address, **public clinic phone**, OPD timings.
2. **Kabhi patient data nahi** — koi review, koi patient list, koi health info.
3. **`source_url` + `last_crawled_at` har row par** — audit trail (kahan se aaya).
4. **Opt-out endpoint** — doctor bole to **48 ghante me** delete (E2 ka DELETE route).
5. **Attribution** — Tier-2 card par "public listing" label.
6. **robots.txt + rate limit** — marammat se crawl, site par load nahi.
7. **Claim flow** — doctor khud claim kare → tab hi Tier-1 marketing me use ho.

## E7. 📊 Part E summary register

| # | Item | Status |
|---|------|--------|
| M6-01 | GH Actions worker repo + crawl4ai + Gemini | 📐 |
| M6-02 | `DoctorProfileSchema` + schema-guided extraction | 📐 |
| M6-03 | `POST /api/v1/ingest/doctors` (token-gated) | 📐 |
| M6-04 | `clinics` crawl columns + `doctor_crawl_runs` | 📐 |
| M6-05 | Tier-2 listing par "public listing" label | 📐 |
| M6-06 | Claim flow → Tier-1 onboarding pipeline | 📐 |
| M6-07 | Opt-out / delete endpoint (DPDP) | 📐 |
| M6-08 | NMC / state medical council + ABDM **HPR** registry source (authoritative) | 📐 |

---

## 3. Data Model — poora module ek schema me

### 3.1 ✅ Jo maujood hai (chhedna nahi, sirf padhna)

| Table | Kaam | File |
|-------|------|------|
| `clinics` | Multi-tenant registry + **lat/long + hpr_id + hfr_id** already hai | `src/infrastructure/clinic/models/clinic_model.py` |
| `queue_entries` | Token + status + **saare timestamps** (`doctor_id` ❌ missing) | `src/infrastructure/queue/models/queue_entry_model.py` |
| `patients` | Patient master (`phone_hash` se dedupe) | `src/infrastructure/patient/models/patient_model.py` |
| `opd_prescriptions` | Rx history (Health Card ka source) | `src/infrastructure/opd/models/opd_models.py` |
| `patient_readings` | Patient self-filled BP/sugar/weight | `src/infrastructure/opd/models/patient_portal_models.py` |
| `patient_portal_links` / `patient_shares` | `/my/<token>` + `/s/<token>` | same |
| `health_cards` | Universal Health Card | same |
| `abha_links` · `consent_artefacts` · `abdm_transactions` | ABDM | `src/infrastructure/abdm/models.py` |
| `lab_orders` | External lab network | `src/infrastructure/lab/models.py` |
| `opd_drug_history` | Drug bank (auto-learn) | OPD engine |

### 3.2 📐 Jo add karna hai (sirf **additive** — purana kuch nahi tootega)

```sql
-- (1) Availability + rating  → "Open now" filter, distance sort
ALTER TABLE clinics ADD COLUMN open_time  VARCHAR(5);    -- "09:00"
ALTER TABLE clinics ADD COLUMN close_time VARCHAR(5);    -- "20:00"
ALTER TABLE clinics ADD COLUMN rating     FLOAT DEFAULT 0;

-- (2) EWT engine + edge cases
ALTER TABLE queue_entries ADD COLUMN complexity_weight INT DEFAULT 1;
ALTER TABLE queue_entries ADD COLUMN estimated_minutes INT;
ALTER TABLE queue_entries ADD COLUMN visit_type        VARCHAR(20);
ALTER TABLE queue_entries ADD COLUMN doctor_id         VARCHAR(100) DEFAULT 'chief';  -- E-04
ALTER TABLE queue_entries ADD COLUMN sort_key          FLOAT;                          -- E-02
ALTER TABLE queue_entries ADD COLUMN requeue_count     INT DEFAULT 0;                  -- E-02
CREATE INDEX ix_queue_clinic_doctor_status ON queue_entries (clinic_id, doctor_id, status);

-- (3) Chamber gate (E-01)
CREATE TABLE chamber_sessions (
    id UUID PRIMARY KEY, clinic_id VARCHAR(36), doctor_id VARCHAR(100),
    session_date DATE, opened_at TIMESTAMP NOT NULL, closed_at TIMESTAMP,
    UNIQUE (clinic_id, doctor_id, session_date)
);

-- (4) Slot booking (B5)
CREATE TABLE appointment_slots (...);

-- (5) Health Card audit + revoke (DPDP)
CREATE TABLE health_card_access (
    id UUID PRIMARY KEY, card_id UUID NOT NULL, accessed_by VARCHAR(200),
    ip_hash VARCHAR(64), accessed_at TIMESTAMP DEFAULT now()
);

-- (6) Growth loop + Module 6
CREATE TABLE clinic_leads (...);
ALTER TABLE clinics ADD COLUMN source VARCHAR(30) DEFAULT 'manual';
ALTER TABLE clinics ADD COLUMN source_url VARCHAR(500) DEFAULT '';
ALTER TABLE clinics ADD COLUMN verified BOOLEAN DEFAULT TRUE;
ALTER TABLE clinics ADD COLUMN claim_status VARCHAR(30) DEFAULT 'n/a';
ALTER TABLE clinics ADD COLUMN last_crawled_at TIMESTAMP;
CREATE TABLE doctor_crawl_runs (...);
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
| POST | `/api/v1/marketplace/book` | 1-tap booking → token + tracking link ⚠️ BUG-01 |
| POST | `/api/v1/marketplace/seed` | Demo clinics (token-gated) |
| GET | `/track/{token}` | Patient live tracking page |
| GET | `/track/{token}/status` | **8s polling JSON** ← E-03 ka base |
| GET | `/my/<token>` | Patient self-portal (BP/sugar/graphs/PDF) |
| GET | `/s/<token>` | Doctor read-only share (7 din) |
| GET | `/card/<uid>` | 🪪 Universal Health Card |
| POST | `/opd/api/health-card` | Doctor: card banao + WhatsApp link |
| GET | `/rx-pad` | 📝 Letterhead prescription pad |
| POST | `/opd/api/lab-order` | 🧪 External lab order |
| GET | `/lab/<token>` | Patient: lab result phone par |
| GET | `/abdm` + `/abdm/{status,fhir/Patient,fhir/Practitioner,consent,dhis/transactions}` | ABDM registry + FHIR + consent + DHIS |

### 4.2 📐 BANANE HAIN

| Method | Path | Kaam | Kahan |
|--------|------|------|-------|
| GET | `/api/v1/marketplace/doctors?open_now=1` | Sirf khuli clinics | `marketplace_routes.py` |
| GET | `/api/v1/marketplace/ewt?clinic_id=&doctor_id=` | EWT breakdown + chamber status | naya `ewt_routes.py` |
| GET | `/api/v1/slots?clinic_id=&date=` | Free slots + confidence | naya `slots_routes.py` |
| POST | `/api/v1/slots/book` | Slot → queue entry | same |
| POST | `/opd/api/chamber/open` · `/close` | ▶️ START OPD (chamber gate · E-01) | naya `chamber_routes.py` |
| POST | `/opd/api/queue/hold` · `/requeue` | Token HOLD → Next+1 (E-02) | same |
| POST | `/opd/api/chamber/next-arrival-alert` | "Doctor aa gaye" — ek tap me sab waiting patients ko | same |
| POST | `/opd/api/notify/leave-now` | Reception 1-click WhatsApp (E-03) | `opd_routes.py` helper |
| POST | `/card/{uid}/revoke` | 🔒 Link band karo (DPDP) | `health_card_routes.py` |
| GET | `/opd/api/queue-ewt` | Doctor Live View ka EWT feed | `opd_routes.py` |
| POST | `/api/v1/marketplace/invite` | Tier-2 → `clinic_leads` | `marketplace_routes.py` |
| POST | `/api/v1/ingest/doctors` | **Module 6 worker → app** (E2) | naya `ingest_routes.py` |
| POST | `/api/v1/ingest/claim/{clinic_id}` | Doctor profile claim | same |
| DELETE | `/api/v1/ingest/profile/{clinic_id}` | Opt-out (DPDP) | same |
| GET | `/abdm/fhir/Bundle/{patient_id}` | Poora record ek FHIR bundle me | `abdm_routes.py` |
| GET | `/abdm/dhis/claim-export` | DHIS incentive claim file | same |

---

## 5. 🔒 Guardrails — jo kabhi nahi todenge

| # | Rule | Kyun |
|---|------|------|
| 1 | **Sirf additive schema** — koi column rename/drop nahi (`ADD COLUMN IF NOT EXISTS`) | Live production SQLite par purana data bacha rahe |
| 2 | **`opd_routes.py` (3650+ lines) 🔒 LOCKED** — naya kaam naye module me | Sabse nazuk file |
| 3 | **Naya code live = `python pa_deploy.py ship --since <commit>`** | PA par files-API upload + reload + health |
| 4 | **Har deploy par BUILD stamp badle** | `/health` + dashboard footer se naya/purana turant pata chale |
| 5 | **PA free:** 100 CPU-sec/din · **no scheduled tasks (403)** · outbound sirf whitelist | Bhaari loop/cron PA par nahi chalega |
| 6 | **AI browser-side BYOK** — server se provider call PA par block hai | Har doctor apni key, owner ka ₹0 |
| 7 | **Patient data public nahi** — phone masked, uid unguessable, read-only share | DPDP Act 2023 |
| 8 | **Koi fake number nahi** — `_live_signal()` demo hata diya gaya | Bharosa = product |
| 9 | **Naya keyword/specialty = sirf `PROBLEM_TO_SPECIALTY` dict** | UI + API sync rahe |
| 10 | **Har feature ke saath ek test** (`tests/`, `scripts/integration_smoke_test.py`) | Live par todo mat |
| **11** | **Server cron nahi** — sab kuch **client-side** (patient browser) ya **GH Actions worker** | PA free ki majboori (E-03) |
| **12** | **Doctor absent = EWT band** — chamber gate ke bina countdown shuru nahi | Warna jhoota wait (E-01) |
| **13** | **HOLD → Next+1**, aakhir me nahi (max 1 free re-queue) | Mareez ka jhagda band (E-02) |
| **14** | **Har EWT strictly per `(clinic_id, doctor_id, service_code)`** | Do doctor ka queue kabhi mix nahi (E-04/E-09) |
| **15** | **Crawler = sirf public professional info** · robots.txt · rate limit · `source_url` · opt-out | Legal + DPDP (Part E) |

---

## 6. Build Order — ek-ek karke tick hoga

> Owner ka nirdesh: **queue/EWT pehle** (yahi asli moat hai), phir edge cases, phir slots, phir growth.

### 🐞 BLOCK 0 — BUG-01 fix (sabse pehle, 1 ghante ka kaam)

| # | Item | File | Effort |
|---|------|------|--------|
| BUG-01 | Token counter me `clinic_id` + `doctor_id` filter | `marketplace_routes.py` | XS |
| BUG-02 | `department` + `room` hardcode hatao | same | XS |
| BUG-03 | Is bug ke liye regression test | `tests/` | S |

### 🔴 BLOCK 1 — EWT Engine + Edge Cases (P0) — *"Uber ETA for OPD"*

| # | Item | File | Effort |
|---|------|------|--------|
| EWT-01 | `ewt.py` — rolling avg + complexity + estimate + confidence | **naya** `src/domain/queue/ewt.py` | M |
| EWT-02 | `complexity_weight` · `estimated_minutes` · `visit_type` · `doctor_id` · `sort_key` · `requeue_count` | model + migration | S |
| EWT-03 | `MINUTES_PER_PATIENT` hardcode → `estimate_wait()` | `marketplace_routes.py` | S |
| EWT-04 | Booking par EWT snapshot save | same | S |
| EWT-05 | Doctor Live View: EWT + delay badge 🟡/🔴 | `templates/opd/dashboard.html` | M |
| EWT-06 | Patient page par EWT breakdown ("3 aage × ~6 min") | `marketplace.html` + `/track` | S |
| **E-01** | **Chamber gate** — ▶️ START OPD + `chamber_sessions` + "Arrival Pending" | naya `chamber_routes.py` | M |
| **E-02** | **HOLD → Next+1** (`sort_key` midpoint + HOLD status + abuse guard) | `queue_status.py` + queue routes | M |
| **E-04** | **`doctor_id` partition** + token prefix (C-14 / G-14) | model + `marketplace_routes.py` | M |
| EWT-07 | Unit tests: formula, chamber gate, hold-return, partition | `tests/test_ewt_calculation.py` | M |

### 🟠 BLOCK 2 — Availability + Alert (P1)

| # | Item | File | Effort |
|---|------|------|--------|
| AVL-01 | `open_time`/`close_time`/`rating` + admin form | clinic model + `onboard_doctor.html` | M |
| AVL-02 | "🟢 Abhi khula hai" filter + `availability: OPEN/CLOSED` | `marketplace_routes.py` | S |
| AVL-03 | Distance sort + "mere paas" button | `marketplace.html` | S |
| **E-03** | **Departure alert client-side** (chime + "AB NIKLO") | `patient_track.html` + public status API | M |
| **E-03b** | Reception 1-click WhatsApp (green icon) | reception dashboard + `staff_routes.py` | S |
| E-06 | Holiday / closed day flag | clinic model + marketplace | S |
| E-07 | No-show auto-detect (8 min) + EWT recompute | queue routes | S |

### 🟡 BLOCK 3 — Slots + Doctor Live View (P1)

| # | Item | File | Effort |
|---|------|------|--------|
| SLT-01 | `appointment_slots` + CRUD | model + migration | M |
| SLT-02 | Slot booking API (capacity check → queue entry) | naya `slots_routes.py` | M |
| SLT-03 | Doctor dashboard slot grid + EWT confidence | `dashboard.html` | M |
| E-08 | Emergency override (`#E-1` + siren) | queue routes + dashboard | M |

### 🔵 BLOCK 4 — Retention + Growth (P2)

| # | Item | File | Effort |
|---|------|------|--------|
| GRW-01 | `health_card_access` audit + `/card/{uid}/revoke` (DPDP) | `health_card_routes.py` | S |
| GRW-02 | `clinic_leads` + Tier-2 "📢 Invite" + Admin pipeline | marketplace + admin | M |
| GRW-03 | City SEO pages `/doctors/<city>` | naya route | S |
| GRW-04 | Family Health Locker (1 mobile → N profiles) | portal | L |

### 🟣 BLOCK 5 — Module 6: Ingestion (P2, alag worker)

| # | Item | File | Effort |
|---|------|------|--------|
| M6-01 | GH Actions worker: crawl4ai + Chromium + Gemini extraction | **naya repo/`workers/`** | L |
| M6-02 | `DoctorProfileSchema` + array wrapper + model-discovery fallback | worker | S |
| M6-03 | `POST /api/v1/ingest/doctors` + claim + opt-out | naya `ingest_routes.py` | M |
| M6-04 | `clinics` crawl columns + `doctor_crawl_runs` | model + migration | S |
| M6-05 | Tier-2 "public listing" label + claim button | `marketplace.html` | S |

### ⚫ BLOCK 6 — Compliance wiring (P0, credentials ka intezaar)

| # | Item | File | Effort |
|---|------|------|--------|
| ABD-01 | ABDM sandbox HFR + HPR register | `abdm_routes.py` | M |
| ABD-02 | ABHA create + link live | same | M |
| ABD-03 | FHIR Bundle export (offline bhi ban sakta hai ✅) | `fhir.py` + routes | M |
| ABD-04 | DHIS claim export (incentive 💰) | `abdm_routes.py` | S |
| ABD-05 | NHA Milestone certification apply | docs | M |

> ⚠️ **ABD-01 se aage credentials ke bina nahi badh sakte** — `ABDM_CLIENT_ID` / `ABDM_CLIENT_SECRET`
> (NHA sandbox) chahiye. Tab tak **ABD-03 offline FHIR export** ban sakta hai.

---

## 7. Success Metrics (North Star)

| Metric | Aaj | 90-din target |
|--------|-----|---------------|
| Doctor search → booking conversion | — | ≥ 15% |
| Partner clinics with live feed | 1 (GIL CLINIC) | 100% |
| Average patient wait (partner) | ~60 min (industry) | **< 15 min** |
| **EWT accuracy (actual vs predicted)** | — | **± 5 min** |
| **Ghost wait (doctor absent me jhoota EWT)** | — | **0** |
| Health Card share rate | — | ≥ 20% visits |
| Tier-2 listings (Module 6 se) | 8 (demo) | 500+ |
| Tier-2 → Tier-1 upgrade | 0 | ≥ 5% / month |
| No-show rate | — | < 10% |

---

## 8. Ek line me

> **Part A patient ko sahi doctor dikhata hai. Part B doctor ko sahi patient deta hai.
> Part C dono ko jodta hai. Part D use asli duniya me chalne layak banata hai —
> aur Part E naye doctors khud laata hai.** 🟢

---

*Files referenced in this blueprint (verified 02-Oct-2026):*
`marketplace_routes.py` · `health_card_routes.py` · `abdm_routes.py` · `fhir.py` · `lab_network_routes.py` ·
`rx_pad_routes.py` · `staff_routes.py` (`/track/{token}` + 8s polling) · `queue_entry_model.py` · `clinic_model.py` ·
`queue_status.py` (asli status list) · `ghos/services/queue-engine/app/engine/{priority,delay,queue_engine}.py` ·
`main_v2.py` · `templates/{marketplace,patient_track,health_card,landing,opd/dashboard}.html` ·
`DEEP_RESEARCH_PRODUCT_DEVELOPMENT.md` · `PRODUCT_UPGRADATION_UBER_HEALTHCARE.md` ·
`COMPETITOR_GAP_ANALYSIS_MISSING_FEATURES.md` · `MEMORY.md` (§2 PA limits)
