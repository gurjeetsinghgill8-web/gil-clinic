"""Presentation layer for the Patient Engine."""

from src.presentation.patient.routes.patient_routes import router as patient_router
from src.presentation.patient.errors.error_handlers import register_error_handlers

__all__ = [
    "patient_router",
    "register_error_handlers",
]
