# 🧠 GIL CLINIC — MEMORY (single source of truth)

> **Ye file har naye session/agent ko SABSE PEHLE padhni chahiye.**
> Yahan sirf wahi baatein hain jo baar-baar kaam aati hain: live URL, login, hosting,
> deploy commands, aur wo faisle jo ho chuke hain. Detail ke liye neeche di gayi files.
>
> **Last updated:** 17-Sep-2026 · **Owner:** Dr. G. S. Gill

---

## 1. 🔴 LIVE SYSTEM (yahi asli production hai)

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
- **Outbound internet sirf whitelist** → AI/WhatsApp ke liye `pa_whitelist_request.txt` bhejna padta hai
  (AI feature error de to samajhna whitelist pending hai; **patient portal ko AI ki zaroorat nahi**)

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

---

## 6. ✅ Faisle jo ho chuke (dobara discuss karne ki zaroorat nahi)

1. **Host = PythonAnywhere (free)** — kyunki card nahi hai aur PA kabhi sota nahi.
2. **Railway chhod diya** — free tier khatam; data bhi volume ke bina udta tha.
3. **PC ko 24/7 host nahi banaya** — PC 3 din me ek baar khulta hai (scripts ready hain, emergency ke liye).
4. **Patient portal me AI nahi** — self-reported readings, graphs, PDF; AI sirf doctor ke tools me.
5. **Share link read-only + 7 din** — doctor kabhi patient ka data badal nahi sakta.

---

## 7. ⏳ Aage ke kaam (agar doctor chahe)

- [ ] Phase 4: patient appointment/follow-up **request** + doctor ka reply (`patient_requests` table ready hai)
- [ ] Prescription PDF par **"ghar ke BP ka average (7 din)"** — patient ke self-readings se
- [ ] Critical reading aane par doctor ko **alert/badge**
- [ ] AI whitelist confirm karna (Groq/DeepSeek/OpenAI PA par chal rahe hain ya nahi)
- [ ] Purane `patient-pwa/` (lab token tracking) ko naye portal ke saath ek installable PWA me jodna
