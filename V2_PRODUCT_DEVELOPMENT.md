# GIL CLINIC — V2 Product Development & Enhancement Plan

> Based on comparison between current GIL CLINIC (FastAPI+V2) and SmartOPD-Pro-McGILL (Streamlit)
> Date: 2026-07-21

---

## 🔴 CRITICAL ISSUE #1: AI Overwriting Doctor's Treatment

### Problem
The AI (`gp_prompt` in `src/ai_engine/prompts.py:19-49`) generates a **complete prescription** including Drugs, Dosages, and Treatment Plan. This overwrites what the doctor has already written. The AI should **assist**, not **replace**.

### What the Doctor Wants
- AI should help with: **Diagnosis suggestions**, **Investigations**, **Advice**, **Follow-up**
- AI should **NOT** change the doctor's prescribed drugs/treatment
- If AI needs to suggest drug changes → it should present as "Suggestions" with a clear "ASK FIRST" approach
- The doctor's treatment is final — AI is a consultant, not a prescriber

### Fix Plan
1. **Split `gp_prompt` into two modes:**
   - **Mode 1 - "AI Assistant" (default):** AI only suggests Diagnosis, Investigations, Advice, Follow-up based on doctor's notes + doctor's medicines. Does NOT generate drugs.
   - **Mode 2 - "AI Suggest Treatment" (opt-in):** AI can suggest drug changes but MUST prefix with "💡 SUGGESTION:"
2. **UI Change:** Add a checkbox "🤖 Allow AI to suggest drug changes?" — default OFF
3. **Prompt Change:** New prompt tells AI: "The doctor has already prescribed these drugs. Do NOT change them unless explicitly asked. Focus on diagnosis refinement, additional investigations, lifestyle advice, and follow-up planning."

---

## 🔴 ISSUE #2: Dietitian — Missing Calorie Input

### Problem
The dietitian generates a plan without asking the user about **calorie requirements** first.

### What the Doctor Wants
"Dietitian ki jo advice hai na usko hamen pahle to kitni calorie per banani hai vah thoda sa user se poochh Lena chahie" — Before generating, ask the user: "How many calories should this diet be based on?"

### Fix Plan
1. **Add a "Daily Calorie Target" field** to the dietitian form (`templates/dashboard/dietician.html`)
   - Type: number input with label "Target Calories (kcal/day)"
   - Add tooltip: "Leave empty for AI to auto-calculate based on BMR"
   - Add quick-select buttons: 1200, 1500, 1800, 2000, 2500 kcal
2. **Update `diet_plan_prompt`** in `src/ai_engine/prompts.py` to accept and use calorie target
3. **Update API endpoint** to pass calorie target

---

## 🔴 ISSUE #3: Diet Plan PDF Download Missing

### Problem
The dietitian page only has "Copy" and "Print" buttons. No PDF download option.

### What the Doctor Wants
"jo diet Hai vah PDF form mein a jaaye jisse ki vah download karke ya save karke aage bhej sake" — Diet plan should be downloadable as PDF.

### Fix Plan
1. **Create `make_diet_pdf()` function** in `src/utils/pdf_generator.py`
   - Professional format: Header with clinic/doctor info, patient details, meal plan sections
   - Clean layout with section separators
2. **Add API endpoint** `POST /staff/api/diet-pdf` in staff routes
3. **Add "📄 Download PDF" button** in dietitian.html
4. **Add "📱 WhatsApp" share button** with pre-filled message

---

## 🟡 ISSUE #4: Doctor Module — Settings Enhancement

### Problem
The doctor says: "doctor ki degree aur Baki chij likhne ka option tha Hospital likhne ka option tha bahut sare option the sab khatm Ho Gaye"

### Current State (Already Present)
Current settings already have:
- Clinic Name ✅
- Doctor Name ✅
- Degree (MBBS, MD) ✅
- Subtitle / Specialty ✅
- Registration No. ✅
- Extra Qualifications ✅
- Email ✅
- Phone ✅
- Clinic Address ✅
- Groq API Key ✅

### What's Missing / Needs Fixing
1. **Hospital Name field** — separate from clinic name (multi-clinic doctors need both)
2. **AI doesn't know doctor credentials** — `gp_prompt()` only passes `doc_name`, not degree/reg no
3. **Add Doctor Photo/Logo upload** — for PDF letterhead branding
4. **Digital Signature field** — for PDF signing

### Fix Plan
1. **Add `doc_hospital` field** to SettingsModel and all settings UI/API
2. **Pass full doctor profile** to AI prompts (degree, specialty, reg no)
3. **Update PDF generator** to show hospital name separately
4. **Add signature upload** (image) to settings

---

## 🟡 ISSUE #5: Super-Speciality Expansion

### Problem
Current Specialty Upgrade section has only 7 specialties. SmartOPD has 15+.

### Current Specialties (7)
❤️ Cardiology, 🦴 Orthopedics, 🫁 Pulmonology, 👶 Pediatrics, 🩸 Diabetology, 🧠 Neurology, 👩‍⚕️ Gynecology

### SmartOPD Specialties (15)
General Medicine, Cardiology, Dermatology, ENT, Gastroenterology, Neurology, Orthopedics, Pediatrics, Psychiatry, Pulmonology, Ophthalmology, Gynecology, Urology, Endocrinology, Rheumatology

### Fix Plan
1. **Expand to 15+ specialties** in the Specialty Upgrade section
2. **Add custom specialty input** (like SmartOPD has "Or type a custom specialty name")
3. **Add multi-select with "Select All"** option for batch comparison
4. **Update `SPECIALTIES` dict** with full guidelines data for each

---

## 🟢 ISSUE #6: Voice Scribe (Speech-to-Text)

### Feature from SmartOPD
SmartOPD has voice recording for complaints using Groq Whisper API:
```python
audio = st.audio_input("🎙️ Record Complaints")
if audio:
    st.session_state["_voice_complaints"] = ai.transcribe_audio(audio)
```

### Current GIL CLINIC
The `call_whisper()` function already exists in `src/ai_engine/groq_client.py:186-221` but there's NO UI for it.

### Fix Plan
1. **Add voice record button** in the New Rx form (next to Complaints textarea)
2. Use browser's MediaRecorder API for audio capture
3. Send to `/opd/api/transcribe` endpoint
4. Fill transcribed text into complaints field

---

## 🟢 ISSUE #7: WhatsApp Sharing Link

### Feature from SmartOPD
SmartOPD has `generate_whatsapp_link()` in `pdf_gen.py:107-120` that creates a `wa.me` link with pre-filled prescription message.

### Fix Plan
1. **Add "📱 WhatsApp" button** next to PDF Preview/Download in Rx form
2. **Create backend endpoint** to generate WhatsApp link with patient data
3. Pre-fill message with patient name, doctor name, follow-up, advice

---

## 🟢 ISSUE #8: Progress Banner (Vitals Comparison)

### Feature from SmartOPD
SmartOPD's `rx_form.py:78-87` shows a progress banner comparing current visit vitals with previous visit vitals.

### Current GIL CLINIC
The `loadPatientHistory()` function already loads past visit data but doesn't show a visual progress comparison.

### Fix Plan
1. **Add vitals comparison UI** in the Rx form when loading existing patient
2. Show green/red indicators for improved/worsened metrics
3. Use the `helpers.compare_progress()` logic (port from SmartOPD)

---

## 🟢 ISSUE #9: Bulk Patient Import

### Feature from SmartOPD
Admin portal has CSV/JSON upload for bulk patient import with progress bar.

### Fix Plan
1. **Add bulk import tab** to admin portal
2. Support CSV and JSON file upload
3. Show import progress and error reporting
4. Duplicate detection by phone number

---

## 🟢 ISSUE #10: Google Sheets Integration

### Feature from SmartOPD
`sync_manager.py:39-60` fetches patient records from Google Sheets CSV export and merges with local DB.

### Fix Plan
1. **Add Google Sheet ID** to settings
2. **Create import endpoint** that fetches and merges
3. **Show "Source: Sheet/Local"** badge in patient search results

---

## 📋 Implementation Priority

| Priority | Issue | Effort | Impact |
|----------|-------|--------|--------|
| 🔴 P0 | #1 AI Overwriting Treatment | Medium | Critical |
| 🔴 P0 | #2 Dietitian Calorie Input | Small | High |
| 🔴 P0 | #3 Diet PDF Download | Medium | High |
| 🟡 P1 | #4 Doctor Settings Enhancement | Medium | High |
| 🟡 P1 | #5 Super-Speciality Expansion | Small | Medium |
| 🟢 P2 | #6 Voice Scribe | Medium | Medium |
| 🟢 P2 | #7 WhatsApp Sharing | Small | Medium |
| 🟢 P2 | #8 Progress Banner | Small | Low |
| 🟢 P3 | #9 Bulk Patient Import | Medium | Low |
| 🟢 P3 | #10 Google Sheets | Medium | Low |

---

## 📁 Files to Modify

### Prompts (AI Behavior)
- `src/ai_engine/prompts.py` — Split gp_prompt, add calorie param to diet_plan_prompt

### PDF Generator
- `src/utils/pdf_generator.py` — Add make_diet_pdf()

### OPD Routes (Doctor Dashboard)
- `src/presentation/opd/routes/opd_routes.py` — Add transcribe endpoint, WhatsApp endpoint, update AI generation flow

### Staff Routes (Dietitian)
- `src/presentation/staff/routes/staff_routes.py` — Add diet-pdf endpoint, update diet-plan endpoint with calorie param

### Templates
- `templates/opd/dashboard.html` — Add voice scribe UI, WhatsApp button, progress banner
- `templates/dashboard/dietician.html` — Add calorie input, PDF download, WhatsApp button
- `templates/opd/admin.html` — Add bulk import tab

### OPD Models (DB Schema)
- `src/infrastructure/opd/models/opd_models.py` — Add doc_hospital field to SettingsModel

### Settings UI
- Already has most fields — verify they render properly
