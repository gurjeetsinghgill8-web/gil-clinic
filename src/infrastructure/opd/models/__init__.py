"""OPD models — all 7 tables."""
from src.infrastructure.opd.models.opd_models import (
    DrugHistoryModel,
    LicenseModel,
    OpdPrescriptionModel,
    PendingScanModel,
    SettingsModel,
    SpecialtyUpgradeModel,
    TemplateModel,
)

__all__ = [
    "OpdPrescriptionModel",
    "DrugHistoryModel",
    "TemplateModel",
    "LicenseModel",
    "SettingsModel",
    "SpecialtyUpgradeModel",
    "PendingScanModel",
]
