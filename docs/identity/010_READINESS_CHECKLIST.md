# 010 — Identity Engine: Readiness Checklist

*Before any code is written, ALL 9 design documents must be reviewed and approved.*
*Before moving to Patient Engine, ALL items below must be checked.*

---

## Phase 1: Design Review (Gate 1)

### All 10 Documents Reviewed and Approved

| # | Document | Status | Reviewer | Date |
|---|---|---|---|---|
| 001 | Functional Specification | [ ] PENDING | — | — |
| 002 | Database Design | [ ] PENDING | — | — |
| 003 | API Specification | [ ] PENDING | — | — |
| 004 | Domain Model | [ ] PENDING | — | — |
| 005 | Event Specification | [ ] PENDING | — | — |
| 006 | Sequence Diagrams | [ ] PENDING | — | — |
| 007 | Security Review | [ ] PENDING | — | — |
| 008 | Test Strategy | [ ] PENDING | — | — |
| 009 | Implementation Plan | [ ] PENDING | — | — |
| 010 | Readiness Checklist | [ ] PENDING | — | — |

**Gate rule:** All 10 documents must be [X] APPROVED before Phase 2 begins.

---

## Phase 2: Implementation (Gate 2)

### Domain Layer

| # | Item | Status |
|---|---|---|
| D-01 | User entity implemented | [ ] |
| D-02 | Session entity implemented (separate aggregate) | [ ] |
| D-03 | RefreshToken entity implemented (separate aggregate) | [ ] |
| D-04 | Role value object implemented | [ ] |
| D-05 | Permission value object implemented | [ ] |
| D-06 | DeviceInfo value object implemented | [ ] |
| D-07 | LockoutResult value object implemented | [ ] |
| D-08 | PinHasher port (Protocol) defined | [ ] |
| D-09 | TokenService port defined | [ ] |
| D-10 | OtpService port defined | [ ] |
| D-11 | EventPublisher port defined | [ ] |
| D-12 | AuthenticationService domain service implemented | [ ] |
| D-13 | PIN validation: 4-6 numeric digits | [ ] |
| D-14 | Lockout logic: 5 failures = 30 min lock | [ ] |
| D-15 | Max sessions: 5 per user, oldest evicted | [ ] |
| D-16 | Token rotation: old refresh token revoked on use | [ ] |
| D-17 | 100% type hints on all domain code | [ ] |
| D-18 | No infrastructure imports in domain | [ ] |
| D-19 | All DomainError codes match IDENTITY_* catalog | [ ] |

### Application Layer

| # | Item | Status |
|---|---|---|
| A-01 | LoginUseCase implemented | [ ] |
| A-02 | CreateUserUseCase implemented | [ ] |
| A-03 | UpdateUserUseCase implemented | [ ] |
| A-04 | DeactivateUserUseCase implemented | [ ] |
| A-05 | RevokeSessionUseCase implemented | [ ] |
| A-06 | RequestOtpUseCase implemented | [ ] |
| A-07 | VerifyOtpUseCase implemented | [ ] |
| A-08 | All DTOs use Pydantic V2 | [ ] |
| A-09 | Transaction management (UoW) in use cases | [ ] |

### Infrastructure Layer

| # | Item | Status |
|---|---|---|
| I-01 | SQLAlchemy models for all 6 tables | [ ] |
| I-02 | SqlAlchemyUserRepository implemented | [ ] |
| I-03 | SqlAlchemySessionRepository implemented | [ ] |
| I-04 | SqlAlchemyTokenRepository implemented | [ ] |
| I-05 | SqlAlchemyRoleRepository implemented | [ ] |
| I-06 | BcryptPinHasher (cost=12) implemented | [ ] |
| I-07 | JwtTokenService (RS256, 2048-bit) implemented | [ ] |
| I-08 | OtpGeneratorService implemented | [ ] |
| I-09 | OutboxEventPublisher implemented | [ ] |
| I-10 | Alembic migration created | [ ] |
| I-11 | Seed data migration (7 default users) | [ ] |
| I-12 | Environment config loaded from env vars | [ ] |

### Presentation Layer

| # | Item | Status |
|---|---|---|
| P-01 | POST /auth/pin endpoint | [ ] |
| P-02 | POST /auth/otp/request endpoint | [ ] |
| P-03 | POST /auth/otp/verify endpoint | [ ] |
| P-04 | POST /auth/password endpoint (admin only) | [ ] |
| P-05 | POST /auth/refresh endpoint | [ ] |
| P-06 | POST /auth/logout endpoint | [ ] |
| P-07 | GET /users endpoint (paginated) | [ ] |
| P-08 | POST /users endpoint | [ ] |
| P-09 | GET /users/{id} endpoint | [ ] |
| P-10 | PUT /users/{id} endpoint | [ ] |
| P-11 | DELETE /users/{id} endpoint (soft-delete) | [ ] |
| P-12 | PUT /users/{id}/reactivate endpoint | [ ] |
| P-13 | PUT /users/{id}/role endpoint | [ ] |
| P-14 | PUT /users/{id}/pin endpoint | [ ] |
| P-15 | GET /sessions endpoint | [ ] |
| P-16 | DELETE /sessions/{id} endpoint | [ ] |
| P-17 | GET /roles endpoint | [ ] |
| P-18 | GET /permissions endpoint | [ ] |
| P-19 | PUT /permissions endpoint | [ ] |
| P-20 | JWT auth middleware (validates on every request) | [ ] |
| P-21 | Rate limit middleware on auth endpoints | [ ] |
| P-22 | Error handlers for all 11 IDENTITY_* errors | [ ] |
| P-23 | CORS configured for known origins | [ ] |

---

## Phase 3: Testing (Gate 3)

| # | Item | Status |
|---|---|---|
| T-01 | All unit tests pass (40+) | [ ] |
| T-02 | All integration tests pass (15) | [ ] |
| T-03 | All E2E tests pass (5) | [ ] |
| T-04 | Coverage ≥ 95% | [ ] |
| T-05 | Security penetration tests pass | [ ] |
| T-06 | Rate limits verified | [ ] |
| T-07 | Account enumeration prevention verified | [ ] |
| T-08 | Token rotation verified | [ ] |
| T-09 | Multi-device session limit verified | [ ] |
| T-10 | Lockout / unlock flow verified | [ ] |
| T-11 | Seed data verified on fresh DB | [ ] |

---

## Phase 4: Event Verification (Gate 4)

| # | Event | Published | Consumed By |
|---|---|---|---|
| E-01 | IDENTITY.USER.CREATED | [ ] | Audit, Analytics |
| E-02 | IDENTITY.USER.UPDATED | [ ] | Audit |
| E-03 | IDENTITY.USER.DISABLED | [ ] | Audit, Notification |
| E-04 | IDENTITY.USER.REACTIVATED | [ ] | Audit |
| E-05 | IDENTITY.USER.LOGIN | [ ] | Audit, Analytics |
| E-06 | IDENTITY.USER.LOGOUT | [ ] | Audit |
| E-07 | IDENTITY.OTP.SENT | [ ] | Audit |
| E-08 | IDENTITY.OTP.VERIFIED | [ ] | Audit |
| E-09 | IDENTITY.TOKEN.REFRESHED | [ ] | Audit |
| E-10 | IDENTITY.ROLE.ASSIGNED | [ ] | Audit, Queue |
| E-11 | IDENTITY.AUTH.FAILED | [ ] | Audit |
| E-12 | IDENTITY.AUTH.LOCKED | [ ] | Audit, Notification |
| E-13 | IDENTITY.AUTH.UNLOCKED | [ ] | Audit |
| E-14 | IDENTITY.PIN.CHANGED | [ ] | Audit |
| E-15 | IDENTITY.SESSION.EXPIRED | [ ] | Audit |
| E-16 | IDENTITY.SESSION.REVOKED | [ ] | Audit |
| E-17 | IDENTITY.SECURITY.ALERT | [ ] | Audit, Notification |

---

## Phase 5: Acceptance (Gate 5)

| AC ID | Criterion | Manual Test | Automated Test | Status |
|---|---|---|---|---|
| AC-01 | Admin can create staff with role and department | T-01 | T-U-01 | [ ] |
| AC-02 | Staff can log in with 4-6 digit PIN | T-02 | T-U-02 | [ ] |
| AC-03 | Staff can request OTP for PIN reset | T-03 | T-U-03 | [ ] |
| AC-04 | 5 failed attempts lock account for 30 min | T-04 | T-U-04 | [ ] |
| AC-05 | JWT expires in 24h | T-05 | T-U-05 | [ ] |
| AC-06 | Refresh token works for 7 days | T-06 | T-U-06 | [ ] |
| AC-07 | Admin can deactivate and reactivate users | T-07 | T-U-07 | [ ] |
| AC-08 | Role assignment changes permissions immediately | T-08 | T-U-08 | [ ] |
| AC-09 | All auth endpoints rate limited | T-09 | T-U-09 | [ ] |
| AC-10 | All auth events published to event bus | T-10 | T-U-10 | [ ] |
| AC-11 | Seed users created when table empty | T-11 | T-U-11 | [ ] |
| AC-12 | Account enumeration not possible | T-12 | T-U-12 | [ ] |
| AC-13 | Session timeout after 15 min inactivity | T-13 | T-U-13 | [ ] |
| AC-14 | Admin can revoke any active session | T-14 | T-U-14 | [ ] |
| AC-15 | Multi-device login works (up to 5 sessions) | T-15 | T-U-15 | [ ] |

---

## Phase 6: Documentation (Gate 6)

| # | Item | Status |
|---|---|---|
| DOC-01 | Update EVENT_MEMORY.md with all checked events | [ ] |
| DOC-02 | Update SESSION_MEMORY.md: IDN-01→IDN-10 completed | [ ] |
| DOC-03 | ENGINE_TEMPLATE.md updated with Identity specifics | [ ] |
| DOC-04 | README updated with Identity Engine section | [ ] |
| DOC-05 | API docs (OpenAPI/Swagger) published | [ ] |
| DOC-06 | Deployment config for Identity Engine | [ ] |

---

## Phase 7: Moving to Patient Engine

**Final gate check before starting Patient Engine:**

- [ ] All 6 gates above are 100% complete
- [ ] Identity Engine is deployed and passing health checks
- [ ] All 19 events are publishing correctly
- [ ] All 11 error codes are returning correctly
- [ ] All 15 acceptance criteria are passing
- [ ] Security review has no HIGH or CRITICAL findings
- [ ] Performance meets NFR targets (<200ms p95 auth)
- [ ] Patient Engine design documents are created (Parallel step)
- [ ] Identity Engine folder structure is frozen
- [ ] This checklist is checked into `docs/identity/010_READINESS_CHECKLIST.md`

---

## Summary Dashboard

```
Phase 1: Design Review     [ ] 0/10 documents approved
Phase 2: Implementation    [ ] 0/... items complete
Phase 3: Testing           [ ] 0/11 items passing
Phase 4: Events            [ ] 0/17 events verified
Phase 5: Acceptance        [ ] 0/15 criteria met
Phase 6: Documentation     [ ] 0/6 items complete
Phase 7: Engine Complete   [ ] NOT READY
```
