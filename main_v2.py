"""
GHOS V2 — FastAPI Application Bootstrap

Wires all 4 engines (Identity, Patient, Experience, Queue Lite)
into a single FastAPI application.

Usage:
    uvicorn main:app --reload          # Uses PostgreSQL (env: GHOS_DB_URL)
    uvicorn main:app --reload --env-file .env

    # Or with SQLite for development:
    GHOS_DB_URL=sqlite:///ghos_dev.db uvicorn main:app --reload
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

# ── Ensure src/ is on path ──────────────────────────────────────────────
_src = Path(__file__).parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

# ── Load .env from project root BEFORE reading any env vars ─────────────
# (CWD-independent — PythonAnywhere/VMs par uvicorn ka CWD project dir nahi hota)
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv(Path(__file__).resolve().parent / ".env")
except Exception:
    pass

# ═════════════════════════════════════════════════════════════════════════
# Development Configuration — MUST be set before ANY engine imports
# ═════════════════════════════════════════════════════════════════════════

# Dev mode bypass — allows API access without JWT during development
# SECURITY: Default is "false". Set GHOS_DEV_AUTH_BYPASS=true only in local .env for development.
os.environ.setdefault("GHOS_DEV_AUTH_BYPASS", "false")

# Detect database URL (default: SQLite for dev)
_DB_URL = os.getenv("GHOS_DB_URL", "")

# ── Hosted platforms: agar volume mount diya hai to data usi par rakho ────────
# Railway/Render par SQLite container ke andar pada ho to **har deploy par data
# ud jata hai** (yahi "data save nahi hota" ki asli wajah thi). Agar platform
# volume mount path deta hai (RAILWAY_VOLUME_MOUNT_PATH / RENDER_DISK_PATH) aur
# GHOS_DB_URL khud set nahi kiya gaya, to DB usi permanent disk par bana lenge.
if not _DB_URL:
    _volume = (
        os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
        or os.getenv("RENDER_DISK_PATH")
        or os.getenv("PERSISTENT_DISK_PATH")
        or ""
    ).strip()
    if _volume:
        try:
            Path(_volume).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        _DB_URL = f"sqlite:///{_volume.rstrip('/')}/ghos_prod.db"
        print(f"[GHOS] Volume mila → data permanent disk par: {_DB_URL}")
    else:
        _DB_URL = "sqlite:///./ghos_dev.db"

# Set async SQLite URL for shared infra (patient engine uses async sessions)
# before any module that imports shared/infrastructure/database.py
if _DB_URL.startswith("sqlite") and not _DB_URL.startswith("sqlite+aiosqlite"):
    _async_url = _DB_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)
    os.environ.setdefault("GHOS_DB_URL_ASYNC", _async_url)
    os.environ["GHOS_DB_URL_ASYNC"] = _async_url

print(f"[GHOS] AUTH BYPASS = {os.environ['GHOS_DEV_AUTH_BYPASS']}")
print(f"[GHOS] DB = {_DB_URL}")
print(f"[GHOS] ASYNC DB = {os.environ.get('GHOS_DB_URL_ASYNC', 'N/A')}")

# ═════════════════════════════════════════════════════════════════════════

# ── App metadata ────────────────────────────────────────────────────────
APP_NAME = "GHOS V2 — GIL CLINIC"
APP_VERSION = "2.0.0"
APP_DESC = "Department Pilot — Reception → Queue → Technician → Patient PWA"


# ── BUILD STAMP ─────────────────────────────────────────────────────────
# Har deploy par `pa_deploy.py ship` ek NAYA build_info.json upload karta hai.
# Isse turant pata chalta hai ki live par NAYA code chadha hai ya PURANA —
# pehle ye hardcoded tha ("2026.08.06.v2.0") is liye kabhi nahi badalta tha.
#   Dekho:  /health   (aur dashboard ke sidebar footer me bhi dikhta hai)
def _load_build_info() -> dict:
    _p = Path(__file__).resolve().parent / "build_info.json"
    try:
        if _p.exists():
            # utf-8-sig: BOM ho to bhi padh le (Windows editors/PowerShell BOM daal dete hain)
            return json.loads(_p.read_text(encoding="utf-8-sig"))
    except Exception as _e:
        print(f"[GHOS] build_info.json padha nahi gaya: {_e}")
    return {}


BUILD_INFO = _load_build_info()
BUILD_STAMP = BUILD_INFO.get("build") or "dev-local"
BUILD_COMMIT = BUILD_INFO.get("commit") or ""
BUILD_AT = BUILD_INFO.get("built_at") or ""
BUILD_FILES = BUILD_INFO.get("file_count") or 0
print(f"[GHOS] BUILD = {BUILD_STAMP} (commit {BUILD_COMMIT}, files {BUILD_FILES})")


# =========================================================================
# Engines
# =========================================================================

# -- Queue Lite --
from src.presentation.queue.routes.queue_routes import router as queue_router

# -- Experience Engine --
from src.experience.presentation.routes.experience_routes import (
    router as experience_router,
    api_router as experience_api_router,
)

# -- Clinic Engine --
from src.presentation.clinic.routes.clinic_routes import (
    router as clinic_router,
)

# -- Clinic Auth (multi-tenant login) --
from src.presentation.clinic.routes.clinic_auth_routes import router as clinic_auth_router

# -- Patient Engine --
from src.presentation.patient.routes.patient_routes import (
    router as patient_router,
)

# -- Staff Dashboard (HTML, session auth) --
from src.presentation.staff.routes.staff_routes import router as staff_router
from src.presentation.staff.routes.staff_routes import public_router as patient_track_router
from src.presentation.staff.routes.settings_routes import router as staff_settings_router

# -- Smart OPD --
from src.presentation.opd.routes.opd_routes import router as opd_router

# -- Patient Portal (patient self-filling + read-only doctor share) --
from src.presentation.patient_portal.routes.patient_portal_routes import (
    doctor_router as patient_portal_doctor_router,
)
from src.presentation.patient_portal.routes.patient_portal_routes import (
    router as patient_portal_router,
)

# -- Admin Panel (Super Admin + CEO) --
from src.presentation.admin.routes.auth_routes import router as admin_auth_router
from src.presentation.admin.routes.dashboard_routes import router as admin_dashboard_router
from src.presentation.admin.routes.doctor_routes import router as admin_doctor_router
from src.presentation.admin.routes.auth_routes import seed_default_admins

# -- Marketplace (Find a Doctor — public city directory) --
from src.presentation.marketplace.routes.marketplace_routes import router as marketplace_router

# -- Universal Health Card (shareable patient summary) --
from src.presentation.health_card.routes.health_card_routes import (
    router as health_card_router,
    doctor_router as health_card_doctor_router,
)

# -- ABDM compliance (NHA scaffold) --
from src.presentation.abdm.routes.abdm_routes import (
    router as abdm_router,
    page_router as abdm_page_router,
)

# -- Smart Prescription Pad (print-ready Rx) --
from src.presentation.rx_pad.routes.rx_pad_routes import router as rx_pad_router

# -- External Lab Network (order → result → patient phone) --
from src.presentation.lab_network.routes.lab_network_routes import (
    router as lab_network_router,
    doctor_router as lab_network_doctor_router,
)

# -- Queue Engine (chamber gate + hold/return + live EWT feed) --
from src.presentation.queue_engine.routes.queue_engine_routes import (
    router as queue_engine_router,
)

# -- Friendly URLs (forgiving aliases + a helpful 404 instead of raw JSON) --
from src.presentation.common.routes.friendly_routes import (
    install_friendly_404,
    router as friendly_router,
)

# -- Slot booking (appointment slots + Code Red emergency override) --
from src.presentation.slots.routes.slots_routes import (
    router as slots_router,
)

# -- Clinic stats (EWT accuracy report + PHI-free network overview) --
from src.presentation.clinic_stats.routes.clinic_stats_routes import (
    router as clinic_stats_router,
)

# -- Verified reviews (visit-verified rating → Bayesian clinic score) --
from src.presentation.reviews.routes.review_routes import (
    router as reviews_router,
)

# -- Referrals (cross-clinic signed slip + accept-to-queue, F-06) --
from src.presentation.referral.routes.referral_routes import (
    router as referral_router,
)

# -- Growth (invite pipeline GRW-02 + city landing pages GRW-03) --
from src.presentation.growth.routes.growth_routes import (
    router as growth_router,
)

# -- Module 6 ingestion (crawled profiles + claim/opt-out, BLOCK 5) --
from src.presentation.ingest.routes.ingest_routes import (
    router as ingest_router,
)

# -- PWA (single manifest + service worker, served from the root) --
from src.presentation.pwa.routes.pwa_routes import (
    router as pwa_router,
)

# -- Clinic tools (one page where every new capability is actually clickable) --
from src.presentation.tools.routes.tools_routes import (
    router as tools_router,
)


# =========================================================================
# Database Setup
# =========================================================================

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.shared.infrastructure.database import Base

# Create engine (sync for development)
if _DB_URL.startswith("sqlite"):
    engine = create_engine(
        _DB_URL,
        connect_args={"check_same_thread": False},
        echo=os.getenv("GHOS_DB_ECHO", "").lower() == "true",
        # Strip the "identity" schema prefix for SQLite (no schema support)
        execution_options={"schema_translate_map": {"identity": None}},
    )
else:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine,
    )
    engine = create_async_engine(_DB_URL, echo=False)

SessionLocal = sessionmaker(bind=engine)


# Include all models so SQLAlchemy Base.metadata knows them
from src.infrastructure.queue.models import (  # noqa: F401
    AuditLogModel,
    QueueEntryModel,
)
from src.infrastructure.patient.models import PatientModel  # noqa: F401
from src.infrastructure.identity.models import (  # noqa: F401
    UserModel,
    RoleModel,
    SessionModel,
    RefreshTokenModel,
    PermissionModel,
    OtpCodeModel,
    OutboxModel,
)
# OPD models — creates all 7 tables on startup
from src.infrastructure.opd.models.opd_models import (  # noqa: F401
    OpdPrescriptionModel,
    DrugHistoryModel,
    TemplateModel,
    LicenseModel,
    SettingsModel,
    SpecialtyUpgradeModel,
    PendingScanModel,
    LabReportModel,
)
# AI usage metering table
from src.infrastructure.opd.models.ai_usage_model import AIUsageModel  # noqa: F401
# Patient Portal tables — patient self-readings, portal links, share snapshots
from src.infrastructure.opd.models.patient_portal_models import (  # noqa: F401
    HealthCardAccessModel,
    HealthCardModel,
    PatientPortalLinkModel,
    PatientReadingModel,
    PatientRequestModel,
    PatientShareModel,
) 
from src.infrastructure.opd.models.ai_wallet_model import (  # noqa: F401
    AIWalletModel,
    AIRechargeModel,
    AIWalletTxnModel,
)
# Staff User model — multi-user auth (receptionists, doctors)
from src.infrastructure.staff.models.staff_user_model import StaffUserModel  # noqa: F401
# Admin User model — super_admin + ceo auth
from src.infrastructure.identity.models.admin_user_model import AdminUserModel  # noqa: F401
# Clinic model — multi-tenant core
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: F401
# Staff PIN model — per-clinic role PINs
from src.infrastructure.clinic.models.staff_pin_model import StaffPinModel  # noqa: F401
# ABDM compliance models — abha_links, consent_artefacts, abdm_transactions
from src.infrastructure.abdm.models import (  # noqa: F401
    AbdmTransactionModel,
    AbhaLinkModel,
    ConsentArtefactModel,
)
# External lab network model — lab_orders
from src.infrastructure.lab.models import LabOrderModel  # noqa: F401
# Queue Engine — chamber sessions (▶ START OPD gate, Part D · E-01)
from src.infrastructure.queue.models.chamber_session_model import (  # noqa: F401
    ChamberSessionModel,
)
# Slot booking — appointment_slots (Part B · B5, BLOCK 3 · SLT-01)
from src.infrastructure.queue.models.appointment_slot_model import (  # noqa: F401
    AppointmentSlotModel,
)
# Verified reviews — clinic_reviews (Part F · F-07)
from src.infrastructure.clinic.models.review_model import (  # noqa: F401
    ClinicReviewModel,
)
# Referrals — cross-clinic slips (Part F · F-06)
from src.infrastructure.clinic.models.referral_model import (  # noqa: F401
    ReferralModel,
)
# Clinic leads — outreach pipeline (BLOCK 4 · GRW-02)
from src.infrastructure.clinic.models.lead_model import ClinicLeadModel  # noqa: F401
# Crawl runs — Module 6 ingestion tracking (BLOCK 5)
from src.infrastructure.clinic.models.crawl_model import (  # noqa: F401
    DoctorCrawlRunModel,
)


# =========================================================================
# App Lifespan
# =========================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: create tables (both SQLite and PostgreSQL)
    if _DB_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        print(f"[GHOS] Database: {_DB_URL} (tables created)")
        _migrate_sqlite_columns()
    else:
        # PostgreSQL — create schemas first, then tables
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS identity"))
            await conn.run_sync(Base.metadata.create_all)
        print(f"[GHOS] Database: PostgreSQL (tables created)")

        # ── Auto-migration: add missing columns to existing tables ──
        await _migrate_missing_columns()

    # Store sync session factory in app state
    # Store sync session factory in app state (used by JSON backend fallback)
    app.state.db_session = SessionLocal

    print(f"[GHOS] {APP_NAME} v{APP_VERSION} ready")

    # Seed default admin accounts (super_admin + ceo) on first startup
    try:
        await seed_default_admins()
    except Exception as e:
        print(f"[GHOS] Admin seed skipped (may exist already): {e}")

    # Start license expiry scheduler
    try:
        from src.infrastructure.clinic.services.license_scheduler import start_license_scheduler
        start_license_scheduler()
    except Exception as e:
        print(f"[GHOS] License scheduler start failed: {e}")

    # Start in-app auto backups (startup + daily 23:30 UTC — hosted envs without cron)
    try:
        from src.infrastructure.clinic.services.auto_backup import start_auto_backup
        start_auto_backup()
    except Exception as e:
        print(f"[GHOS] Auto-backup start failed: {e}")

    yield

    # Stop scheduler on shutdown
    try:
        from src.infrastructure.clinic.services.license_scheduler import stop_license_scheduler
        stop_license_scheduler()
    except Exception:
        pass
    try:
        from src.infrastructure.clinic.services.auto_backup import stop_auto_backup
        stop_auto_backup()
    except Exception:
        pass
    print("[GHOS] Shutdown complete")


def _migrate_sqlite_columns():
    """Generic SQLite column migrator.

    SQLite `create_all` creates new tables but never adds columns to existing
    tables, so model updates (e.g. multi-tenant clinic_id, AI BYOK keys) leave
    production DBs missing columns. This compares each model table against the
    live schema and ALTERs in whatever is missing. Idempotent + non-fatal.
    """
    try:
        from sqlalchemy import inspect as _inspect

        insp = _inspect(engine)
        with engine.connect() as conn:
            for table in Base.metadata.sorted_tables:
                if not insp.has_table(table.name):
                    continue
                existing = {c["name"] for c in insp.get_columns(table.name)}
                for col in table.columns:
                    if col.name in existing:
                        continue
                    coltype = col.type.compile(dialect=engine.dialect)
                    default_sql = ""
                    try:
                        arg = getattr(col.default, "arg", None)
                        if isinstance(arg, str):
                            default_sql = f" DEFAULT '{arg.replace(chr(39), chr(39) * 2)}'"
                        elif isinstance(arg, (int, float)) and not isinstance(arg, bool):
                            default_sql = f" DEFAULT {arg}"
                    except Exception:
                        default_sql = ""
                    sql = f"ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}{default_sql}"
                    conn.execute(text(sql))
                    print(f"[GHOS] SQLite migration: added {table.name}.{col.name} ({coltype})")
            conn.commit()

            # ALTER TABLE ADD COLUMN never creates indexes, so add the ones the
            # queue engine depends on. Idempotent, and skipped harmlessly when
            # the table is not there yet.
            for idx_sql in (
                "CREATE INDEX IF NOT EXISTS ix_queue_clinic_doctor_status "
                "ON queue_entries (clinic_id, doctor_id, status)",
                "CREATE INDEX IF NOT EXISTS ix_chamber_clinic_doctor_date "
                "ON chamber_sessions (clinic_id, doctor_id, session_date)",
                # Slot booking (BLOCK 3): counting a slot's bookings reads the
                # queue, so this index keeps the slot grid to one query.
                "CREATE INDEX IF NOT EXISTS ix_queue_slot_id "
                "ON queue_entries (slot_id)",
                "CREATE INDEX IF NOT EXISTS ix_slot_clinic_date "
                "ON appointment_slots (clinic_id, slot_date)",
            ):
                try:
                    conn.execute(text(idx_sql))
                except Exception as e:  # pragma: no cover - index is an optimisation
                    print(f"[GHOS] index create skipped: {e}")
            conn.commit()
    except Exception as e:
        print(f"[GHOS] SQLite migration skipped/failed (non-fatal): {e}")


async def _migrate_missing_columns():
    """Add any missing columns to existing tables (safe idempotent migration).
    
    Checks each column against the table and adds it if missing.
    This handles cases where the model was updated but the production DB
    already has the table from a previous create_all.
    """
    from sqlalchemy import inspect as sa_inspect

    migrations = [
        # (table_name, column_name, column_type_sql, default_sql)
        ("opd_settings", "wa_reception", "VARCHAR(20)", "' '"),
        ("opd_settings", "wa_manager", "VARCHAR(20)", "' '"),
        ("opd_settings", "wa_doctor", "VARCHAR(20)", "' '"),
        ("opd_settings", "wa_dietitian", "VARCHAR(20)", "' '"),
        ("opd_settings", "doc_extra_quals", "TEXT", "' '"),
        # Multi-tenant: add clinic_id to all tables
        ("queue_entries", "clinic_id", "VARCHAR(36)", "NULL"),
        ("patients", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_prescriptions", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_drug_history", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_templates", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_licenses", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_settings", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_specialty_upgrades", "clinic_id", "VARCHAR(36)", "NULL"),
        ("opd_pending_scans", "clinic_id", "VARCHAR(36)", "NULL"),
        ("staff_users", "clinic_id", "VARCHAR(36)", "NULL"),
        # ── Marketplace geolocation (Find a Doctor distance sort) ──
        ("clinics", "latitude", "DOUBLE PRECISION", "NULL"),
        ("clinics", "longitude", "DOUBLE PRECISION", "NULL"),
        # ── ABDM registry IDs (HPR/HFR) ──
        ("clinics", "hpr_id", "VARCHAR(50)", "''"),
        ("clinics", "hfr_id", "VARCHAR(50)", "''"),
        # ── AI Provider upgrade (BYOK): new encrypted key columns + mode ──
        ("opd_settings", "ai_mode", "VARCHAR(20)", "'auto'"),
        ("opd_settings", "ai_model", "VARCHAR(100)", "''"),
        ("opd_settings", "openai_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "anthropic_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "deepseek_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "gemini_api_key", "VARCHAR(500)", "''"),
        # ── Drug Bank upgrade: full medicine fields on opd_drug_history ──
        ("opd_drug_history", "brand_name", "VARCHAR(200)", "''"),
        ("opd_drug_history", "strength", "VARCHAR(100)", "''"),
        ("opd_drug_history", "salt_composition", "VARCHAR(500)", "''"),
        ("opd_drug_history", "form", "VARCHAR(50)", "''"),
        ("opd_drug_history", "default_frequency", "VARCHAR(20)", "''"),
        ("opd_drug_history", "default_timing", "VARCHAR(100)", "''"),
        ("opd_drug_history", "default_duration", "VARCHAR(50)", "''"),
        ("opd_drug_history", "active", "BOOLEAN", "TRUE"),
        ("opd_drug_history", "updated_at", "TIMESTAMP WITH TIME ZONE", "NOW()"),
        # New tables that might need creation
        ("clinic_staff_pins", "id", "INTEGER", "NULL"),  # will cause skip if table exists
        # ── Queue Engine (EWT + Part D edge cases) ──
        # SQLite gets these automatically from the models; PostgreSQL (hosted)
        # needs them listed here.
        ("queue_entries", "doctor_id", "VARCHAR(100)", "'chief'"),
        ("queue_entries", "visit_type", "VARCHAR(20)", "''"),
        ("queue_entries", "complexity_weight", "INTEGER", "1"),
        ("queue_entries", "estimated_minutes", "INTEGER", "NULL"),
        ("queue_entries", "sort_key", "DOUBLE PRECISION", "NULL"),
        ("queue_entries", "requeue_count", "INTEGER", "0"),
        ("queue_entries", "held_at", "TIMESTAMP WITH TIME ZONE", "NULL"),
        ("queue_entries", "hold_reason", "VARCHAR(200)", "''"),
        # ── Opening hours + ratings (BLOCK 2 · AVL-01 / AVL-02 / E-06 / F-07) ──
        # Without these the marketplace called every licensed clinic "OPEN",
        # including on a Sunday at 11 PM.
        ("clinics", "open_time", "VARCHAR(5)", "'09:00'"),
        ("clinics", "close_time", "VARCHAR(5)", "'18:00'"),
        ("clinics", "closed_days", "VARCHAR(50)", "''"),
        ("clinics", "holiday_until", "VARCHAR(10)", "''"),
        ("clinics", "rating", "DOUBLE PRECISION", "NULL"),
        ("clinics", "rating_count", "INTEGER", "0"),
        # ── Slot booking (BLOCK 3 · SLT-01 / SLT-02) ──
        # The appointment_slots table itself is created by create_all; these two
        # columns link a queue entry back to the slot it reserved.
        ("queue_entries", "slot_id", "VARCHAR(36)", "NULL"),
        ("queue_entries", "slot_time", "VARCHAR(5)", "''"),
        # ── Health card revocation (BLOCK 4 · GRW-01 / DPDP) ──
        # active=0 was a silent switch with no record behind it; a consent
        # withdrawal needs who/when/why to be auditable.
        ("health_cards", "revoked_at", "TIMESTAMP WITH TIME ZONE", "NULL"),
        ("health_cards", "revoked_by", "VARCHAR(100)", "''"),
        ("health_cards", "revoked_reason", "VARCHAR(200)", "''"),
        # ── Ingestion provenance (BLOCK 5 · Module 6) ──
        # A crawled listing must never look like a clinic-confirmed one, and an
        # opt-out must survive the next crawl run — both need stored state.
        ("clinics", "source", "VARCHAR(20)", "'manual'"),
        ("clinics", "crawl_source_url", "VARCHAR(500)", "''"),
        ("clinics", "crawl_run_id", "VARCHAR(36)", "''"),
        ("clinics", "crawl_verified_at", "TIMESTAMP WITH TIME ZONE", "NULL"),
        ("clinics", "claim_status", "VARCHAR(20)", "'unclaimed'"),
        ("clinics", "claimed_at", "TIMESTAMP WITH TIME ZONE", "NULL"),
        ("clinics", "opted_out_at", "TIMESTAMP WITH TIME ZONE", "NULL"),
        ("clinics", "opt_out_reason", "VARCHAR(200)", "''"),
    ]

    try:
        async with engine.begin() as conn:
            # Get existing columns for each table
            for table_name, col_name, col_type, default_val in migrations:
                try:
                    # Check if column exists
                    check_sql = text(
                        f"SELECT column_name FROM information_schema.columns "
                        f"WHERE table_name = :tbl AND column_name = :col"
                    )
                    result = await conn.execute(check_sql, {"tbl": table_name, "col": col_name})
                    exists = result.fetchone() is not None

                    if not exists:
                        alter_sql = text(
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type} DEFAULT {default_val}"
                        )
                        await conn.execute(alter_sql)
                        print(f"[GHOS] Migration: Added column {table_name}.{col_name}")
                except Exception as e:
                    print(f"[GHOS] Migration warning ({table_name}.{col_name}): {e}")

            # Widen groq_api_key to fit Fernet-encrypted values (legacy VARCHAR(200))
            try:
                await conn.execute(text("ALTER TABLE opd_settings ALTER COLUMN groq_api_key TYPE VARCHAR(500)"))
                print("[GHOS] Migration: opd_settings.groq_api_key widened to VARCHAR(500)")
            except Exception as e:
                print(f"[GHOS] Migration warning (groq_api_key widen): {e}")

        print("[GHOS] Auto-migration check complete")
    except Exception as e:
        print(f"[GHOS] Auto-migration error (non-fatal): {e}")


# =========================================================================
# FastAPI App
# =========================================================================

# Docs are OFF by default: the OpenAPI schema lists every internal and
# staff endpoint, and exposing it publicly was one of the audit's P0 findings.
# Turn them on locally with ENABLE_DOCS=1 when actually developing against them.
_ENABLE_DOCS = os.getenv("ENABLE_DOCS") == "1"

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESC,
    lifespan=lifespan,
    docs_url="/docs" if _ENABLE_DOCS else None,
    redoc_url="/redoc" if _ENABLE_DOCS else None,
)

# Make clinic settings available for the root page
from src.infrastructure.clinic.settings_provider import get_clinic_settings

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================================
# Routes
# =========================================================================

# Queue Lite API
app.include_router(queue_router)

# Experience Engine (PWA + API)
app.include_router(experience_api_router)
app.include_router(experience_router)

# Clinic Engine
app.include_router(clinic_router)

# Clinic Auth (multi-tenant login)
app.include_router(clinic_auth_router)

# Patient Engine
app.include_router(patient_router)

# Staff Dashboard (HTML, session auth)
app.include_router(staff_router)
app.include_router(staff_settings_router)

# Public Patient Tracking — NO login required, clean URL: /track/{token}
app.include_router(patient_track_router)

# Smart OPD (HTML + API, session auth)
app.include_router(opd_router)

# Patient Portal — public token links (/my/<token>, /s/<token>) + doctor APIs
app.include_router(patient_portal_router)
app.include_router(patient_portal_doctor_router)

# Admin Panel (Super Admin + CEO)
app.include_router(admin_auth_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_doctor_router)

# Marketplace — Find a Doctor (public, no login)
app.include_router(marketplace_router)

# Universal Health Card (public card + doctor create endpoint)
app.include_router(health_card_router)
app.include_router(health_card_doctor_router)

# ABDM compliance (API + status page)
app.include_router(abdm_router)
app.include_router(abdm_page_router)

# Smart Prescription Pad
app.include_router(rx_pad_router)

# External Lab Network
app.include_router(lab_network_router)
app.include_router(lab_network_doctor_router)

# Queue Engine — chamber gate (▶ START OPD), token hold/return, live EWT feed
app.include_router(queue_engine_router)

# Friendly URLs — /opd/Dashboard, /dashboard, /opd/dashbord … ab dead-end nahi
app.include_router(friendly_router)
install_friendly_404(app)

# Slot booking — appointment slots grid, capacity-checked booking, Code Red
app.include_router(slots_router)

# Clinic stats — EWT accuracy (F-03) + PHI-free network view (F-08)
app.include_router(clinic_stats_router)

# Verified reviews — one review per completed visit (F-07)
app.include_router(reviews_router)

# Referrals — signed cross-clinic slip, accept creates a real token (F-06)
app.include_router(referral_router)

# Growth — clinic invite pipeline (GRW-02) + city SEO pages (GRW-03)
app.include_router(growth_router)

# Module 6 — crawled doctor profiles, run history, claim and opt-out (BLOCK 5)
app.include_router(ingest_router)

# PWA — one manifest + one root-scoped service worker (installable app)
app.include_router(pwa_router)

# Clinic tools — a real page for referral / slots / reviews / FHIR / audit
app.include_router(tools_router)

# Serve static files from experience/pwa
pwa_static = Path(__file__).parent / "src" / "experience" / "pwa"
if pwa_static.exists():
    app.mount(
        "/static/pwa",
        StaticFiles(directory=str(pwa_static)),
        name="pwa-static",
    )

# Serve staff dashboard static files
_dash_static = Path(__file__).parent / "static"
if _dash_static.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(_dash_static)),
        name="dash-static",
    )


# =========================================================================
# Root
# =========================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Public landing / demo page (friend/client ko bhejne ke liye)."""
    return HTMLResponse(content=await _render_home())


@app.get("/login", include_in_schema=False)
@app.get("/portal", include_in_schema=False)
async def staff_login_page():
    """Staff login — Super Admin or Clinic Login."""
    return HTMLResponse(content=_render_landing())


async def _render_home() -> str:
    """Public demo landing page — live stats (doctors/cities/specialties) ke saath."""
    import jinja2
    import sqlalchemy as sa

    from src.infrastructure.clinic.models.clinic_model import ClinicModel
    from src.shared.infrastructure.database import async_session_factory

    stats = {"doctors": 0, "cities": 0, "specialties": 0}
    try:
        async with async_session_factory() as session:
            active = ClinicModel.is_active == True  # noqa: E712
            stats["doctors"] = int(
                (await session.execute(
                    sa.select(sa.func.count()).select_from(ClinicModel).where(active)
                )).scalar() or 0
            )
            stats["cities"] = int(
                (await session.execute(
                    sa.select(sa.func.count(sa.distinct(ClinicModel.city))).where(active)
                )).scalar() or 0
            )
            stats["specialties"] = int(
                (await session.execute(
                    sa.select(sa.func.count(sa.distinct(ClinicModel.specialty))).where(active)
                )).scalar() or 0
            )
    except Exception as e:  # pragma: no cover - stats are cosmetic
        print(f"[GHOS] home stats skipped: {e}")

    _loader = jinja2.FileSystemLoader(str(Path(__file__).parent / "templates"))
    _env = jinja2.Environment(loader=_loader, auto_reload=True)
    return _env.get_template("home.html").render(**stats)


def _render_landing() -> str:
    """Render the staff login page (buttons)."""
    import jinja2
    _loader = jinja2.FileSystemLoader(str(Path(__file__).parent / "templates"))
    _env = jinja2.Environment(loader=_loader, auto_reload=True)
    return _env.get_template("landing.html").render()


@app.get("/clinic-portal", include_in_schema=False)
async def clinic_portal(request: Request, error: str = ""):
    """Dedicated clinic login page — only username+password from admin."""
    return HTMLResponse(content=_render_template("clinic_login.html", error=error))


def _render_template(name: str, **context) -> str:
    """Render a Jinja2 template from the templates directory."""
    import jinja2
    _loader = jinja2.FileSystemLoader(str(Path(__file__).parent / "templates"))
    _env = jinja2.Environment(loader=_loader, auto_reload=True)
    return _env.get_template(name).render(**context)


@app.get("/presentation", include_in_schema=False)
@app.get("/presentation.html", include_in_schema=False)
@app.get("/deck", include_in_schema=False)
async def presentation():
    """Master Presentation & Executive Concept Note (32 Slides)."""
    p_path = Path(__file__).parent / "CardioQueue_Master_Presentation.html"
    if p_path.exists():
        return HTMLResponse(content=p_path.read_text(encoding="utf-8"))
    return HTMLResponse(content=_render_template("presentation.html"))


@app.get("/manual", include_in_schema=False)
@app.get("/user-manual", include_in_schema=False)
async def user_manual():
    """CardioQueue Operations & User Manual."""
    m_path = Path(__file__).parent / "USER_MANUAL.html"
    if m_path.exists():
        return HTMLResponse(content=m_path.read_text(encoding="utf-8"))
    return HTMLResponse(content=_render_template("manual.html"))


@app.get("/health", include_in_schema=False)
async def health():
    """Healthcheck + LIVE BUILD stamp.

    `build` har deploy par badalta hai, is liye yahi sabse aasan tarika hai ye
    janne ka ki live par naya code chadha hai ya purana.
    """
    return {
        "status": "ok",
        "build": BUILD_STAMP,
        "commit": BUILD_COMMIT,
        "built_at": BUILD_AT,
        "files_shipped": BUILD_FILES,
        "version": APP_VERSION,
    }


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main_v2:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=True,
    )
