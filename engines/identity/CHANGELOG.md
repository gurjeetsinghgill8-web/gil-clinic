# Identity Engine — Changelog

All notable changes to the Identity Engine are documented here.

---

## [1.0.0] — 2026-07-12

### Added

#### Domain Layer (30 files)
- **Entities**: User, Session, RefreshToken, Role — 4 aggregate roots with full business logic
  - User: PIN/password auth, lockout (5 attempts, 30 min), role assignment
  - Session: Multi-device tracking, expiry, device trust, revocation
  - RefreshToken: Token rotation with theft detection (all tokens revoked on reuse)
  - Role: Hierarchy-based authorization, wildcard permission matching
- **Value Objects**: Permission, DeviceInfo, LockoutResult, OtpCode
- **Policies**: LockoutPolicy, SessionPolicy
- **Services**: AuthenticationDomainService (PIN/OTP format validation, hierarchy checks)
- **Events**: 19 IdentityEvent types (IDENTITY.*) following CloudEvents 1.0
- **Exceptions**: 11 DomainError classes (IDENTITY_001 through IDENTITY_011) with bilingual messages
- **Ports**: 9 Protocol interfaces (UserRepository, SessionRepository, RefreshTokenRepository, RoleRepository, OtpRepository, PinHasher, TokenService, OtpService, EventPublisher)

#### Application Layer (32 files)
- **Common**: BaseUseCase, Command/Query markers, Result type, BaseValidator, 6 typed exceptions, Pagination, TransactionManager
- **Use Cases**: 9 implemented command handlers
  - AuthenticateWithPinUseCase
  - AuthenticateWithPasswordUseCase
  - RefreshTokenUseCase
  - LogoutUseCase
  - RequestOtpUseCase
  - VerifyOtpUseCase
  - ChangePinUseCase
  - UnlockAccountUseCase
  - AssignRoleUseCase
- **DTOs**: 18 frozen dataclasses (10 request, 8 response)
- **Interfaces**: IdentityUnitOfWork protocol

#### Infrastructure Layer (pending)
- SQLAlchemy models for all 7 identity tables (user_model.py, session_model.py, refresh_token_model.py, role_model.py, permission_model.py, otp_code_model.py, outbox_model.py)
- AES-256-GCM encryption utility
- CleanupService for ephemeral data
- Alembic migration (revision 001) with 16 indexes, 3 CHECK constraints, seed data

### Architecture Decisions

- **Clean Architecture**: Domain → Application → Infrastructure → Presentation
- **DDD with 3 separate aggregates**: User, Session, RefreshToken are independent
- **Events-only communication**: Identity publishes events, never calls other engines
- **CQRS**: Commands (mutations) and Queries (reads) are separate pathways
- **Result type**: Rust-style Ok/Error for predictable error handling
- **Frozen DTOs**: All data carriers are immutable
- **Application Service pattern**: Each use case follows validate → authorize → execute → events → respond
- **Engine freeze**: No further changes to Identity without ADR
