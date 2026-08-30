# GIL CLINIC — Graphical Project Memory (Knowledge Graph)
## v2 · 30-Aug-2026 · C1+C2+C3+C5 shipped · Live system state

> Ye file project ki memory ko **graphical form** mein rakhti hai — taaki koi bhi
> recording/feature kaam dubara na khoye (memory crash-proof). Har feature ship
> hone par ye graph update hota hai. Nodes ke neeche file-links hain.

---

## GRAPH 1 — System Architecture (Live)

```mermaid
flowchart TB
    subgraph FRONT["Browser (any device)"]
        OPD["OPD Doctor Portal<br/>templates/opd/dashboard.html"]
        STAFF["Staff Portal + Live Board<br/>templates/dashboard/*"]
        PATIENT["Patient Tracking<br/>templates/patient_track.html"]
        GW["AI Gateway (browser)<br/>static/js/ai_gateway.js"]
    end
    subgraph BACK["Backend — main_v2.py (FastAPI)"]
        OPDAPI["OPD Routes<br/>src/presentation/opd/routes/opd_routes.py"]
        STAFFAPI["Staff/Queue Routes<br/>src/presentation/staff/routes/staff_routes.py"]
        AIENG["AI Engine<br/>src/ai_engine/provider_router.py"]
        DB["SQLite ghos_prod.db<br/>(auto-migrate + auto-backup)"]
    end
    OPD -->|aiFetch| GW
    GW --> OPDAPI
    STAFF --> STAFFAPI
    PATIENT --> STAFFAPI
    OPDAPI --> AIENG
    AIENG --> DB
    STAFFAPI --> DB
    OPDAPI --> DB
```

## GRAPH 2 — AI Routing (BYOK → Puter → Fallback)

```mermaid
flowchart LR
    FEAT["AI Feature<br/>(generate-rx, OCR, upgrade, diet...)"]
    ROUTER{"ai_mode?"}
    OFF["off — AI band"]
    PUTER["puter — browser Puter AI<br/>(sign-in banner + popup)"]
    BYOK["clinic keys: groq → deepseek → gemini<br/>→ openai → anthropic"]
    FALL["system fallback<br/>(hamari Groq, capped)"]
    FEAT --> ROUTER
    ROUTER -->|off| OFF
    ROUTER -->|puter| PUTER
    ROUTER -->|auto/own| BYOK
    BYOK -->|"keys nahi"| FALL
    PUTER -->|"PUTER_CHAT/OCR/TRANSCRIBE<br/>hop via ai_gateway.js"| FEAT
```

## GRAPH 3 — OPD Doctor Workflow (aaj + planned)

```mermaid
flowchart TB
    IN["Patient Info + Vitals + Complaints"]
    SCAN["📷 Camera / 🖼️ Gallery / ✍️ Writing Pad / 🔁 Re-scan"]
    HWR{"Scan type"}
    HWRX["Handwritten Rx OCR<br/>→ fills Diagnosis + Advice (editable) ✅"]
    HBATCH["📸 Batch Scan (multi-page) ✅ C3:<br/>top button + Add More Pages<br/>+ originals delete after save"]
    GEN["🤖 AI Generate Prescription<br/>→ rx-output"]
    C1["✅ C1: AI output se Diagnosis + Advice<br/>inline fill (editable) + Fill from AI button"]
    UPGR["⚕️ Specialist Opinions<br/>(custom specialty ✅)"]
    SAVE["💾 Save → opd_prescriptions<br/>(clinic_id migrated ✅)"]
    IN --> GEN
    IN --> HWR
    SCAN --> HWR
    HWR --> HWRX
    HWR --> HBATCH
    GEN --> C1
    GEN --> UPGR
    HWRX --> SAVE
    C1 --> SAVE
    UPGR --> SAVE
```

## GRAPH 4 — Deploy & Ship (live + weekly-ship plan)

```mermaid
flowchart TB
    DEV["Laptop (local dev + tests 64)"]
    GIT["GitHub main<br/>(public repo)"]
    PA["PythonAnywhere FREE<br/>gillhopitalsoftware1.pythonanywhere.com"]
    DEPLOY["pa_deploy.py<br/>(files upload + site reload)"]
    AUTOB["In-app auto-backup<br/>(startup + daily 23:30 UTC)"]
    SHIP["✅ C5: pa_deploy.py ship<br/>(tests → commit+push → upload changed<br/>→ reload → health) — verified 30-Aug"]
    DEV -->|"commit + push"| GIT
    GIT -->|"upload changed files"| DEPLOY
    DEPLOY --> PA
    PA --> AUTOB
    SHIP -.->|weekly| GIT
    SHIP -.->|weekly| PA
```

## GRAPH 5 — Memory Map (ye file khud)

```mermaid
flowchart LR
    G["GRAPH_MEMORY.md (ye)"]
    IDX["GHOS_MASTER_INDEX.md"]
    P0["ghos_memory/phase_0_foundation/*"]
    P1["phase_1_core_engine/*"]
    P2["phase_2_user_modules/*"]
    P3["phase_3_clinical_modules/*"]
    P5["phase_5_ai/*"]
    P12["phase_12_future/*"]
    G --> IDX
    IDX --> P0
    IDX --> P1
    IDX --> P2
    IDX --> P3
    IDX --> P5
    IDX --> P12
```

---

## Node → File Index (sab kuch ek jagah)

| Node | File |
|---|---|
| OPD Doctor Portal | `templates/opd/dashboard.html` |
| AI Gateway (browser) | `static/js/ai_gateway.js` |
| AI Router | `src/ai_engine/provider_router.py` |
| OPD Routes | `src/presentation/opd/routes/opd_routes.py` |
| Staff/Queue Routes | `src/presentation/staff/routes/staff_routes.py` |
| Auto-backup | `src/infrastructure/clinic/services/auto_backup.py` |
| DB migration (SQLite) | `main_v2.py` → `_migrate_sqlite_columns()` |
| Deploy driver | `pa_deploy.py` + `pa_requirements.txt` |
| PA deploy guide | `PA_DEPLOY_GUIDE.md` |
| Cloud deploy guide (Oracle) | `CLOUD_DEPLOY_GUIDE.md` + `deploy_oracle.sh` + `deploy_remote.ps1` |
| Upgradation plan | `PRODUCT_UPGRADATION_PUTER_PLAN.md` (PART C = 30-Aug upgrades) |
| Status trail | `SYSTEM_STATUS_REPORT.md` |

**Update rule:** koi bhi feature ship ho → ye graph + index update karo (recording kabhi na gume).
