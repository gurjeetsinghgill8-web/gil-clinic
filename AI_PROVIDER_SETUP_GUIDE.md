# GIL CLINIC — AI Provider Setup Guide (Clinic + Admin)

> नया AI system: **हर clinic अपना AI खुद pay करता है। GIL CLINIC को ₹0 लगता है।**
> Implemented 28-Aug-2026 per `PRODUCT_UPGRADATION_PUTER_PLAN.md` (Part B — revised plan).

---

## 1. Clinic Owner कैसे setup करे (2 मिनट)

**Settings → 🤖 AI Provider** में तीन modes हैं:

| Mode | कौन pay करता है | Setup |
|---|---|---|
| **Auto — my own API keys** ✅ recommended | Clinic का अपना provider bill (OpenAI/Anthropic/Groq/DeepSeek/Gemini की exact price, कोई third-party cut नहीं) | नीचे कोई भी 1 key डालें → Save |
| **Puter Free AI** | Clinic का free Puter account (free credits; बड़े usage पर उनकी subscription — हमारा ₹0) | "🔌 Connect Puter" दबाएँ → free account बनाएँ |
| **Off** | कोई नहीं — AI बंद | — |

### Option A — अपनी API key (BYOK)
1. इनमें से किसी एक provider पर free/paid key बनाएँ:
   - **Groq** (सबसे सस्ता, तेज़): console.groq.com → `gsk_...`
   - **OpenAI**: platform.openai.com → `sk-...`
   - **Anthropic**: console.anthropic.com → `sk-ant-...`
   - **DeepSeek**: platform.deepseek.com → `sk-...`
   - **Google Gemini**: aistudio.google.com → `AIza...`
2. Settings → AI Provider में key paste करें → 💾 Save।
3. Key **AES-encrypted** होकर database में save होती है — कभी किसी को नहीं दिखती, कहीं leak नहीं होती।
4. System automatic failover करता है: जितनी keys डालोगे, उतने backup। Vision (handwriting/scan/lab) के लिए Gemini/OpenAI/Groq में से कोई एक ज़रूरी है। Voice के लिए Groq/OpenAI/Gemini में से एक।

### Option B — Puter (बिना key, free credits)
1. "🔌 Connect Puter" दबाएँ → popup में free account बनाएँ (Google sign-in भी चलता है)।
2. AI Mode = "Puter Free AI" → Save।
3. बस — हर AI feature चलने लगेगा, usage आपके Puter account पर जाएगा।
4. चाहें तो puter.com → Settings → AI में **अपनी खुद की provider key** भी जोड़ सकते हैं (BYOK) — तब आपका bill सीधे आपके provider को जाता है, Puter को कुछ नहीं।

### Usage देखना
Settings → AI Provider में नीचे: **"🤖 AI calls — today / this month (billed to your clinic)"**।

---

## 2. GIL CLINIC Admin (हमारे लिए) — Zero-Cost Controls

| Setting | कहाँ | Default | Meaning |
|---|---|---|---|
| `SYSTEM_AI_FALLBACK_ENABLED` | Railway env | `true` | `false` करने पर हमारी पुरानी keys (Groq/DeepSeek/Gemini/secret.txt) कभी use नहीं होंगी — **100% clinic-funded AI** |
| `GHOS_AI_KEYS_SECRET` | Railway env | SECRET_KEY से derive | Clinic keys की AES-encryption का secret — **production में set करें** (change करने पर पुरानी keys unreadable हो जाएँगी — सिर्फ deploy से पहले set करें) |
| `ai_usage_logs` table | DB | — | हर AI call का metering: clinic_id, feature, provider, tokens, success |

**Recommendation:** 1–2 हफ्ते clinics को migrate करने दें, फिर `SYSTEM_AI_FALLBACK_ENABLED=false` कर दें → हमारी API bills शून्य।

---

## 3. Architecture (2 मिनट में)

```
Clinic browser (OPD/Staff dashboard)
   │  aiFetch('/opd/api/generate-rx', ...)      ← static/js/ai_gateway.js
   ▼
FastAPI backend (opd_routes/staff_routes)
   │  ai_mode?
   ├─ "auto"  → provider_router.route_chat() → clinic की OWN keys से provider को direct call
   │            (Groq → DeepSeek → Gemini → OpenAI → Anthropic, failover automatic)
   ├─ "puter" → {code:'PUTER_CHAT', prompt, model} वापस भेजता है
   │            browser puter.ai.chat/img2txt/speech2txt करता है (USER PAYS)
   │            → result re-post → server parse/save करता है
   └─ (fallback) SYSTEM_AI_FALLBACK_ENABLED=true हो तो पुरानी system keys (capped, emergency)
```

- **New files:** `src/ai_engine/provider_router.py`, `src/ai_engine/usage.py`, `src/infrastructure/opd/models/ai_usage_model.py`, `static/js/ai_gateway.js`, `tests/test_ai_router.py`, `tests/test_e2e_ai_settings.py`
- **Modified:** `opd_models.py` (6 नए columns), `main_v2.py` (SQLite+Postgres auto-migration), `opd_routes.py` (settings + 13 AI endpoints + `/api/ai-config` + `/api/ai-usage`), `staff_routes.py` (diet-plan + `/api/ai-usage`), `templates/opd/dashboard.html` (AI Provider card + Puter button + aiFetch), `templates/dashboard/base.html` + `dietician.html`
- **Tests:** `python tests/test_ai_router.py` (16/16) · `python tests/test_e2e_ai_settings.py` (6/6)

## 4. Compliance note (DPDP Act 2023)
AI चालू करते समय Settings में consent text दिखता है। BYOK mode में patient data सिर्फ clinic के अपने provider के पास जाता है (clinic का अपना agreement)। Puter mode में data Puter (US) से होकर गुजरता है — clinic को consent देना ज़रूरी है। हर AI call `ai_usage_logs` में audited है।

## 5. Railway deploy checklist
1. `GHOS_AI_KEYS_SECRET` env set करें (लंबा random string)
2. Deploy → startup पर Postgres auto-migration नए columns + `ai_usage_logs` table बना देगा
3. (Optional, 1-2 हफ्ते बाद) `SYSTEM_AI_FALLBACK_ENABLED=false`
