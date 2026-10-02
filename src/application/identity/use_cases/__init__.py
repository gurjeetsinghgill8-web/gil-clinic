"""Identity Engine application use cases.

Every use case follows the same pattern:
1. Input DTO → 2. Validator → 3. Authorization → 4. Repository → 5. Domain Aggregate
→ 6. Policies → 7. Domain Events → 8. Commit (UnitOfWork) → 9. Return DTO
"""

from src.application.identity.use_cases.authenticate_with_pin_use_case import (
    AuthenticateWithPinUseCase,
)
from src.application.identity.use_cases.authenticate_with_password_use_case import (
    AuthenticateWithPasswordUseCase,
)
from src.application.identity.use_cases.refresh_token_use_case import (
    RefreshTokenUseCase,
)
from src.application.identity.use_cases.logout_use_case import LogoutUseCase
from src.application.identity.use_cases.request_otp_use_case import (
    RequestOtpUseCase,
)
from src.application.identity.use_cases.verify_otp_use_case import (
    VerifyOtpUseCase,
)
from src.application.identity.use_cases.change_pin_use_case import (
    ChangePinUseCase,
)
from src.application.identity.use_cases.unlock_account_use_case import (
    UnlockAccountUseCase,
)
from src.application.identity.use_cases.assign_role_use_case import (
    AssignRoleUseCase,
)

__all__ = [
    "AuthenticateWithPinUseCase",
    "AuthenticateWithPasswordUseCase",
    "RefreshTokenUseCase",
    "LogoutUseCase",
    "RequestOtpUseCase",
    "VerifyOtpUseCase",
    "ChangePinUseCase",
    "UnlockAccountUseCase",
    "AssignRoleUseCase",
]
