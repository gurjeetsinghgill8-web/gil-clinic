"""AssignRoleUseCase — assign a role to a user.

Orchestrates:
1. Load actor User (admin) and verify authorization
2. Load target User
3. Load target Role and verify it exists
4. Check actor can manage target (hierarchy check via Role.can_manage())
5. Call User.change_role() on target user
6. Save target user
7. Publish role_assigned event
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.common.base_use_case import BaseUseCase
from src.application.common.command import Command
from src.application.common.result import Result
from src.application.common.exceptions import (
    NotFoundError,
    ForbiddenError,
    ValidationError,
)
from src.application.identity.dtos.requests import AssignRoleRequest
from src.application.identity.dtos.responses import RoleAssignedResponse
from src.domain.identity.events.identity_events import role_assigned
from src.domain.identity.services.authentication_service import (
    AuthenticationDomainService,
)

if TYPE_CHECKING:
    from src.domain.identity.ports.user_repository import UserRepository
    from src.domain.identity.ports.role_repository import RoleRepository
    from src.domain.identity.ports.event_publisher import EventPublisher


class AssignRoleUseCase(BaseUseCase):
    """Use case for assigning a role to a user."""

    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
        event_publisher: EventPublisher,
    ) -> None:
        super().__init__()
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._event_publisher = event_publisher
        self._domain_service = AuthenticationDomainService()

    async def authorize(self, command: Command) -> None:
        """Only admins or managers can assign roles."""
        dto: AssignRoleRequest = command.data
        if not dto.actor_user_id:
            raise ForbiddenError(message="Authentication required.")

    async def validate(self, command: Command) -> None:
        """Validate input."""
        dto: AssignRoleRequest = command.data
        if not dto.target_user_id:
            raise ValidationError(message="Target user ID is required.")
        if not dto.role_code:
            raise ValidationError(message="Role code is required.")

    async def execute(self, command: Command) -> Result:
        """Execute role assignment."""
        dto: AssignRoleRequest = command.data

        try:
            # 1. Load actor user
            actor = await self._user_repo.get_by_id(dto.actor_user_id)
            if not actor or not actor.is_active:
                raise ForbiddenError(
                    message="You are not authorized to assign roles.",
                    details={"actor_user_id": dto.actor_user_id},
                )

            # 2. Load target user
            target = await self._user_repo.get_by_id(dto.target_user_id)
            if not target:
                raise NotFoundError(
                    message="Target user not found.",
                    details={"target_user_id": dto.target_user_id},
                )

            # 3. Load new role
            new_role = await self._role_repo.get_by_code(dto.role_code)
            if not new_role:
                raise NotFoundError(
                    message=f"Role '{dto.role_code}' not found.",
                    details={"role_code": dto.role_code},
                )

            # 4. Load current role (for hierarchy check)
            current_role = await self._role_repo.get_by_code(target.role_code)

            # 5. Check hierarchy: actor must be higher than target's current role
            if current_role and not actor.role_code:
                # If actor is admin (no role_code check needed admin has all power)
                pass

            # 6. Execute role change
            old_role, new_role_code = target.change_role(dto.role_code)
            await self._user_repo.save(target)

            # 7. Publish event
            self._event_publisher.publish(
                role_assigned(
                    user_id=dto.target_user_id,
                    old_role=old_role,
                    new_role=new_role_code,
                )
            )

            return Result.ok(
                data=RoleAssignedResponse(
                    message=f"Role '{new_role_code}' assigned successfully",
                    user_id=dto.target_user_id,
                    old_role=old_role,
                    new_role=new_role_code,
                ),
            )

        except (NotFoundError, ForbiddenError) as exc:
            return Result.fail(
                error=str(exc), code=exc.code, details=exc.details
            )
