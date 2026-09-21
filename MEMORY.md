# 🧠 GIL CLINIC — MEMORY (single source of truth)

> ## ⚠️ SABSE PEHLE: DO ALAG SOFTWARE HAIN (kabhi mix na karo)
>
> Doctor ke paas **do bilkul alag products** hain. Inka code, data, hosting aur login — sab alag hai.
> **Ek me kiye gaye change doosre me apne aap nahi jaate** (feature dono me banana padta hai,
> jaise patient portal dono me hai — par code alag hai).
>
> | | **GIL CLINIC** — Smart OPD / GHOS v2 | **NANO CLINIC** — CLINICITY OPD |
> |---|---|---|
> | Folder | `C:\Users\pc\Desktop\gurjas ai\GIL CLINIC` | `C:\Users\pc\Desktop\gurjas ai\newmcg nano clinic` |
> | Kya hai | Hospital/OPD system — reception → queue/token → doctor → lab → admin | Single-doctor OPD clinic app (patients, prescription, AI, monitoring) |
> | Tech | **Python FastAPI + Jinja2 + SQLite** | **React + TypeScript + Vite PWA + IndexedDB + Firebase** |
> | LIVE URL | **https://gillhopitalsoftware1.pythonanywhere.com/opd/dashboard** | **https://clincity-opd.web.app** |
> | Host | PythonAnywhere (free, card nahi) | Firebase Hosting (GitHub push par CI deploy) |
> | Login | PIN **5554** / 1234 / 1010 | Doctor PIN (6-digit, device par set hota hai) |
> | Data kahan | SQLite `/home/…/gil-clinic/ghos_prod.db` (host par) | IndexedDB (device) + Firestore (cloud) |
> | Git repo | `gurjeetsinghgill8-web/gil-clinic` | `gurjeetsinghgill8-web/clincity-opd` |
> | Version | GHOS v2.0.0 | CLINICITY **v0.8.0** |
> | Patient self-filling | `/my/<token>` (patient) · `/s/<token>` (doctor read-only) | `#patient/<token>` · `#share/<token>` |
> | Naya code live | `python pa_deploy.py ship --since <commit> --no-git --no-tests` | `git push` (CI) ya `npm run build && firebase deploy` |
> | Memory file | **yahi file** | `…\newmcg nano clinic\MEMORY.md` |
>
> Neeche sirf **GIL CLINIC** ki baatein hain.

> **Ye file har naye session/agent ko SABSE PEHLE padhni chahiye.**
> Yahan sirf wahi baatein hain jo baar-baar kaam aati hain: live URL, login, hosting,
> deploy commands, aur wo faisle jo ho chuke hain. Detail ke liye neeche di gayi files.
>
> **Last updated:** 21-Sep-2026 · **Owner:** Dr. G. S. Gill

---

## 1. 🔴 LIVE SYSTEM — GIL CLINIC (yahi asli production hai)

| | |
|---|---|
| **Doctor dashboard (LIVE)** | **https://gillhopitalsoftware1.pythonanywhere.com/opd/dashboard** |
| Login page | https://gillhopitalsoftware1.pythonanywhere.com/opd/login |
| **Doctor PIN** | **5554** (Chief) · 1234 (Junior) · 1010 (Admin) |
| Patient portal (patient ko bheja jata hai) | `https://gillhopitalsoftware1.pythonanywhere.com/my/<token>` |
| Doctor read-only share (patient → koi bhi doctor) | `https://gillhopitalsoftware1.pythonanywhere.com/s/<token>` |
| Health check | https://gillhopitalsoftware1.pythonanywhere.com/health |
| Host | **PythonAnywhere** — account `gillhopitalsoftware1` (**FREE**, no card, kabhi sleep nahi) |
| Code location on host | `/home/gillhopitalsoftware1/gil-clinic` (venv: `~/.virtualenvs/gilclinic`) |
| Live DB (permanent) | `/home/gillhopitalsoftware1/gil-clinic/ghos_prod.db` |
| Git repo | https://github.com/gurjeetsinghgill8-web/gil-clinic (`main` branch) |

**Railway:** service `gil-clinic` **Offline** hai (free tier khatam ho gaya, ab $5/mo plan) — **use nahi karna**.
**Clinic ka PC:** 3 din me ek baar khulta hai — is liye PC ko host **nahi** banaya (sirf emergency backup scripts ready hain).

---

## 2. ⚠️ Card nahi hai (is liye ye raste band hain)

| Host | Kyun band |
|---|---|
| Oracle Cloud Always Free | signup me **card verification** chahiye |
| Google Cloud e2-micro | card chahiye |
| Railway / Fly.io / Render paid | card / paid plan |
| **PythonAnywhere (free)** | ✅ **card nahi chahiye** — isliye yahi hamara host hai |

**PA free ki limits (yaad rakho):**
- **100 CPU-second / din** → bhaari AI usage quota khatam kar sakti hai (us din app band)
- **Scheduled tasks allowed nahi** (403) → daily backup app ke in-built auto-backup se hota hai
- **Custom domain nahi** → address `gillhopitalsoftware1.pythonanywhere.com` hi rahega
- **Outbound internet sirf whitelist — SABSE BADA AI BLOCKER** → PA free server sirf whitelisted hosts
  tak internet deta hai. Is liye **BYOK API keys (Groq / DeepSeek / OpenAI / Gemini) PA par kaam NAHI karti** —
  key bilkul sahi hone par bhi "connection failed" aata hai, kyunki server provider tak pahunch hi nahi sakta.
  - Live par confirm kiya (21-Sep-2026): `POST /opd/api/test-key` (Groq key saved thi) →
    `"Groq (Llama) tak pahunch nahi paye: All connection attempts failed"`
  - **AI chalane ka ekmatra FREE rasta = Puter** — wo **doctor ke BROWSER** se chalta hai, is server block se
    affect nahi hota. Isi liye app ka default `ai_mode = puter` hai.
  - Apni paid key chalani ho to: **(a)** PA ko whitelist request bhejo — project me `pa_whitelist_request.txt`
    ready hai (pythonanywhere.com → **Help → Send feedback** me paste karo), ya **(b)** PA ka **Hacker plan ($5/mo)**
    lo — usme outbound block nahi hota.
  - **Patient portal ko AI ki zaroorat nahi** — wo is block se bilkul affect nahi hota (verified).

---

## 3. 🚀 Naya code live kaise karte hain (3 command)

```bash
python pa_deploy.py ship --since <jis-commit-se-aage> --no-git --no-tests   # upload + reload + health
python pa_deploy.py status_check                                           # live routes verify
node scripts/pa_live_e2e.cjs && python scripts/pa_cleanup.py                # poora live test + safai
```
- `pa_deploy.py status` → account state · `env_check` → remote .env · `log` → setup log
- Token `pa_token.txt` me hai (**gitignored — kabhi commit nahi**)
- PA ka remote git checkout files-API upload ke baad peeche reh jata hai → `setup.sh` ab
  `git fetch + reset --hard origin/main` karta hai (git pull nahi)
- Poora detail: **`PA_DEPLOY_GUIDE.md`**

### 3.1 🔍 NAYA CODE LIVE HUA YA NAHI — kaise pata chalega (BUILD STAMP)

> **Ye zaroori rule hai — har deploy par build stamp badalna chahiye.**

**Problem jo pehle thi:** `/health` me build string **hardcoded** thi (`"2026.08.06.v2.0"`) —
is liye naya code chadhne ke baad bhi wahi purana dikhta tha aur pata hi nahi chalta tha
ki naya version live hua ya nahi.

**Ab kya hota hai:** `pa_deploy.py ship` **har baar** ek naya `build_info.json`
(git commit + UTC time + kitni files gayi) banata hai, upload karta hai, aur app use padhta hai.

**Naya/purana check karne ke 3 tareeke:**

| Kahan | Kaise |
|---|---|
| **1. Browser me (sabse aasan)** | OPD dashboard kholo → sidebar ke **sabse neeche footer** me **`Build: 2026-09-21.1432.12d49c3 · 2026-09-21T09:02Z`** likha dikhta hai. Har deploy ke baad ye badal jata hai. |
| **2. Health URL** | https://gillhopitalsoftware1.pythonanywhere.com/health → `{"status":"ok","build":"2026-09-21.1432.12d49c3","commit":"12d49c3","built_at":"...","files_shipped":1,"version":"2.0.0"}` |
| **3. Terminal** | `python pa_deploy.py status_check` → sabse pehli line **`BUILD LIVE : ...`** print karta hai |

**Deploy ke baad ka niyam:** `ship` ke output me `BUILD = ...` line aati hai — wahi build
dashboard footer me dikhna chahiye. **Agar dono same hain to naya code live hai.**
Agar footer me purana build dikhe → browser **hard refresh (Ctrl+Shift+R)** karo (cache),
phir bhi purana ho to reload fail hua — `pa_deploy.py site_reload` chalao.

**`build_info.json`** project root me banta hai (deploy ke waqt) — ise chhedna nahi,
ye apne aap ban jata hai.

---

## 4. 🧩 Patient Self-Filling System (v1.0 — LIVE, verified)

| Feature | Route / jagah |
|---|---|
| Patient apni BP/sugar/pulse/weight/temp bhare (mobile verify ke baad) | `/my/<token>` |
| Graphs (server-side SVG, green normal band) + Excel-style table | usi page par |
| Download PDF (graphs ke saath) / HTML / CSV | `/my/<token>/export?fmt=pdf\|html\|csv` |
| **"Doctor ko bhejo"** read-only link (7 din expiry, koi write nahi) | `/s/<token>` |
| Doctor: **📱 Patient link** button (patient select karte hi) | New Rx tab |
| Doctor: **🩺 Patient Monitor** tab (list → graphs → report) | dashboard nav |
| Doctor APIs | `/opd/api/patient-link · patient-readings · portal-patients · portal-stats · patient-report · base-url` |
| Naye tables | `patient_readings`, `patient_portal_links`, `patient_shares`, `patient_requests` |

**Verified 17-Sep-2026 (live PA par, asli browser):** doctor login → patient link → patient verify →
reading save → graph/table → share link → doctor read-only view. Test data delete kar diya (production me 0 readings).
Detail + phase 4 list: **`PRODUCT_UPGRADATION_PATIENT_FILLING_PLAN.md`**

---

## 5. 🛠 Kaam ke files (kis file me kya hai)

| File | Kaam |
|---|---|
| `main_v2.py` | FastAPI app boot (routers + tables create + volume/DB path) |
| `src/presentation/opd/routes/opd_routes.py` | Smart OPD (doctor dashboard APIs) — **3638 lines, chhedne se bacho** |
| `src/presentation/patient_portal/routes/patient_portal_routes.py` | Patient portal + share + doctor APIs (naya) |
| `src/utils/patient_*.py` | metrics, SVG charts, reports (HTML/CSV/PDF), tokens, portal HTML |
| `src/utils/public_url.py` | patient links ka base URL (dead tunnel/Railway URL se bachav) |
| `templates/opd/dashboard.html` | doctor dashboard UI (nav + Patient Monitor tab + link modal) |
| `tests/test_patient_portal.py` | 12 pytest (metrics, reports, portal flow, expiry, base URL) |
| `deploy/permanent/` | PC-server + permanent URL ke scripts (emergency/backup rasta) |
| `FREE_HOSTING_PLAN.md` | hosting faisla + Railway verdict |
| `PA_DEPLOY_GUIDE.md` | PA deploy ka poora tarika |
| `build_info.json` | deploy ke waqt apne aap banta hai — live **BUILD stamp** (naya/purana check karne ke liye) |
| `FIR_PRODUCT_DEVELOPMENT.md` | issues ka register (FIR) + deployment log |
| `PRODUCT_UPGRADATION_PLAN.md` | upgrade plan + implementation status |
| `future_ideas/PATIENT_PORTAL_UPLOAD.md` | patient upload idea (⏸️ abhi implement nahi karna) |

---

## 6. ✅ Faisle jo ho chuke (dobara discuss karne ki zaroorat nahi)

1. **Host = PythonAnywhere (free)** — kyunki card nahi hai aur PA kabhi sota nahi.
2. **Railway chhod diya** — free tier khatam; data bhi volume ke bina udta tha.
3. **PC ko 24/7 host nahi banaya** — PC 3 din me ek baar khulta hai (scripts ready hain, emergency ke liye).
4. **Patient portal me AI nahi** — self-reported readings, graphs, PDF; AI sirf doctor ke tools me.
5. **Share link read-only + 7 din** — doctor kabhi patient ka data badal nahi sakta.
6. **Har deploy par BUILD stamp badalta hai** — `/health` aur dashboard sidebar footer se turant pata chalta hai ki naya code live hua ya nahi (pehle version hardcoded tha, is liye kabhi nahi badalta tha).
7. **AI ka sabse bharosemand rasta = Groq key** — Puter ka sign-up Puter ki taraf se hi toota hua hai ([#1430](https://github.com/HeyPuter/puter/issues/1430)); is liye doctor ko Groq key ka option hamesha batana (usme koi login/popup nahi chahiye).
8. **Drug bank = doctor ka personal medicine bank** — ek baar save karo, agli baar sirf naam type karo, dose/timing khud bhar jayega.

---

## 7. ⏳ Aage ke kaam (agar doctor chahe)

- [ ] Phase 4: patient appointment/follow-up **request** + doctor ka reply (`patient_requests` table ready hai)
- [ ] Prescription PDF par **"ghar ke BP ka average (7 din)"** — patient ke self-readings se
- [ ] Critical reading aane par doctor ko **alert/badge**
- [ ] AI whitelist confirm karna (Groq/DeepSeek/OpenAI PA par chal rahe hain ya nahi)
- [ ] Purane `patient-pwa/` (lab token tracking) ko naye portal ke saath ek installable PWA me jodna

---

## 8. 💊 Drug Bank (Medicine auto-fill) — LIVE 21-Sep-2026

Doctor ki sabse badi shikayat thi: *"medicine ka naam, dose, timing baar-baar type karna padta hai"*.

| Cheez | Jagah |
|---|---|
| Drug bank table | `opd_drug_history` — 9 naye columns: `brand_name`, `strength`, `salt_composition`, `form`, `default_frequency`, `default_timing`, `default_duration`, `active`, `updated_at` |
| **GET** `/opd/api/drugs?q=` | autocomplete — ab **JSON objects** deta hai (pehle sirf plain strings) |
| **POST** `/opd/api/drugs` | medicine save/upsert (one-tap 💾 save-to-library) |
| **DELETE** `/opd/api/drugs?drug_id=` | library se hide |
| **POST** `/opd/api/drugs/backfill?reset=true` | purani prescriptions se bank dobara banao (idempotent — duplicate nahi bante) |
| UI | Rx tab → medicine row me **dropdown auto-fill** + **💾** button; **💊 Library** button se pura manage (add/edit/delete, brand, salt) |

**Auto-learn:** har saved prescription se drugs khud bank me aate hain (`_learn_drugs`).
**Live par bhara gaya:** 16 purani prescriptions → **11 entries** (Olmin 20, Citrizine 5/10, Dolo 500/650, zifi 200, Ascoryl, Augmentin 625, Azee 500, Cetrizine 10mg, Moxikind cv 625).

**Yaad rakho:** Rx parser (`_parse_rx_line`) **do format** sambhalta hai —
`Tab Olmin 20 OD before food x 30` **aur** `1. Tab. Metformin 500mg - BD - After meals - 30 Days`.
Drug naam **case-insensitive** match hota hai ("Dolo" = "dolo" → ek hi entry, duplicate nahi).

---

## 9. 🔐 Puter AI account — "naya account nahi ban raha" (IMPORTANT)

**Doctor ki report:** *"puter pe naya account nahi ban ra"*.

**Sach:** ye **Puter ki taraf ka bug hai**, hamare app ki galti nahi —
[HeyPuter/puter #1430](https://github.com/HeyPuter/puter/issues/1430) · [#1373](https://github.com/HeyPuter/puter/issues/1373).

**App me kya kiya:**
- Settings me **"🆕 Naya Account banao"** button — `puter.com/login` nayí tab me kholta hai (wahan email/Google se sign up)
- `signIn` ab **full-tab login** karta hai (blank popup ka fix) + temporary **guest account detect** karke clear karta hai
- Error message me saaf likha aata hai: account banao, ya Groq key lagao

**Doctor ko sirf 2 raste batane hain:**
1. Settings → **"🆕 Naya Account banao"** → puter.com par email/Google se free account banao → phir **"🔌 Connect Puter"** dabao.
2. **Puter bilkul hi na chale to** → Settings → "My own API keys" me **Groq key** (free — console.groq.com) daal do.
   Usme **koi login, koi popup hi nahi** chahiye aur AI seedha chalta hai. **Yahi sabse bharosemand rasta hai.**

> ⚠️ **Par dhyan rahe:** PA free par Groq/DeepSeek key **kaam nahi karegi** (upar section 2 ka outbound block).
> Is liye PA par **Puter hi asli rasta hai**. Groq/DeepSeek key sirf tab kaam karegi jab whitelist approve ho
> ya PA paid plan par shift karo. **Doctor ko galat ummeed mat do** — pehle `🧪 Test` se check karwao.

### 9.1 Key save/test ka naya UI (21-Sep-2026)

Doctor ki shikayat thi: *"deepseek api daali paid but vo save nahi ho rahi"* — jabki key **save ho chuki thi**,
sirf UI usko dikha nahi raha tha. Is liye 3 cheezein add ki:

| Cheez | Kya kiya |
|---|---|
| Save confirmation | Save karte hi har key label me **✅ saved** turant dikhta hai (pehle sirf page reload par dikhta tha) |
| **🧪 Test button** | Har key ke saath — `POST /opd/api/test-key` se **chhota REAL call** karke batata hai: key sahi / galat / balance khatam / outbound block |
| AI Mode warning | Key save hote waqt agar `ai_mode = puter` hai to warning + **ek click me "Auto (BYOK)" switch** ka offer |
| Puter dummy account | `puterStatus()` ab **guest flag** deta hai — dummy/guest account ko "Puter Attached" nahi dikhata, warning + **🔄 Re-login (apni ID se)** button deta hai |

**Sabak:** key ka **save** hona ≠ key ka **chalna**. Is liye (1) save par turant confirmation,
(2) real Test button, (3) `ai_mode` ka check — teenon zaroori hain.
