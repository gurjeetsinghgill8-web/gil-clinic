"""FastAPI dependency injection: use cases, repositories, UoW.

Provides FastAPI dependency callables that wire up use cases with
their infrastructure dependencies.

Usage:
    @router.post("/login")
    async def login(
        request: AuthenticateWithPinRequest,
        use_case: AuthenticateWithPinUseCase = Depends(get_auth_with_pin_use_case),
    ):
        ...
"""

from src.presentation.identity.dependencies.use_case_dependencies import (
    get_auth_with_pin_use_case,
    get_auth_with_password_use_case,
    get_refresh_token_use_case,
    get_logout_use_case,
    get_change_pin_use_case,
    get_request_otp_use_case,
    get_verify_otp_use_case,
    get_assign_role_use_case,
    get_unlock_account_use_case,
    get_user_repository,
    get_session_repository,
    get_unit_of_work,
)

__all__ = [
    "get_auth_with_pin_use_case",
    "get_auth_with_password_use_case",
    "get_refresh_token_use_case",
    "get_logout_use_case",
    "get_change_pin_use_case",
    "get_request_otp_use_case",
    "get_verify_otp_use_case",
    "get_assign_role_use_case",
    "get_unlock_account_use_case",
    "get_user_repository",
    "get_session_repository",
    "get_unit_of_work",
]
