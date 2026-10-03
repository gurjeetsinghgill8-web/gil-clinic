# GIL CLINIC — Product Upgradation Plan (Round 3)

> **Owner:** Gurjas Singh Gill · **Date:** 2026-10-03
> Ye file 3 issues ka plan hai jo X-ray/ECG section + marketplace me mile.

---

## Issue 1 — Report Ready / Mark Complete → patient ko WhatsApp NAHI jaata

**Problem (live):** X-ray/ECG me tech "📄 Report Ready" ya "✅ Mark Complete" dabata hai, status badal jaata hai, PAR patient ko WhatsApp message nahi jaata ("aapki report ready hai, le aao").

**Root cause:** `src/presentation/queue/routes/queue_routes.py` ke `technician_action` me WhatsApp notification **sirf `call` aur `recall`** pe bheja jaata hai (line 170). `report-ready`, `complete`, `deliver` pe koi notification nahi.

**Fix:** `report-ready` + `complete` (aur `deliver`) action pe bhi patient ko auto WhatsApp bhejo:
- `report-ready` → "📋 Aapki {dept} report ready hai — counter se le lijiye"
- `complete` → "✅ Aapka {dept} test complete ho gaya hai"
- Cloud API ho to direct send, warna `wa.me` link return (browser khol de).

---

## Issue 2 — "WhatsApp Options ▾" dropdown niche khul kar clip/ghayab

**Problem:** "WhatsApp Options ▾" dabane par dropdown **neeche** khulta hai aur content ke piche chhup jaata hai (options dikhte nahi).

**Root cause:** `templates/dashboard/department.html` line 47 — `wa-menu` ka `top:100%` (neeche khulta hai). Doosre pages (dietician, OPD) me `bottom:100%` (upar khulta hai) hai — yahan galat hai.

**Fix:** `top:100%` → `bottom:100%` + `margin-top:4px` → `margin-bottom:4px` (dropdown upar khule).

---

## Issue 3 — Marketplace ranking: vacancy/load → reviews → baaki

**Vision:** Patient city + specialty daale → top 3-4 doctors dikhe, ranking: **kam patient load (khali/vacancy)** upar → reviews → baaki params.

**Status:** Marketplace me `discovery.rank_score` already hai (multi-factor: live depth/load + rating + distance). "Smart" sort isi ko use karta hai. ✅ Mostly done.

**Enhance:** verify + `_sort_key("smart")` me **vacancy (wait/patients_ahead) ko weight** diya jaye taaki kam wait wale upar aayein, aur `0 waiting` clinics pe "🟢 Turant turn" tag dikhe.

---

## Order

1. Issue 1 (WhatsApp report-ready) — sabse zaroori
2. Issue 2 (dropdown) — chhota
3. Issue 3 (ranking) — verify + halka enhance
