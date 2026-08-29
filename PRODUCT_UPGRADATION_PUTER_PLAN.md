# GIL CLINIC (GHOS v2) — Product Upgradation Plan
## Puter AI Integration — "User Pays" Model (Zero API Cost for Us)

| | |
|---|---|
| **Version** | 1.0 (Plan only — no code changed) |
| **Date** | 28-Aug-2026 |
| **Status** | ✅ **IMPLEMENTED 28-Aug-2026** — Part B revised plan live: Direct BYOK (5 providers) + Puter user-pays + encrypted keys + usage metering + settings UI. Tests 22/22. See `AI_PROVIDER_SETUP_GUIDE.md`. |
| **UPDATE 28-Aug (2nd round)** | ⚠️ **Part B added** — आपके 4 सवालों के जवाब, सारे free alternatives का comparison, और **revised final recommendation (Direct BYOK primary + Puter optional)**। Part B को पढ़ें — यही नया final decision है। |
| **Scope** | AI cost architecture upgrade: every clinic brings/uses its own AI, GIL CLINIC pays ₹0 |
| **Reference** | https://github.com/heyputer/puter |

---

## 0. TL;DR — सार (Executive Summary)

**Problem (हमारी समस्या):** आज हर AI feature — AI prescription, handwriting OCR, voice scribe, lab analysis, diet plan — हमारी अपनी API keys (Groq / DeepSeek / Gemini / Whisper) से चलता है। जितने भी clinics हैं, उन सबका AI bill **हमारे ऊपर** आता है। हर बार API लेने/भरने/चलाने का खर्चा हमें उठाना पड़ता है।

**Solution (समाधान):** [Puter](https://github.com/heyputer/puter) — open-source "Internet OS" जिसका Puter.js SDK किसी भी website में free AI जोड़ देता है। इसका बिलिंग model है **"User-Pays Model"**:

> Developer pays **₹0**. AI usage का bill उस user के Puter account पर जाता है जो signed-in है — **हर clinic अपना खुद का AI pay करेगा**, या तो free credits से, या अपनी subscription से, या (BYOK) अपनी खुद की OpenAI/Anthropic/Groq key डालकर।

**Result (नतीजा):**
- ✅ हर user (clinic) अपनी API key खुद डालेगा और **अपना payment खुद करेगा**
- ✅ GIL CLINIC के ऊपर कोई AI खर्चा नहीं — **zero impact**
- ✅ Puter अपने आप 200+ models (GPT, Claude, Gemini, Llama, DeepSeek, Whisper…) manage करता है — automatic fallback भी
- ✅ हमारे मौजूदा Groq/DeepSeek/Gemini keys सिर्फ emergency backup बन जाती हैं (और बाद में पूरी तरह हट सकती हैं)

**What this document is:** पूरी deep review (आपके system की + Puter की) + step-by-step integration plan + cost impact + compliance + risks। **कोई code change नहीं किया गया है** — यह file ही एकमात्र output है। आपकी हरी झंडी के बाद हम Phase-wise implement करेंगे।

---

## 1. Current System — Deep Review (GIL CLINIC / GHOS v2)

### 1.1 What the system is

| Layer | Technology | Location |
|---|---|---|
| Backend | **FastAPI monolith** (Python) | `main_v2.py` — wires all engines |
| Frontend | Jinja2 templates + vanilla JS | `templates/`, `static/dashboard/app.js`, `templates/opd/dashboard.html` |
| Database | SQLite (dev) / PostgreSQL (Railway) | SQLAlchemy models in `src/infrastructure/` |
| Deployment | Railway + Docker | `Dockerfile`, `.railway/`, `DEPLOY.md` |
| Multi-tenant | Clinics + per-clinic staff PIN + license | `src/infrastructure/clinic/` |
| Legacy | Streamlit v1 (CardioQueue) | `llm_harness.py` (still in repo, v2 has replaced it) |

Engines: **Identity → Patient → Queue → Experience (PWA) → Clinic → OPD → Staff → Admin**.

### 1.2 AI feature inventory — who pays today (the pain points)

All of these today consume **our** keys through `src/ai_engine/groq_client.py` (Groq → DeepSeek fallback, Gemini, Google Vision, Whisper):

| # | AI Feature | Endpoint (file) | AI call today | Bill goes to |
|---|---|---|---|---|
| 1 | AI Prescription (Generate Rx) | `POST /opd/api/generate-rx` (`opd_routes.py`) | `call_groq` → Groq llama-3.3-70b → DeepSeek | ❌ GIL CLINIC |
| 2 | Follow-up Rx | `POST /opd/api/generate-followup-rx` | same | ❌ GIL CLINIC |
| 3 | Optimize Rx | `POST /opd/api/optimize-rx` | same | ❌ GIL CLINIC |
| 4 | Clinical Support | `POST /opd/api/clinical-support` | same | ❌ GIL CLINIC |
| 5 | Drug Review | `POST /opd/api/drug-review` | same | ❌ GIL CLINIC |
| 6 | CME generation | `POST /opd/api/cme` | same | ❌ GIL CLINIC |
| 7 | Research | `POST /opd/api/research` | same | ❌ GIL CLINIC |
| 8 | Voice Scribe (transcribe) | `POST /opd/api/transcribe` | Groq Whisper | ❌ GIL CLINIC |
| 9 | Handwriting OCR (Rx scan) | `POST /opd/api/handwriting-ocr` | Gemini → Groq Vision → Google Vision | ❌ GIL CLINIC |
| 10 | Scan AI | `POST /opd/api/scan-ai` | Vision LLM | ❌ GIL CLINIC |
| 11 | Lab Report Analyze | `POST /opd/api/lab-report-analyze` | Vision LLM | ❌ GIL CLINIC |
| 12 | Diet Plan (Dietitian) | `POST /api/diet-plan` (`staff_routes.py`) | `call_groq` | ❌ GIL CLINIC |
| 13 | Diet PDF | `POST /api/diet-pdf` | — | — |

**Planned AI (ghos_memory/phase_5_ai/ — docs approved, not yet live):** AI Receptionist (voice calls via Twilio), AI Triage, AI Follow-up, AI Voice Agent, AI Dietician, AI Prescription, AI Report Explainer. **These would multiply today's bill 5–10×** if built on our keys. They are exactly what Puter makes free-for-us.

### 1.3 How API keys are managed today (the root cause)

1. `src/ai_engine/groq_client.py` loads keys at **module import time** from: env vars → `secret.txt` (repo root, plaintext) → `.env`. It then **mutates `os.environ`** per request.
2. There IS a per-clinic `groq_api_key` column in `opd_settings` (see `opd_models.py` line 179, settings page), so a clinic *can* enter its own Groq key — but in practice most clinics don't, so **calls fall through to our keys**.
3. `staff_routes.py` (`/api/diet-plan`) uses the same global key path.
4. No per-clinic AI metering, no cap, no recharge, no cost recovery.
5. Plaintext keys in repo root files (`secret.txt`, `.env`) — a security + billing risk.

**Summary of the disease:** one shared wallet. Every clinic's usage drains GIL CLINIC's money, and we must keep recharging our own API keys (Groq, DeepSeek, Gemini) — exactly the "बार-बार API लेने के लिए पैसा देना पड़ता है" problem.

---

## 2. Puter — Deep Review

### 2.1 What is Puter

- **Open-source "Internet OS" / personal cloud computer** — [github.com/HeyPuter/puter](https://github.com/HeyPuter/puter) (AGPL-3.0, TypeScript/Node, 40k+ stars). Hosted free at **puter.com**.
- **Puter.js SDK** — one line in any website unlocks cloud services with **no backend needed**:

```html
<script src="https://js.puter.com/v2/"></script>
```

- SDK capabilities: `puter.auth` (sign-in popup), `puter.ai.*` (chat / image-to-text / text-to-image / speech-to-text / text-to-speech), `puter.fs` (user's own cloud storage), `puter.kv` (serverless key-value store), hosting, email — all free.
- Works in **browser and Node.js** (`@heyputer/puterjs` with an auth token — official "[Puter.js in Node.js](https://developer.puter.com/tutorials/puter-js-node-js/)" tutorial).

### 2.2 The AI layer

- `puter.ai.chat(prompt, { model })` → returns `{ message: { content } }`.
- **200+ models** behind one API: OpenAI (GPT), Anthropic (Claude), Google (Gemini), Groq (Llama), DeepSeek, Mistral, Meta, Perplexity, Reka, Liquid, LongCat, xAI… (catalog: `developer.puter.com/ai/<provider>/<model>/`).
- `puter.ai.img2txt(image)` — image → text/OCR (this replaces our Gemini/Groq/Google Vision chain).
- `puter.ai.speech2txt(audio)` — Whisper-grade transcription (replaces Groq Whisper).
- `puter.ai.txt2speech(text)` — TTS (powers future AI Receptionist).
- Puter internally handles **automatic provider fallback** — if one model/provider is down, it switches.

### 2.3 The User-Pays Model — THE key point

Official docs: **[docs.puter.com/user-pays-model](https://docs.puter.com/user-pays-model/)** and **[developer.puter.com/pricing](https://developer.puter.com/pricing/)**.

> "One user or a million, the cost is the same: **$0**." — the developer (us) pays nothing. The **end user** (each clinic's staff member, signed into their free Puter account) pays for their own AI usage.

How it works:
1. Clinic staff clicks **"Connect AI"** → `puter.auth.signIn()` popup → staff signs in with a **free Puter account** (or Google sign-in).
2. All `puter.ai.*` calls from that browser are billed to **that user's Puter account** — free monthly credits first, then their own (optional) subscription.
3. **BYOK (Bring Your Own Key):** in Puter's AI settings, the user can add their **own OpenAI/Anthropic/Groq/DeepSeek API key** ("custom driver"). From then on their requests route to **their own key and their own provider bill**. This is exactly your requirement: *"jo bhi user hoga, woh apni API key daale aur apna payment kare — hamare upar koi prabhav nahin."*
4. Optional: developers *can* buy "app credits" to subsidize users — **we will not** (that would recreate today's problem).

Verified community proof of this exact pattern:
- [Puter.jsでAPIキー不要のAIチャットを作り、BYOKで複数AIを共通化する](https://zenn.dev/orectic/articles/puter-js-keyless-ai-byok) (Zenn)
- [Puter.jsでAPIキー不要のAIチャットを作り、BYOKで複数AIを切り替える](https://qiita.com/masakazuimai/items/44a4d4596e4645a1fe69) (Qiita)
- [I Used This Open Source Library to Integrate OpenAI, Claude, Gemini Without API Keys](https://itsfoss.com/puter-js-ai-without-api/)
- [Free, Unlimited AI API (official tutorial)](https://developer.puter.com/tutorials/free-unlimited-ai-api/), [Serverless AI, Forever Free for Developers](https://developer.puter.com/tutorials/serverless-ai-forever-free-for-developers/)

### 2.4 Self-hosting (for completeness)

- Puter is open source and Docker-deployable. **But** a self-hosted instance has no "free credits economy" — its AI must be configured with **your own provider keys** ([issue #1180](https://github.com/HeyPuter/puter/issues/1180), [self-host AI config guide](https://blog.gitcode.com/3272b3560c8c09d2816e8f2138141ee2.html)) — which would put the bill back on us.
- **Verdict:** use hosted **puter.com** for the user-pays model. Consider self-host/Enterprise only later for a big clinic demanding strict data residency (Phase 4, optional).

### 2.5 What Puter does NOT solve (be honest)

- It is not an LLM — it's a gateway/billing layer in front of 200+ models. Model quality still depends on the chosen model.
- Medical-prompt quality must be tested per model (we control which model each feature uses).
- Puter is a young company — we keep a fallback path (see §6).
- PHI (patient data) leaving the browser to Puter's servers is a compliance question we must handle per clinic (see §5).

---

## 3. Integration Architecture — How We Fit It Into GIL CLINIC

### 3.1 Core decision: AI calls move from backend → browser (client-side Puter.js)

Why: **the user-pays billing only applies when the call carries the end-user's Puter session** — i.e., the call is made from the clinic staff's browser. A server-side call would be billed to *us* (app credits).

New flow for, e.g., Generate Rx:
```
Doctor clicks "Generate Rx"
  → browser JS builds the SAME medical prompt (prompt templates moved to JS or fetched from backend)
  → puter.ai.chat(prompt, { model })        ← billed to clinic's Puter account (₹0 for us)
  → result rendered in Rx editor
  → existing POST /api/save-rx saves it to DB (backend, no AI)
```

Backend stays in charge of: **auth, prompt templates (as an API), saving, auditing, licensing**. AI billing leaves our servers entirely.

### 3.2 New module: `static/js/ai_gateway.js` (single gateway, ~1 file)

One JS wrapper used by every dashboard page:

```js
// concept only — implementation in Phase 2 (after your approval)
aiGateway.chat({ feature: 'generate-rx', messages, model })
aiGateway.ocr(image)            // → puter.ai.img2txt
aiGateway.transcribe(blob)      // → puter.ai.speech2txt
```

Responsibilities: check "AI mode" per clinic (Puter / BYOK / fallback), call Puter.js, **log usage count to `/api/ai-usage`**, and fall back to the legacy backend AI endpoint **only** when the clinic has no Puter connection (and only using *their* key, never ours by default).

### 3.3 Per-clinic AI Provider Modes (Settings page)

New section in clinic/doctor settings (existing `/api/settings` UI in `opd_routes.py` + staff settings):

| Mode | Who pays | When to use |
|---|---|---|
| **A. Puter (Free)** ✅ default | Clinic's Puter account (free credits → their subscription) | Most clinics |
| **B. Puter + BYOK** ✅ recommended for big clinics | Clinic's own OpenAI/Anthropic/Groq key inside Puter | Clinics that want their own provider bill |
| **C. Own key (legacy)** | Clinic's own `groq_api_key` in GIL settings (already exists) | Clinics that refuse Puter |
| **D. System fallback** | GIL CLINIC (metered + capped, or disabled) | Emergency only |

Important privacy choice: the Puter **auth token stays in the browser's localStorage only** — we never send it to our server, so we never hold clinic credentials. "Connect Puter" is a one-click popup; if browser data is cleared, staff clicks reconnect.

### 3.4 Feature-by-feature migration map

| Current feature (today → our keys) | New call (browser) | Suggested Puter model (verify exact ID in Phase 0) |
|---|---|---|
| Generate Rx / Follow-up / Optimize | `puter.ai.chat` | `llama-3.3-70b-versatile` (Groq) or `gpt-4o-mini` |
| Clinical Support / Drug Review | `puter.ai.chat` | `gpt-4o-mini` or `claude-3-5-haiku` |
| CME / Research | `puter.ai.chat` | `deepseek-chat` / `gpt-4o` |
| Diet Plan | `puter.ai.chat` | `llama-3.3-70b-versatile` |
| Handwriting OCR | `puter.ai.img2txt(image)` | Puter auto-routes (Gemini-class OCR) |
| Scan AI / Lab Report Analyze | `puter.ai.chat` + image | `gemini-2.0-flash` / `gpt-4o-mini` |
| Voice Scribe | `puter.ai.speech2txt(audio)` | Whisper via Puter |
| **Future:** AI Receptionist (Twilio) | `speech2txt` + `chat` + `txt2speech` | billed to clinic, ₹0 for us |

### 3.5 Backend changes (small, surgical)

1. **Remove default AI calls** from `opd_routes.py` AI endpoints (lines ~799–1070, 1635–1775, 2026–2100, 2630+) and `staff_routes.py` (`/api/diet-plan`, line ~828) — replace with "prompt template API" + save endpoints. Keep the old code behind a `legacy_fallback` flag.
2. **New tiny endpoint** `POST /api/ai-usage` (count only: clinic_id, feature, success/fail, tokens if returned) → per-clinic metering table + admin dashboard widget.
3. `groq_client.py` stays for Mode C/D only (clinic's own key / capped system fallback). Stop mutating `os.environ` per request.
4. No new Python AI dependencies. No Node.js server required (browser SDK).

---

## 4. Cost Impact — Before vs After

| | Today | After |
|---|---|---|
| AI bill payer | **GIL CLINIC** (all clinics) | **Each clinic** (own Puter account / own key) |
| Our API keys (Groq, DeepSeek, Gemini) | Required, constantly recharged | Optional emergency backup only |
| Per-clinic AI metering | None | Built-in (ai-usage table) |
| Cost recovery from clinics | None | Possible: software subscription for GIL CLINIC stays; AI cost automatically theirs |
| Scaling to 10 / 50 / 100 clinics | Bill grows linearly on us | **Bill stays ₹0 for us** |
| Future AI features (Receptionist, Voice) | Would multiply our bill | Same ₹0 |

Sample math (today, roughly): Groq llama-3.3-70b ≈ $0.59/M input tokens + $0.79/M output; Gemini Flash ≈ ₹0.02/image; Whisper per audio-minute. With N clinics × daily patients × Rx generation + OCR + voice, this quietly becomes thousands of rupees/month on our card. **After this upgrade: zero.**

---

## 5. Security, Privacy & Compliance (Hospital-grade caution)

This is a medical system — we must not skip this:

1. **India DPDP Act 2023:** clinics are *data fiduciaries*; patient data (PHI) is *sensitive personal data*. Sending PHI to a US-hosted AI gateway (Puter) is cross-border processing → requires **clinic-level consent + notice**. Mitigations:
   - **BYOK mode** = PHI goes to the clinic's own provider (OpenAI/Anthropic etc.) under the clinic's own agreement — cleanest.
   - Add a one-time **consent checkbox** in Settings when enabling AI ("AI ke liye patient data third-party AI service ko bheja jaata hai").
   - **Pseudonymize** where clinically possible (e.g., OCR can run without patient identity).
2. **We never store clinic Puter tokens** (browser localStorage only) → no credential liability on our DB.
3. **Audit trail:** every AI call logged (feature, clinic, timestamp, success) — we already have `AuditLogModel`; extend to AI usage. This also enables billing disputes resolution.
4. **Verify Puter's data/ToS** before go-live (Phase 0) and keep a one-page summary for clinics.
5. **Housekeeping:** remove plaintext `secret.txt` keys from repo root; move remaining system keys to Railway env vars (already partially supported). Never commit keys again.

---

## 6. Rollout Plan (Phases — after your GO)

| Phase | Work | Effort | Exit criteria |
|---|---|---|---|
| **0. Spike/POC** | Puter account; test page with `puter.ai.chat`, `img2txt`, `speech2txt`; verify model IDs, free-tier limits, ToS | 1 day | All 3 API families work with a test account; model mapping table finalized |
| **1. Foundation** | `ai_gateway.js` + "Connect Puter" button + AI mode setting in Settings (OPD + staff) + `/api/ai-usage` | 2–3 days | Clinic connects via popup; mode persists; usage counted |
| **2. Text AI migration** | Rx, follow-up, optimize, clinical support, drug review, CME, research, diet-plan → Puter-first with fallback | ~1 week | Zero calls to our keys when Mode A/B active |
| **3. Vision + Voice migration** | handwriting-ocr, scan-ai, lab-report-analyze → `img2txt`/vision chat; transcribe → `speech2txt` | ~1 week | OCR quality ≥ today (side-by-side test) |
| **4. Scale + future** | AI Receptionist/Voice Agent on Puter STT/LLM/TTS + Twilio; per-clinic metering dashboard; optional self-hosted Puter for data-residency clinics; remove system fallback | ongoing | New AI features launch clinic-funded by design |

**Acceptance test (end of Phase 3):** run one full clinic day with **our system keys deleted** — every AI feature still works for the clinic, billed to the clinic. That is the proof of "koi prabhav nahin ham par."

---

## 7. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Puter outage / young company | Medium | Fallback chain: clinic's own key (Mode C) → capped system key (Mode D). Puter also auto-falls-back across providers |
| Model quality on medical prompts | Medium | Per-feature model choice + low temperature + doctor always reviews (existing flow) + Phase 3 side-by-side testing |
| Free-tier limits frustrate clinics | Medium | BYOK path (their key = their limits); document clearly in Settings |
| Staff clears browser storage → disconnected | Low | One-click reconnect; status badge in dashboard header |
| PHI cross-border compliance | Medium | Consent checkbox + BYOK recommendation + audit log + pseudonymization (§5) |
| Puter changes model IDs/pricing | Medium | Model IDs centralized in one config (`ai_gateway.js`); monitor announcements |
| AGPL concern | Low | We consume the **hosted SDK** (js.puter.com/v2), not redistributing Puter code; verify ToS in Phase 0. Self-hosting would trigger AGPL review — avoid for now |

---

## 8. Open Decisions — need your answer before Phase 0

1. **Default mode for new clinics:** Puter Free (A) — recommended, or force BYOK (B)?
2. **System fallback (Mode D):** keep our Groq/DeepSeek keys as capped emergency backup, or remove completely after Phase 3?
3. **First POC feature:** we recommend **Handwriting OCR** (highest per-use cost today, most visible win). Agree?
4. **Self-hosted Puter** for big data-residency clinics: park it for now (Phase 4), or required from day one?
5. **Clinic subscription:** keep GIL CLINIC charging clinics for *software* while AI stays their cost? (Recommended: yes — software fee remains ours, AI bill is theirs.)

---

## 9. Sources

- [github.com/heyputer/puter](https://github.com/heyputer/puter) — open-source repo
- [docs.puter.com — User-Pays Model](https://docs.puter.com/user-pays-model/)
- [developer.puter.com — Pricing: The User-Pays Model](https://developer.puter.com/pricing/)
- [Puter.js Getting Started](https://developer.puter.com/tutorials/getting-started-with-puterjs/)
- [Puter.js in Node.js](https://developer.puter.com/tutorials/puter-js-node-js/)
- [Free, Unlimited AI API (official)](https://developer.puter.com/tutorials/free-unlimited-ai-api/)
- [Serverless AI, Forever Free for Developers (official)](https://developer.puter.com/tutorials/serverless-ai-forever-free-for-developers/)
- [Puter AI chat docs](https://docs.puter.com/AI/chat/)
- [Puter AI model catalog (examples)](https://developer.puter.com/ai/qwen/qwen3.8-flash/)
- [BYOK pattern (Zenn)](https://zenn.dev/orectic/articles/puter-js-keyless-ai-byok) · [BYOK pattern (Qiita)](https://qiita.com/masakazuimai/items/44a4d4596e4645a1fe69)
- [itsfoss.com — Puter.js AI without API keys](https://itsfoss.com/puter-js-ai-without-api/)
- [Self-hosted AI config · issue #1180](https://github.com/HeyPuter/puter/issues/1180)
- [DeepWiki — Puter AI Provider Integration](https://deepwiki.com/HeyPuter/puter/8.3-ai-provider-integration)

---

## 10. What I Did NOT Change (as instructed)

- ❌ No code changes, no file edits, no DB changes, no config changes.
- ✅ Only this one plan file created: `PRODUCT_UPGRADATION_PUTER_PLAN.md`.

---

# PART B — आपके 4 सवालों के जवाब + Full Alternative Comparison (Deep Study, 28-Aug-2026)

## B1. आपके सवालों के सीधे जवाब (Direct Answers)

### सवाल 1: क्या Puter best है, या इससे भी best कुछ और है?

**Honest answer: Puter "सबसे best" नहीं है — यह एक काम में best है, बाकी कामों में दूसरे options बेहतर हैं।**

- Puter best है: **"user pays + user को कोई API key खरीदनी ही नहीं पड़ती + 200+ models एक जगह + automatic fallback"** के लिए। छोटे clinics को zero-friction onboarding चाहिए तो Puter से आसान कुछ नहीं।
- Puter best नहीं है: **"user का पैसा सिर्फ उसके अपने provider को जाए, बीच में किसी तीसरे को ₹0 जाए"** के लिए। उस काम में **Direct BYOK** (clinic अपनी key हमारे Settings में डाले, हम सीधे provider को call करें) ज़्यादा transparent और सस्ता है — और यही आपकी असली requirement है।
- **Conclusion:** कोई एक "best" नहीं — **best = दोनों का hybrid** (नीचे B3 देखें)।

### सवाल 2: क्या यह free है? API का cost normal ही आता है या कुछ amount Puter को चला जाता है?

**सच्चाई तीन हिस्सों में:**

1. **हमारे (developer) के लिए: 100% free — यह पक्का है।** Puter की official pricing page का headline ही है: *"One user or a million, the cost is the same: $0"* — developer से कोई पैसा नहीं लिया जाता ([developer.puter.com/pricing](https://developer.puter.com/pricing/))।
2. **User के लिए, अगर वह Puter के credits/subscription use करता है: हाँ, कुछ amount Puter को जाता है।** Puter एक VC-funded company है, charity नहीं। User Puter से credits/subscription खरीदता है, और Puter उसके पीछे providers (OpenAI, Anthropic…) को pay करता है। **Puter अपनी exact per-token price/margin publicly publish नहीं करता** — यानी user को provider की सीधी list price से थोड़ा ज़्यादा (margin) लग सकता है, या Puter अपनी volume-deal subsidy से घाटा उठाता है — यह transparent नहीं है। (Phase 0 में हम एक test account से real numbers नापेंगे।)
3. **User के लिए, अगर वह Puter के अंदर अपनी खुद की key डालता है (BYOK): Puter को ₹0 जाता है।** उस case में request user की अपनी key से उसके अपने provider तक जाती है — user वही normal provider price pay करता है जो उसे वैसे भी देनी थी, और Puter का उस traffic पर कोई हिस्सा नहीं।

**तो आपके सवाल का सटीक जवाब:** Puter free repository तो है (code open-source है), पर hosted service के पीछे business है — **Puter mode में user का पैसा Puter से होकर जाता है (margin संभव); BYOK mode में सीधा provider को जाता है, Puter को कुछ नहीं।** हमें (GIL CLINIC को) दोनों ही mode में ₹0 लगता है।

### सवाल 3: और कौन-से free/best software हैं? हमारे options क्या हैं जहाँ user खुद pay करे और हमें कुछ न लगे?

नीचे B2 की full comparison table — 8 options का पूरा अध्ययन। छोटा जवाब: **सबसे साफ option है "Direct BYOK" — बीच में कोई third-party ही नहीं।** Puter उसके ऊपर एक convenience layer है (free credits, no key)। OpenRouter/Vercel/Cloudflare जैसे gateways भी हैं, पर वे बीच में एक और company जोड़ते हैं।

### सवाल 4: Deep study — क्या Puter को भी कुछ पैसा जाता है या यह free repository है?

- **Code/repository: free और open-source** ([github.com/HeyPuter/puter](https://github.com/HeyPuter/puter), AGPL-3.0 license) — कोई भी self-host कर सकता है। Self-host करने पर AI अपनी keys से configure करनी पड़ती है ([issue #1180](https://github.com/HeyPuter/puter/issues/1180)) — यानी self-host में user-pays economy नहीं मिलती।
- **Hosted puter.com: एक business है।** कमाई के स्रोत: (a) users की AI/storage subscriptions और credits, (b) developers द्वारा खरीदे गए "app credits" (हमें नहीं चाहिए), (c) Puter Enterprise. Free users को credits Puter अपनी जेब से fund करता है (user-acquisition cost)।
- **तो: "free repository" — हाँ code के हिसाब से; "free service" — हमारे लिए हाँ, users के paid usage पर Puter की margin — संभव है, published नहीं।** इसीलिए हमारा revised plan BYOK को primary बनाता है।

---

## B2. 8 Options की Full Comparison Table (Deep Study)

| # | Option | हमें cost | User को cost | बीच की company को cut | Setup effort | PHI/Data path | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **Direct BYOK** — clinic की अपनी key हमारे Settings में (encrypted), हम provider को direct call करें | **₹0** | Provider की exact list price | **₹0 — कोई बिचौलिया नहीं** | Low–Medium (हमारे पास per-clinic key column पहले से है; multi-provider UI + encryption जोड़ना है) | Clinic का key → provider directly | ⭐ **सबसे transparent & सस्ता — PRIMARY बनाएं** |
| 2 | **Puter (hosted, User-Pays)** | **₹0** | Free credits → Puter subscription/credits (margin opaque) | Puter की margin (publish नहीं) | Very Low (1 script) | Browser → Puter (US) → provider | ⭐ **Free-tier onboarding के लिए OPTIONAL** |
| 3 | **Puter + BYOK (user की key Puter में)** | **₹0** | Provider की exact price | ₹0 (Puter सिर्फ pass-through) | Very Low | Browser → Puter → clinic का provider | अच्छा, पर फिर भी PHI Puter से होकर गुजरता है |
| 4 | **OpenRouter (user OAuth PKCE)** — user अपने OpenRouter account से sign-in करे, usage उसके credits से | ₹0 | OpenRouter की price (provider price + platform fee) | ~5–5.5% platform fee (credit-card), 2026 में fee घटाई गई है ([Amnic](https://amnic.com/blogs/openrouter-pricing), [Coplay](https://www.coplay.dev/blog/openrouter-drops-fees-in-response-to-vercel-s-ai-gateway)) | Medium (OAuth PKCE flow) | Browser → OpenRouter → provider | Puter जैसा ही concept, पर fee पब्लिक है |
| 5 | **Vercel AI Gateway** — zero-markup gateway | ₹0 | Provider price (no markup) | 0% markup ([Vercel pricing](https://vercel.com/docs/ai-gateway/pricing)) | Medium — Vercel ecosystem के लिए बना है, हमारा Railway+Python stack awkward है | Via Vercel infra | "No-cut" gateway — पर हमारे stack से मेल नहीं खाता |
| 6 | **Cloudflare AI Gateway** — free allocation + overage, BYOK support | ~₹0 (free allocation) | Provider price + Cloudflare overage fee | छोटा usage fee (pricing page: [Cloudflare](https://developers.cloudflare.com/ai-gateway/reference/pricing/)) | Medium | Via Cloudflare infra | Enterprise-grade, पर extra infra dependency |
| 7 | **Self-hosted gateway (LiteLLM / Portkey)** — हमारा proxy, per-clinic virtual keys, Portkey BYOK | Infra cost (server ~₹500–1500/माह) | Provider price (clinic की key) | ₹0 third-party (सिर्फ हमारा infra) | High (ops, monitoring) | हमारे server से provider तक — सबसे ज़्यादा control | Phase 4 का option (data-residency/बड़े clinics) |
| 8 | **Providers के free tiers direct** (Groq free, Gemini free…) | ₹0 | ₹0 | ₹0 | Low | Direct provider | ❌ Production के लिए unreliable — rate limits छोटे, terms के खिलाफ scale पर use करना |

**Gateway market की ground reality (2026):** हर gateway (Puter, OpenRouter, Vercel, Cloudflare, Portkey…) में मूल सवाल एक ही है — *"markup कौन लेता है और कितना?"* ([dev.to — Who Marks Up Your Tokens](https://dev.to/smakosh/ai-gateway-fees-compared-who-marks-up-your-tokens-19), [llmgateway.io — Fees & Markups Compared](https://llmgateway.io/blog/ai-gateway-fees-compared), [TheRouter.ai — Pricing Compared](https://therouter.ai/blog/ai-model-router-pricing-cost-comparison-2026/))। **इसीलिए सबसे सस्ता और सबसे साफ रास्ता हमेशा "बिना gateway" (Option 1) होता है — और user-pays requirement के लिए वही सही है।**

---

## B3. REVISED FINAL RECOMMENDATION (यह Part A के §3 से नया और बेहतर है)

**"Direct BYOK primary + Puter free-tier optional + system keys emergency-only"**

```
                    ┌─────────────────────────────────────────────┐
                    │  GIL CLINIC — AI Provider Router (per clinic)│
                    └─────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
  MODE 1 (default)            MODE 2 (onboarding)          MODE 3 (emergency)
  Direct BYOK                Puter Connect                Capped system key
  clinic की अपनी key         free Puter account           (बाद में हटा सकते हैं)
  OpenAI/Anthropic/Groq/     no key खरीदनी नहीं पड़ती     सिर्फ fallback
  DeepSeek/Gemini (कोई भी)   free credits से AI चलता है
        │                           │                           │
        ▼                           ▼                           ▼
  Provider को direct          Puter → provider             Groq/DeepSeek
  clinic pay करता है          clinic का account pay       (हम, capped)
  (exact list price,          करता है (free credits/
  ₹0 middleman)               subscription)
```

**क्यों यह revised plan बेहतर है:**

1. **आपकी असली requirement पूरी होती है:** "user अपनी API key डाले और अपना payment करे, हम पर कोई प्रभाव नहीं" = Mode 1 (Direct BYOK), **बिना किसी third-party के**। Clinic को provider की exact normal price ही देनी पड़ती है — "कुछ amount किसी और को चला जाता है" वाली चिंता खत्म।
2. **छोटे clinics के लिए friction खत्म:** जो clinic key खरीदना ही नहीं चाहता, वह Mode 2 (Puter free credits) से तुरंत शुरू करता है — और बाद में जब चाहे Mode 1 पर shift हो सकता है।
3. **हमें हर mode में ₹0।** Mode 3 (हमारी key) सिर्फ emergency में, metered + capped — और Phase 3 पूरा होते ही optional रूप से बंद।
4. **Medical privacy बेहतर:** Mode 1 में PHI सिर्फ clinic के अपने provider तक जाता है (clinic का अपना agreement) — DPDP Act 2023 के हिसाब से सबसे साफ रास्ता। Puter (US middleman) सिर्फ उन्हीं clinics के लिए जो खुद consent दें।

**इस revised plan से implementation और आसान हो जाता है:** `opd_settings.groq_api_key` column पहले से मौजूद है — उसे multi-provider "AI keys" section (OpenAI/Anthropic/Groq/DeepSeek/Gemini, AES-encrypted at rest) में upgrade करना है + one `ai_gateway.js` router (Mode 1 → backend with clinic's key; Mode 2 → puter.js in browser)। बाकी सब कुछ (prompts, save, audit) वैसा ही रहता है जैसा Part A में लिखा है।

---

## B4. ईमानदारी से बताने वाली बातें (Honest Caveats)

1. **Puter की exact per-token price/margin publicly publish नहीं है** — मैंने ढूँढा, उनकी pricing page सिर्फ "developer pays $0" कहती है। इसलिए मैं आपको गलत number नहीं बता रहा। **Phase 0 में हम एक test Puter account से real usage कीमत नापेंगे** और तब decide करेंगे कि Mode 2 default रखें या सिर्फ optional।
2. **Puter users के free credits की exact monthly संख्या भी public docs में साफ नहीं है** — यह भी Phase 0 verification item है।
3. **OpenRouter की fee 2026 में बदल रही है** (Vercel competition की वजह से fee drop हुई है) — go-live से पहले current rate check करना होगा, अगर कभी Option 4 चाहिए तो।
4. **Free tiers (Groq/Gemini free) production SaaS के लिए reliable नहीं** — "free unlimited" वाले blog claims पर भरोसा मत करें; rate limits और terms असली सीमा हैं ([dev.to — Real Rate Limits](https://dev.to/hirak8/best-free-ai-apis-for-developers-2026-with-real-rate-limits-1k5l), [TokenMix — Reality Check](https://tokenmix.ai/blog/free-ai-api-no-limit-2026-reality-check))।
5. **Puter एक young company है** — इसीलिए उसे हमारा single point of failure नहीं बनाना। Revised plan में वह वैसे भी secondary है।

---

## B5. Updated Decisions — अब सिर्फ ये confirm करें

1. ✅ **Revised plan मंज़ूर है?** (Direct BYOK primary + Puter optional + capped system fallback)
2. **Mode 1 में कौन-से providers की keys clinics को देने दें?** (Recommend: OpenAI + Anthropic + Groq + DeepSeek + Gemini — सबका एक ही dropdown)
3. **Mode 2 (Puter free tier) onboarding के लिए default रखें या बंद?** (Recommend: रखें — छोटे clinics के लिए)
4. **System fallback (हमारी keys):** capped emergency रखें या पूरी तरह हटा दें? (Recommend: 3 महीने capped रखें, फिर बंद)

**Next step:** आप "GO" कहें → Phase 0 (1-day POC): (a) test Puter account से असली prices/limits नापना, (b) Direct BYOK का एक prototype (clinic की key से generate-rx), (c) दोनों की side-by-side quality test। उसके बाद Phase 1–3 implement करते हैं।
