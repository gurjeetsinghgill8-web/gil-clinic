# Identity Engine — Migration Guide

How to evolve the Identity Engine safely after freeze.

---

## Interface Changes Require an ADR

The following published interfaces are **frozen**:

```
Domain Events:    IDENTITY.USER.CREATED, IDENTITY.USER.LOGIN, IDENTITY.AUTH.FAILED, etc. (19 events)
Repository Ports: UserRepository, SessionRepository, RefreshTokenRepository, RoleRepository, OtpRepository
Service Ports:    PinHasher, TokenService, OtpService, EventPublisher
Use Case DTOs:    All 10 request DTOs + 8 response DTOs
Use Case Classes: 9 command handlers
```

Any change to these requires an **Architecture Decision Record (ADR)** filed in `docs/adr/`.

---

## How to Add a New Use Case

1. Create DTOs in `dtos/requests.py` and `dtos/responses.py`
2. Create use case in `use_cases/` following the existing pattern
3. Add to `use_cases/__init__.py` and `application/identity/__init__.py`
4. Update `CHANGELOG.md` (minor version bump)
5. Update `KNOWN_LIMITATIONS.md` if fixing a listed limitation

Use case template:

```python
class MyNewUseCase(BaseUseCase):
    async def validate(self, command: Command) -> None:
        ...

    async def execute(self, command: Command) -> Result:
        try:
            # 1. Load aggregates from repositories
            # 2. Call domain business logic
            # 3. Save aggregates
            # 4. Publish events
            return Result.ok(data=MyResponseDTO(...))
        except (NotFoundError, UnauthorizedError) as exc:
            return Result.fail(error=str(exc), code=exc.code)
```

---

## How to Add a New Event

1. Add event helper function in `domain/identity/events/identity_events.py`
2. Add to `events/__init__.py` exports
3. Update `VERSION.md` (minor bump)
4. Add ADR documenting the new event contract

---

## How to Add a New Domain Entity

1. Create entity in `domain/identity/entities/`
2. Add value objects in `domain/identity/value_objects/` if needed
3. Create repository port in `domain/identity/ports/`
4. Create SQLAlchemy model in `infrastructure/identity/models/`
5. Create Alembic migration
6. Create use case in `application/identity/use_cases/`
7. Update all `__init__.py` files
8. Update `VERSION.md` (minor bump)
9. Update `CHANGELOG.md`
10. Add ADR for the new aggregate boundary

---

## How to Fix a Bug (Patch)

1. Create a branch from the freeze point
2. Fix the bug (internal implementation only — no interface changes)
3. Run all checks (syntax, imports, sequence validation)
4. Update `CHANGELOG.md` (patch bump)
5. Create PR with reference to the tracked issue

---

## ADR Template

File: `docs/adr/ADR-XXX-description.md`

```markdown
# ADR-XXX: Title

## Status
Proposed | Accepted | Superseded

## Context
Why this change is needed.

## Decision
What changed and why.

## Consequences
Impact on Identity Engine and consuming engines.

## Interface Changes
List of changed/frozen interfaces.
```
