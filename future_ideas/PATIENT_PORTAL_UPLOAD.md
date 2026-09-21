# 🏠 Patient Portal Upload + Remote Vitals — Idea Blueprint (⏸️ KEEP ASIDE)

> **Status:** ⏸️ FUTURE — **implement NAHI karna** abhi. Jab owner plan karega, tabhi lenge.
> **Date:** 21 Sep 2026
> **Owner:** Gurjas Singh Gill
> **Parent docs:** `FIR_PRODUCT_DEVELOPMENT.md` (FIR-03) · `PRODUCT_UPGRADATION_PLAN.md`

---

## 💡 Idea (owner ka statement)

> "Patient site pe bhej diya — kya patient **apni side se apna data upload** kar de (PDF, reports, baaki cheezein) aur woh sara data **doctor ke paas aa jaye**? Jaise patient ke **ghar se BP/pulse** bhi nikal lein. **Ye bhi revolutionary hai.**"

> ✅ Note: Patient ko ghar link bhejna **already bahut achha kaam kar raha hai** (owner confirmed) — ye usi ka **extension** hai.

---

## 🎯 Target Behavior (jab implement hoga)

1. Doctor patient ko ek **secure link** bhejta hai (already working ✅).
2. Patient link kholta hai → **apna data khud upload** kar sakta hai:
   - 📄 **PDF / reports** (lab reports, purani prescriptions, doctor letters)
   - 📷 **Photos** (reports ki photo, rash/wound photo)
   - 📊 **Self-monitored vitals** — BP (systolic/diastolic), Pulse, SpO₂, Sugar, Weight, Temperature
3. Ye sab **doctor ke dashboard** mein dikhe — patient ke record ke saath, timeline/trend graph ke saath.
4. Doctor ke paas **approve/review** option — patient ka upload doctor ki OPD screen pe aaye, PDF/consultation mein use ho.

---

## 🧱 Design Draft (abhi code nahi, sirf blueprint)

### Data model (nano clinic already is pattern ka reference hai)
- `Reading` (self-monitored vitals): `readingId, patientId, code (bp-systolic/rbs/tsh…), loinc, label, value, unit, dateTime, source ('patient'|'clinic'), note, status (ok/high/low/critical)`
  - Reference: `newmcg nano clinic/src/types.ts:184-201`
- `PatientLink` (secure token): `token, patientId, phoneLast4, createdAt`
  - Reference: `newmcg nano clinic/src/types.ts:206-213`
- **Naya (GIL ke liye)**: `PatientUpload` — `uploadId, patientId, kind (pdf|image|vital), fileUrl/storage, ocrText?, uploadedAt, reviewedBy, status (pending|reviewed)`

### Flow
```
Doctor → "Patient Link" bhejta hai (WhatsApp/SMS) ✅ existing
Patient → link kholta hai → patient-pwa portal
  ├─ 📤 Upload PDF / reports / photos
  └─ 📊 BP / Pulse / SpO₂ / Sugar / Weight daalta hai
Backend → secure storage + doctor ke OPD dashboard me dikhata hai
Doctor → dashboard "Patient Uploads" section → review → prescription/PDF me use
```

### GIL current assets (reuse hoga)
- `patient-pwa/` — existing patient portal (status tracker) → **extend** karna hoga
- `templates/patient_portal.html` — existing portal page
- `src/infrastructure/opd/models/opd_models.py` — LabReportModel (OCR + structured values) pattern reuse ho sakta hai
- `static/js/ai_gateway.js` — OCR/vision pipeline reuse ho sakti hai (patient PDF/report OCR ke liye)

### Security / Privacy (important)
- Patient data DPDP Act / medical privacy ke under — uploads **encrypted + access-controlled**.
- Token-based access (nano `PatientShareSnapshot` pattern — secret token = access).
- Doctor-only review; patient sirf apna data dekhe.

---

## ⏳ Next Steps (jab plan kare)

1. Patient portal (patient-pwa) mein **upload + vitals entry** UI add karna.
2. Backend **patient upload storage + endpoints**.
3. Doctor dashboard mein **"Patient Uploads"** tab/section + trend graphs.
4. OCR on uploaded PDFs/reports (existing AI vision pipeline reuse).

> 🔒 **Abhi kuch bhi implement nahi karna.** Ye file sirf reference ke liye hai.
