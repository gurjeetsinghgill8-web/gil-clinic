# 008 — Identity Engine: Test Strategy

*Unit, integration, E2E, and acceptance test plan.*

---

## 1. Test Pyramid

```
         /\
        /  \          E2E (5 tests)
       /    \
      /      \        Integration (15 tests)
     /        \
    /          \      Unit (40+ tests)
   /____________\
```

| Layer | Count | Speed | Scope |
|---|---|---|---|
| Unit | 40+ | <1ms each | Domain entities + services |
| Integration | 15 | <100ms each | Repositories + API |
| E2E | 5 | <5s each | Full auth flows |
| Acceptance | 15 | Manual | AC-01 through AC-15 |

---

## 2. Unit Tests (Domain Layer)

### 2.1 User Aggregate Tests

| Test | Scenario | Expected |
|---|---|---|
| `test_verify_pin_correct` | Match PIN | Returns True |
| `test_verify_pin_incorrect` | Wrong PIN | Returns False |
| `test_verify_pin_no_hash` | User has no PIN set | Returns False |
| `test_is_locked_when_not_locked` | locked_until is None | Returns False |
| `test_is_locked_when_past_lock` | locked_until in past | Returns False |
| `test_is_locked_when_active_lock` | locked_until in future | Returns True |
| `test_record_failed_attempt_under_limit` | 4th failure | LockoutResult(locked=False) |
| `test_record_failed_attempt_at_limit` | 5th failure | LockoutResult(locked=True), until set |
| `test_record_failed_attempt_over_limit` | 6th failure | locked_until unchanged |
| `test_record_successful_login` | After success | login_attempts=0, locked_until=None |
| `test_change_pin_valid` | Correct old PIN | PIN hash updated |
| `test_change_pin_wrong_old` | Incorrect old PIN | Raises DomainError |
| `test_change_pin_invalid_format` | "abc" (letters) | Raises DomainError |
| `test_change_pin_short` | "123" (3 digits) | Raises DomainError |
| `test_change_pin_long` | "1234567" (7 digits) | Raises DomainError |
| `test_unlock_account` | Admin unlock | locked_until=None, attempts=0 |
| `test_deactivate_user` | Admin deactivate | is_active=False |

### 2.2 Session Aggregate Tests

| Test | Scenario | Expected |
|---|---|---|
| `test_session_active` | Not expired, not revoked | is_active=True |
| `test_session_expired` | Past expires_at | is_active=False |
| `test_session_revoked` | revoked_at set | is_active=False |
| `test_session_timed_out` | 16 min idle | is_timed_out=True |
| `test_session_timed_out_under` | 10 min idle | is_timed_out=False |
| `test_revoke_session` | Revoke called | revoked_at set |
| `test_refresh_activity` | Activity refresh | last_activity updated |

### 2.3 RefreshToken Aggregate Tests

| Test | Scenario | Expected |
|---|---|---|
| `test_token_valid` | Not revoked, not expired | is_valid=True |
| `test_token_revoked` | revoked=True | is_valid=False |
| `test_token_expired` | Past expires_at | is_valid=False |
| `test_revoke_token` | Revoke called | is_revoked=True, revoked_at set |

### 2.4 AuthenticationService Tests

| Test | Scenario | Expected |
|---|---|---|
| `test_login_with_pin_success` | Valid PIN + active user | LoginResult with tokens |
| `test_login_with_pin_locked` | Locked account | Raises IDENTITY_002 |
| `test_login_with_pin_inactive` | Deactivated user | Raises IDENTITY_006 |
| `test_login_with_pin_failure` | Wrong PIN | Raises IDENTITY_003, lockout on 5th |
| `test_refresh_token_success` | Valid token | New tokens, old revoked |
| `test_refresh_token_revoked` | Already used token | Raises IDENTITY_007 |
| `test_refresh_token_expired` | Expired token | Raises IDENTITY_007 |
| `test_max_sessions_enforced` | 6th login from new device | Oldest session revoked |

---

## 3. Integration Tests

### 3.1 Repository Tests

| Test | What It Tests |
|---|---|
| `test_user_repo_find_by_username` | Query by username |
| `test_user_repo_create_user` | Persist new user, verify UUID |
| `test_user_repo_update_user` | Update fields, verify persistence |
| `test_session_repo_find_active_by_user` | Filter active sessions |
| `test_session_repo_active_sessions_under_limit` | Count < 5 |
| `test_token_repo_find_by_hash` | Query by SHA-256 hash |
| `test_otp_repo_cleanup_expired` | Delete expired OTPs |

### 3.2 API Integration Tests

| Test | What It Tests |
|---|---|
| `test_post_auth_pin` | Full request→response cycle |
| `test_post_auth_otp_request` | Rate limit headers present |
| `test_post_auth_otp_verify` | OTP consumed after use |
| `test_post_auth_refresh` | Old token revoked, new issued |
| `test_post_users_admin_only` | Non-admin gets 403 |

---

## 4. E2E Tests

| Test | Flow | Steps |
|---|---|---|
| `test_e2e_staff_login_full` | Login → API call → Logout | POST /auth/pin → GET /users → POST /auth/logout |
| `test_e2e_otp_login_full` | Request OTP → Verify → Refresh | POST /auth/otp/request → POST /auth/otp/verify → POST /auth/refresh |
| `test_e2e_admin_crud_user` | Create → Read → Update → Delete | POST /users → GET /users/{id} → PUT /users/{id} → DELETE /users/{id} |
| `test_e2e_lockout_recovery` | 5 failures → wait → unlock | POST /auth/pin ×5 → POST /auth/pin (locked) → admin unlock → login |
| `test_e2e_multi_device` | Login device A → Login device B → Revoke A | POST /auth/pin (dev1) → POST /auth/pin (dev2) → DELETE /sessions/{dev1} |

---

## 5. Test Doubles Strategy

| Dependency | Unit Test | Integration Test | E2E |
|---|---|---|---|
| UserRepo | InMemoryUserRepo | Test PostgreSQL | Real DB |
| SessionRepo | InMemorySessionRepo | Test PostgreSQL | Real DB |
| TokenRepo | InMemoryTokenRepo | Test PostgreSQL | Real DB |
| PinHasher | MockBcrypt (constant time) | Real bcrypt | Real bcrypt |
| TokenService | MockJWT | Real JWT with test keys | Real JWT |
| EventPublisher | SpyEventPublisher | Fake Redis | Real Redis |
| CommunicationSvc | Mock | Mock | Real (test mode) |

---

## 6. Test Fixtures

```python
@pytest.fixture
def user_repo():
    return InMemoryUserRepo()

@pytest.fixture
def session_repo():
    return InMemorySessionRepo()

@pytest.fixture
def token_repo():
    return InMemoryTokenRepo()

@pytest.fixture
def pin_hasher():
    return MockPinHasher()

@pytest.fixture
def event_spy():
    return SpyEventPublisher()

@pytest.fixture
def auth_service(user_repo, session_repo, token_repo, pin_hasher, event_spy):
    return AuthenticationService(
        user_repo=user_repo,
        session_repo=session_repo,
        token_repo=token_repo,
        pin_hasher=pin_hasher,
        otp_service=MockOtpService(),
        token_service=MockTokenService(),
        event_publisher=event_spy,
    )

@pytest.fixture
def active_user(user_repo, pin_hasher):
    user = User(
        id=uuid7(),
        username="testuser",
        full_name="Test User",
        role_code="RECEPTIONIST",
        phone="9999999999",
        is_active=True,
        login_attempts=0,
    )
    user._pin_hash = pin_hasher.hash("1234")
    user_repo.save(user)
    return user
```

---

## 7. Running Tests

```bash
# Unit tests only
pytest tests/unit/identity/ -v

# Integration tests (requires test DB)
pytest tests/integration/identity/ -v

# E2E tests (requires full stack)
pytest tests/e2e/identity/ -v

# All identity tests with coverage
pytest tests/ -k "identity" --cov=engines/identity --cov-report=html

# With testcontainers (auto DB)
pytest tests/integration/identity/ --with-postgres
```

---

## 8. Coverage Targets

| Layer | Target |
|---|---|
| Domain entities | 100% |
| Domain services | 100% |
| Application use cases | 100% |
| API endpoints | 90% |
| Repositories | 80% |
| **Overall** | **95%** |

---

## 9. Acceptance Tests (Manual)

| AC ID | Criterion | Test Script Reference |
|---|---|---|
| AC-01 | Admin can create staff with role and department | Manual: Create user via API |
| AC-02 | Staff can log in with 4-6 digit PIN | Manual: POST /auth/pin |
| AC-03 | Staff can request OTP for PIN reset | Manual: POST /auth/otp/request |
| AC-04 | 5 failed attempts lock account for 30 min | Manual: Fail 5 times, try again |
| AC-05 | JWT issued on successful auth expires in 24h | Automated: decode JWT, check exp |
| AC-06 | Refresh token works for 7 days | Automated: verify expiry claim |
| AC-07 | Admin can deactivate and reactivate users | Manual: toggle via API |
| AC-08 | Role assignment changes permissions immediately | Manual: change role, verify access |
| AC-09 | All auth endpoints rate limited | Automated: hammer endpoint, check 429 |
| AC-10 | All auth events published to event bus | Automated: check event_spy |
| AC-11 | Seed users created when table empty | Automated: check DB after migration |
| AC-12 | Account enumeration not possible | Automated: same error for all failures |
| AC-13 | Session timeout after 15 min inactivity | Manual: wait 16 min, try API call |
| AC-14 | Admin can revoke any active session | Manual: revoke, check blocked |
| AC-15 | Multi-device login works (up to 5 sessions) | Manual: login 5 devices, 6th fails |
