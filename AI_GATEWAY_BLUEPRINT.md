# GIL AI GATEWAY — Apna Puter-Jaisa Tool (Earning Blueprint)
## 30-Aug-2026 · Deep-research based · Owner earns, clinics use without API key
## Status: BLUEPRINT — approval ke baad Phase 1 se code shuru

---

## 0. Seedha jawab (TL;DR)

**Sawaal:** Kya hum Puter jaisa apna tool bana sakte hain — main owner, main hi sab kamaunga?

**Jawab:** 
- **Poora Puter clone (Internet OS)** = ❌ **NAHI** (cloud storage + KV + workers + hosting + GUI + 500 models + global payments — mahinoon ki engineering + team + bada ops kharcha; humare liye practical nahi)
- **Puter ka paisa-kamane wala hissa (AI Gateway/reseller)** = ✅ **HAAN, bilkul practical** — ye wahi cheez hai jo Puter karta hai: users ke AI usage par margin kamana. Hum apna **chhota, clinic-focused version** bana sakte hain, aur margin **100% hamara**.

**Real-world proof (deep research):**
- Reselling AI tokens ek asli bada business hai — open-source **white-label AI gateway** ready milte hain jo 50% markup ke saath bechte hain ([ulnit/ai-api-gateway](https://github.com/ulnit/ai-api-gateway), [50% markup guide](https://dev.to/ulnit/ai-api-gateway-resell-gpt-4o-and-claude-access-with-50-markup-2oki))
- [Product Hunt: "Don't Build Products, Resell AI Tokens"](https://www.producthunt.com/p/don-t-build-products-resell-ai-tokens) — middlemen quietly cash in on AI API chaos
- China mein token-middleman market 8 billion yuan ka ho chuka hai ([36kr](https://eu.36kr.com/en/p/3950630025180169))
- OpenRouter yehi model hai (API resell with markup) — legal, standard practice
- India mein payments ke liye **Razorpay wallet/recharge** standard hai ([Indian AI startups payments stack 2026](https://dev.to/umangbuilds/the-complete-payments-infrastructure-stack-for-indian-ai-startups-in-2026-120a#1))

---

## 1. Pros & Cons (imanadari se)

### ✅ Pros (fayde)
| # | Fayda |
|---|---|
| 1 | **Poora margin hamara** — clinics ka AI bill hamare wallet se katega, markup (30-50%) hamari kamai |
| 2 | **Recurring revenue** — har prescription/OCR/diet-plan par paisa; clinics roz use karti hain |
| 3 | **Clinic ko API key ki zaroorat nahi** — sirf wallet recharge (Puter jaisa UX, hamara control) |
| 4 | **Puter dependency khatam** — unka pricing/prompt hamare upar rule nahi karega |
| 5 | **Data + customer hamare paas** — usage data se pricing/analytics improve |
| 6 | **Bada future option** — Phase 2 mein "clinic-ai.js" SDK → doosre developers ki apps bhi humara gateway use karein |
| 7 | **Ready infrastructure** — GIL CLINIC mein usage metering (`ai_usage_logs`), routing, encrypted keys PEHLE SE hain — bas wallet + payments add karna hai |

### ❌ Cons (nuksan/risks)
| # | Risk | Mitigation |
|---|---|---|
| 1 | **Provider bill ka risk** — clinic ne use kiya, hum provider ko dete hain | **Prepaid wallet** — clinic pehle recharge kare, phir use; koi credit nahi. Negative kabhi nahi |
| 2 | **Provider ToS** — kuch providers subscription-auth ko resell se mana karte hain (Anthropic ne ban kiya — [news](https://theagenttimes.com/articles/anthropic-officially-bans-using-subscription-auth-for-third)) | **API-account se resell** (OpenRouter jaisa standard) — API terms mein allowed; har provider ka ToS Phase 1 mein check |
| 3 | **Payment/KYC** — Razorpay ke liye business entity chahiye (proprietorship + current account, PAN, GST) | 1-2 hafte ka paperwork; GST chhote turnover par exempt |
| 4 | **Support burden** — "mera paisa kahan gaya" wale sawaal | Wallet mein transparent usage log + PDF statement |
| 5 | **Provider outage/rate change** | Multi-provider fallback (Groq→DeepSeek→Gemini) pehle se hai |
| 6 | **Competition** — OpenRouter/Puter already hain | Hamara edge: clinic-specific features + Hindi UX + patient data integration — generic gateway se aage |

**Practicality verdict: 8/10** — Phase 1 (app ke andar wallet) 1-2 hafte mein live ho sakta hai, margin turant shuru.

---

## 2. Architecture (3 phases)

### PHASE 1 — "GIL AI Wallet" (app ke andar, 1-2 weeks) ⭐ YEHI PEHLE
Clinic ka paisa seedha hamare paas:

```
Clinic → Razorpay Recharge (₹100/₹500/₹1000) → wallet_credits (DB)
    ↓
AI use (Rx/OCR/diet...) → provider call (HAMARI Groq/DeepSeek keys)
    ↓
usage cost × (1 + margin 40%) → wallet se kata → ai_usage_logs (pehle se hai)
    ↓
Balance kam → 20% par warning → 0 par "Recharge" prompt
```

**Naya schema (2 tables):**
- `ai_wallets`: clinic_id, balance_paise (int), last_recharge_at
- `ai_recharges`: id, clinic_id, razorpay_order_id, payment_id, amount_paise, status, created_at

**Naye endpoints (6):**
- `POST /api/wallet/recharge` → Razorpay order create → amount/currency
- `POST /api/wallet/verify` → payment signature verify → balance += amount
- `GET /api/wallet/balance` → balance + last 10 transactions
- `GET /api/wallet/statement` → PDF/CSV statement
- (internal) `deduct_ai_cost()` → har AI call ke baad; balance insufficient → 402-style error "Recharge karo"
- `GET /api/wallet/pricing` → per-feature pricing table (Rx = ₹X, OCR = ₹Y...)

**Pricing model (suggested, margin ~40%):**
| Feature | Provider cost (approx) | Clinic price (incl. margin) |
|---|---|---|
| AI Prescription (generate-rx) | ~₹0.5-1 | ₹2 |
| Quick Diagnosis | ~₹0.2-0.5 | ₹1 |
| Handwriting OCR (page) | ~₹0.3 | ₹1 |
| Lab report analyze | ~₹0.5 | ₹2 |
| Diet plan | ~₹0.3 | ₹1 |
| Specialist opinions (per specialty) | ~₹1 | ₹3 |

**Razorpay setup:** proprietorship + current account + PAN + website (www.gilclinic.com ya landing page) → Razorpay account → API keys → integration (2% + 18% GST per txn).

### PHASE 2 — Standalone "clinicio-ai.js" SDK + white-label (3-4 weeks)
- Apna JS SDK `https://ai.gilclinic.com/v1.js` (Puter ke `js.puter.com/v2/` jaisa)
- `window.clinicio.ai.chat()/img2txt()` — kisi bhi developer ki app mein add ho
- Admin dashboard: clinics, wallets, usage, margins
- Ready open-source base reuse kar sakte hain ([ulnit/ai-api-gateway](https://github.com/ulnit/ai-api-gateway) ya LiteLLM proxy) — khud se sab nahi likhna

### PHASE 3 — Full aggregation (baad mein)
- Clinic BYOK (apni key, hum ₹0 + platform fee) + reseller mode dono
- 400+ models (OpenRouter ke through bhi le sakte hain wholesale)
- Monthly subscriptions + free-tier limits (Puter jaisa)

---

## 3. 90-Din ka Roadmap

| Week | Kaam |
|---|---|
| W1 | Wallet schema + recharge/verify endpoints + Razorpay account setup (aapka paperwork parallel) |
| W2 | Deduct-on-usage wiring (saare AI features) + balance UI + pricing page + tests + live |
| W3-4 | Statement/PDF + 20% warning + admin wallet dashboard + GST invoice note |
| W5-8 | `clinicio-ai.js` SDK + public site (ai.gilclinic.com) + developer docs |
| W9-12 | White-label onboarding + marketing (clinics + developers) |

---

## 4. Legal & Compliance Checklist (India)

- [ ] Business entity (proprietorship OK) + current account + PAN
- [ ] GST registration (40L turnover se pehle optional; B2B invoice ke liye useful)
- [ ] Razorpay KYC + settlement account
- [ ] Provider ToS review (Groq/DeepSeek/Gemini API resell terms — API-key based, standard allowed; OpenRouter precedent)
- [ ] DPDP Act 2023 — patient PHI encryption (hamare paas pehle se AES-encrypted keys + data policy)
- [ ] Wallet balance = advance payment → simple accounting (unearned revenue)

---

## 5. Decision

| Q | Recommendation |
|---|---|
| Poora Puter clone? | ❌ Nahin — 8/10 impractical |
| AI Gateway (earning part)? | ✅ 9/10 practical — Phase 1 se shuru |
| Pehla step? | **Phase 1 (app wallet)** — 2 hafte, ₹0 infrastructure (existing PA server), Razorpay sirf paperwork |

**Aap bolo "Phase 1 GO" → main wallet code + UI bana dunga; aap Razorpay signup karo — margin aapka, clinics bina key ke chalengi.**
