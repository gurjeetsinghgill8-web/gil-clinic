"""Repository protocols for Clinic Engine (Departments + Services).

Defines the persistence contract for department and service management.
"""

from __future__ import annotations

from typing import Protocol

from src.domain.clinic.entities.department import Department
from src.domain.clinic.entities.service import Service


class DepartmentRepository(Protocol):
    """Repository protocol for Department CRUD."""

    async def list_all(self) -> list[Department]:
        """Return all departments (active and inactive)."""
        ...

    async def list_active(self) -> list[Department]:
        """Return only active departments, sorted by display_order."""
        ...

    async def get_by_code(self, code: str) -> Department | None:
        """Find a department by its unique code."""
        ...

    async def save(self, department: Department) -> None:
        """Create or update a department (upsert by code)."""
        ...

    async def delete(self, code: str) -> bool:
        """Delete a department by code. Returns True if deleted."""
        ...

    async def exists(self, code: str) -> bool:
        """Check if a department with given code exists."""
        ...


class ServiceRepository(Protocol):
    """Repository protocol for Service CRUD."""

    async def list_all(self) -> list[Service]:
        """Return all services."""
        ...

    async def list_by_department(self, department_code: str) -> list[Service]:
        """Return all services for a given department."""
        ...

    async def list_active_by_department(self, department_code: str) -> list[Service]:
        """Return active services for a given department."""
        ...

    async def get_by_code(self, code: str) -> Service | None:
        """Find a service by its unique code."""
        ...

    async def save(self, service: Service) -> None:
        """Create or update a service (upsert by code)."""
        ...

    async def delete(self, code: str) -> bool:
        """Delete a service by code. Returns True if deleted."""
        ...

    async def exists(self, code: str) -> bool:
        """Check if a service with given code exists."""
        ...
