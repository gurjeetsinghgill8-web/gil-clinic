# 🚨 FIR — Product Development File (GIL CLINIC)

> **Owner:** Gurjas Singh Gill
> **Date:** 21 Sep 2026
> **Status:** ✅ FIXED + **DEPLOYED LIVE** on https://gillhopitalsoftware1.pythonanywhere.com (21 Sep 2026)
> **Purpose:** Har bade issue ko ek-ek karke (one-by-one) register karna — description, evidence, root cause. Solution/upgrade plan alag file `PRODUCT_UPGRADATION_PLAN.md` mein hai.

---

## ✅ DEPLOYMENT LOG (21 Sep 2026)

| Ship | Commit | Files | Live verify |
|------|--------|-------|-------------|
| 1 | `fd10178` | `ai_gateway.js`, `opd_models.py`, `opd_routes.py`, `main_v2.py`, `dashboard.html` | health 200 · `/api/drugs` ab JSON objects · DB migration OK (9 columns) |
| 2 | `27c78b4` | `opd_routes.py`, `dashboard.html` | Rx parser fixes + naya `/api/drugs/backfill` |
| 3 | `12d49c3` | `opd_routes.py` | syrup prefix fix + case-insensitive matching + `reset` option |

**Live drug bank (asli data se bana):** 16 prescriptions → **11 entries** — Olmin 20 (used 4), Citrizine 5/10, Dolo 500/650, zifi 200, Ascoryl (Syrup), Augmentin 625, Azee 500, Cetrizine 10mg, Moxikind cv 625. Backfill idempotent (dobara chalane par duplicate nahi bante).

---

## 📋 Issue Summary (एक नज़र में)

| FIR# | Issue | Type | Severity | Status |
|------|-------|------|----------|--------|
| **FIR-01** | Doctor ki image/prescription se data extract (OCR) — Puter pe **work hi nahi karta** | Bug / Blocker | 🔴 CRITICAL | ✅ **FIXED + LIVE** |
| **FIR-02** | **Drug Bank / Medicine auto-fill missing** — doctor ko baar-baar dose/timing type karni padti hai | Missing Feature | 🔴 CRITICAL (sabse bada flaw) | ✅ **FIXED + LIVE** (11 drugs seeded) |
| **FIR-03** | Patient side se PDF/reports + ghar ke BP/pulse upload (patient→doctor) | New Idea (revolutionary) | 🟢 FUTURE | ⏸️ KEEP ASIDE — implement nahi karna |
| **FIR-04** | Puter settings/Connect — popup **blank ho jata hai**, site pe le jata hai, Puter side nahi khulti | Bug | 🟠 HIGH | ✅ **FIXED + LIVE** |

> **Important instruction:** Coding **ek-ek karke** hui hai (FIR-01 → FIR-04 → FIR-02), aur sab **live deploy + verify** ho chuka hai. FIR-03 (patient upload) abhi bhi sirf blueprint hai — jab plan karenge tabhi karenge.

---

## 🔴 FIR-01 — Doctor ki Image / Prescription se Data Extract (OCR) Puter pe nahi chal raha

### Kya ho raha hai (owner ka statement)
> "Image lekar ke (doctor ki image) hum usko OCR ya batches scan karke usme se data nikalna chahte hain — **possible nahi ho pa raha**. Pehle **Groq** ke saath working tha. Ab **Puter ki help se work hi nahi karta.**"

### Current flow (kaise kaam karta hai abhi)
1. Doctor photo upload karta hai → `processAllScansSequential()` (`templates/opd/dashboard.html:1842`)
2. Image ko data URL bana kar backend ko bhejta hai → `aiFetch('/opd/api/scan-ai', {image: dataUrl})`
3. Backend (`src/presentation/opd/routes/opd_routes.py:2389` `api_scan_ai`) → `route_vision()` (`src/ai_engine/provider_router.py:529`)
4. Puter mode mein backend `{ok:false, code:'PUTER_OCR', prompt, model}` return karta hai
5. Browser gateway (`static/js/ai_gateway.js`) `doOcr()` → image ko **File object** banata hai → `window.puter.ai.img2txt(file)` → result wapas backend ko.

### 🔍 Root Cause (asli wajah — 4 problems ek saath)

| # | Problem | Evidence (file:line) | Effect |
|---|---------|----------------------|--------|
| 1 | **`img2txt` ko `File` object bheja ja raha hai, jabki Puter ko data URL chahiye** | `static/js/ai_gateway.js:130-136` (`b64ToFile` → `img2txt(file)`). Reference nano clinic (jo chal raha hai) data URL bhejta hai: `newmcg nano clinic/src/lib/puter.ts:141-145` (`aiImg2txt(dataUrl)`) | Puter ko galat input milta hai → OCR return hi nahi karta → "work hi nahi karta" |
| 2 | **Image compress nahi hoti** — phone camera ki photo 10 MB se badi hoti hai | GIL raw base64 bhejta hai. Nano explicitly compress karta hai: `newmcg nano clinic/src/lib/puter.ts:583-617` (`fileToCompressedDataUrl`, maxDim=1600, quality=0.85, comment: *"Puter's OCR rejects inputs > 10 MB"*) | Puter 10 MB se badi image **silently reject** karta hai → empty result |
| 3 | **`extractText` Puter ka array-form response handle nahi karta** | `static/js/ai_gateway.js:35-42` vs nano `newmcg nano clinic/src/lib/puter.ts:79-95` (jo `message.content` array ko join karta hai) | Response garbled → parse fail → empty prescription |
| 4 | **Sign-in auto-popup + guest account problem** | `static/js/ai_gateway.js:28-33` (plain `signIn()`) — details FIR-04 mein | Blank popup / temporary guest → OCR fail |

### Verdict
> Pehle Groq pe isliye chalta tha kyunki Groq path server-side tha (`src/ai_engine/groq_client.py` → `call_vision_with_fallback`). Puter path **browser-side** hai aur wahan upar ke 4 bugs hain. Fix ke liye `PRODUCT_UPGRADATION_PLAN.md → Issue 1` dekho.

---

## 🔴 FIR-02 — Drug Bank / Medicine Auto-Fill Missing (sabse bada flaw)

### Kya ho raha hai (owner ka statement)
> "Nano clinic mein medicine add karte hi **doctor ka medicine bank / personal drug system** ban jata hai. Nai medicine daali, uski dose daali, naam, **salt** vagaira — jo jo add kiya sab **save ho jata hai**. Agli baar doctor ko **baar-baar type nahi karna padta** (dose, timing, kitni baar lena hai). Hamare clinic software mein **yeh sab missing hai**."

### Current state (GIL CLINIC mein abhi kya hai vs kya nahi)

**Jo hai (partial):**
- `opd_drug_history` table — lekin sirf `drug_name` + `dose` + `use_count` (`src/infrastructure/opd/models/opd_models.py:78-99`)
- Drug autocomplete buttons — free-text `pt-medicines` textarea ke neeche (`templates/opd/dashboard.html:2317-2350` + `src/presentation/opd/routes/opd_routes.py:863-887`)
- Structured medicine rows (name/dose/freq/food/duration) — `addMedicineRow()` (`templates/opd/dashboard.html:4107-4178`)
- Rx templates save/load (`templates/opd/dashboard.html:2746-2780`)

**Jo MISSING hai (Nano clinic ke paas hai, hamare paas nahi):**

| # | Missing feature | Nano clinic reference |
|---|-----------------|----------------------|
| 1 | **Full drug bank data**: `brandName`, `strength`, `form` (Tablet/Syrup/Injection), `defaultDose`, `defaultFrequency`, `defaultTiming`, `active`, `useCount` | `newmcg nano clinic/src/types.ts:89-101` (`Medicine` interface) |
| 2 | **Salt / composition** field | (nano `Medicine` me nahi hai explicitly, but GIL ka doctor specifically "salt vagaira" chahta hai — naya add karna hoga) |
| 3 | **Dropdown autocomplete** (sirf text buttons nahi) — name + brand + strength + form dikhata hai | `newmcg nano clinic/src/components/MedicinePicker.tsx` |
| 4 | **Auto-fill**: medicine pick karte hi form/dose/frequency/timing **khud bhar jate hain** | `MedicinePicker.tsx:124-147` (`pick()`) + `TIMING_FOR_FREQ` map (`MedicinePicker.tsx:23-31`) |
| 5 | **Form → dose auto default** (Tablet→"1 tablet", Syrup→"5 ml") | `newmcg nano clinic/src/lib/utils.ts` (`defaultDoseForForm`) |
| 6 | **One-tap "Save to library"** prescription row se hi (Medicine screen pe jaana nahi padta) | `MedicinePicker.tsx:164-198` (`saveToLibrary()`) |
| 7 | **Medicine library CRUD screen** (search/add/edit/delete/deactivate) | `newmcg nano clinic/src/screens/MedicinesScreen.tsx` |
| 8 | **Auto-learn ranking** (most-used pehle aata hai) | `MedicinePicker.tsx:71` (sort by `useCount` desc) |
| 9 | **Form-prefix strip** ("Tab. Paracetamol" → "Paracetamol" library se link) | `MedicinePicker.tsx:50-53` (`FORM_PREFIX_RE`, `stripMedPrefix`) |

### 🔍 Root Cause
> GIL ka `_learn_drugs()` (`src/presentation/opd/routes/opd_routes.py:890-932`) sirf **final free-text Rx** ko regex se todta hai aur **sirf naam + dose** save karta hai. Structured medicine rows (brand/strength/form/frequency/timing/duration) **kabhi bank mein save nahi hote**. Isliye har baar doctor ko poori cheez dobara type karni padti hai.

---

## 🟢 FIR-03 — Patient Side Upload (PDF/Reports + Ghar ke BP/Pulse) — ⏸️ KEEP ASIDE

### Kya chahte ho (owner ka statement)
> "Patient site pe bhej diya — kya patient **apni side se apna data upload** kar de (PDF, reports, baaki cheezein) aur woh sara data doctor ke paas aa jaye? Jaise patient ke **ghar se BP/pulse** bhi nikal lein. **Abhi implement NAHI karna** — bas bana kar ek folder mein side rakhna. Jab plan karenge tabhi lenge. **Ye bhi revolutionary hai.**"

### Current state
- `patient-pwa/` = **sirf queue status tracker** (patient mobile daal ke apne test ka status dekhta hai — `patient-pwa/app.js`). Upload nahi hai.
- Patient link ghar bhejna **already bahut achha kaam kar raha hai** (owner confirmed ✅).

### Status
> ⏸️ **Documented only.** Design/blueprint `future_ideas/PATIENT_PORTAL_UPLOAD.md` mein rakha hai. **Koi code nahi**, jab tak owner plan kare.

---

## 🟠 FIR-04 — Puter Settings/Connect Popup Blank Bug

### Kya ho raha hai (owner ka statement)
> "Jab puter ko **settings** mein open karte hain to woh **site pe le jata hai** (recharge/open wala kaam karta hai). Lekin **front** mein (Connect Puter) jab dabate hain to **site pe le ja kar blank ho jata hai** — Puter ki side nahi khulti."

### Current flow
- Settings → "🔌 Connect Puter" → `connectPuter()` (`templates/opd/dashboard.html:3733-3750`) → `window.puterConnect()` → `signIn()` → `window.puter.auth.signIn()` (no options) (`static/js/ai_gateway.js:28-33`)

### 🔍 Root Cause
> GIL ka `signIn()` **plain** hai — koi protection nahi:
> 1. SDK ka popup kuch devices (mobile/PWA) pe **blank** render hota hai (no `window.opener` / `embedded_in_popup` issue).
> 2. Popup fail/cancel hone pe Puter **chupchaap temporary guest account** bana deta hai → `isSignedIn()` true dikhata hai, lekin woh real account nahi (no email) → AI fail.
> 3. Koi timeout fallback nahi → hang / blank.

> Nano clinic ne **yehi exact bug already fix** kiya hai (yehi "proven working" reference hai):
> - `signIn({ attempt_temp_user_creation: false, request_auth: true })` + hard timeout
> - Guest account detection (`isRealPuterAccount` — email ke bina = guest)
> - Mobile/PWA pe **full-tab dual-channel login** (`puterSignInViaTab` — no `window.opener` needed)
> - Reference: `newmcg nano clinic/src/lib/puter.ts:273-491`

---

## ✅ Conclusion

| FIR# | Action |
|------|--------|
| FIR-01 | OCR Puter pipeline fix — `PRODUCT_UPGRADATION_PLAN.md → Issue 1` |
| FIR-02 | Full Drug Bank + auto-fill — `PRODUCT_UPGRADATION_PLAN.md → Issue 2` |
| FIR-03 | ⏸️ KEEP ASIDE — blueprint in `future_ideas/PATIENT_PORTAL_UPLOAD.md` |
| FIR-04 | Puter sign-in blank fix — `PRODUCT_UPGRADATION_PLAN.md → Issue 4` |
