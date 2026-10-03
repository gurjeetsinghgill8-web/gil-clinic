# 🕷️ Crawler Activation Guide — "Find a Doctor" marketplace ko REAL doctors se bharo

> **Ye guide batati hai ki crawler ko LIVE chalane ke liye kya-kya karna hai.**
> Crawler ka code + receiving end (ingest API) + marketplace page sab READY hai.
> Sirf 2 cheezein aapko deni hain: **(1) Gemini key, (2) asli hospital URLs.**

---

## Abhi kya chal raha hai (verified LIVE)

| Cheez | State |
|---|---|
| Marketplace page `/find-doctor` | ✅ 9 demo doctors dikh rahe hain |
| Ingest API (receiving end) | ✅ LIVE, token-gated |
| Marketplace API | ✅ LIVE |
| **Crawler (GitHub Actions)** | ❌ **IDLE** — targets khaali + secrets nahi |

Crawler hi "idle" hai kyunki:
1. `targets.json` me asli hospital URL nahi hai (sirf placeholder).
2. GitHub me 2 secrets nahi hain (`INGEST_TOKEN` + `GEMINI_API_KEY`).

---

## Step 1 — GEMINI_API_KEY (free) banao

1. Kholo: **https://aistudio.google.com/apikey**
2. "Create API key" dabao → key copy karo.
3. Ye key crawler ko doctors extract karne ke liye chahiye (LLM extraction).

---

## Step 2 — GitHub me 2 secrets daalo

1. GitHub repo kholo: **https://github.com/gurjeetsinghgill8-web/gil-clinic**
2. `Settings` → `Secrets and variables` → `Actions` → `New repository secret`
3. **Secret 1:**
   - Name: `INGEST_TOKEN`
   - Value: `GIL-DEMO-SEED-2026` (abhi app ka default; production ke liye koi unique secret value rakh do aur PythonAnywhere ke env `INGEST_TOKEN` me bhi wahi daalo)
4. **Secret 2:**
   - Name: `GEMINI_API_KEY`
   - Value: (Step 1 wali key)

---

## Step 3 — Asli hospital ke "Our Doctors" URLs daalo

File: `workers/crawl_doctors/targets.json`

Har hospital/clinic ki **public "Our Doctors" page** ka URL daalo. Format:

```json
{
  "url": "https://apne-hospital.com/our-doctors",
  "label": "Apna Hospital — doctors",
  "city": "Jodhpur",
  "state": "Rajasthan",
  "wait_for": ".doctor-list, .team-member, .profile-card"
}
```

> ⚠️ Sirf **public** pages (login ke piche wali nahi). Practo/Lybrate/JustDial ka data scrape **mat** karo (unka robots.txt mana karta hai). Apne hospital ki apni website ya government hospital ki public roster use karo.

---

## Step 4 — Crawler chalao

3 tarike:
- **Manual (turant):** GitHub → `Actions` → `Ingest doctor profiles` → `Run workflow` → dry_run = false.
- **Automatic weekly:** `.github/workflows/ingest-doctors.yml` me `# schedule:` wali 2 lines ka `#` hata do (uncomment). Phir har Sunday raat auto chalega.
- **Pehle dry-run test:** dry_run = true se bina data-post kiye extract check karo.

---

## Verify (crawler chalne ke baad)

1. `/find-doctor` kholo → asli doctors Tier 2 (directory) me dikhenge.
2. Crawl run history: `GET /api/v1/ingest/runs?token=...` (ya `/tools` page pe "crawled listings" count).

---

## Files (reference)

| File | Kya hai |
|---|---|
| `workers/crawl_doctors/targets.json` | Crawl karne wale URLs |
| `.github/workflows/ingest-doctors.yml` | GitHub Actions workflow (cron enable) |
| `workers/crawl_doctors/main.py` | Crawler code (crawl → extract → post) |
| `src/presentation/ingest/routes/ingest_routes.py` | Receiving end (token-gated) |
| `src/presentation/marketplace/routes/marketplace_routes.py` | Marketplace display + seed |
