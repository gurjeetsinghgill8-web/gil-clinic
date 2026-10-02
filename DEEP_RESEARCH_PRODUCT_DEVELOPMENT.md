# 🔬 Deep Research & Product Development File — GIL CLINIC (GHOS)

> **Owner:** Gurjas Singh Gill
> **Product:** Gill Hospital OS (GHOS) — GIL CLINIC
> **Version:** 3.0
> **Status:** ✅ Research + Build (Find a Doctor marketplace shipped in `main_v2.py`)
> **Scope:** Three patient-growth features — (1) Geolocation **Find a Doctor**, (2) **Doctor's Live View**, (3) Shareable **Health Card**.

---

## 0. TL;DR — What this file delivers

| # | Deliverable | Where it lives | Status |
|---|-------------|----------------|--------|
| 1 | **Find a Doctor** marketplace (city + specialty + problem search, two-tier ranking) | `src/presentation/marketplace/` + `templates/marketplace.html` + routes in `main_v2.py` | ✅ **BUILT** |
| 2 | **Data schema** for geolocation search, availability, queue, health card | §6 below (SQL) | 📐 Ready to migrate |
| 3 | **Doctor's Live View** wireframe (queue, slots, EWT) | §4 below | 📐 Spec |
| 4 | **Health Card** feature specification (shareable digital link) | §5 below | 📐 Spec (portal already has share links) |
| 5 | Deep market research + roadmap | §2, §7 | ✅ |

---

## 1. The Business Problem (why these three features matter)

GHOS already runs the *clinical* side of a clinic — queue, OPD, pharmacy, lab, AI. What it is missing is the **patient-acquisition flywheel**: a way for a patient standing in Jodhpur/ Ahmedabad/ Jaipur to *find* the clinic, see that it is *alive right now*, and walk in with zero waiting.

That is exactly the "Uber/Ola for OPD" insight:

> **Traditional booking apps show a name and a time-slot. We show a live queue and a countdown.**

Three features form the loop:

```
Find a Doctor  →  Book / walk-in  →  Doctor's Live View  →  Health Card (share → next patient)
   (growth)          (conversion)       (delivery + trust)        (retention + virality)
```

---

## 2. Deep Research — Market & Competitive Landscape

### 2.1 Where the incumbent players fail

| Player | What they do | The gap GHOS exploits |
|--------|--------------|------------------------|
| **Practo / Lybrate** | Static directory + appointment booking | No **live queue**, no "walk in now at token #17". Booking ≠ shorter wait. |
| **QMe / DocPulse** | Clinic queue on tablets | Single-clinic, no **patient-facing city marketplace**. |
| **Google Maps / JustDial** | Directory + reviews | No real-time **chamber status**; data is stale. |
| **Phone-call booking** | The default in Tier-2 India | Zero visibility, patient has no idea how long they'll wait. |

**The white space:** nobody combines a **public, city-level doctor directory** with **live queue telemetry** and a **portable patient health card**. That is the "12 innovations" moat described in `PRODUCT_UPGRADATION_UBER_HEALTHCARE.md`.

### 2.2 Why geolocation is table-stakes but not the moat

- Patients filter by **city** far more than by GPS-distance (India is city-anchored).
- GPS matters at the **last mile**: "how far from my location is this clinic, and should I leave now?"
- The *real* moat is **proximity + live wait**: "3 patients ahead → 15 min drive → leave now for zero wait."

### 2.3 Unit economics of the two-tier ranking

| Tier | Who | Cost to serve | Revenue lever |
|------|-----|---------------|---------------|
| **Tier 1 — Partner clinics** (active SaaS license) | Paying GHOS customers | ~₹0 marginal (data already in queue engine) | Renewals + upgrades |
| **Tier 2 — Directory listings** (non-network) | Everyone else | ~₹0 (public info) | **Growth loop**: patient demand "nudges" them to buy the SaaS |

This is the classic **marketplace flywheel**: free listings create demand data; demand data converts listings into paying partners.

### 2.4 Research sources & signals

- Indian OPD wait-time studies consistently report **60–120 min average wait**; GHOS targets **< 15 min** via live EWT (see `1200_ROADMAP.md` North Star metric).
- **WhatsApp-first**: > 95% smartphone penetration but low native-app install intent for health; hence the **zero-app PWA + deep-link** strategy (already live in `patient-pwa/` and `/my/<token>`).
- **DPDP Act 2023** compliance is mandatory for the Health Card share (see §5.4 consent).

---

## 3. Feature 1 — Find a Doctor (Geolocation Marketplace) — ✅ BUILT

### 3.1 User flow

```
Landing (/)  →  "Find a Doctor"  →  /find-doctor
   → type problem ("seene me dard") OR pick city + specialty
   → two-tier results, partner clinics on top with LIVE QUEUE
   → Book Token / Call / Directions  (or "Invite to Live Queue" for Tier 2)
```

### 3.2 Ranking algorithm (business advantage)

1. **Filter:** `city`, `specialty`, and plain-language `problem` (keyword → specialty map).
2. **Rank:** `is_license_active DESC` (partners first), then `doctor_name ASC`.
3. **Live signal** (partner only): serving token, patients-ahead, estimated wait, chamber.

### 3.3 Implementation map (what shipped)

| Component | Path | Role |
|-----------|------|------|
| Public API | `src/presentation/marketplace/routes/marketplace_routes.py` | `GET /api/v1/marketplace/doctors`, `.../meta` |
| Page route | `.../marketplace_routes.py` | `GET /find-doctor` |
| UI | `templates/marketplace.html` | Mobile-first marketplace |
| Wiring | `main_v2.py` | router registered + `/find-doctor` link on landing |

> **Honesty note:** the live token/wait numbers are currently a **deterministic demo signal** (stable hash of clinic id) because the per-clinic live queue feed is not yet exposed. The function is isolated in `_live_signal()` so it can be swapped for a real `queue_entries` read without touching the UI.

---

## 4. Feature 2 — Doctor's Live View (Wireframe + Spec)

The doctor's half of the loop. It already partially exists in the OPD dashboard; this is the **target wireframe** unifying queue + slots + EWT.

```
┌────────────────────────────────────────────────────────────────────────┐
│ 🏥 Dr. G.S. Gill  ·  Cardiology  ·  Room 2            [🔴 IN CHAMBER]  │
│ ────────────────────────────────────────────────────────────────────── │
│ ┌──────────────┬───────────────────────────────┬─────────────────────┐ │
│ │ 📞 Quick Look│  LIVE QUEUE (real-time)       │  SLOTS / EWT        │ │
│ │  [10-digit  ]│  #14 in room · 3 ahead        │  🟢 ~18 min wait    │ │
│ │  [ 🔍 Search]│  ████░░░░░░ 4/7 done          │  📅 2:00 ▢ 2:30 ▣  │ │
│ │  (500ms)     │                               │  3:00 ▢ 3:30 ▣     │ │
│ ├──────────────┴───────────────────────────────┴─────────────────────┤ │
│ │  [▶ CALL NEXT]   [⏸ HOLD]   [↪ SEND TO ECG]   [✓ COMPLETE]          │ │
│ └─────────────────────────────────────────────────────────────────────┘ │
│  👤 Now: Token #14 · Ramesh (45M) · Follow-up · 3-line AI brief ▸       │
└────────────────────────────────────────────────────────────────────────┘
```

**Key components (with data source):**

| Component | Data | Existing? |
|-----------|------|-----------|
| Top header QR/mobile quick-lookup | `patients` by `mobile` | ✅ OPD dashboard |
| Live queue + call-next | `queue_entries` | ✅ Queue Engine |
| Estimated wait per patient | EWT engine (complexity-weighted) | 📐 `PRODUCT_UPGRADATION_UBER_HEALTHCARE.md` §EWT |
| Appointment slots | `appointment_slots` (new table, §6) | 📐 New |
| 3-line AI clinical brief | AI triage/pre-consult | 📐 Phase 5 AI (blueprint exists) |

---

## 5. Feature 3 — Shareable "Health Card" (Feature Specification)

### 5.1 What it is

A **portable, verified digital summary** of a patient's history + test results, addressable by a **unique link / QR**:

```
/track/:token   (queue status)        ← exists
/my/:token      (patient self-portal) ← exists
/card/:uid      (UNIVERSAL HEALTH CARD) ← NEW
```

### 5.2 Card contents

| Section | Source | Sensitive? |
|---------|--------|------------|
| Identity + photo + DOB/blood group | `patients` | ✅ masked |
| Allergies & active medications | `opd_drug_history`, allergies | ✅ |
| Diagnoses timeline | `opd_prescriptions` | ✅ |
| Vital timeline (BP/SpO₂/weight) | `patient_readings` (portal) | ✅ |
| Test results (ECG/Echo/Lab) + graphs | clinical modules | ✅ |
| Emergency contact | `patients` | ✅ |

### 5.3 The unique digital link

- **`GET /card/:uid`** → renders the card; `uid` is an unguessable UUID (not sequential).
- **Access control:** same 10-digit mobile-verification gate the portal already uses (`phone_last4` lock).
- **Doctor share:** read-only, time-limited link (mirrors existing `/s/<token>` share links with `share_days`).
- **WhatsApp 1-click share:** deep link `https://…/card/<uid>` with a sanitized preview.

### 5.4 Consent & compliance (mandatory)

- Share requires **explicit patient consent** (already the UX in `patient_portal.html`).
- **DPDP Act 2023**: purpose limitation, data minimisation, right to revoke (add a "revoke link" action).
- Logs: every share/view written to `audit_logs` (`0803_AUDIT_LOG.md`).

---

## 6. Data Schema (SQL) — the new/changed tables

Below extends the existing `supabase_schema.sql`. Only **additive** changes; nothing existing breaks.

### 6.1 `clinics` — add geolocation + availability + partner flags

```sql
ALTER TABLE clinics ADD COLUMN latitude       DOUBLE PRECISION;
ALTER TABLE clinics ADD COLUMN longitude      DOUBLE PRECISION;
ALTER TABLE clinics ADD COLUMN open_time      TIME;           -- e.g. 09:00
ALTER TABLE clinics ADD COLUMN close_time     TIME;           -- e.g. 20:00
ALTER TABLE clinics ADD COLUMN is_partner     BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE clinics ADD COLUMN rating         NUMERIC(2,1)   DEFAULT 0;
CREATE INDEX ix_clinics_city     ON clinics (city);
CREATE INDEX ix_clinics_specialty ON clinics (specialty);
```

### 6.2 `appointment_slots` — doctor availability (Feature 2)

```sql
CREATE TABLE appointment_slots (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id     UUID NOT NULL REFERENCES clinics(id),
    doctor_id     UUID REFERENCES users(id),
    slot_date     DATE NOT NULL,
    start_time    TIME NOT NULL,
    end_time      TIME NOT NULL,
    capacity      INT  NOT NULL DEFAULT 1,
    booked        INT  NOT NULL DEFAULT 0,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (clinic_id, doctor_id, slot_date, start_time)
);
```

### 6.3 `queue_entries` — add EWT columns (live view + marketplace)

```sql
ALTER TABLE queue_entries ADD COLUMN complexity_weight INT DEFAULT 1;
-- 1 = follow-up (~6 min) · 2 = new visit (~15 min) · 3 = report review (~5 min)
ALTER TABLE queue_entries ADD COLUMN estimated_minutes INT;
ALTER TABLE queue_entries ADD COLUMN started_at  TIMESTAMPTZ;
ALTER TABLE queue_entries ADD COLUMN completed_at TIMESTAMPTZ;
```

### 6.4 `health_cards` — the universal health passport (Feature 3)

```sql
CREATE TABLE health_cards (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uid           VARCHAR(64) NOT NULL UNIQUE,          -- unguessable share token
    patient_id    UUID NOT NULL REFERENCES patients(id),
    clinic_id     UUID NOT NULL REFERENCES clinics(id),
    snapshot_json JSONB,                                 -- denormalised card payload
    status        VARCHAR(20) NOT NULL DEFAULT 'active', -- active | revoked | expired
    expires_at    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE health_card_access (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id       UUID NOT NULL REFERENCES health_cards(id),
    accessed_by   VARCHAR(200),      -- doctor name / phone hash
    accessed_at   TIMESTAMPTZ DEFAULT now(),
    ip_hash       VARCHAR(64)
);
```

### 6.5a ABDM / National compliance (GAP-01 → GAP-05)

```sql
-- ABHA health ID on the patient record
ALTER TABLE patients ADD COLUMN abha_id VARCHAR(20);
-- HPR (doctor) + HFR (facility) registry IDs
ALTER TABLE clinics ADD COLUMN hpr_id VARCHAR(50);
ALTER TABLE clinics ADD COLUMN hfr_id VARCHAR(50);

-- Consent artefacts (DPDP + ABDM consent manager)
CREATE TABLE consent_artefacts (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id  UUID NOT NULL REFERENCES patients(id),
    purpose     VARCHAR(100),
    hip_id      VARCHAR(50),
    granted_at  TIMESTAMPTZ DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
```

### 6.5 Geolocation distance (Postgres)

```sql
-- once lat/long are populated:
SELECT *, ( 6371 * acos( cos(radians(:lat)) * cos(radians(latitude))
        * cos(radians(longitude) - radians(:lon))
        + sin(radians(:lat)) * sin(radians(latitude)) ) ) AS distance_km
FROM clinics ORDER BY is_partner DESC, distance_km ASC;
```

---

## 7. Roadmap (18-month, grounded)

| Phase | Window | Milestone | Ship |
|-------|--------|-----------|------|
| **P0 — Marketplace** | Now | Find a Doctor page + API + landing link | ✅ done |
| **P0.5 — Live feed** | Next 2 weeks | Replace `_live_signal()` demo with real `queue_entries` read | backend |
| **P0.6 — Compliance moat** | Weeks 2–8 | ABDM (ABHA/HPR/HFR/HIP-HIU/Consent) + FHIR R4 + NHA approval + DHIS incentive — **GAP-01 → GAP-05** | `COMPETITOR_GAP_ANALYSIS_MISSING_FEATURES.md` |
| **P1 — Availability** | Month 1 | Add `open_time`/`close_time` + "open now" filter | schema §6.1 |
| **P1 — Geofence** | Month 1–2 | Lat/long per clinic + distance sort + "leave now" alert | schema §6.5 |
| **P2 — Slots + EWT** | Month 2–3 | `appointment_slots` + complexity-weighted EWT in Doctor's View | §6.2/6.3 |
| **P2 — Health Card** | Month 3–4 | `/card/:uid` universal card + QR + consent/revoke | §6.4 |
| **P3 — Flywheel** | Month 4–6 | Tier-2 "invite to Live Queue" → onboarding pipeline (admin) | loop |
| **P4 — Growth** | Month 6+ | WhatsApp deep links, family locker (1 number → N profiles) | loop |

---

## 8. Success Metrics (North Star)

| Metric | Baseline | 90-day target |
|--------|----------|---------------|
| Doctor search → booking conversion | — | ≥ 15% |
| Partner clinics with live feed | 0 | 100% onboarded |
| Avg patient wait (partner) | ~60 min | < 15 min |
| Health Card share rate | — | ≥ 20% of visits |
| Tier-2 → Tier-1 upgrade rate | — | ≥ 5% / month |

---

## 9. Competitor Gap Analysis — Numbered Missing-Features Register

Competitors (EKA DOC · Tatvacare · VCDoctor) ki marketing se collect karke compare kiya gaya. **Full numbered register** (GAP-01 → GAP-15, har item ek-ek tick hoga) alag file me hai:

> 📄 **`COMPETITOR_GAP_ANALYSIS_MISSING_FEATURES.md`**

### Summary (priority-wise)

| Block | GAP# | Theme | Priority |
|-------|------|-------|----------|
| 🔴 Compliance | 01–05 | ABDM core, FHIR R4, NHA approval, ABHA/Health Locker, **DHIS govt incentive** | P0 |
| 🟠 Clinical parity | 06–10 | Smart Rx pad, AI scribe, teleconsult, external lab network, patient engagement | P1 |
| 🟡 Records | 11–12 | FHIR-native EMR, IPD | P2 |
| 🟡 Growth/trust | 13–15 | Analytics, PubMed journals, ISO/AWS security posture | P2 |

> **Verdict:** sabse bada missing = **ABDM/FHIR/NHA compliance** (teeno competitors ka headline). Yeh **government DHIS incentive + trust + tender eligibility** deta hai — isliye ab compliance pehle, clinical baad me. Abhi **no code**; aap bolo to GAP-01 se shuru karte hain.

---

*"Queue First. Patient Always. AI Assist."*
