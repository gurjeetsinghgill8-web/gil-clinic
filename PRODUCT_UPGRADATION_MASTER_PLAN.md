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

### BRICK 4 — Phase 3: consolidate modules
- Move each `/staff/<dept>` + OPD tab to a canonical module route.
- Split the 380KB OPD template.

### BRICK 5 — Phase 4: retire the old
- Delete `templates/dashboard/*`, shim logins, js.puter.com, placeholder modules.

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

**Last update:** 2026-10-03 (after Brick 3b — one hallway COMPLETE)
**State:** Brick 1 ✅ + Brick 2 ✅ (single login) + Brick 3 ✅ (nav model + `/home` hub + dono dashboards link). Tests 686 green. Build `a148414` live.
**Next action:** Brick 4 — Phase 3: modules consolidate (380KB OPD template ko todo, `/staff/<dept>` pages ko canonical routes par).
**How to resume:** ye file + `git pull` → `scripts/audit_probe_live.py` → Brick 4.

---

## 7. Resume guide (agar sab kuch kho jaye)

1. Ye file padho (SECTION 6 = kahan thhe).
2. `git pull` karo (code latest hai GitHub par).
3. `python scripts/audit_inventory.py` → routes/templates map banao.
4. `python scripts/audit_probe_live.py` → live state check.
5. SECTION 6 ke "Next action" se aage badho.
