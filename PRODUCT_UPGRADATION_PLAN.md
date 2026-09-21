# 📈 Product Upgradation Plan — GIL CLINIC

> **Owner:** Gurjas Singh Gill
> **Date:** 21 Sep 2026
> **Status:** ✅ IMPLEMENTED + **DEPLOYED LIVE** (21 Sep 2026) — https://gillhopitalsoftware1.pythonanywhere.com
> **Companion:** `FIR_PRODUCT_DEVELOPMENT.md` (issues + deployment log), `future_ideas/PATIENT_PORTAL_UPLOAD.md` (keep-aside)
> **Related:** `PRODUCT_UPGRADATION_PUTER_PLAN.md` (existing Puter plan — isme reference hota hai)

---

## ✅ Implementation status (21 Sep 2026)

| Issue | Kya hua | Commit |
|---|---|---|
| **Issue 1** (OCR) | `doOcr` ab **data URL** bhejta hai (File nahi) + **auto-compress** (1600px/0.85) + `extractText` array-form handle karta hai | `fd10178` |
| **Issue 4** (Puter blank) | robust `signIn`: guest-account detect/clear, `attempt_temp_user_creation:false`, 25s timeout, mobile/PWA pe **full-tab login** | `fd10178` |
| **Issue 2 Layer 1** (DB) | `opd_drug_history` mein 9 naye columns + SQLite/Postgres auto-migration (live par verified) | `fd10178` |
| **Issue 2 Layer 2** (API) | `/api/drugs` GET (JSON objects) + POST (save/upsert) + DELETE (hide) + `/api/drugs/backfill`; `_learn_drugs` pura fields sikhata hai | `fd10178`, `27c78b4`, `12d49c3` |
| **Issue 2 Layer 3** (UI) | dropdown autocomplete + **auto-fill** (dose/freq/timing/duration) + **💾 save-to-library** + **💊 Medicine Library** modal (salt/brand/edit/delete) | `fd10178`, `27c78b4` |

**Bonus (live data se mila):** Rx parser 2 asli bugs fix hue — (a) `syp(?:rup)?s?` regex "Syrup" se match hi nahi karta tha, (b) bare-number strength ("Olmin 20") aur "x 30" duration parse nahi hote the. Ab 16 purani prescriptions se **11 saaf drug-bank entries** ban gayi hain (`POST /api/drugs/backfill?reset=true`).

---

## 🧭 How to use (kaise chalega)

1. Har issue ka solution neeche diya hai — **file-level change plan** ke saath.
2. Coding **one-by-one** hogi: pehle **Issue 1 (OCR)**, phir **Issue 4 (Puter blank)**, phir **Issue 2 (Drug Bank)** — kyunki 1 aur 4 ka fix ek hi file (`static/js/ai_gateway.js`) mein overlap karta hai.
3. Har issue ke baad owner **check karega** → approve → agla issue.
4. **Issue 3 (Patient upload)** abhi **implement nahi hoga** — blueprint side mein rakha hai.

---

## 🔴 Issue 1 — Fix: Doctor Image / Prescription OCR (Puter path)

### Solution (kya karna hai)

Port karo nano clinic ka **proven working** OCR pipeline GIL mein. 4 fixes:

#### Fix 1.1 — `img2txt` ko **data URL** bhejo (File nahi)
- `static/js/ai_gateway.js` ke `doOcr()` mein `b64ToFile()` hata kar **data URL directly** bhejo.
- `b64ToFile()` function ab OCR ke liye chahiye hi nahi (audio ke liye alag hai).

```js
async function doOcr(body) {
  var b64 = body && (body.image || body.image_b64 || body.imageData);
  if (!b64) throw new Error('No image in request for Puter OCR');
  // b64 already ek data URL hai (scan-ai frontend readFileAsDataURL se aata hai).
  var res = await window.puter.ai.img2txt(b64);   // data URL direct — File nahi
  return extractText(res);
}
```

#### Fix 1.2 — Image **compress** karo (10 MB limit bypass)
- Nano clinic ka `fileToCompressedDataUrl` (maxDim=1600, quality=0.85) ka logic GIL mein add karo.
- `processAllScansSequential()` (`templates/opd/dashboard.html:1842`) mein `readFileAsDataURL(file)` ki jagah compressed version use karo. Ya gateway mein hi compress karo (data URL → Image → canvas → JPEG).

```js
// gateway ke andar (ya dashboard helper) — image ko shrink karo:
function compressDataUrl(dataUrl, maxDim = 1600, quality = 0.85) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      let w = img.width, h = img.height;
      if (w > maxDim || h > maxDim) {
        const s = Math.min(maxDim / w, maxDim / h, 1);
        w = Math.round(w * s); h = Math.round(h * s);
      }
      const c = document.createElement('canvas');
      c.width = w; c.height = h;
      const ctx = c.getContext('2d');
      if (!ctx) return reject(new Error('Canvas unavailable'));
      ctx.drawImage(img, 0, 0, w, h);
      resolve(c.toDataURL('image/jpeg', quality));
    };
    img.onerror = () => reject(new Error('Image load nahi hui'));
    img.src = dataUrl;
  });
}
```

#### Fix 1.3 — `extractText` ko **array-form** handle karne layak banao
- Nano clinic ka `extractText` (`newmcg nano clinic/src/lib/puter.ts:79-95`) copy karo — `message.content` string **ya array** dono handle kare.

```js
function extractText(res) {
  if (!res) return '';
  if (typeof res === 'string') return res;
  if (res.message && res.message.content != null) {
    const c = res.message.content;
    if (typeof c === 'string') return c;
    if (Array.isArray(c)) return c.map(p => (p && p.text) || '').join('');
    return String(c);
  }
  if (res.text != null) return String(res.text);
  if (res.content != null) return String(res.content);
  try { return JSON.stringify(res); } catch (e) { return ''; }
}
```

#### Fix 1.4 — Sign-in flow fix (Issue 4 ke saath combine)
- Plain `signIn()` ko nano ke robust version se replace karo — detail **Issue 4** mein.

### Result
> Phone se doctor ki handwritten prescription / lab report ki photo → **auto-compress** → Puter OCR (data URL) → correct text extraction → auto-fill form. Groq key laga ho to wahi (server-side) use hoga, warna Puter.

### Files affected
- `static/js/ai_gateway.js` (doOcr + extractText + compress helper)
- `templates/opd/dashboard.html` (scan flow mein compress use karna — optional, gateway hi sambhal sakta hai)

---

## 🟠 Issue 4 — Fix: Puter Sign-in Blank Popup (Settings / Connect)

### Solution (nano clinic ka proven fix port karo)

`static/js/ai_gateway.js` ka `signIn()` (line 28-33) abhi plain hai. Replace karo:

1. **Guest account detection** — sign-in ke baad `getUser()` se email check karo; email nahi = temporary guest → clear session + dobara real login.
2. **`signIn({ attempt_temp_user_creation: false, request_auth: true })`** + hard timeout (25s) — blank popup kabhi hang nahi karega, guest bhi nahi banega.
3. **Mobile/PWA pe full-tab login** (no popup) — popup blank hone ka main karan.
4. **Dedicated visible "Sign in to Puter" button** — AI call ke beech auto-popup **nahi** (yehi blank deta hai). Nano yehi karta hai.

### Reference (copy/adapt karna)
- `newmcg nano clinic/src/lib/puter.ts:273-491` (`puterSignIn`, `puterSignInViaTab`, `isRealPuterAccount`, `clearPuterSession`)

### Files affected
- `static/js/ai_gateway.js`
- `templates/opd/dashboard.html` (Connect Puter button — already hai, bas signIn robust hoga)

---

## 🔴 Issue 2 — Fix: Full Drug Bank + Medicine Auto-Fill (sabse bada flaw)

### Target behavior (doctor ka experience)
> Doctor medicine ka naam type kare → **dropdown** se select kare → **form, dose, frequency, timing, duration sab khud bhar jaye**. Nayi medicine ho to **"Save to library"** dabao — abhi save. Agli baar wahi medicine type karte hi dikhe (most-used pehle). Salt/composition bhi save ho.

### Solution — 3 layers

#### Layer 1 — DB: `opd_drug_history` ko **full drug bank** banao
New columns add karo (Alembic migration):

| Column | Type | Notes |
|--------|------|-------|
| `generic_name` | String(200) | (rename `drug_name` → `generic_name` ya naya) |
| `brand_name` | String(200) | e.g. Telma |
| `strength` | String(100) | e.g. 40 mg |
| `salt_composition` | String(500) | doctor ka "salt vagaira" |
| `form` | String(50) | Tablet / Syrup / Injection / Drops / Capsule / Cream |
| `default_dose` | String(100) | e.g. "1 tablet", "5 ml" |
| `default_frequency` | String(20) | OD / BD / TDS / QID / HS / SOS / STAT |
| `default_timing` | String(100) | Morning / After meals / Bedtime … |
| `default_duration` | String(50) | e.g. "30 days" |
| `active` | Boolean | false = autocomplete se hide |
| `use_count` | Integer | (already hai) |
| `last_used` | String(30) | (already hai) |

> Existing `dose` column → `default_dose` + `strength` mein migrate karo.

#### Layer 2 — Backend API
- **GET `/opd/api/drugs?q=`** upgrade: `"{name} {dose}"` string ki jagah **JSON objects** return karo:
  `{ id, generic_name, brand_name, strength, form, default_dose, default_frequency, default_timing, default_duration, use_count }`
  Sort: `use_count desc, generic_name asc`.
- **POST `/opd/api/drugs`** (new): drug bank mein **save/upsert** karo — one-tap "Save to library" ke liye. Fields: generic_name, brand_name, strength, salt_composition, form, default_dose, default_frequency, default_timing, default_duration.
- **DELETE `/opd/api/drugs?id=`** (new): remove/deactivate.
- **`_learn_drugs()` upgrade** (`opd_routes.py:890-932`): structured medicine rows se **saare fields** save karo (sirf regex name+dose nahi). Har saved Rx pe `use_count` bump + `last_used` update.

#### Layer 3 — Frontend (dashboard.html)
1. **Dropdown autocomplete** (sirf text buttons nahi) — nano `MedicinePicker.tsx` jaisa:
   - Type karte hi suggestion dropdown (name + brand + strength + form + default dose dikhe).
   - Select karte hi **form/dose/frequency/timing/duration auto-fill**.
   - `TIMING_FOR_FREQ` map: OD→Morning, BD→Morning+Evening, TDS→Morning+Afternoon+Evening, HS→Bedtime, SOS→As needed, STAT→Immediately.
   - `defaultDoseForForm`: Tablet→"1 tablet", Syrup→"5 ml", Injection→"1 ml", Drops→"5 drops", Capsule→"1 capsule", Cream→"apply thin layer".
2. **Structured medicine rows upgrade** (`addMedicineRow`, `dashboard.html:4107`):
   - Add fields: **brand, strength, form, salt, timing** (sirf dose/freq/food/duration nahi).
   - Har row pe **"💾 Save to library"** button (one-tap, medicine screen pe jaana nahi).
3. **Medicine Library screen/tab** (nano `MedicinesScreen.tsx` jaisa): search + add/edit/delete/deactivate + full list with use-count.
4. **Rx templates already hain** — unhe structured drug-bank linkage ke saath improve karo (combo reload = medicines auto-fill).

### Implementation order (owner check ke baad)
1. DB migration + `_learn_drugs` upgrade (backend)
2. `/opd/api/drugs` upgrade + save/delete endpoints (backend)
3. Dropdown + auto-fill + save-to-library (frontend)
4. Medicine library screen (frontend)

### Files affected
- `src/infrastructure/opd/models/opd_models.py` (DrugHistoryModel)
- `alembic/versions/` (new migration)
- `src/presentation/opd/routes/opd_routes.py` (drugs endpoints + `_learn_drugs`)
- `templates/opd/dashboard.html` (dropdown, rows, library screen)

---

## 🗺️ Overall Implementation Sequence (एक-एक करके)

| Step | Issue | Deliverable | Owner check |
|------|-------|-------------|-------------|
| 1 | **FIR-01 + FIR-04** | `ai_gateway.js` fix (OCR data URL + compress + extractText + robust sign-in) | ✅ check → approve |
| 2 | **FIR-02 Layer 1-2** | Drug bank DB + API | ✅ check → approve |
| 3 | **FIR-02 Layer 3** | Dropdown auto-fill + save-to-library + library screen | ✅ check → approve |
| 4 | **FIR-03** | (⏸️ future — jab plan karo) | — |

---

## 📚 Sources / References

- Puter OCR docs: [docs.puter.com/AI/img2txt](https://docs.puter.com/AI/img2txt/) · [developer.puter.com — How to Perform OCR in JavaScript](https://developer.puter.com/tutorials/how-to-perform-ocr-in-javascript/)
- Puter user-pays / pricing: [docs.puter.com/user-pays-model](https://docs.puter.com/user-pays-model/)
- Reference implementation (working drug bank + Puter fix): `C:\Users\pc\Desktop\gurjas ai\newmcg nano clinic\`
  - `src/components/MedicinePicker.tsx` · `src/screens/MedicinesScreen.tsx` · `src/lib/puter.ts` · `src/lib/ai.ts` · `src/types.ts`
- Existing repo plan: `PRODUCT_UPGRADATION_PUTER_PLAN.md`
