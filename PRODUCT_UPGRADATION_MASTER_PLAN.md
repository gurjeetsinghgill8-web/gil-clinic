# GIL CLINIC — Product Upgradation Master Plan

> **Purpose:** Ek hi jagah poora plan + **resume point** + role model + completion rules.
> **Owner:** Gurjas Singh Gill (Owner = full access)
> **Created:** 2026-10-03
> **How to resume:** laptop/mobile band ho jaye to ye file kholo → "CURRENT CHECKPOINT" padho → wahin se aage.

---

## 0. The one-line vision

**EK product, EK login, role-based modules.** Reception sirf reception dekhe, lab sirf lab,
doctor apna sab, admin usse zyada, CEO sab (read-only), **Owner sab dekh + sab change**.

---

## 1. Role model (THE access matrix — final)

| Role | Dehta hai | Change kar sakta hai | Modules visible |
|---|---|---|---|
| **Owner** | sab kuch | **sab kuch** (full write) | ALL |
| **CEO** | sab kuch | **kuch nahi** (read-only) | ALL (view) |
| **Admin** | admin + clinic sab | admin settings, users, leads, network | admin + reception + billing + reports |
| **Doctor** | apna OPD sab | Rx, queue, slots, referrals, notes | /opd (doctor cockpit) + tools |
| **Lab technician** | sirf lab | lab reports, results | /lab |
| **Receptionist** | sirf reception | booking, queue entry, tokens | /reception |
| **Dietician** | dietician | diet plans | /dietician |
| **Billing** | billing | invoices | /billing |

**Rule:** nav menu sirf role ke allowed modules dikhata hai. Koi route bina role-check ke accessible nahi.

---

## 2. Current state (2026-10-03, from the audit)

* 287 routes · 31 templates · 600 tests green.
* **Do dashboards:** `/staff/*` (22 pages, reception/ecg/echo/tmt/xray/lab/dietician/billing/tv)
  vs `/opd/*` (13 pages, doctor cockpit + queue engine).
* **Chaar logins:** `/opd/login`, `/staff/login`, `/clinic-portal`, `/admin/login`.
* **"Clinic Login" → `/staff/home` (purana)**, lekin queue/slots/referrals → `/opd/dashboard` (naya).
* Naya OPD dashboard me koi nav nahi (sirf logout + tools).
* "Coming Soon" placeholders: Pharmacy, HR & Payroll, Inventory.
* P0 crash: `GET /api/v1/queue/notes/{entry_id}` → 500 on bad id.
* `/docs` public · `/staff/seed*` production me.
* Branding: landing title "CardioQueue".
* Dead code delete HO GAYA (assets/, patient-pwa/).

---

## 3. Target architecture

```
GIL CLINIC (one product)
├── ONE login (role → route, one session cookie)
├── ONE shell (sidebar + topbar, role-filtered)
├── Modules (one route each): /reception /opd /ecg /echo /tmt /xray /lab /dietician /billing /tv /tools /admin
├── ONE shared data layer
└── ONE PWA (done: /manifest.json + /sw.js)
```

---

## 4. The Lego plan (each brick = build → test → commit → push → deploy → verify → checkpoint)

### BRICK 1 — Phase 0: correctness + cleanup (no behaviour change) — ✅ DONE 2026-10-03
- [x] Dead files delete (assets/, patient-pwa/) — commit 61bcd41
- [x] Audit harness committed (scripts/audit_*.py) — commit 61bcd41
- [x] Fix `queue/notes` 500 → 404 — commit 24a9798, live-verified
- [x] Branding: landing subtitle "GIL CLINIC" — commit 24a9798
- [x] `/docs` + `/redoc` production me disable (ENABLE_DOCS=1 opt-in) — 24a9798
- [x] `/staff/seed*` env-flag ke peeche (ALLOW_SEED=1) — 24a9798

### BRICK 2 — Phase 1: one front door (single login, role routing) — ✅ DONE 2026-10-03
- [x] **Brick 2a:** Unified PIN login `/signin` + identity resolver `src/domain/auth/identity.py`
      — unique PIN routes directly, ambiguous PIN (1234) shows a role picker. Commit 14e06d4.
- [x] **Brick 2b:** username/password (admin + clinic) on the same door
      — shared verifiers `src/application/auth/credentials.py` (lockout + licence). Commit e4804ee.
- [x] **Brick 2c:** staff phone+password added; old login pages become 302 shims to `/signin`;
      PWA start_url → `/signin`. Commit 2b8d410. Tests 649, 15/15 live.
- [ ] (Phase 4 me) old POST handlers ko hatao — ab shim hi kaafi hai, full removal baad me.

### BRICK 3 — Phase 2: one hallway (single shell + nav) — ✅ DONE 2026-10-03
- [x] **Brick 3a:** role-filtered nav model `src/domain/auth/nav.py` (pure matrix) +
      `/home` hub page (reads any session, shows the role's modules). Commit 794d782.
- [x] **Brick 3b:** dono dashboards me `/home` ("🏠 My Modules") link inject kiya
      (OPD sidebar + staff base.html). Commit a148414. Tests 686, 10/10 live.

### BRICK 4 — Phase 3: consolidate + enforce
- [x] **Brick 4a:** role-based ROUTE enforcement (`nav.can_access_staff_route`) — nav matrix
      ab sirf link chhupata nahi, route bhi refuse karta hai. Dead modules (billing/tv)
      nav se hataye. Commit 6c00886, 700 tests, 11/11 live.
- [x] **Brick 4b:** 380KB OPD template (`templates/opd/dashboard.html`, 6760 lines) ko
      4 Jinja partials me toda — `templates/opd/partials/{_head,_sidebar,_main,_scripts}.html`.
      `dashboard.html` ab sirf include-shell hai. **Byte-identical render verified**
      (359818 chars, `scripts/verify_opd_split.py`). Commit 997d783, 708 tests, 10/10 live.

### BRICK 5 — Phase 4: retire the old (cleanup) — ✅ DONE 2026-10-03
- [x] **Brick 5a:** dead/fake nav hataya — sidebar se `Manager/Billing/TV` (sab disabled
      redirects) aur `Pharmacy/HR & Payroll/Inventory` ("Coming Soon" fake links).
      `/staff/home` ke galat "COMING"/"BUILDING" badges bhi hataye (ECG/Echo/TMT ab LIVE
      dikhte hain). Dead `data-uc` popup + `UNDER_CONSTRUCTION` data hataya.
      Commit 41fdf53, 708 tests, 22/22 live.
- **js.puter.com = ACTIVE dependency** (free AI gateway fallback for OCR/chat/diet) —
  hataya NAHI, ise hatao mat. (Sahi faisla — plan me pehle galat likha tha.)
- [x] **Brick 7:** purane login templates (`opd/login.html`, `dashboard/login.html`,
      `clinic_login.html`, `admin/login.html`) DELETE. POST error paths ab `unified_login.html`
      render karte hain (mode=password for username/password, PIN door for PIN). Commit c63a363, 11/11 live.
- (NOT applicable) `templates/dashboard/*` delete karna — ye staff dashboard ka LIVE UI
      hai, delete nahi karna tha. Plan correction: inhe chhodo.

### BRICK 6 — Phase 5: har page se ghar wapasi (back-to-home) — ✅ DONE 2026-10-03
- [x] Har authenticated page pe dikhne wala "🏠 Home" link (→ `/home`) add kiya:
      staff `base.html` topbar, OPD sidebar (sabse upar "Home / My Modules"),
      admin dashboard topbar, admin onboard topbar, OPD admin header.
      Commit 672bf8e, 9/9 live.

### BRICK 8 — Phase 6: SECURITY — reception/doosre staff ko OPD se block — ✅ DONE 2026-10-03
- [x] **Critical fix:** `opd_routes._get_opd_session` ka staff-session fallback HATAYA
      (ye kisi bhi staff role ko doctor "junior" bana deta tha — reception prescription
      pad khol sakta tha). Ab OPD access sirf `opd_session` cookie se.
- [x] **Cookie stacking fix:** har login (`/signin`, `/signin/password`) ab doosre
      session cookies (`opd_session`/`gc_session`/`admin_session`) clear karta hai,
      taaki reception login karne par purana doctor session stack na ho.
- [x] `/staff/doctor` route ko role-guard kiya (reception/lab ab `/home` pe bounce).
- [x] 5 regression tests. Commit 66e48cd, 713 tests, 6/6 live.
- ⚠️ **ABHI BHI BAQI (CREDENTIAL issue):** PIN `1234` junior doctor KA BHI hai aur
      Reception/ECG/Echo/TMT/Xray/Lab/Dietician KA BHI. Isliye receptionist jo `1234`
      jaanta hai, wo role-picker me "Junior Doctor" chun kar OPD khol sakta hai.
      **Fix = junior doctor ka PIN badlo (ya reception ka PIN).** Owner decide kare.

---

## 5. The COMPLETION RITUAL (har brick ke baad — kabhi skip nahi)

1. `python -m pytest tests/ -q -p no:warnings --ignore=...` → sab green.
2. `git add -A && git commit` + `git push origin main`.
3. Deploy: `python pa_deploy.py ship --since <prev-hash> --no-git --no-tests`.
4. Live verify: `python scripts/audit_probe_live.py` (+ verify_pwa_live.py).
5. **Is file ka "CURRENT CHECKPOINT" update karo** (kya done, kya next).
6. Jo bekaar cheez bani ho usse delete karo (junk cleanup).

**Online system (kabhi mat bhoolna):**
* Live URL: `https://gillhopitalsoftware1.pythonanywhere.com`
* Health: `GET /health` (build hash dikhta hai)
* Deploy tool: `scripts` me `pa_deploy.py`
* Live verify: `scripts/audit_probe_live.py` (169 GET routes probe)

---

## 6. CURRENT CHECKPOINT (resume from here)

**Last update:** 2026-10-03 (Round 2 — free-text input + DeepSeek crawler)
**State:** Marketplace **free-text city/specialty input** ✅ (patient khud type kare) + crawler **DeepSeek** pe shift ✅ (Gemini nahi). 9 doctors live. Build `8fbe7f4` live.
**Next action (sirf 1 input chahiye):** asli hospital "Our Doctors" URLs `targets.json` me daalo → crawler DeepSeek se real doctors extract karega. (`CRAWLER_ACTIVATION.md` + `PRODUCT_UPGRADATION_PLAN_V2.md` me baaki plan: Junior PIN 1122, PIN hierarchy, version badge.)
**How to resume:** ye file + `git pull` → `CRAWLER_ACTIVATION.md` padho.

---

## 7. Resume guide (agar sab kuch kho jaye)

1. Ye file padho (SECTION 6 = kahan thhe).
2. `git pull` karo (code latest hai GitHub par).
3. `python scripts/audit_inventory.py` → routes/templates map banao.
4. `python scripts/audit_probe_live.py` → live state check.
5. SECTION 6 ke "Next action" se aage badho.
