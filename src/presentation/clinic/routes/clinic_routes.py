"""Clinic Engine — FastAPI routes.

API Contract:
    GET  /api/v1/clinic/settings          →  Current clinic settings
    PUT  /api/v1/clinic/settings          ←  Update partial settings
    GET  /api/v1/clinic/departments       →  List departments
    POST /api/v1/clinic/departments       ←  Create department
    PUT  /api/v1/clinic/departments/{code}←  Update department
    DELETE /api/v1/clinic/departments/{code}
    GET  /api/v1/clinic/services          →  List services (?department_code=)
    POST /api/v1/clinic/services          ←  Create service
    PUT  /api/v1/clinic/services/{code}   ←  Update service
    DELETE /api/v1/clinic/services/{code}
    POST /api/v1/clinic/services/reset    →  Reset to defaults
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.application.common.command import Command
from src.presentation.clinic.schemas.clinic_schemas import (
    ClinicSettingsResponse,
    ClinicSettingsUpdateRequest,
    ClinicSettingsUpdateResponse,
    DepartmentCreateRequest,
    DepartmentDeleteResponse,
    DepartmentListResponse,
    DepartmentResponse,
    DepartmentSingleResponse,
    DepartmentUpdateRequest,
    ServiceCreateRequest,
    ServiceDeleteResponse,
    ServiceListResponse,
    ServiceResponse,
    ServiceSingleResponse,
    ServiceUpdateRequest,
)
from src.presentation.clinic.dependencies.clinic_dependencies import (
    get_clinic_settings_use_case,
    get_update_clinic_settings_use_case,
)

router = APIRouter(prefix="/api/v1/clinic", tags=["Clinic"])


@router.get(
    "/settings",
    response_model=ClinicSettingsResponse,
    summary="Get current clinic settings",
)
async def get_settings(
    use_case=Depends(get_clinic_settings_use_case),
):
    """Get the current clinic branding and contact settings.

    Returns all settings fields. This is a public endpoint.
    """
    command = Command(data={})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result.error),
        )

    return ClinicSettingsResponse(**result.data)


@router.put(
    "/settings",
    response_model=ClinicSettingsUpdateResponse,
    summary="Update clinic settings",
)
async def update_settings(
    request: ClinicSettingsUpdateRequest,
    use_case=Depends(get_update_clinic_settings_use_case),
):
    """Update clinic branding and contact information.

    Only provided fields are updated. Returns the complete updated settings.
    Requires admin authorization (via middleware).
    """
    # Filter out None values
    overrides = request.model_dump(exclude_none=True)
    command = Command(data=overrides)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )

    return ClinicSettingsUpdateResponse(
        message=result.message or "Clinic settings updated",
        settings=ClinicSettingsResponse(**result.data),
    )


# =============================================================================
# Department Routes
# =============================================================================


@router.get(
    "/departments",
    response_model=DepartmentListResponse,
    summary="List all departments",
)
async def list_departments(
    active_only: bool = Query(default=False, description="Only return active departments"),
):
    """List all departments, optionally filtered to active only."""
    from src.application.clinic.use_cases.department_use_cases import ListDepartmentsUseCase

    use_case = ListDepartmentsUseCase()
    command = Command(data={"active_only": active_only})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result.error),
        )
    return DepartmentListResponse(**result.data)


@router.post(
    "/departments",
    response_model=DepartmentSingleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new department",
)
async def create_department(request: DepartmentCreateRequest):
    """Create a new department with the given code and name."""
    from src.application.clinic.use_cases.department_use_cases import CreateDepartmentUseCase

    use_case = CreateDepartmentUseCase()
    command = Command(data=request.model_dump())
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return DepartmentSingleResponse(
        department=DepartmentResponse(**result.data["department"]),
        message=result.message or "Department created",
    )


@router.put(
    "/departments/{code}",
    response_model=DepartmentSingleResponse,
    summary="Update a department",
)
async def update_department(code: str, request: DepartmentUpdateRequest):
    """Update an existing department by its code."""
    from src.application.clinic.use_cases.department_use_cases import UpdateDepartmentUseCase

    use_case = UpdateDepartmentUseCase()
    data = request.model_dump(exclude_none=True)
    data["code"] = code
    command = Command(data=data)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return DepartmentSingleResponse(
        department=DepartmentResponse(**result.data["department"]),
        message=result.message or "Department updated",
    )


@router.delete(
    "/departments/{code}",
    response_model=DepartmentDeleteResponse,
    summary="Delete a department",
)
async def delete_department(code: str):
    """Delete a department by its code."""
    from src.application.clinic.use_cases.department_use_cases import DeleteDepartmentUseCase

    use_case = DeleteDepartmentUseCase()
    command = Command(data={"code": code})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return DepartmentDeleteResponse(message=result.message or "Department deleted")


# =============================================================================
# Service Routes
# =============================================================================


@router.get(
    "/services",
    response_model=ServiceListResponse,
    summary="List all services",
)
async def list_services(
    department_code: str | None = Query(default=None, description="Filter by department code"),
    active_only: bool = Query(default=False, description="Only return active services"),
):
    """List all services, optionally filtered by department."""
    from src.application.clinic.use_cases.service_use_cases import ListServicesUseCase

    use_case = ListServicesUseCase()
    command = Command(data={
        "department_code": department_code or "",
        "active_only": active_only,
    })
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result.error),
        )
    return ServiceListResponse(**result.data)


@router.post(
    "/services",
    response_model=ServiceSingleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service",
)
async def create_service(request: ServiceCreateRequest):
    """Create a new service/test type under a department."""
    from src.application.clinic.use_cases.service_use_cases import CreateServiceUseCase

    use_case = CreateServiceUseCase()
    command = Command(data=request.model_dump())
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return ServiceSingleResponse(
        service=ServiceResponse(**result.data["service"]),
        message=result.message or "Service created",
    )


@router.put(
    "/services/{code}",
    response_model=ServiceSingleResponse,
    summary="Update a service",
)
async def update_service(code: str, request: ServiceUpdateRequest):
    """Update an existing service by its code."""
    from src.application.clinic.use_cases.service_use_cases import UpdateServiceUseCase

    use_case = UpdateServiceUseCase()
    data = request.model_dump(exclude_none=True)
    data["code"] = code
    command = Command(data=data)
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return ServiceSingleResponse(
        service=ServiceResponse(**result.data["service"]),
        message=result.message or "Service updated",
    )


@router.delete(
    "/services/{code}",
    response_model=ServiceDeleteResponse,
    summary="Delete a service",
)
async def delete_service(code: str):
    """Delete a service by its code."""
    from src.application.clinic.use_cases.service_use_cases import DeleteServiceUseCase

    use_case = DeleteServiceUseCase()
    command = Command(data={"code": code})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.error),
        )
    return ServiceDeleteResponse(message=result.message or "Service deleted")


@router.post(
    "/services/reset",
    response_model=ServiceDeleteResponse,
    summary="Reset services to factory defaults",
)
async def reset_services():
    """Reset all departments and services to the hardcoded defaults."""
    from src.application.clinic.use_cases.service_use_cases import ResetServicesUseCase

    use_case = ResetServicesUseCase()
    command = Command(data={})
    result = await use_case.run(command)

    if result.is_fail:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(result.error),
        )
    return ServiceDeleteResponse(message=result.message or "Reset to defaults")
