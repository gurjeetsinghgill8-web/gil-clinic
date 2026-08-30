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
_DB_URL = os.getenv("GHOS_DB_URL", "sqlite:///./ghos_dev.db")

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

# -- Admin Panel (Super Admin + CEO) --
from src.presentation.admin.routes.auth_routes import router as admin_auth_router
from src.presentation.admin.routes.dashboard_routes import router as admin_dashboard_router
from src.presentation.admin.routes.doctor_routes import router as admin_doctor_router
from src.presentation.admin.routes.auth_routes import seed_default_admins


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
# Staff User model — multi-user auth (receptionists, doctors)
from src.infrastructure.staff.models.staff_user_model import StaffUserModel  # noqa: F401
# Admin User model — super_admin + ceo auth
from src.infrastructure.identity.models.admin_user_model import AdminUserModel  # noqa: F401
# Clinic model — multi-tenant core
from src.infrastructure.clinic.models.clinic_model import ClinicModel  # noqa: F401
# Staff PIN model — per-clinic role PINs
from src.infrastructure.clinic.models.staff_pin_model import StaffPinModel  # noqa: F401


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
        # ── AI Provider upgrade (BYOK): new encrypted key columns + mode ──
        ("opd_settings", "ai_mode", "VARCHAR(20)", "'auto'"),
        ("opd_settings", "ai_model", "VARCHAR(100)", "''"),
        ("opd_settings", "openai_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "anthropic_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "deepseek_api_key", "VARCHAR(500)", "''"),
        ("opd_settings", "gemini_api_key", "VARCHAR(500)", "''"),
        # New tables that might need creation
        ("clinic_staff_pins", "id", "INTEGER", "NULL"),  # will cause skip if table exists
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

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=APP_DESC,
    lifespan=lifespan,
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

# Admin Panel (Super Admin + CEO)
app.include_router(admin_auth_router)
app.include_router(admin_dashboard_router)
app.include_router(admin_doctor_router)

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
    """Landing page — Super Admin or Clinic Login."""
    return HTMLResponse(content=_render_landing())


def _render_landing() -> str:
    """Render the 2-button landing page."""
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
    """Healthcheck endpoint for Railway deployment container."""
    return {"status": "ok", "build": "2026.08.06.v2.0", "version": APP_VERSION, "timestamp": "2026-08-06T19:30:00Z"}


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
