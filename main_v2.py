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

# ═════════════════════════════════════════════════════════════════════════
# Development Configuration — MUST be set before ANY engine imports
# ═════════════════════════════════════════════════════════════════════════

# Dev mode bypass — allows API access without JWT during development
os.environ.setdefault("GHOS_DEV_AUTH_BYPASS", "true")

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
APP_VERSION = "0.9.0"
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

# -- Patient Engine --
from src.presentation.patient.routes.patient_routes import (
    router as patient_router,
)

# -- Staff Dashboard (replaces Streamlit) --
from src.presentation.staff.routes.staff_routes import router as staff_router

# -- Smart OPD --
from src.presentation.opd.routes.opd_routes import router as opd_router


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
)
# Staff User model — multi-user auth (receptionists, doctors)
from src.infrastructure.staff.models.staff_user_model import StaffUserModel  # noqa: F401


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
    else:
        # PostgreSQL — create schemas first, then tables
        async with engine.begin() as conn:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS identity"))
            # Drop all tables first to ensure schema matches models
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        print(f"[GHOS] Database: PostgreSQL (tables created)")
        print(f"[GHOS] Database: PostgreSQL (tables created)")

    # Store sync session factory in app state
    # Store sync session factory in app state (used by JSON backend fallback)
    app.state.db_session = SessionLocal

    print(f"[GHOS] {APP_NAME} v{APP_VERSION} ready")
    yield
    print("[GHOS] Shutdown complete")


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

# Patient Engine
app.include_router(patient_router)

# Staff Dashboard (HTML, session auth)
app.include_router(staff_router)

# Smart OPD (HTML + API, session auth)
app.include_router(opd_router)

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
    """Root redirect → Staff Dashboard."""
    return RedirectResponse("/staff/")


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
