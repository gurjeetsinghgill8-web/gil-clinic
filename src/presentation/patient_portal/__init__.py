"""Patient Portal (Smart OPD) — patient self-filling + read-only doctor share."""

from src.presentation.patient_portal.routes.patient_portal_routes import (  # noqa: F401
    doctor_router,
    router,
)

__all__ = ["router", "doctor_router"]
