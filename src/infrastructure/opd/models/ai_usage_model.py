"""AI usage metering — one row per AI call, per clinic, so each clinic's AI
consumption is visible and billable independently (GIL CLINIC pays ₹0)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.shared.infrastructure.database import Base


class AIUsageModel(Base):
    __tablename__ = "ai_usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    clinic_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    doctor_id: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    feature: Mapped[str] = mapped_column(String(50), nullable=False, default="", index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    success: Mapped[int] = mapped_column(Integer, default=1)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
