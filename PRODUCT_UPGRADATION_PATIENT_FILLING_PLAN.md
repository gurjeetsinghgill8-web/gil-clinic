# GIL CLINIC (GHOS v2) — Product Upgradation Plan
## Patient Self-Filling System (Patient Portal + Trends + Reports + "Doctor ko bhejo" link) — Smart OPD me

| | |
|---|---|
| **Version** | 1.0 (Plan → then Phase-wise implementation) |
| **Date** | 17-Sep-2026 |
| **Scope** | Smart OPD (`/opd`) ke andar **patient khud apni BP / sugar / pulse / weight / temp readings bhare**, trends/graph dekhe, file download kare, aur **kisi bhi doctor ko read-only link** bhej sake |
| **Source system (reference)** | CLINICITY OPD (`C:\Users\pc\Desktop\gurjas ai\newmcg nano clinic`) — v0.8.0 me yahi system doctor ne approve kiya |
| **Target system** | GIL CLINIC / GHOS v2 — FastAPI + Jinja2 + SQLAlchemy (`main_v2.py`, `/opd` router) |
| **Status** | ✅ **Phase 1–3 IMPLEMENTED (17-Sep-2026)** — patient portal + graphs + PDF/HTML/CSV + "Doctor ko bhejo" read-only link + doctor ka Patient Monitor tab. Tests: **10 pytest + 30 browser checks (Playwright) sab green**. Neeche §16 me exact files aur verification. |

---

## 0. TL;DR — सार (Executive Summary)

**Doctor ki demand:**
1. CLINICITY wala **patient filling system** yahan (GIL CLINIC) ke **Smart OPD** me bhi chahiye.
2. Patient apne phone se apni **BP / sugar / pulse / weight / temperature** bhare — ghar baithe.
3. Patient ko **graphs** dikhein (bade, saaf) aur **poora record** ek jagah (Excel-style).
4. Patient wo record **download** kar sake (PDF / HTML / CSV) — **graph ke saath**.
5. Patient apna record **kisi bhi doctor ko dikha sake** — ek link se, bina app/password.

**Jo banega (1 line me):** Smart OPD me ek naya **Patient Portal** — WhatsApp par bheja gaya **secret link** (`/my/<token>`) → patient ghar se readings bharta hai → **trends + graphs + Excel-style table** dikhte hain → **PDF/HTML/CSV download** → ek button se **read-only "doctor share" link** (`/s/<token>`, 7 din valid) jo **koi bhi doctor apne browser me khol sakta hai** (na app, na PIN, na login).

**Iska core design rule (jo CLINICITY me doctor ko pasand aaya):**
> **Patient ka data patient ke paas bhi rahe, doctor ke paas bhi.**
> Patient self-report karta hai (home tracking), doctor dekhta hai aur apna clinical decision **khud** leta hai. AI/portal kabhi doctor ka prescription nahi badalta.

**Zero naya kharcha:** koi nayi API key, koi paid service nahi. Sab kuch maujooda stack (FastAPI + SQLite/Postgres + Jinja2 + fpdf2) me banega. Patient portal AI use nahi karta — sirf values, ranges aur graphs.

---

## 1. Aaj ka system — Deep Review (GIL CLINIC / Smart OPD)

### 1.1 Jo pehle se maujood hai (isme hum kaam karenge)

| Layer | Technology | File / jagah |
|---|---|---|
| App | **FastAPI monolith** | `main_v2.py` (router include + `Base.metadata.create_all`) |
| Smart OPD | **APIRouter prefix `/opd`** | `src/presentation/opd/routes/opd_routes.py` (~3638 lines) |
| Doctor UI | **Ek hi bada HTML** (vanilla JS + tabs) | `templates/opd/dashboard.html` (~5285 lines, 292 KB) |
| Login | PIN → signed cookie `opd_session` (itsdangerous) | `_create_opd_session()` / `_require_opd_session()` |
| DB | SQLite (`cardioqueue.db`) dev me, PostgreSQL Railway par | `src/shared/infrastructure/database.py` |
| Models | `patients`, `queue_entries`, `opd_prescriptions`, `opd_lab_reports`, `opd_settings`, licences… | `src/infrastructure/**/models/*.py` |
| PDF | **fpdf2** (`make_rx_pdf`, `make_cme_pdf`) | `src/utils/pdf_generator.py` |
| Static | `/static` mount (`static/` folder) | `main_v2.py` line ~426 |
| Templates | Jinja2 `FileSystemLoader('templates')` | `_render()` (opd_routes) / `_render_template()` (main_v2) |
| **Public patient page** | **`GET /track/{token}`** — signed token, koi login nahi | `staff_routes.py` (public_router) — lab/token tracking |
| WhatsApp base URL | `APP_BASE_URL` (tunnel/Railway URL) | `.env` → `_tracking_base(request)` |
| Tests | pytest (`tests/`) | `tests/test_queue_workflow.py` etc. |

### 1.2 Jo **already** patient-facing hai (aur usse hum kya seekh sakte hain)

`GET /track/<token>` — patient ko WhatsApp par bheja gaya **signed token** link, jisme wo apne lab/token ka status dekh sakta hai (8s polling). Yeh pattern **exactly** wahi hai jo patient portal ko chahiye:

```python
_track_signer = URLSafeSerializer(SECRET_KEY, salt="patient-public-track-v1")
make_tracking_token(patient_id)          # → signed token
decode_tracking_token(token)             # → patient_id
tracking_url = f"{base}/track/{token}"   # WhatsApp message me
```

**Natija:** humein koi naya auth system nahi banana padta — wahi signed-token mechanism use karenge, bas **naye salt** ke saath (taaki lab-tracking link aur self-filling link alag-alag revoke/expire ho sakein).

### 1.3 Jo **nahi** hai (yahi gap hai — aur yahi is plan ka kaam hai)

| # | Cheez | Aaj ki sthiti | Chahiye |
|---|---|---|---|
| 1 | Patient khud readings bhare | ❌ sirf reception/doctor bharti hai (`/api/register`, vitals text field) | ✅ patient apne phone se BP/sugar/pulse/weight/temp bhare |
| 2 | Readings **structured** (per-metric) | ❌ `vitals` sirf **ek text line** hai (`"BP 140/90, Pulse 82"`) | ✅ har value alag row (code + value + unit + time + status) |
| 3 | Trend graphs | ⚠️ lab-intel tab me lab values ke charts hain, vitals ke nahi | ✅ har metric ka graph (normal-range band + labels) |
| 4 | Patient ko download | ❌ kuch nahi | ✅ PDF + HTML (graph ke saath) + CSV |
| 5 | Patient → kisi bhi doctor share | ❌ kuch nahi | ✅ read-only link `/s/<token>` (7 din) |
| 6 | Doctor ko patient ke self-readings dikhein | ❌ vitals text ke alawa kuch nahi | ✅ naya "Patient Monitor" tab + New Rx screen par link button |

---

## 2. Kya banega — Feature Parity Table (CLINICITY v0.8.0 ↔ GIL CLINIC)

| # | Feature (CLINICITY me approved) | GIL CLINIC me kaise aayega |
|---|---|---|
| 1 | Patient portal (`#patient/<token>`) — BP/pulse/SpO₂/weight/temp/sugar + custom field | **`GET /my/<token>`** page + `POST /my/<token>/readings` API |
| 2 | Phone verification lock (registered mobile ka last 10 digit) | **`POST /my/<token>/verify`** (`patient.phone_hash` already DB me hai!) |
| 3 | "Aaj ki readings" Excel-sheet style entry + "+ Add field" | Same UI (Jinja template + JS), custom label/unit support |
| 4 | Red-flag guidance (BP 160+, sugar critical) | `flag_reading()` (Python) + Hinglish guidance text |
| 5 | Bade trend graphs (320×160 viewBox, green normal band, value + date labels) | **Server-side SVG builder** (Python) — ek hi source of truth, screen aur file dono me |
| 6 | Excel-style pivot table (BP 135/85 ek column) | `pivot_readings()` (Python) → portal table + reports |
| 7 | Download HTML (graph inline) | `GET /my/<token>/export?fmt=html` (server-rendered, SVG andar hi) |
| 8 | Download **PDF** (vector graphs, WhatsApp-friendly) | `GET /my/<token>/export?fmt=pdf` — **fpdf2** se vector lines/dots |
| 9 | Download CSV (Excel) | `GET /my/<token>/export?fmt=csv` |
| 10 | Appointment request → doctor reply | **Phase 3** — `patient_requests` table + OPD dashboard me reply (queue system chhua nahi jayega) |
| 11 | **"Doctor ko bhejo" read-only share link** (7 din, print/PDF) | **`GET /s/<token>`** + `POST /my/<token>/share` (snapshot + expiry) |
| 12 | Doctor side: patient link banake WhatsApp bhejna | OPD dashboard: patient select karte hi **"📱 Patient link"** button + WhatsApp text |
| 13 | Doctor side: patient ke self-readings dekhna | Naya tab **"🩺 Patient Monitor"** (list → expand → trends + report download) |

---

## 3. Architecture (naya kya judega)

```
┌───────────────────────────────────────────────────────────────────────────────┐
│                          GIL CLINIC  (main_v2.py)                             │
│                                                                               │
│  DOCTOR SIDE (login)                        PATIENT SIDE (no login, token)    │
│  ┌───────────────────────────────┐          ┌───────────────────────────────┐ │
│  │ /opd/dashboard                │          │ /my/<token>   → self-filling  │ │
│  │  ├ New Rx  (+"Patient link")  │  link    │   ├ readings bharna           │ │
│  │  ├ 🩺 Patient Monitor  (NEW)  │ ───────▶ │   ├ trends/graphs (SVG)       │ │
│  │  └ Reports: PDF/HTML/CSV      │ WhatsApp │   ├ download PDF/HTML/CSV     │ │
│  │                               │          │   └ "Doctor ko bhejo" → /s/…  │ │
│  │ /opd/api/patient-link   (NEW) │          └───────────────────────────────┘ │
│  │ /opd/api/patient-readings(NEW)│                                            │
│  └───────────────────────────────┘          ┌───────────────────────────────┐ │
│                                             │ /s/<token>  READ-ONLY snapshot│ │
│                                             │  (koi bhi doctor khol sakta   │ │
│                                             │   hai — app/PIN nahi)         │ │
│                                             └───────────────────────────────┘ │
│                                                                               │
│  DB (SQLite / PostgreSQL):                                                    │
│   patient_readings        ← har value (code, value, unit, dateTime, status)    │
│   patient_portal_links    ← kaun sa patient, kaun sa token, active/expiry      │
│   patient_shares          ← read-only snapshot (JSON) + expiry (7 din)         │
└───────────────────────────────────────────────────────────────────────────────┘
```

**Best practice jo hum follow karenge:** portal ka data **structured** rahega — is liye ek hi baar bhara hua BP aage 4 jagah kaam aayega:
1. Patient ke graph me, 2. Doctor ke Patient Monitor tab me, 3. Reports (PDF/HTML/CSV) me, 4. (Phase 4) ghar ke BP ka average seedha prescription print par.

---

## 4. Data Model (nayi tables — sab automatic ban jayengi)

`main_v2.py` startup par `Base.metadata.create_all()` chalta hai aur SQLite ke liye ek **auto column migrator** bhi hai (`_migrate_sqlite_columns`). Is liye: **nayi table = bas model likho, server restart = table ready.** Koi manual SQL nahi.

```sql
-- 1) Patient ki har self-reported (ya clinic) reading — per-metric row
patient_readings
  id            INTEGER PK
  clinic_id     TEXT NULL
  patient_id    TEXT   NOT NULL   (patients.patient_id se link)
  code          TEXT   NOT NULL   ('bp-systolic', 'bp-diastolic', 'pulse', 'spo2',
                                   'weight', 'temperature', 'rbs', 'fbs', 'ppbs',
                                   'hba1c', 'tsh', 'hb', 'creatinine', 'ldl', 'custom')
  label         TEXT   NOT NULL   (screen par dikhne wala naam, e.g. "Hemoglobin")
  unit          TEXT   NOT NULL   ('mmHg', 'mg/dL', 'g/dL' …)
  value         REAL   NOT NULL
  date_time     TEXT   NOT NULL   (ISO — reading ka waqt, save ka nahi)
  source        TEXT   NOT NULL   ('patient' | 'clinic')
  status        TEXT   NOT NULL   ('ok' | 'low' | 'high' | 'critical')
  note          TEXT   NULL
  created_at / updated_at
  INDEX (patient_id, date_time), INDEX (patient_id, code)

-- 2) Patient ka secret portal link (WhatsApp par bhejne ke liye)
patient_portal_links
  id            INTEGER PK
  token         TEXT UNIQUE NOT NULL   (secrets.token_urlsafe(24))
  patient_id    TEXT NOT NULL
  patient_name  TEXT NOT NULL DEFAULT ''
  phone_last4   TEXT NULL              (verify screen par hint)
  active        INTEGER NOT NULL DEFAULT 1
  created_by    TEXT NOT NULL DEFAULT ''  (doctor_id)
  created_at    DATETIME, last_used_at DATETIME NULL
  use_count     INTEGER NOT NULL DEFAULT 0

-- 3) Read-only "Doctor ko bhejo" snapshot (7 din)
patient_shares
  id            INTEGER PK
  token         TEXT UNIQUE NOT NULL
  patient_id    TEXT NOT NULL
  patient_name  TEXT NOT NULL DEFAULT ''
  note          TEXT NOT NULL DEFAULT ''     (patient ka message)
  payload_json  TEXT NOT NULL DEFAULT '{}'   (readings + appointments ka snapshot)
  expires_at    DATETIME NOT NULL
  created_at / updated_at DATETIME
  view_count    INTEGER NOT NULL DEFAULT 0

-- 4) (Phase 3) Patient ki appointment / follow-up request + doctor ka reply
patient_requests
  id, patient_id, patient_name, phone, message, status('requested'|'confirmed'|'declined'),
  reply_date, reply_note, created_at, updated_at
```

**Kyun snapshot (live query nahi)?** Share link wo doctor kholta hai jiske paas **login nahi** hai. Is liye `/s/<token>` par sirf ek **freeze ki hui copy** dikhani safe hai — token hi secret hai, aur 7 din baad apne aap band. (Yeh exactly CLINICITY me kiya hai, aur wahan doctor ne approve kiya.)

---

## 5. API Surface (naye endpoints)

### 5.1 Patient side — public, token = secret (koi login nahi)

| Method | Path | Kaam |
|---|---|---|
| GET | `/my/{token}` | Patient portal page (HTML) — pehle phone-verify screen, phir entry + trends |
| POST | `/my/{token}/verify` | Registered mobile ke last-10 digit match (session cookie set) |
| GET | `/my/{token}/data` | Patient ka naam + saari readings (JSON) |
| POST | `/my/{token}/readings` | Ek ya zyada reading save (`{dateTime, values:[{code,value,label,unit}]}`) |
| DELETE | `/my/{token}/readings/{rid}` | Patient apni galti se bhari reading delete kar sake (audit note ke saath) |
| GET | `/my/{token}/chart.svg?code=…&w=…&h=…` | Ek metric ka trend graph (SVG) — screen aur file dono me yahi |
| GET | `/my/{token}/export?fmt=pdf\|html\|csv` | Poora record download (graphs ke saath) |
| POST | `/my/{token}/share` | Read-only doctor link banao/refresh karo (`{note, days=7}`) → `{url, expiresAt}` |
| GET | `/my/{token}/appointments` | (Phase 3) patient ki requests |

### 5.2 Doctor side — login (opd_session cookie)

| Method | Path | Kaam |
|---|---|---|
| POST | `/opd/api/patient-link` | Patient ka portal link banao (ya maujooda wapas do) + WhatsApp text |
| GET | `/opd/api/patient-readings?patient_id=…` | Patient ke self-readings + series (Monitor tab ke liye) |
| GET | `/opd/api/patient-report?patient_id=…&fmt=pdf\|html\|csv` | Doctor bhi wahi report download kare |
| GET | `/opd/api/portal-stats` | Kitne patients ne link khola / kitni readings aayi (chhota dashboard) |
| POST | `/opd/api/patient-request-reply` | (Phase 3) appointment request ka reply |

### 5.3 Shared (read-only) side — public

| Method | Path | Kaam |
|---|---|---|
| GET | `/s/{token}` | Doctor ke liye read-only record page (graphs + table + print) |
| GET | `/s/{token}/export?fmt=pdf\|html\|csv` | Usi snapshot ka download |

> ⚠️ **`/s/` par koi POST/PUT/DELETE nahi hai — jaan-boojh kar.** Doctor sirf dekh sakta hai, badal nahi sakta.

---

## 6. Screens (Hinglish UI, jo patient ko samajh aaye)

### 6.1 Patient Portal — `/my/<token>`

```
┌─────────────────────────────────────────────┐
│ 🏥 GIL CLINIC — Patient Monitor             │   ← header (clinic name + patient)
│ Namaste, <Patient Name>                     │
├─────────────────────────────────────────────┤
│ 🔒 Suraksha Satyapan (pehli baar)           │   ← registered mobile ke last 10 digit
│    (clinic me darj number dalein)           │
├─────────────────────────────────────────────┤
│ 📥 Apne records download karo (PDF/HTML/CSV)│
│ 🩺 Kisi bhi doctor ko bhejein (link se)     │   ← read-only link + WhatsApp
├─────────────────────────────────────────────┤
│ ℹ️ Medical Disclaimer (self-reported)       │
├─────────────────────────────────────────────┤
│ 🚨 Red flags (BP 160+, sugar critical)      │   ← "turant doctor se milein"
├─────────────────────────────────────────────┤
│ Aaj ki readings   [Date & time: ____]       │
│  BP Systolic   [____] mmHg                  │
│  BP Diastolic  [____] mmHg                  │
│  Pulse         [____] bpm                   │
│  SpO2          [____] %                     │
│  Weight        [____] kg                    │
│  Temp          [____] °F                    │
│  Sugar (Random)[____] mg/dL                 │
│  + Add field (Hemoglobin, CBC…)             │
│  [💾 Save readings]                         │
├─────────────────────────────────────────────┤
│ 📈 My trends  (har metric ka bada graph)    │
│    320×160 viewBox, green normal band       │
├─────────────────────────────────────────────┤
│ 📋 Sabhi readings — Excel-style (ek jagah)  │
│    BP 135/85 ek column me                   │
└─────────────────────────────────────────────┘
```

### 6.2 Doctor view — `/opd/dashboard` me 2 naye touch-points

1. **New Rx tab** — patient select karte hi `selected-patient` bar me naya button:
   `📱 Patient link` → modal: link copy + **WhatsApp par bhejo** + "Patient ko exactly ye message jayega" preview.
2. **Naya nav tab `🩺 Patient Monitor`** — self-readings wale patients ki list (naam, last reading, status badge) → expand → graphs + Excel table + `📄 PDF report`.

### 6.3 Read-only doctor view — `/s/<token>`

Wahi report layout jo PDF me hai (letterhead → patient ka message → summary → graphs → Excel table), saath me **🖨️ Print / Save as PDF** button. Header par: *"Patient ne khud ye record share kiya hai (read-only) — link valid till <date>"*.

---

## 7. Reports (teen format, ek hi data source)

| Format | Kaise banta hai | Kis kaam ka |
|---|---|---|
| **PDF** | `fpdf2` — **vector** graphs (line/circle/rect draw), letterhead + summary table + per-metric graph (46mm) + readings table + disclaimer + page numbers | WhatsApp par doctor ke phone me **seedha khulta hai** — best |
| **HTML** | Server-rendered page, graphs **inline SVG** (koi internet/script nahi chahiye) | Print / WhatsApp document / file rakhne ke liye |
| **CSV** | `pivot_readings()` → Excel-style matrix (BP 135/85 ek column) | Excel me hisaab / apne record ke liye |

**Ek chart engine, teen jagah:** `src/utils/patient_chart_svg.py` ka `trend_chart_svg()` hi:
- portal ki screen par chart banata hai (`GET /my/{token}/chart.svg` se),
- HTML report me inline chapta hai,
- aur PDF wale vector chart ka **geometry** usi se aata hai.

Isi wajah se doctor ki purani shikayat ("download me graph nahi aate") dobara **kabhi nahi** ho sakti — file aur screen ek hi code se bante hain.

---

## 8. Files — exact list (kya naya, kya badlega)

### Naye files

| # | File | Kaam |
|---|---|---|
| 1 | `src/utils/patient_metrics.py` | Metric catalog (code/label/unit/min/max), `flag_reading()`, `guidance_for()`, `pivot_readings()`, `build_series()` |
| 2 | `src/utils/patient_chart_svg.py` | `trend_chart_svg()` — server-side SVG trend chart (normal band, axes, value + date labels) |
| 3 | `src/utils/patient_report.py` | `build_report_html()`, `build_report_csv()`, `build_report_pdf()` (fpdf2 vector graphs) |
| 4 | `src/utils/patient_tokens.py` | Portal/share token banao + verify (itsdangerous + `secrets`), expiry helpers |
| 5 | `src/infrastructure/opd/models/patient_portal_models.py` | `PatientReadingModel`, `PatientPortalLinkModel`, `PatientShareModel` (+ Phase 3 `PatientRequestModel`) |
| 6 | `src/presentation/patient_portal/__init__.py` | package |
| 7 | `src/presentation/patient_portal/routes/patient_portal_routes.py` | `/my/*` + `/s/*` public routes |
| 8 | `src/presentation/patient_portal/routes/opd_patient_api.py` | `/opd/api/patient-link`, `/api/patient-readings`, `/api/patient-report` |
| 9 | `templates/patient_portal.html` | Patient entry + trends + downloads (Jinja) |
| 10 | `templates/patient_shared.html` | Read-only doctor view (Jinja) |
| 11 | `static/patient/portal.js` | Portal JS (fetch, save, charts inject, clipboard, WhatsApp) |
| 12 | `static/patient/portal.css` | Portal styling (mobile-first) |
| 13 | `tests/test_patient_portal.py` | pytest — metrics, token, expiry, report builders, API |
| 14 | `PRODUCT_UPGRADATION_PATIENT_FILLING_PLAN.md` | Yahi file |

### Badalne wale files (minimal, surgical)

| # | File | Kya badlega |
|---|---|---|
| 1 | `main_v2.py` | Naye models import (create_all ke liye) + naya router include |
| 2 | `templates/opd/dashboard.html` | (a) nav item `🩺 Patient Monitor`, (b) naya `tab-content`, (c) `selected-patient` bar me `📱 Patient link` button, (d) JS functions (~150 lines) |
| 3 | `src/presentation/opd/routes/opd_routes.py` | Sirf 1 line nahi — naye doctor API **alag file** me hain, is liye ye file **chhui bhi nahi jayegi** (3638 lines ka monolith safe rahega) |
| 4 | `SMART_OPD_MASTER_REFERENCE.md` / `SYSTEM_STATUS_REPORT.md` | Naya module document karne ke liye chhota update (docs) |

---

## 9. Phases (checkbox-wise — har phase alag se test hoga)

### ✅ Phase 0 — Plan (yahi file)
- [x] Current system deep review
- [x] Data model + API + screens freeze
- [x] File list + risks

### ✅ Phase 1 — Data + Engine (koi UI nahi) — **DONE**
- [x] `patient_metrics.py` (catalog + flag + Hinglish guidance + pivot + series) — 14 metrics, LOINC-coded
- [x] `patient_chart_svg.py` (server-side SVG trend chart — green normal band, value + date labels)
- [x] `patient_report.py` (HTML inline-SVG + CSV + **fpdf2 vector PDF**)
- [x] `patient_tokens.py` (portal + share token, phone verify helpers, expiry)
- [x] `patient_portal_models.py` (4 tables — auto-create ho jati hain)
- [x] pytest: flags, BP 135/85 pivot, custom fields alag, 2+ points chart, PDF me charts, expiry

### ✅ Phase 2 — Patient Portal — **DONE**
- [x] `/my/{token}` page + phone verify (galat number 403, brute-force guard)
- [x] Readings save / list / delete (sirf apni reading delete ho sakti hai)
- [x] Trends (server SVG) + Excel-style table + summary + red-flag guidance
- [x] Downloads: PDF / HTML / CSV — **teeno me graph**
- [x] Save ke baad page reload ke bina trends/table refresh (`/content`)
- [x] "Add to Home screen" guide + disclaimer

### ✅ Phase 3 — Doctor side + "Doctor ko bhejo" — **DONE**
- [x] `/s/{token}` read-only snapshot + expiry (7 din) + `/s/.../export`
- [x] `/my/{token}/share` — snapshot banao/refresh karo (same link refresh hota hai)
- [x] OPD dashboard: **📱 Patient link** button (patient select karte hi) + modal + WhatsApp text + copy
- [x] OPD dashboard: naya **🩺 Patient Monitor** tab (list → trends + Excel table + PDF/HTML/CSV)
- [x] `/opd/api/patient-link`, `/patient-readings`, `/portal-patients`, `/portal-stats`, `/patient-report`

### ⏳ Phase 4 — Polish (aapki marzi)
- [ ] Appointment/follow-up request (patient → doctor reply) — table `patient_requests` already bana hua hai
- [ ] "Ghar ke BP ka average" prescription PDF par (7 din / 30 din)
- [ ] Doctor ko alert: patient ne critical value bhari → dashboard badge + WhatsApp
- [ ] Purane `patient-pwa/` (lab tracking) aur naye portal ko ek installable PWA me merge
- [ ] Patient ki purani (clinic me bhari) vitals ko `patient_readings` me backfill


---

## 10. Security & Privacy (DPDP + practical)

| # | Rule | Implementation |
|---|---|---|
| 1 | Token hi secret hai | `secrets.token_urlsafe(24)` (192-bit) — guess karna impossible; URL me sirf token |
| 2 | Koi listing nahi | Token ke bina kisi patient ka data nahi; koi "saare patients" endpoint public nahi |
| 3 | Likhne wala portal, padhne wala share | `/my/` me write, `/s/` me **sirf read** (server par koi write route hi nahi) |
| 4 | Expiry | Share: `expires_at` (default 7 din) — server par check, client par nahi. Portal link: doctor `active=0` karke band kar sakta hai + optional 90-din expiry |
| 5 | Phone verification | Pehli baar: registered mobile ke last 10 digit → session cookie (`patient_session_<token>`, HttpOnly) |
| 6 | Doctor ka access | Doctor ke liye koi naya open door nahi — `/opd/api/*` sab `_require_opd_session` ke peeche |
| 7 | Audit | Reading save/delete + link create + share view ka count DB me (kabhi kabhi doctor dekh sake) |
| 8 | Data kahan | Wahi DB jahan baaki clinic data hai (SQLite/Postgres) — koi third-party upload nahi |
| 9 | Sensitive | Patient ka naam/phone sirf uske apne token wale page par; share snapshot me sirf naam + readings (full phone **nahi**) |
| 10 | Disclaimer | Har report/portal par: *"self-reported readings — diagnosis nahi, emergency me turant doctor"* |

---

## 11. Testing Plan

| Test | Kya check hoga |
|---|---|
| `tests/test_patient_metrics.py` | BP 120/80 → ok, 160/100 → high, 190/120 → critical; sugar ranges; pivot me BP `135/85` ek column; series chronological + custom fields alag |
| `tests/test_patient_chart.py` | 1 reading → koi chart nahi; 3 readings → SVG `<polyline>` + green band + date labels; viewBox 320×160 |
| `tests/test_patient_report.py` | PDF `%PDF-` magic + size; HTML me `class="trend-chart"` count = 2+ points wale metrics; CSV header me merged BP |
| `tests/test_patient_portal_api.py` | Token round-trip; galat token → 404; share expiry ke baad → 410; `/s/` par koi write method nahi; readings save → list me aaye |
| Manual (phone) | WhatsApp link → verify → readings save → graph turant bane → PDF download → doctor ko bhejo → doosre phone par link khule |

---

## 12. Deploy / Rollout (koi drama nahi)

1. Code push → Railway/PA restart → `Base.metadata.create_all()` naye tables bana dega (SQLite ke liye auto column migrator bhi pehle se hai).
2. Koi naya env var **zaroori nahi**. Links `APP_BASE_URL` (tunnel/Railway URL) se banenge — jo lab tracking me pehle se use ho raha hai.
3. Backward compatible: purana `/track/<token>` (lab tracking) **waise hi** chalega; purana `vitals` text field bhi **waise hi** rahega.
4. Rollback: naya router hata do → sistem purani halat me. (Data tables padhe rahenge, koi nuksan nahi.)

---

## 13. Risks & Honest Limitations

| # | Risk | Sach | Upaay |
|---|---|---|---|
| 1 | WhatsApp par link kisi aur ke phone me chala gaya | Token wale link ka yeh natural risk hai | Phone-verify screen + doctor `active=0` kar sake + 90-din expiry + share link 7 din |
| 2 | Patient ghar par galat value bhare | Self-reported data hamesha aisa hota hai | Values par "self-reported" label, doctor ke liye alag dikhana, prescription me AI/auto-merge **nahi** |
| 3 | SQLite par traffic | Bade clinic ke liye SQLite kamzor | Postgres (Railway) me same code chalta hai — sirf `GHOS_DB_URL` badalna hai |
| 4 | Purane `vitals` text aur naye structured readings | Do jagah data | Doctor UI me dono saath dikhenge; chahein to Phase 4 me backfill |
| 5 | Internet na ho | Patient ghar par offline | Save fail hone par saaf Hinglish error; form ki values gayab nahi hongi (local draft) |
| 6 | Doctor ka WhatsApp number | Message patient ke phone se jayega (`wa.me` share sheet) | Patient khud apne WhatsApp se bhejta hai — clinic ka koi business account chahiye nahi |

---

## 14. Out of Scope (abhi nahi)

- Public **self-signup** (koi bhi bina doctor ke link apna account banaye) — security risk, alag project.
- Patient se **paise** lena / online payment.
- Lab report **file upload** patient se (wo `opd_lab_reports` + OCR wale flow me hai — wahan se hoga).
- AI se patient ke readings ka **diagnosis** — AI sirf doctor ke liye hai, patient ko nahi.

---

## 15. Approval

| Kaam | Kaun | Sthiti |
|---|---|---|
| Plan | — | ✅ Yeh file |
| Phase 1 (data + engine) | — | ✅ Done + tested |
| Phase 2 (patient portal) | — | ✅ Done + tested |
| Phase 3 (doctor side + share link) | — | ✅ Done + tested |
| Live test (doctor ke phone se) | Dr. G. S. Gill | ⏳ |

---

## 16. Implementation Status (17-Sep-2026) — kya bana, kaise test hua

### Naye files

| File | Kaam |
|---|---|
| `src/utils/patient_metrics.py` | 14 metrics (LOINC), `flag_reading`, Hinglish `guidance_for`, `pivot_readings`, `build_series` |
| `src/utils/patient_chart_svg.py` | `trend_chart_svg()` — server-side SVG (green normal band, axes, value + date labels) |
| `src/utils/patient_report.py` | `build_report_html` (inline SVG) · `build_report_csv` · `build_report_pdf` (fpdf2 vector charts) |
| `src/utils/patient_portal_html.py` | Portal fragments: trends/table/flags/summary HTML |
| `src/utils/patient_tokens.py` | Token, phone verify (sha256 + digits), expiry, patient session cookie |
| `src/infrastructure/opd/models/patient_portal_models.py` | `patient_readings`, `patient_portal_links`, `patient_shares`, `patient_requests` |
| `src/presentation/patient_portal/routes/patient_portal_routes.py` | `/my/*` + `/s/*` public routes **+** `/opd/api/*` doctor routes |
| `templates/patient_portal.html` | Patient ka portal (verify → entry → trends → downloads → share) |
| `templates/patient_shared.html` | Doctor ka read-only share view |
| `static/patient/portal.js`, `static/patient/portal.css` | Portal ka front-end (mobile-first, bade graphs) |
| `tests/test_patient_portal.py` | 10 pytest — metrics, reports, portal flow, share expiry, doctor APIs |
| `scripts/patient_portal_e2e.py` + `.cjs` + `patient_portal_seed.py` | **One-command real-browser E2E** (`python scripts/patient_portal_e2e.py`) |
| `scripts/patient_report_preview.py` | Sample report (HTML/CSV/PDF) bana kar `scratch/preview/` me daal deta hai |

### Badle files (sirf 3)

| File | Kya badla |
|---|---|
| `main_v2.py` | Naye models import (create_all ke liye) + 2 router include — **bas 12 lines** |
| `templates/opd/dashboard.html` | nav me `🩺 Patient Monitor` · `📱 Patient link` button · modal · ~230 lines JS |
| `PRODUCT_UPGRADATION_PATIENT_FILLING_PLAN.md` | Yahi document |

**`src/presentation/opd/routes/opd_routes.py` (3638 lines ka monolith) chhui bhi nahi gayi** — naye doctor APIs alag file me hain.

### Verification (sab green)

```
python -m pytest tests/test_patient_portal.py -q     → 10 passed
python scripts/patient_portal_e2e.py                 → 30 browser checks passed (Playwright, real Chromium)
```

E2E me jo cheezein actually verify hui (asli browser me, phone size 390px):

1. Doctor login (PIN) → patient search → **📱 Patient link** → link + WhatsApp text mile
2. Patient portal: **galat mobile number reject**, sahi number par portal khula
3. Pehli reading → table me dikhi (graph nahi banta — sahi), **doosri reading → trend graph bana**
4. Graph me **green normal band**, phone par **300×150 px** (bina zoom padhne layak)
5. BP 152/96 par **red-flag Hinglish guidance** dikhi
6. PDF / HTML / CSV teeno buttons — aur **PDF me graphs** (server-side vector)
7. "Doctor ko bhejo" → `/s/<token>` link + WhatsApp button + validity date
8. **Saaf browser (koi cookie/login nahi)** me `/s/<token>` khula → graphs + patient ka message +
   Print/Save-as-PDF — aur **koi save/edit button nahi** (read-only)
9. Doctor ka **Patient Monitor** tab → patient list → graphs + Excel table
10. **Zero uncaught page errors**

### Live karne ke liye

1. `pip install -r requirements.txt` (kuch naya nahi chahiye — sab pehle se hai)
2. App restart (`START_LOCAL.bat` / Railway deploy) — **tables apne aap ban jayengi**
3. ⚠️ `.env` me `APP_BASE_URL` **live public URL** hona chahiye (abhi purana tunnel URL
   `rio-minerals-rim-skills.trycloudflare.com` likha hai — wo band ho chuka hai, patient ko wahi
   link jayega). Railway par apna domain, ya naya tunnel URL daalein.

> **Ek line me:** Smart OPD me patient ab apni BP/sugar ghar se bharega, apne graph dekhega, PDF
> download karega, aur ek link se **kisi bhi doctor** ko apna record dikha sakega — aur poora system
> wahi rahega jo abhi chal raha hai, bas ek naya module jud gaya.

