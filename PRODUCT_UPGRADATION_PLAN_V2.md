# GIL CLINIC — Product Upgradation Plan (Round 2)

> **Owner:** Gurjas Singh Gill
> **Date:** 2026-10-03
> **Status:** PLAN ONLY — abhi koi code change NAHI kiya gaya. Ye file batati hai ki aage kya-kya karna hai.
> **Current live build:** `66e48cd`

---

## 0. Kya kya issue mila (diagnosis — maine LIVE chalakar dekha)

Maine system ko LIVE run karke check kiya. Ye 5 issues hain jo aapne bataye + jo mujhe mili:

| # | Issue | Kya mila (live) |
|---|---|---|
| 1 | Junior doctor ka PIN | Abhi `1234` hai (reception/ecg/echo/tmt/xray/lab/dietician ke saath SHARED) |
| 2 | PIN change karne ka option | `/staff/settings` me "Change Your PIN" hai, PAR **sidebar me link nahi** (dhundna mushkil) + **BROKEN** (change ka asar login pe nahi hota) |
| 3 | Hierarchy (CEO→clinic→doctor→staff) | Abhi nahi hai — koi manager/CEO doosre ka PIN nahi badal sakta |
| 4 | **"Uber/Ola for OPD" city marketplace** (Find a Doctor) | Page BUILT hai, par **EMPTY/idle** — `/find-doctor` pe "No doctor"; crawler (GitHub) kabhi real data se chala nahi |
| 5 | Naya version dikhna | Version sirf `/health` + OPD sidebar me hai; landing pe nahi dikhta |

---

## 1. Junior Doctor PIN → `1122`

**Aapka decision:** Junior doctor ka PIN `1122` rakho.

**Kya karna hai (aage, jab code-change ka time hoga):**
- `src/domain/auth/identity.py` — `OPD_JUNIOR_PIN` ko `"1234"` → `"1122"`.
- `src/presentation/opd/routes/opd_routes.py` — wahi `JUNIOR_PIN` mirror update.
- Tests update (jo `1234` ko junior PIN maante hain).
- **Effect:** ab `1234` sirf reception/ecg/echo/tmt/xray/lab/dietician ka rahega. Junior doctor `1122` se login karega. Reception ab "Junior Doctor" nahi chun sakta (kyunki junior ka PIN alag ho gaya).

> ⚠️ Ye CHANGE karne se pehle junior doctor ko `1122` bata dena (warna lock out ho jayega).

---

## 2. PIN management — hierarchy (CEO → clinic → doctor → staff)

**Aapka vision (jo pehle decide hua tha):**
1. Sabhi ka PIN pehle default rahega.
2. Jab senior doctor / manager aaye, wo **apne hisab se sabka PIN badal kar dega**.
3. CEO kisi hospital/doctor ko system + password deta hai.
4. Doctor apne password se apne neeche ke logon (1, 2, 3... jitne chahe) ke PIN generate karke unhe dega.
5. **Har doctor ki clinic ek isolated system hai** — bahut saari clinics alag-alag khul sakti hain.

**Abhi ki asliyat (kya toota hai):**
- `POST /staff/api/change-pin` apna PIN `StaffPinModel` (DB) me likhta hai.
- **PAR login `STAFF_PINS` (hardcoded dict) padhta hai — DB ka PIN padhta hi nahi.** Isliye PIN badalne ka koi asar nahi hota.
- `/staff/settings` ka link sidebar me nahi hai.
- Koi "doosre ka PIN badalne" ka page nahi hai.

**Plan (bricks me):**
1. **Fix:** login/resolve_pin me `StaffPinModel` se custom PIN padho — agar DB me role+clinic ka PIN hai to wahi lo, warna hardcoded default. (Pehle ye fix, warna change ka matlab hi nahi.)
2. **Sidebar me "⚙️ Settings" link** add karo (har staff role ko apna PIN badalne ke liye).
3. **"Manage Staff PINs" page** — sirf **manager/CEO/owner** ke liye: list of roles + unke PIN set karo (doosre ka PIN badalne ka option).
4. **Hierarchy enforce:** sirf higher role (manager/ceo/owner) doosre ka PIN badal sake; doctor apne clinic ke staff ka PIN badal sake (apne clinic_id ke andar).

---

## 3. Clinic isolation (har doctor ki clinic alag)

- Abhi `clinic_id` se data scope hota hai (`StaffPinModel.clinic_id`, `assigned_opds`, etc.) — base hai.
- Jab PIN management (Issue 2) complete ho, to:
  - Doctor apne clinic ke staff ka PIN generate kare (sirf apne `clinic_id` me).
  - Doosri clinic ka data/PIN na dikhe na bade.
- Ye Issue 2 ke saath hi complete hoga (ek hi brick me).

---

## 4. "Uber/Ola for OPD" city marketplace (Find a Doctor) — IDLE ko ALIVE karna

> 📖 **Memory files (yehi "option 2" hai):**
> - `PRODUCT_UPGRADATION_UBER_HEALTHCARE.md` — *"Uber made you stop waiting for a taxi. GHOS makes you stop waiting for a doctor."*
> - `GLOBAL_CLINIC_SEARCH_AND_QUEUE_ENGINE_BLUEPRINT.md` — *"Practo ek directory dikhata hai. GHOS ek ZINDA queue dikhata hai."*
> - `PRODUCT_DEVELOPMENT_UBER_HEALTHCARE_PLAN.md` · `DEEP_RESEARCH_PRODUCT_DEVELOPMENT.md`

**Kya hai ye feature (vision):**
Ek **city-level doctor marketplace** — jaise Ola/Uber me aap apne city me gaadiyan dekhte ho, waise ye patient ko **apne city me doctors** dikhata hai:
- Patient city + specialty + problem (Hindi me "seene me dard") daalta hai.
- **Tier 1 (upar):** GHOS partner clinics — 🟢 LIVE QUEUE, real token + wait time, 1-tap "Book Token".
- **Tier 2 (neeche):** External/non-network doctors — directory (call + directions) + "📢 Invite to GHOS" (growth loop).

**Kya BUILT hai (already done — blueprint se):**
Two-tier ranking ✅ · `/find-doctor` page ✅ · meta/search/book APIs ✅ · "Abhi khula" + distance sort ✅ · city landing pages `/doctors/<city>` ✅ · growth loop (invite) ✅ · claim button ✅ · EWT engine ✅ · slots ✅ · demo seed script ✅

**To ye "toy/idle" kyun lag raha hai (diagnosis — live):**
`/find-doctor` pe **"No doctor / empty"** dikh raha hai — page bana hai par **andar data (doctors) nahi hai**:

| Wajah | State |
|---|---|
| Tier 1 (partner clinics) | Koi onboard/seed nahi hua |
| Tier 2 (external directory) crawler | **IDLE** — `targets.json` me sirf 1 **FAKE** `example-hospital.example`, cron **disabled** |
| GitHub secrets (`INGEST_TOKEN`, `GEMINI_API_KEY`) | Configure nahi hain |

**Plan (marketplace ko ALIVE karne ke liye):**
1. **Demo seed** (turant, bina crawler ke): `scripts/seed_marketplace_demo.py` chalake 8 demo clinics daalo → `/find-doctor` pe doctors turant dikhein (city + specialty + live queue).
2. **Crawler real banao:** `targets.json` me **REAL public doctor roster URLs** daalo (asli hospital/clinic "Our Doctors" pages).
3. **GitHub secrets** configure karo: `INGEST_TOKEN` + `GEMINI_API_KEY`.
4. **Cron enable** karo (weekly, already likha hai bas uncomment).
5. **Live queue feed** verify karo (Tier 1 clinics ka real token/wait time dikhe).

> ⚠️ **Mujhe aapse input chahiye:** Tier 1 ke liye **kaunse partner clinics** (aapke apne), aur Tier 2 ke liye **kaunse hospital/clinic ke doctors** real me chahiye? (URLs ya naam do). Warna main pehle demo seed se ALIVE kar dunga, phir real data.

---

## 5. Naya version har baar dikhe (version display)

**Aapka point:** jab bhi kuch naya ho, page pe dikhna chahiye ki "naya version aaya" — taaki aapko pata chale.

**Abhi:** build hash `/health` + OPD sidebar me hai (logged-in), landing page pe nahi.

**Plan:**
1. **Landing page (`/`) pe ek chhota version badge** — jaise `v66e48cd` (har deploy pe badle).
2. **Har authenticated page pe bhi** ek chhota build tag (footer/topbar).
3. Ek `VERSION` ya `RELEASE` constant banao jo har deploy ke saath automatic update ho (build hash se).
4. **Memory file (`PRODUCT_UPGRADATION_MASTER_PLAN.md`) me bhi** "latest version = `<build>`" hardcode karo har brick ke baad (ye already SECTION 6 me hota hai — isko aur clear karenge).

---

## 6. Priority order (kaunsa pehle)

1. **Issue 1 (Junior PIN 1122)** — sabse chhota, turant.
2. **Issue 2 + 3 (PIN management + clinic isolation)** — hierarchy, sabse important feature.
3. **Issue 5 (version display)** — chhota, user ko visibility.
4. **Issue 4 (Uber/Ola marketplace ALIVE)** — demo seed turant, crawler aapke input (hospital URLs) ke baad.

---

## 7. Aage ka step

**Aap batao:**
1. Kya main **Issue 1 (Junior PIN 1122)** se shuru karun? (code change hoga)
2. **Issue 4 (crawler)** ke liye kaunse hospital/clinic ke doctors chahiye?
3. Baaki plan (PIN hierarchy, version) confirm?

Jab aap "haan" kaho, main ek-ek brick karke: code → tests → commit → push → deploy → live verify → memory update karunga.
