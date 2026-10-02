"""Use cases for Service CRUD operations.

Provides list, create, update, delete, and reset-to-defaults use cases.
Each follows the Command → Result pattern.
"""

from __future__ import annotations

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.domain.clinic.entities.service import Service
from src.infrastructure.clinic.department_provider import (
    department_exists,
    get_all_services,
    get_services_by_department,
    get_active_services_by_department,
    get_service_by_code,
    save_service,
    delete_service,
    service_exists,
    reset_to_defaults,
    get_service_map,
)


class ListServicesUseCase(BaseUseCase):
    """List services, optionally filtered by department."""

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        dto = command.data
        department_code = dto.get("department_code", "").strip()
        active_only = dto.get("active_only", False)

        if department_code:
            if active_only:
                services = get_active_services_by_department(department_code)
            else:
                services = get_services_by_department(department_code)
        else:
            services = get_all_services()
            if active_only:
                services = [s for s in services if s.is_active]

        return Result.ok(data={
            "services": [s.to_dict() for s in services],
            "total": len(services),
        })


class CreateServiceUseCase(BaseUseCase):
    """Create a new service."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        dto = command.data
        code = dto.get("code", "").strip()
        display_name = dto.get("display_name", "").strip()
        dept_code = dto.get("department_code", "").strip()

        if not code:
            raise ValueError("Service code is required")
        if not display_name:
            raise ValueError("Service display name is required")
        if not dept_code:
            raise ValueError("Department code is required")
        if not department_exists(dept_code):
            raise ValueError(f"Department with code '{dept_code}' not found")
        if service_exists(code):
            raise ValueError(f"Service with code '{code}' already exists")

    async def execute(self, command: Command) -> Result:
        dto = command.data
        service = Service.create(
            code=dto["code"],
            display_name=dto["display_name"],
            department_code=dto["department_code"],
            room_name=dto.get("room_name", ""),
            avg_test_time=dto.get("avg_test_time", 10),
        )
        save_service(service)
        return Result.ok(data={"service": service.to_dict()}, message=f"Service '{service.display_name}' created")


class UpdateServiceUseCase(BaseUseCase):
    """Update an existing service."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        code = command.data.get("code", "").strip()
        if not code:
            raise ValueError("Service code is required")
        if not service_exists(code):
            raise ValueError(f"Service with code '{code}' not found")

    async def execute(self, command: Command) -> Result:
        dto = command.data
        code = dto["code"]
        service = get_service_by_code(code)
        if not service:
            return Result.fail(error=f"Service '{code}' not found")

        # If department_code is being changed, validate it exists
        new_dept = dto.get("department_code")
        if new_dept and not department_exists(new_dept):
            return Result.fail(error=f"Department with code '{new_dept}' not found")

        service.update(
            display_name=dto.get("display_name"),
            room_name=dto.get("room_name"),
            avg_test_time=dto.get("avg_test_time"),
            is_active=dto.get("is_active"),
        )
        if new_dept:
            service.department_code = new_dept

        save_service(service)
        return Result.ok(data={"service": service.to_dict()}, message=f"Service '{service.display_name}' updated")


class DeleteServiceUseCase(BaseUseCase):
    """Delete a service by code."""

    async def authorize(self, command: Command) -> None:
        pass

    async def validate(self, command: Command) -> None:
        code = command.data.get("code", "").strip()
        if not code:
            raise ValueError("Service code is required")
        if not service_exists(code):
            raise ValueError(f"Service with code '{code}' not found")

    async def execute(self, command: Command) -> Result:
        code = command.data["code"]
        deleted = delete_service(code)
        if deleted:
            return Result.ok(data={}, message=f"Service '{code}' deleted")
        return Result.fail(error=f"Failed to delete service '{code}'")


class ResetServicesUseCase(BaseUseCase):
    """Reset departments and services to factory defaults."""

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        reset_to_defaults()
        return Result.ok(
            data={
                "departments": [d.to_dict() for d in get_all_services()],
                "message": "Reset to defaults",
            },
            message="Departments and services reset to default values",
        )


class GetServiceMapUseCase(BaseUseCase):
    """Return a service_code → Service dict for replacing hardcoded lookups."""

    async def authorize(self, command: Command) -> None:
        pass

    async def execute(self, command: Command) -> Result:
        smap = get_service_map()
        return Result.ok(data={
            "services": {k: v.to_dict() for k, v in smap.items()},
        })
