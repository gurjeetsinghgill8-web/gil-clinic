"""Experience Engine — Feedback Use Case.

Allows patients to submit post-visit feedback (rating + comment).
Stored in a simple JSON file — no DB table needed.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result


class FeedbackUseCase(BaseUseCase):
    """Use case for submitting patient feedback.

    Feedback is appended to a JSON file at cardioqueue_data/feedback.json.
    """

    FEEDBACK_DIR = Path(os.getenv("GHOS_DATA_DIR", "cardioqueue_data"))
    FEEDBACK_FILE = FEEDBACK_DIR / "feedback.json"

    def __init__(self) -> None:
        super().__init__()
        self._ensure_feedback_file()

    def _ensure_feedback_file(self) -> None:
        """Ensure the feedback directory and file exist."""
        self.FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        if not self.FEEDBACK_FILE.exists():
            self.FEEDBACK_FILE.write_text("[]", encoding="utf-8")

    def _load_feedback(self) -> list[dict[str, Any]]:
        """Load all feedback entries from the JSON file.

        Returns:
            List of feedback dicts.
        """
        try:
            data = self.FEEDBACK_FILE.read_text(encoding="utf-8")
            return json.loads(data) if data.strip() else []
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def _save_feedback(self, entries: list[dict[str, Any]]) -> None:
        """Save feedback entries to the JSON file.

        Args:
            entries: List of feedback dicts to persist.
        """
        self.FEEDBACK_FILE.write_text(
            json.dumps(entries, indent=2, default=str),
            encoding="utf-8",
        )

    async def authorize(self, command: Command) -> None:
        """Feedback submission requires patient session."""
        pass

    async def execute(self, command: Command) -> Result:
        """Submit feedback for the current patient.

        Args:
            command: Command with patient_uuid, patient_id, name,
                     rating (1-5), and optional comment.

        Returns:
            Result with submission confirmation.
        """
        dto = command.data
        patient_uuid = dto.get("patient_uuid", "")
        patient_id = dto.get("patient_id", "")
        patient_name = dto.get("patient_name", "")
        rating = dto.get("rating", 0)
        comment = dto.get("comment", "")

        if not patient_uuid:
            return Result.fail(error="Patient identifier is required.")

        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return Result.fail(error="Rating must be an integer between 1 and 5.")

        entry = {
            "patient_uuid": patient_uuid,
            "patient_id": patient_id,
            "patient_name": patient_name,
            "rating": rating,
            "comment": comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        entries = self._load_feedback()
        entries.append(entry)
        self._save_feedback(entries)

        return Result.ok(
            data={
                "status": "submitted",
                "message": "Thank you for your feedback! 🙏",
                "rating": rating,
            },
            message="Feedback submitted successfully.",
        )

    async def list_feedback(
        self,
        limit: int = 50,
        min_rating: int | None = None,
    ) -> Result:
        """List feedback entries for staff viewing (internal use).

        Args:
            limit: Max entries to return (newest first).
            min_rating: Optional minimum rating filter.

        Returns:
            Result with list of feedback entries.
        """
        entries = self._load_feedback()
        entries.reverse()  # Newest first

        if min_rating is not None:
            entries = [e for e in entries if e.get("rating", 0) >= min_rating]

        return Result.ok(data={"feedback": entries[:limit], "total": len(entries)})
