# IDN-14 Refactor Report — AuthenticationService → Application Layer

## Summary

**Problem:** `AuthenticationService` in `src/domain/identity/services/` contained orchestration logic (repository calls, session creation, event publishing) that belongs in the Application Layer.

**Fix:** Stripped all orchestration from the domain service. Moved it into 9 use cases in the Application Layer. Created shared base classes in `src/application/common/` for reuse across all 13 engines.

---

## What Changed

### 1. Domain Layer — Stripped (30 files → 30 files, no change in count)

**Before:** `AuthenticationService` had 6 methods with repository calls, event publishing, token creation:
- `login_with_pin()` — called repos, created sessions, published events ✅ MOVED
- `login_with_password()` — same pattern ✅ MOVED
- `refresh_token()` — theft detection + rotation ✅ MOVED
- `logout()` — session/token revocation ✅ MOVED
- `request_otp()` / `verify_otp()` — OTP lifecycle ✅ MOVED
- `change_pin()` / `unlock_account()` — account management ✅ MOVED

**After:** `AuthenticationDomainService` contains ONLY pure domain rules:
- `validate_pin_format()` — PIN pattern validation (4-6 digits)
- `validate_otp_format()` — OTP pattern validation (6 digits)
- `can_role_manage_role()` — hierarchy level comparison
- `get_session_limit_info()` — session count evaluation

No repositories. No event publishers. No side effects. Pure domain.

### 2. Application Layer — Created (32 new/updated files)

#### `src/application/common/` — Shared base classes (9 files)

| File | Purpose |
|---|---|
| `__init__.py` | Public API with all exports |
| `base_use_case.py` | Abstract `BaseUseCase` with authorize → validate → execute → commit → events lifecycle |
| `command.py` | `Command` and `Query` CQRS marker dataclasses |
| `handler.py` | `CommandHandler` / `QueryHandler` Protocol interfaces |
| `validator.py` | `BaseValidator` + `ValidationResult` for input validation |
| `result.py` | `Result` type (Rust-style Ok/Error pattern) with `.ok()`, `.fail()`, `.is_ok`, `.value` |
| `exceptions.py` | `ApplicationException` + `ValidationError`, `NotFoundError`, `ConflictError`, `UnauthorizedError`, `ForbiddenError`, `InternalError` |
| `pagination.py` | `Pagination` value object with page/total/has_next calculation |
| `transaction.py` | `TransactionManager` Protocol for UoW commit abstraction |

#### `src/application/identity/` — Identity Engine Application Layer (23 files)

| Layer | Files | Description |
|---|---|---|
| `use_cases/` | 10 | 9 use case classes + `__init__.py` |
| `dtos/` | 4 | Request DTOs (10), Response DTOs (8) + `__init__.py` |
| `interfaces/` | 3 | `IdentityUnitOfWork` Protocol + `__init__.py` |
| Root | 2 | `__init__.py` with full public API |

#### 9 Use Cases Created

| Use Case | Input DTO | Output DTO | Key Orchestration |
|---|---|---|---|
| `AuthenticateWithPinUseCase` | `AuthenticateWithPinRequest` | `AuthenticateResponse` | PIN login, lockout check, session creation, token rotation, event publish |
| `AuthenticateWithPasswordUseCase` | `AuthenticateWithPasswordRequest` | `AuthenticateResponse` | Password login (same pattern) |
| `RefreshTokenUseCase` | `RefreshTokenRequest` | `TokenRefreshResponse` | Theft detection, token rotation, all-session revocation on theft |
| `LogoutUseCase` | `LogoutRequest` | `LogoutResponse` | Single/all session revocation + token cleanup |
| `RequestOtpUseCase` | `RequestOtpRequest` | `OtpResponse` | OTP generation, old OTP invalidation, event publish |
| `VerifyOtpUseCase` | `VerifyOtpRequest` | `OtpVerifiedResponse` | OTP verify with expiry/attempts checks |
| `ChangePinUseCase` | `ChangePinRequest` | `PinChangedResponse` | Old PIN verification, new PIN set, other sessions revoked |
| `UnlockAccountUseCase` | `UnlockAccountRequest` | `AccountUnlockedResponse` | User unlock + event publish |
| `AssignRoleUseCase` | `AssignRoleRequest` | `RoleAssignedResponse` | Actor authorization, role lookup, hierarchy check, role change |

---

## Architecture Before vs After

### Before (Violation)

```
Domain Layer
└── AuthenticationService  ← ORCHESTRATION (wrong layer!)
    ├── login_with_pin()    ← calls repos, creates entities, publishes events
    ├── login_with_password()
    ├── refresh_token()
    ├── logout()
    └── ...
```

### After (Clean Architecture)

```
Domain Layer                          (30 files — pure business rules)
├── entities/                         User, Session, RefreshToken, Role
├── value_objects/                    Permission, DeviceInfo, LockoutResult, OtpCode
├── policies/                         LockoutPolicy, SessionPolicy
├── services/
│   └── AuthenticationDomainService   ← ONLY validate_pin_format, hierarchy checks
├── events/                           19 event helpers
├── exceptions/                       11 DomainError classes
└── ports/                            9 Protocol interfaces

Application Layer                     (32 files — orchestration)
├── common/                           ← SHARED across all 13 engines
│   ├── base_use_case.py             BaseUseCase with lifecycle hooks
│   ├── command.py                   Command / Query markers
│   ├── result.py                    Ok/Error Result type
│   ├── validator.py                 BaseValidator + ValidationResult
│   ├── exceptions.py                6 typed app exceptions
│   ├── pagination.py                Pagination value object
│   └── transaction.py               TransactionManager Protocol
│
└── identity/
    ├── use_cases/                    9 use cases (full orchestration)
    ├── dtos/                         18 DTOs (10 request + 8 response)
    └── interfaces/                   IdentityUnitOfWork Protocol
```

---

## Every Use Case Pattern

```
Input DTO
    ↓
Validator (validate input format)
    ↓
Authorize (check caller permissions)
    ↓
Repository (load aggregates)
    ↓
Domain Aggregate (business logic)
    ↓
Policies (lockout, session limits)
    ↓
Repository (save aggregates)
    ↓
Event Publisher (emit domain events)
    ↓
UnitOfWork (commit transaction)
    ↓
Return Result<OutputDTO>
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **`BaseUseCase` with template method** | Consistent lifecycle across all engines: authorize → validate → execute → post_execute → error_handle |
| **`Result` type instead of exceptions** | Functional error handling. Use cases return `Result.ok(data)` or `Result.fail(error, code)`. No try/catch for expected failures |
| **`Command.data` for input** | Each use case receives a `Command` wrapping a typed DTO. Enables metadata (trace IDs, correlation IDs) alongside business data |
| **`IdentityUnitOfWork` Protocol** | Every use case gets a unit of work with repository accessors + commit(). Infrastructure provides `SqlAlchemyIdentityUnitOfWork` |
| **Separate use cases (not one big service)** | Each authentication flow is a single-responsibility command handler. Easy to test, easy to evolve, easy to replace |
| **`ApplicationException` hierarchy** | 6 typed exceptions with machine-readable codes + HTTP status codes. Caught by framework layer and mapped to API responses |
| **DTOs frozen everywhere** | All DTOs are frozen dataclasses — immutable data carriers. No business logic in DTOs |

---

## Verification

✅ All 62 Python files compile cleanly (AST syntax check)
✅ Domain layer: 30 files (pure business rules only)
✅ Application layer: 32 files (orchestration + DTOs + interfaces)
✅ No circular imports
✅ All `__init__.py` files export public APIs

---

## IDN-15 Readiness

The Identity Engine application layer is ready for the remaining use cases:

Still needed:
- `CreateUserUseCase` (skeleton exists)
- `UpdateUserUseCase` (skeleton exists)
- `DeactivateUserUseCase` (skeleton exists)
- `ReactivateUserUseCase` (skeleton exists)
- `RevokeSessionUseCase` (skeleton exists)
- `ResetPinUseCase` (skeleton exists)
- `GetUserQuery` (read-only, Query handler)
- `ListUsersQuery` (read-only, Query handler with Pagination)

These can be generated in IDN-15.
