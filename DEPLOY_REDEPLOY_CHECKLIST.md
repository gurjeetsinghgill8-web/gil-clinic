# 🚀 Redeploy Checklist — GIL CLINIC (PythonAnywhere)

> **Live:** https://gillhopitalsoftware1.pythonanywhere.com
> **Repo:** github.com/gurjeetsinghgill8-web/gil-clinic
> **Driver:** `pa_deploy.py` (laptop se chalane wala deploy tool — isi se aap already deploy karte hain)

Ye checklist **is update** (patient-growth suite) ko live karne ke liye hai — step-by-step.

---

## 0. Is update mein kya aaya (ek nazar)

| Feature | URL / button |
|---------|--------------|
| **Find a Doctor** marketplace | `/find-doctor` (+ landing page par "Find a Doctor" button) |
| **Universal Health Card** | `/card/<uid>` + OPD dashboard "🪪 Health Card" button |
| **ABDM/FHIR compliance** | `/abdm` status page + `/api/v1/abdm/*` |
| **Smart Rx Pad** (letterhead) | OPD dashboard "📝 Letterhead Rx" button |
| **Video Consult** (free Jitsi) | OPD dashboard "📹 Video" button |
| **External Lab Network** | OPD dashboard "🧪 Lab Order" button + `/lab/<token>` patient view |
| **Settings → Location/ABDM backfill** | OPD dashboard Settings tab |

---

## 1. Deploy (code live karna)

Laptop par, project root me (PowerShell):

```
python pa_deploy.py ship
```

Ye khud karta hai: **tests → git commit+push → changed files upload → site reload → health check**.

> **Agar code pehle se GitHub par commit ho chuka hai** (e.g. maine commit kar diya), to ye command chalao — git dobara commit nahi karega:
> ```
> python pa_deploy.py ship --no-git
> ```
> **Tests skip karni ho** (jaldi ke liye): `python pa_deploy.py ship --no-git --no-tests`

---

## 2. DB auto-migration (apne aap hota hai — aapko kuch nahi karna)

App reload hote hi (pehli request par) ye **automatic** ho jata hai:

- **Naye tables** ban jate hain: `health_cards`, `lab_orders`, `abha_links`, `consent_artefacts`, `abdm_transactions`
- **Naye columns** add ho jate hain: `clinics.latitude`, `clinics.longitude`, `clinics.hpr_id`, `clinics.hfr_id`

> Koi manual SQL nahi. Ye existing `main_v2.py` startup migrator (`create_all` + `_migrate_sqlite_columns`) se hota hai — purana data safe rehta hai.

---

## 3. Verify live hai ya nahi

Reload ke baad browser me kholo:

1. **Build stamp badla?** → `https://gillhopitalsoftware1.pythonanywhere.com/health`
   - `"build"` field naya hona chahiye (purana nahi). Ye hi sabse pakka proof hai ki naya code chadha.
2. **Landing page** → `https://gillhopitalsoftware1.pythonanywhere.com/` → **"Find a Doctor"** button dikhega.
3. **Marketplace** → `/find-doctor` → city + specialty filter + doctor cards.
4. **ABDM status** → `/abdm` → "Scaffold Mode" page.

---

## 4. Marketplace ko "alive" banao (demo doctors seed karo)

`/find-doctor` abhi khali lagega jab tak clinics table me doctors nahi hain. **8 demo clinics** daalne ke liye:

**PythonAnywhere → Consoles → Bash** kholo, phir:

```
cd gil-clinic
python scripts/seed_marketplace_demo.py
```

Ye 8 demo clinics (Jodhpur/Jaipur/Ahmedabad/Delhi, alag specialties, lat/long) daal deta hai. **Idempotent** hai — dobara chalane par duplicate nahi bante.

> Demo clinics baad me **Admin panel (`/admin`)** se edit/delete kar sakte ho — ye asli rows hain.

---

## 5. Poora system check (smoke test — optional but recommended)

Deploy ke baad sab feature ek saath test karne ke liye (PythonAnywhere Bash console me):

```
cd gil-clinic
python scripts/integration_smoke_test.py
```

**15/15 PASS** aana chahiye. (Ye sirf temp records banata + delete karta hai — production data ko nahi chhetta.)

---

## 6. Zaroori env var (one-time, link/QR ke liye)

Patient links (Health Card / Lab result / track) sahi public URL par banne ke liye, `.env` me:

```
APP_BASE_URL=https://gillhopitalsoftware1.pythonanywhere.com
```

> Set na ho to links "request ke host" se bante hain (jo abhi bhi kaam karta hai), par permanent URL best hai.

---

## 7. Rollback (agar kuch toota)

1. **Code rollback:** `git revert <commit>` + `python pa_deploy.py ship --no-git`
2. **Data rollback:** PythonAnywhere ke `backups/` folder se latest `daily-*.db` restore karo.
3. Ya mujhe bolo — main fix karke dobara ship karwa dunga.

---

## 8. Abhi bhi jo external/आप पर है (mujh par nahi)

| Cheez | Kya chahiye |
|-------|-------------|
| **NHA sandbox credentials** (ABDM live) | `ABDM_CLIENT_ID/SECRET` + `ABDM_HIP_ID/HIU_ID/FACILITY_ID` → `.env` me daalo |
| **External lab API** (real lab send) | partner lab ka API — pipeline ready hai |
| **ISO 27001 / AWS** (GAP-15) | certification process |

---

*Deploy hone ke baad mujhe `/health` ka build stamp batao — main confirm kar dunga ki naya code live hai.*
