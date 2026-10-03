# Module 6 — Autonomous external doctor data ingestion worker

Crawls public hospital / clinic rosters and posts structured doctor profiles to
the GIL CLINIC (GHOS) ingest API.

## Why this is a separate program and not part of the app

Part E of the master blueprint established this with measurements, not opinion:

| Constraint | Consequence |
|---|---|
| PythonAnywhere free blocks outbound internet except a whitelist | Crawl4AI literally cannot fetch a hospital page from inside the app |
| No scheduled tasks on the free tier (403) | Nothing in the app could run on a timer even if it could fetch |
| ~100 CPU-seconds/day for the whole web app | Chromium is ~400 MB and eats that budget in one page load |
| 512 MB disk | Chromium's install alone is most of it |

So the crawler runs here, in GitHub Actions, on a cron. The app only receives.

## How it works

```
GitHub Actions (cron)
   └─ python -m worker.main --config targets.json
        ├─ crawl4ai + Chromium       → raw HTML from each roster page
        ├─ Gemini (schema-guided)    → doctor profiles
        ├─ validate against the API's own schema
        └─ POST /api/v1/ingest/doctors  (token-gated)
                                          └─ opt-outs enforced server-side
```

## The three rules this worker obeys

1. **The schema is fetched, not assumed.** `GET /api/v1/ingest/schema` returns
   the exact contract the server validates against. Hard-coding it here would
   let the two drift, and the failure mode is silent: extraction starts emitting
   a field nobody checks, and a wrong phone number reaches a public listing.

2. **Never invent a field.** The extraction instruction says so explicitly, and
   `validate_profile()` enforces it again locally — an LLM that fills in a
   plausible-looking registration number is worse than one that leaves it blank,
   because a blank is visibly unknown and a fabricated number is not.

3. **Opt-out is the server's decision, not the worker's.** The worker may not
   know which clinics asked to be removed, so it never filters on that basis —
   the ingest endpoint checks it before writing anything. A worker that tried to
   be clever here would be a second, worse source of truth.

## Files

| File | Purpose |
|---|---|
| `main.py` | CLI entry point: crawl → extract → validate → post |
| `targets.json` | Which roster URLs to crawl, and how |
| `requirements.txt` | crawl4ai, httpx, pydantic |
| `../.github/workflows/ingest-doctors.yml` | The cron that runs it |

## Running it locally

```bash
pip install -r requirements.txt
playwright install chromium
export INGEST_TOKEN=...            # same secret the app expects
export GEMINI_API_KEY=...
python main.py --config targets.json --dry-run   # extract, do not post
```
