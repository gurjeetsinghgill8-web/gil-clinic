"""Queue Lite — Manager Dashboard.

Composite analytics view for clinic management showing:
- Today's KPIs (patients, tests, wait times, completion rate)
- Per-department load (waiting / in-progress / completed counts)
- Recent queue activity (from audit log)
- 7-day daily trend (created vs completed)
- Per-service performance stats
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.domain.queue.events.queue_events import EVENT_LABELS
from src.infrastructure.clinic.department_provider import get_active_departments

if TYPE_CHECKING:
    from src.domain.queue.ports.queue_repository import QueueRepository
    from src.infrastructure.persistence.queue.repositories.audit_repository import (
        SqlAlchemyAuditRepository,
    )


class ManagerDashboardUseCase(BaseUseCase):
    """Use case for the Manager Dashboard analytics view."""

    def __init__(
        self,
        queue_repo: QueueRepository,
        audit_repo: SqlAlchemyAuditRepository | None = None,
    ) -> None:
        super().__init__()
        self._queue_repo = queue_repo
        self._audit_repo = audit_repo

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        days = dto.get("days", 7)

        try:
            now = datetime.now(timezone.utc)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)

            # ── Today's counts ──────────────────────────────────────────
            tests_today = await self._queue_repo.count_created_between(
                today_start, today_end
            )
            completed_today = 0
            # For completion count, use list_by_status
            completed_entries = await self._queue_repo.list_by_status(
                status="COMPLETED", limit=1000
            )
            completed_today = len(completed_entries)

            # ── Report readiness / delivery KPIs ─────────────────────────
            report_ready_entries = await self._queue_repo.list_by_status(
                status="REPORT_READY", limit=1000
            )
            report_ready_today = len(report_ready_entries)

            delivered_entries = await self._queue_repo.list_by_status(
                status="DELIVERED", limit=1000
            )
            delivered_today = len(delivered_entries)

            # Report delivery rate
            delivery_rate = 0.0
            report_total = report_ready_today + delivered_today
            if report_total > 0:
                delivery_rate = round(delivered_today / report_total * 100, 1)

            # Unique patients today = count distinct patient_id from recent entries
            # Approximate via all today entries
            all_today = await self._queue_repo.get_daily_counts(days=1)
            patients_today = 0
            if all_today:
                patients_today = all_today[-1].get("created", 0)

            # ── Average wait time today ─────────────────────────────────
            service_stats = await self._queue_repo.get_service_stats(
                today_start, today_end
            )
            total_avg = 0.0
            if service_stats:
                weighted_sum = sum(
                    s["avg_wait_minutes"] * s["count"] for s in service_stats
                )
                total_count = sum(s["count"] for s in service_stats)
                total_avg = round(weighted_sum / total_count, 1) if total_count > 0 else 0.0

            # Completion rate
            completion_rate = 0.0
            if tests_today > 0:
                completion_rate = round(completed_today / tests_today * 100, 1)

            # ── Department load ─────────────────────────────────────────
            # Fetch all today's entries and compute department breakdown in Python
            # (avoids async session isolation issues with count_by_status)
            departments = get_active_departments()
            all_today_entries = []
            for status_filter in ("WAITING", "CALLED", "IN_PROGRESS", "COMPLETED"):
                entries = await self._queue_repo.list_by_status(status_filter, limit=500)
                all_today_entries.extend(entries)

            # Count by department name in Python
            dept_counts: dict[str, dict] = {}
            for dept in departments:
                dept_counts[dept.name] = {
                    "code": dept.code,
                    "name": dept.name,
                    "waiting": 0,
                    "called": 0,
                    "in_progress": 0,
                    "active": 0,
                    "completed": 0,
                }
            for entry in all_today_entries:
                dept_name = entry.department
                if dept_name not in dept_counts:
                    continue
                status = entry.status.value if entry.status else ""
                if status == "WAITING":
                    dept_counts[dept_name]["waiting"] += 1
                elif status == "CALLED":
                    dept_counts[dept_name]["called"] += 1
                elif status == "IN_PROGRESS":
                    dept_counts[dept_name]["in_progress"] += 1
                elif status == "COMPLETED":
                    dept_counts[dept_name]["completed"] += 1

            department_load = []
            for d in dept_counts.values():
                d["active"] = d["waiting"] + d["called"] + d["in_progress"]
                total = d["active"] + d["completed"]
                d["load_pct"] = round(d["active"] / max(total, 1) * 100, 0)
                department_load.append(d)

            department_load.sort(key=lambda x: x["active"], reverse=True)

            # ── Recent activity ─────────────────────────────────────────
            recent_activity = []
            if self._audit_repo:
                audit_entries = await self._audit_repo.query(
                    date_from=today_start,
                    date_to=today_end,
                    limit=30,
                )
                for entry in audit_entries:
                    details = entry.get("details", {}) or {}
                    recent_activity.append({
                        "time": entry["created_at"],
                        "action": entry["action"],
                        "action_label": EVENT_LABELS.get(entry["action"], entry["action"]),
                        "actor": entry["actor"],
                        "patient_name": details.get("patient_name", ""),
                        "service_code": details.get("service_code", ""),
                        "token_number": details.get("token_number"),
                    })

            # ── Daily trend ────────────────────────────────────────────
            daily_trend = await self._queue_repo.get_daily_counts(days=days)

            # ── Service stats ───────────────────────────────────────────
            # Combine today's service stats with full names from provider
            from src.infrastructure.clinic.department_provider import get_service_map
            service_map = get_service_map()
            enriched_services = []
            for s in service_stats:
                svc = service_map.get(s["service_code"])
                enriched_services.append({
                    "service_code": s["service_code"],
                    "service_name": svc.display_name if svc else s["service_code"],
                    "count": s["count"],
                    "avg_wait_minutes": s["avg_wait_minutes"],
                })

            return Result.ok(
                data={
                    "stats": {
                        "patients_today": patients_today,
                        "tests_today": tests_today,
                        "completed_today": completed_today,
                        "report_ready_today": report_ready_today,
                        "delivered_today": delivered_today,
                        "delivery_rate_pct": delivery_rate,
                        "avg_wait_minutes": total_avg,
                        "completion_rate_pct": completion_rate,
                    },
                    "department_load": department_load,
                    "recent_activity": recent_activity,
                    "daily_trend": daily_trend,
                    "service_stats": enriched_services,
                },
            )

        except Exception as exc:
            return Result.fail(
                error=str(exc),
                code="MANAGER_500",
            )
