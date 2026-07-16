"""DI container for the Identity Engine.

Central registry for all infrastructure dependencies.
Provides a single import point for use cases, services, and repositories.

Usage:
    from src.presentation.identity.dependencies.container import IdentityContainer

    container = IdentityContainer()
    use_case = container.auth_with_pin_use_case()
"""

from __future__ import annotations

from src.infrastructure.identity.services import (
    BcryptPinHasher,
    JwtTokenService,
    OtpGeneratorService,
)

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
from src.application.identity.use_cases.change_pin_use_case import ChangePinUseCase
from src.application.identity.use_cases.request_otp_use_case import RequestOtpUseCase
from src.application.identity.use_cases.verify_otp_use_case import VerifyOtpUseCase


class IdentityContainer:
    """Simple DI container for the Identity Engine.

    Creates and caches service instances. Use case factories accept
    a unit of work at call time (since UoW is request-scoped).
    """

    def __init__(self) -> None:
        self._pin_hasher: BcryptPinHasher | None = None
        self._token_service: JwtTokenService | None = None
        self._otp_service: OtpGeneratorService | None = None

    @property
    def pin_hasher(self) -> BcryptPinHasher:
        if self._pin_hasher is None:
            self._pin_hasher = BcryptPinHasher()
        return self._pin_hasher

    @property
    def token_service(self) -> JwtTokenService:
        if self._token_service is None:
            self._token_service = JwtTokenService()
        return self._token_service

    @property
    def otp_service(self) -> OtpGeneratorService:
        if self._otp_service is None:
            self._otp_service = OtpGeneratorService()
        return self._otp_service

    def auth_with_pin_use_case(self, uow) -> AuthenticateWithPinUseCase:
        return AuthenticateWithPinUseCase(
            unit_of_work=uow,
            pin_hasher=self.pin_hasher,
            token_service=self.token_service,
        )

    def auth_with_password_use_case(self, uow) -> AuthenticateWithPasswordUseCase:
        return AuthenticateWithPasswordUseCase(
            unit_of_work=uow,
            pin_hasher=self.pin_hasher,
            token_service=self.token_service,
        )

    def refresh_token_use_case(self, uow) -> RefreshTokenUseCase:
        return RefreshTokenUseCase(
            unit_of_work=uow,
            token_service=self.token_service,
        )

    def logout_use_case(self, uow) -> LogoutUseCase:
        return LogoutUseCase(unit_of_work=uow)

    def change_pin_use_case(self, uow) -> ChangePinUseCase:
        return ChangePinUseCase(
            unit_of_work=uow,
            pin_hasher=self.pin_hasher,
        )

    def request_otp_use_case(self, uow) -> RequestOtpUseCase:
        return RequestOtpUseCase(
            unit_of_work=uow,
            otp_service=self.otp_service,
        )

    def verify_otp_use_case(self, uow) -> VerifyOtpUseCase:
        return VerifyOtpUseCase(
            unit_of_work=uow,
            otp_service=self.otp_service,
        )


# Singleton container
container = IdentityContainer()
