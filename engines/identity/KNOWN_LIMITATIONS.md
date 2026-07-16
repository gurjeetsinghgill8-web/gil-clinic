# Identity Engine — Known Limitations

**Last Updated: 2026-07-12**

---

## Domain Layer

| # | Limitation | Impact | Planned Fix |
|---|---|---|---|
| 1 | **No MFA support** | Currently supports PIN/password + OTP but not true multi-factor authentication (MFA requires two different auth methods simultaneously) | Future: `MfaPolicy` + `MfaFlowUseCase` |
| 2 | **No password expiry policy** | Passwords don't expire or require rotation | Future: `PasswordExpiryPolicy` with configurable duration |
| 3 | **No brute-force detection** | Lockout is per-user only; no global IP-based or distributed brute-force detection | Future: `BruteForceDetector` using Redis counters |
| 4 | **SessionPolicy hardcoded limits** | Max 10 concurrent sessions, 24-hour default duration are constants, not configurable | Future: Config-driven policies from app settings |
| 5 | **Role hierarchy hardcoded levels** | Hierarchy levels are seed data, not dynamically configurable | Acceptable for current scope |

## Application Layer

| # | Limitation | Impact | Planned Fix |
|---|---|---|---|
| 6 | **No Queries implemented** | Only Commands exist; read-side (GetUserQuery, ListUsersQuery, GetSessionsQuery) not yet built | Phase when read models are needed |
| 7 | **No Authorization framework** | `authorize()` is a pass-through in most use cases; no role/permission check middleware | Phase when RBAC is wired |
| 8 | **No audit trail** | Events are published but not persisted for audit | Phase 16.5 (Observability) |
| 9 | **No rate limiting** | OTP requests, login attempts not throttled at application layer | Future: `RateLimiter` port |
| 10 | **7 stale skeleton files** | `create_user_use_case.py`, `deactivate_user_use_case.py`, etc. are empty stubs | Implement when feature is needed |

## Infrastructure Layer (not yet built)

| # | Limitation | Impact | Planned Fix |
|---|---|---|---|
| 11 | **No SQLAlchemy repositories** | Domain entities cannot be persisted | Phase 16.1 |
| 12 | **No JWT implementation** | `TokenService` protocol has no implementation | Phase 16.2 |
| 13 | **No PIN hashing** | `PinHasher` protocol has no implementation | Phase 16.2 |
| 14 | **No OTP provider** | `OtpService` protocol generates but doesn't deliver | Phase 16.3 |
| 15 | **No outbox relay** | Events are published in-process, not via outbox table | Phase 16.4 |
| 16 | **No Redis pub/sub** | Cross-engine event distribution not wired | Phase 16.4 |
| 17 | **No retry/DLQ** | Failed event publishing has no retry mechanism | Phase 16.4 |
| 18 | **No monitoring** | No metrics, tracing, or health checks | Phase 16.5 |
| 19 | **No secrets management** | `GHOS_ENCRYPTION_KEY` read from env var directly | Future: Vault/HashiCorp integration |

## Security

| # | Limitation | Impact | Planned Fix |
|---|---|---|---|
| 20 | **No session hijacking detection** | IP/user-agent changes on same session not flagged | Future: `SessionHijackingDetector` |
| 21 | **No device fingerprinting** | Device ID is client-provided, not derived | Future: Fingerprint computation in DeviceInfo |
| 22 | **No concurrent session alerts** | Same credentials used from multiple locations not alerted | Future: `ConcurrentLoginDetector` |

## Cross-Engine

| # | Limitation | Impact | Planned Fix |
|---|---|---|---|
| 23 | **Other engines not consuming Identity events** | Patient, Queue, Billing engines don't listen to IDENTITY.* events yet | When those engines are built |
| 24 | **No SSO / OAuth** | No external identity provider integration | Future scope |
