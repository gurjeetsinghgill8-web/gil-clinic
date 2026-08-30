# GIL CLINIC — "Jarvis" Voice Professor (Human-like Clinical Discussion)
## Blueprint · 30-Aug-2026 · Sirf FREE tools · Status: PLAN (approval ke baad code)

> **Doctor ka vision:** CME ko aisa banao jo **sunkar jawab de** — jaise koi human doctor/professor
> clinical-scientific sawal **voice mein sun kar**, **voice mein hi samjhaye**. Multi-language
> (Hindi/English/regional). Jarvis jaisa experience. **Sab free.**

---

## 0. Seedha jawab

**HAAN, 100% ban sakta hai — aur ₹0 mein.** Poora voice pipeline **browser ke andar hi** chalta hai:

```
Doctor bola (mic)  →  Speech-to-Text (browser, FREE)  →  LLM brain (Puter/DeepSeek/Groq, FREE)
     →  Text-to-Speech (browser, FREE)  →  Professor ki awaz speaker se jawab
```

Koi server cost nahi, koi paid API nahi. Ye wahi pattern hai jo Siri/Alexa use karte hain — par hum
clinical professor ke roop mein, Indian languages mein.

---

## 1. FREE Tools (sirf ye 4, sab ₹0)

| Layer | Tool | Cost | Kahan chalta hai |
|---|---|---|---|
| **1. Sunna (STT)** | **Web Speech API** (`webkitSpeechRecognition`) — Chrome/Edge mein built-in | **₹0** | Doctor ke browser mein (Google speech servers, free, no key) |
| **2. Brain (LLM)** | **Puter AI** (pehle se integrated) ya **DeepSeek/Groq free tier** | **₹0** (free credits/tier) | Puter browser / hamara wallet/keys |
| **3. Bolna (TTS)** | **Web Speech API** (`speechSynthesis`) — browser ki local neural voices | **₹0** | Browser (offline bhi) |
| **4. Fallback TTS** | **edge-tts** (Microsoft Edge neural voices — pehle se requirements mein) | **₹0** | Server (PA par whitelist ke baad) |

**Sabse bada fayda:** STT + TTS browser mein hain, isliye **PA ka outbound-block/whitelist koi issue nahi** — sirf LLM (Puter) chahiye jo pehle se chal raha hai.

---

## 2. Multi-Language (Web Speech API support karta hai)

| Language | Code | Kaun |
|---|---|---|
| Hindi | `hi-IN` | North India clinics |
| English (India) | `en-IN` | Default |
| Marathi | `mr-IN` | Maharashtra |
| Tamil | `ta-IN` | Tamil Nadu |
| Telugu | `te-IN` | AP/Telangana |
| Bengali | `bn-IN` | WB |
| Gujarati | `gu-IN` | Gujarat |

Ek **language toggle** — doctor Hindi bole, professor Hindi mein jawab de. Mixed Hinglish bhi chalega.

---

## 3. "Jarvis Professor" Persona (LLM prompt)

> "Tum ek senior clinical professor + practicing physician ho — 25 saal ka teaching experience.
> Doctor se EK HUMAN jaisi baat kar rahe ho, lecture nahi de rahe. Uska sawal SUNKAR jawab do:
> - Pehle seedha jawab (1-2 line), phir short reason, phir 1 practical OPD tip.
> - Short sentences — voice ke liye (lambe paragraphs mat bolo).
> - Numbers/doses saaf bolo. Indian brand names bhi batao.
> - 2026-aware: guidelines evolve — outdated mat bolo, 'latest verify karo' agar yaad na ho.
> - Doctor ki language mein hi jawab do (Hinglish → Hinglish, Tamil → Tamil).
> - Kabhi kabhi 1 follow-up sawal khud poocho ('Dose confirm karna chahenge?')."

---

## 4. Features (Jarvis jaisa)

1. **🎙️ Tap-to-talk button** — dabao → bolo → professor jawab de (aur **voice se bhi**)
2. **🔁 Auto-listen** — jawab ke baad khud sunna shuru, continuous discussion
3. **🗣️ Voice ON/OFF** — voice sunna ho ya sirf text padhna, doctor ki marzi
4. **🌐 Language toggle** — hi-IN / en-IN / regional
5. **📝 Text fallback** — mic na ho to type bhi kar sakta hai (current chat yahi hai)
6. **🔊 Read-aloud** — purane jawab bhi suno
7. **⏹️ Stop/Skip** — professor bol raha ho to rok do
8. **💾 Discussion save** — poori baat record (text + optional audio summary)
9. **👁️ "Jarvis" chip** — corner mein chhota assistant icon (jeevan hua feel)

---

## 5. Implementation Phases (90 din)

| Phase | Kya | Time |
|---|---|---|
| **P1 — Voice in CME** | CME Discuss mein mic button + voice answer. Language toggle (hi-IN/en-IN). Persona prompt. | 2-3 din |
| **P2 — Auto-listen + read-aloud** | Continuous conversation + stop/skip + old answers sunna | 2 din |
| **P3 — App-wide Jarvis** | Assistant har page par (Rx, OPD, Settings) — "patient ka BP 190/70 hai kya karu?" | 4-5 din |
| **P4 — Polish** | Regional languages, wake-word "Hey Clinic", discussion save/replay | baad mein |

---

## 6. Honest Limitations (pehle se jaan lo)

1. **Browser STT internet maangta hai** (Google speech servers) — mic kholte waqt browser permission puchta hai. Doctor ke laptop/mobile par Chrome/Edge hona chahiye.
2. **Medical terms ki accuracy** — "Telmisartan", "HFpEF" jaisi words kabhi-kabhi galat sun sakti hain; isliye **text bhi saath dikhta hai** (doctor turant correct kar le).
3. **Hindi TTS voice** — kuch Windows par Hindi voice pre-installed nahi hoti; fallback `edge-tts` (server) ya doctor 1 voice install kare. English voice har jagah hai.
4. **Privacy (DPDP):** doctor ki awaaz browser ke STT engine (Google) par jati hai — patient PHI bolte waqt care karein; ya `edge-tts`/local model future mein. Consent note UI mein add karenge.
5. **Puter LLM** pehle se hai — isliye voice ka koi naya bill nahi; sirf agar DeepSeek/Groq key daalenge to wo cost (free tier se shuru).

---

## 7. Cost — 100% Free

| Cheez | Cost |
|---|---|
| STT (browser Web Speech) | ₹0 |
| TTS (browser speechSynthesis) | ₹0 |
| LLM (Puter free credits / DeepSeek-Groq free tier) | ₹0 (shuru mein) |
| **Total** | **₹0** |

---

## 8. Decision

| Q | Recommendation |
|---|---|
| Ban sakta hai? | ✅ HAAN — P1 2-3 din mein |
| Kahan se shuru? | **P1: CME Discuss mein "🎙️ Bolo" + voice jawab** |
| Free? | ✅ 100% free (browser voice + Puter) |

**Aap bolo "P1 GO" → main CME mein mic button + voice answer + Hindi/English toggle bana dunga, browser mein test karke dikhaunga.**
