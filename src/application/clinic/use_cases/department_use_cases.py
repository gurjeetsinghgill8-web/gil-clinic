"""Use cases for Department CRUD operations.

Provides list, create, update, and delete use cases.
Each follows the Command → Result pattern.
"""

from __future__ import annotations

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.domain.clinic.entities.department import Department
from src.infrastructure.clinic.department_provider import (
    get_all_departments,
    get_active_departments,
    get_department_by_code,
    save_department,
    delete_department,
    department_exists,
)


class ListDepartmentsUseCase(BaseUseCase):
    """List all departments, optionally only active ones."""

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        active_only = dto.get("active_only", False)

        if active_only:
            departments = get_active_departments()
        else:
            departments = get_all_departments()

        return Result.ok(data={
            "departments": [d.to_dict() for d in departments],
            "total": len(departments),
        })


class CreateDepartmentUseCase(BaseUseCase):
    """Create a new department."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        dto = command.data
        code = dto.get("code", "").strip()
        name = dto.get("name", "").strip()

        if not code:
            raise ValueError("Department code is required")
        if not name:
            raise ValueError("Department name is required")
        if department_exists(code):
            raise ValueError(f"Department with code '{code}' already exists")

    async def execute(self, command: Command) -> Result:
        dto = command.data
        dept = Department.create(
            code=dto["code"],
            name=dto["name"],
            description=dto.get("description", ""),
            display_order=dto.get("display_order", 0),
        )
        save_department(dept)
        return Result.ok(data={"department": dept.to_dict()}, message=f"Department '{dept.name}' created")


class UpdateDepartmentUseCase(BaseUseCase):
    """Update an existing department."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        code = command.data.get("code", "").strip()
        if not code:
            raise ValueError("Department code is required")
        if not department_exists(code):
            raise ValueError(f"Department with code '{code}' not found")

    async def execute(self, command: Command) -> Result:
        dto = command.data
        code = dto["code"]
        dept = get_department_by_code(code)
        if not dept:
            return Result.fail(error=f"Department '{code}' not found")

        dept.update(
            name=dto.get("name"),
            description=dto.get("description"),
            is_active=dto.get("is_active"),
            display_order=dto.get("display_order"),
        )
        save_department(dept)
        return Result.ok(data={"department": dept.to_dict()}, message=f"Department '{dept.name}' updated")


class DeleteDepartmentUseCase(BaseUseCase):
    """Delete a department by code."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        code = command.data.get("code", "").strip()
        if not code:
            raise ValueError("Department code is required")
        if not department_exists(code):
            raise ValueError(f"Department with code '{code}' not found")

    async def execute(self, command: Command) -> Result:
        code = command.data["code"]
        deleted = delete_department(code)
        if deleted:
            return Result.ok(data={}, message=f"Department '{code}' deleted")
        return Result.fail(error=f"Failed to delete department '{code}'")
