# 009 — Identity Engine: Implementation Plan

*Step-by-step build order. Document-first, code-second.*

---

## 1. Build Order (Strict Sequence)

Each step produces a deliverable. Do NOT start the next step until the current one is reviewed and all tests pass.

| Step | Layer | What to Build | Deliverable | Dependencies |
|---|---|---|---|---|
| 1 | Domain | Entities: User, Session, RefreshToken, Role, Permission | `domain/identity/entities/` | None |
| 2 | Domain | Value Objects: OtpCode, DeviceInfo, LockoutResult | `domain/identity/value_objects/` | Step 1 |
| 3 | Domain | Ports: PinHasher, TokenService, OtpService, EventPublisher | `domain/identity/ports/` | Step 1 |
| 4 | Domain | Service: AuthenticationService | `domain/identity/services/` | Steps 1-3 |
| 5 | Domain | Tests: All domain unit tests | `tests/unit/identity/` | Steps 1-4 |
| 6 | Application | Use Cases: LoginUseCase, CreateUserUseCase, RevokeSessionUseCase | `application/identity/use_cases/` | Steps 1-4 |
| 7 | Application | DTOs: LoginRequest, CreateUserRequest, UserResponse | `application/identity/dtos/` | Steps 1-4 |
| 8 | Infrastructure | Repositories: SqlAlchemyUserRepo, SqlAlchemySessionRepo, etc. | `infrastructure/identity/repositories/` | Step 1, 6 |
| 9 | Infrastructure | Services: BcryptPinHasher, JwtTokenService, OtpGeneratorService | `infrastructure/identity/services/` | Step 3 |
| 10 | Infrastructure | Alembic migration for identity tables | `migrations/versions/` | DB schema from doc 002 |
| 11 | Infrastructure | Event publisher adapter (Redis outbox) | `infrastructure/identity/events/` | Step 3 |
| 12 | Infrastructure | Seed data script | `infrastructure/identity/seed.py` | Step 10 |
| 13 | Presentation | FastAPI routes: /auth/*, /users/*, /sessions/* | `presentation/identity/routes/` | Steps 6, 8, 9 |
| 14 | Presentation | Middleware: JWT auth middleware | `presentation/identity/middleware/` | Step 9 |
| 15 | Presentation | Exception handlers for all IDENTITY_* errors | `presentation/identity/errors/` | Error catalog |
| 16 | Integration | Tests for all API endpoints | `tests/integration/identity/` | Steps 13-15 |
| 17 | E2E | Full flow tests | `tests/e2e/identity/` | All steps |
| 18 | Review | Security review, penetration tests | Security checklist | All steps |

---

## 2. Folder Structure (to be created)

```
src/
├── domain/
│   └── identity/
│       ├── __init__.py
│       ├── entities/
│       │   ├── __init__.py
│       │   ├── user.py
│       │   ├── session.py
│       │   ├── refresh_token.py
│       │   └── role.py
│       ├── value_objects/
│       │   ├── __init__.py
│       │   ├── otp_code.py
│       │   ├── device_info.py
│       │   ├── permission.py
│       │   └── lockout_result.py
│       ├── ports/
│       │   ├── __init__.py
│       │   ├── pin_hasher.py
│       │   ├── token_service.py
│       │   ├── otp_service.py
│       │   └── event_publisher.py
│       └── services/
│           ├── __init__.py
│           └── authentication_service.py
│
├── application/
│   └── identity/
│       ├── __init__.py
│       ├── use_cases/
│       │   ├── __init__.py
│       │   ├── login_use_case.py
│       │   ├── create_user_use_case.py
│       │   ├── update_user_use_case.py
│       │   ├── deactivate_user_use_case.py
│       │   ├── revoke_session_use_case.py
│       │   ├── request_otp_use_case.py
│       │   └── verify_otp_use_case.py
│       └── dtos/
│           ├── __init__.py
│           ├── requests.py
│           └── responses.py
│
├── infrastructure/
│   └── identity/
│       ├── __init__.py
│       ├── repositories/
│       │   ├── __init__.py
│       │   ├── user_repository.py
│       │   ├── session_repository.py
│       │   ├── token_repository.py
│       │   └── role_repository.py
│       ├── services/
│       │   ├── __init__.py
│       │   ├── bcrypt_pin_hasher.py
│       │   ├── jwt_token_service.py
│       │   └── otp_generator_service.py
│       ├── events/
│       │   ├── __init__.py
│       │   ├── outbox_publisher.py
│       │   └── event_serializer.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── sqlalchemy_models.py
│       ├── seed.py
│       └── config.py
│
├── presentation/
│   └── identity/
│       ├── __init__.py
│       ├── routes/
│       │   ├── __init__.py
│       │   ├── auth_routes.py
│       │   ├── user_routes.py
│       │   ├── session_routes.py
│       │   └── role_routes.py
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── jwt_middleware.py
│       ├── errors/
│       │   ├── __init__.py
│       │   └── error_handlers.py
│       └── dependencies/
│           ├── __init__.py
│           └── container.py
│
└── tests/
    ├── unit/
    │   └── identity/
    │       ├── __init__.py
    │       ├── test_user.py
    │       ├── test_session.py
    │       ├── test_refresh_token.py
    │       ├── test_role.py
    │       └── test_authentication_service.py
    ├── integration/
    │   └── identity/
    │       ├── __init__.py
    │       ├── test_user_repository.py
    │       ├── test_auth_api.py
    │       └── test_user_api.py
    └── e2e/
        └── identity/
            ├── __init__.py
            ├── test_auth_flows.py
            └── test_admin_flows.py
```

---

## 3. Key Implementation Notes

### 3.1 Domain Layer (Steps 1-4)

- **NO imports** from application, infrastructure, or presentation
- **NO Pydantic** in domain — use plain dataclasses
- **ALL validation** in domain (PIN format, lockout logic)
- **ALL events** published from domain service, not from API layer
- **Ports** are Protocols (structural typing), not ABCs

### 3.2 Application Layer (Steps 6-7)

- Each use case = one class with `__call__` method
- Use cases call domain services, not repositories directly
- DTOs use Pydantic V2 for request/response validation
- Transaction management in use case (unit of work pattern)

### 3.3 Infrastructure Layer (Steps 8-11)

- SQLAlchemy models in separate file from domain entities
- Repository pattern: infrastructure models ↔ domain entities
- JWT signing in infrastructure only (domain never sees raw tokens)
- Outbox writer in same DB transaction as domain operation

### 3.4 Presentation Layer (Steps 13-15)

- FastAPI dependency injection for use cases
- JWT middleware validates token on every protected request
- Error handlers map DomainError → HTTP response with correct error code
- Rate limiting via middleware

---

## 4. Effort Estimate

| Step | Hours | Dependencies |
|---|---|---|
| 1. Domain entities | 3 | None |
| 2. Value objects | 1 | Step 1 |
| 3. Ports | 1 | Step 1 |
| 4. AuthenticationService | 4 | Steps 1-3 |
| 5. Unit tests | 3 | Steps 1-4 |
| 6. Use cases | 4 | Steps 1-4 |
| 7. DTOs | 1 | Steps 1-4 |
| 8. Repositories | 4 | Steps 1, 6 |
| 9. Infrastructure services | 3 | Step 3 |
| 10. Alembic migration | 1 | DB schema |
| 11. Event publisher | 2 | Step 3 |
| 12. Seed data | 1 | Step 10 |
| 13. API routes | 4 | Steps 6, 8, 9 |
| 14. JWT middleware | 2 | Step 9 |
| 15. Error handlers | 1 | Error catalog |
| 16. Integration tests | 2 | Steps 13-15 |
| 17. E2E tests | 2 | All |
| 18. Security review | 2 | All |
| **Total** | **41 hours** | |

---

## 5. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| bcrypt cost=12 too slow | Medium | Login latency | Test with real hardware first |
| Outbox + Redis = eventual consistency | Low | Stale user status | Max 1s delay, acceptable |
| JWT key rotation breaks sessions | Low | Logged-out staff | Grace period for old keys |
| Race condition on login_attempts | Medium | Over-lockout | Optimistic locking on User row |
| SQLAlchemy vs domain entity mismatch | Low | Bugs | Dedicated unit of work with mapping |
