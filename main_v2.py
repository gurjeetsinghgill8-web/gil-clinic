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


# =========================================================================
# Database Setup
# =========================================================================

from sqlalchemy import create_engine
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


# =========================================================================
# App Lifespan
# =========================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup: create tables if using SQLite
    if _DB_URL.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        print(f"[GHOS] Database: {_DB_URL} (tables created)")

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

# Serve static files from experience/pwa
pwa_static = Path(__file__).parent / "src" / "experience" / "pwa"
if pwa_static.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(pwa_static)),
        name="pwa-static",
    )


# =========================================================================
# Root
# =========================================================================


@app.get("/", include_in_schema=False)
async def root():
    """Root redirect — show available dashboards."""
    cs = get_clinic_settings()
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head><title>{cs.logo_emoji} {cs.name}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #f5f7fa;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .card {{
            background: white;
            border-radius: 20px;
            padding: 40px 32px;
            max-width: 420px;
            width: 90%;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }}
        h1 {{ font-size: 22px; color: #2c3e50; margin-bottom: 4px; }}
        .sub {{ color: #888; font-size: 14px; margin-bottom: 24px; }}
        .btn {{
            display: block;
            width: 100%;
            padding: 14px 20px;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            text-align: center;
            text-decoration: none;
            margin-bottom: 10px;
            transition: all 0.2s;
        }}
        .btn:active {{ transform: scale(0.97); }}
        .btn-primary {{ background: #3498db; color: white; }}
        .btn-success {{ background: #2ecc71; color: white; }}
        .btn-warning {{ background: #f39c12; color: white; }}
        .btn-danger {{ background: #e74c3c; color: white; }}
        .btn-purple {{ background: #9b59b6; color: white; }}
        .btn-outline {{
            background: white;
            color: #2c3e50;
            border: 2px solid #e0e0e0;
        }}
        .footer {{ margin-top: 20px; font-size: 12px; color: #bbb; text-align: center; }}
        .section {{ font-size: 11px; color: #999; text-transform: uppercase; margin: 16px 0 8px; letter-spacing: 1px; }}
    </style>
    </head>
    <body>
    <div class="card">
        <h1>{cs.logo_emoji} {APP_NAME}</h1>
        <div class="sub">{cs.specialty} — v{APP_VERSION}</div>

        <div class="section">Staff Dashboards</div>
        <a href="/api/v1/queue/technician-dashboard?staff=Tech1" class="btn btn-primary">🔧 Technician Dashboard</a>
        <a href="/api/v1/queue/reception-dashboard" class="btn btn-danger">🏥 Reception Dashboard</a>
        <a href="/api/v1/queue/doctor-dashboard-page" class="btn btn" style="background:#2c3e50;color:white;">👨‍⚕️ Doctor Dashboard</a>
        <a href="/api/v1/queue/tv-display" class="btn btn-warning">📺 Live TV Display</a>

        <div class="section">Patient Experience</div>
        <a href="/experience/" class="btn btn-success">📱 Patient PWA (Login)</a>
        <a href="/api/v1/queue/patient/demo" class="btn btn-outline">👤 Demo Patient Status</a>

        <div class="section">API</div>
        <a href="/docs" class="btn btn-purple">📋 API Docs (Swagger)</a>

        <div class="footer">
            {cs.name} — {cs.specialty}<br>
            {cs.doctor_name}{(' | ' + cs.phone) if cs.phone else ''}
        </div>
    </div>
    </body>
    </html>
    """)


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
