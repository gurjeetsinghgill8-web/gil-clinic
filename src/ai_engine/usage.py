"""Async AI usage logging — safe to call from any route; failures are non-fatal."""

from __future__ import annotations

import logging
from typing import Optional

from src.infrastructure.opd.models.ai_usage_model import AIUsageModel
from src.shared.infrastructure.database import async_session_factory

logger = logging.getLogger("ai_usage")


async def log_ai_usage(
    *,
    clinic_id: Optional[str] = None,
    doctor_id: str = "",
    feature: str = "",
    provider: str = "",
    model: str = "",
    success: bool = True,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    error: str = "",
) -> None:
    try:
        async with async_session_factory() as session:
            session.add(
                AIUsageModel(
                    clinic_id=clinic_id,
                    doctor_id=doctor_id or "unknown",
                    feature=feature or "unknown",
                    provider=provider or "unknown",
                    model=model or "",
                    success=1 if success else 0,
                    prompt_tokens=int(prompt_tokens or 0),
                    completion_tokens=int(completion_tokens or 0),
                    error=(error or "")[:500],
                )
            )
            await session.commit()
    except Exception as e:
        logger.warning("log_ai_usage failed (non-fatal): %s", e)
