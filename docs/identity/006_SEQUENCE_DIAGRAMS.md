# 006 — Identity Engine: Sequence Diagrams

*6 critical flows visualized with Mermaid sequence diagrams.*

---

## Flow 1: PIN Login (Happy Path)

```mermaid
sequenceDiagram
    actor Staff
    participant API as FastAPI /auth/pin
    participant AuthSvc as AuthService
    participant UserRepo as UserRepo
    participant SessionRepo as SessionRepo
    participant TokenRepo as TokenRepo
    participant Events as Event Bus

    Staff->>API: POST /auth/pin {username, pin}
    API->>AuthSvc: login_with_pin(username, pin, device_info)

    AuthSvc->>UserRepo: find_by_username(username)
    UserRepo-->>AuthSvc: User aggregate

    AuthSvc->>AuthSvc: verify_pin(pin, hasher)
    AuthSvc->>AuthSvc: record_successful_login()

    AuthSvc->>SessionRepo: find_active_by_user(user_id)
    SessionRepo-->>AuthSvc: [sessions...]

    alt max sessions reached (>=5)
        AuthSvc->>SessionRepo: revoke oldest session
    end

    AuthSvc->>AuthSvc: create Session aggregate
    AuthSvc->>AuthSvc: create access_token (JWT)
    AuthSvc->>AuthSvc: create RefreshToken aggregate

    AuthSvc->>UserRepo: save(user)
    AuthSvc->>SessionRepo: save(session)
    AuthSvc->>TokenRepo: save(refresh_token)

    AuthSvc->>Events: publish IDENTITY.USER.LOGIN

    AuthSvc-->>API: LoginResult
    API-->>Staff: 200 {access_token, refresh_token, user, session}
```

---

## Flow 2: PIN Login (Locked Account)

```mermaid
sequenceDiagram
    actor Staff
    participant API as FastAPI /auth/pin
    participant AuthSvc as AuthService
    participant UserRepo as UserRepo
    participant Events as Event Bus

    Staff->>API: POST /auth/pin {username, pin}
    API->>AuthSvc: login_with_pin(username, pin, device_info)

    AuthSvc->>UserRepo: find_by_username(username)
    UserRepo-->>AuthSvc: User (locked_until in future)

    AuthSvc->>AuthSvc: is_locked() -> True

    AuthSvc-->>API: raise DomainError("IDENTITY_002")
    API-->>Staff: 423 {error: "Account locked. 30 min remaining."}
```

---

## Flow 3: PIN Login (Failed → Lockout)

```mermaid
sequenceDiagram
    actor Staff
    participant API as FastAPI /auth/pin
    participant AuthSvc as AuthService
    participant UserRepo as UserRepo
    participant Events as Event Bus

    Staff->>API: POST /auth/pin {username, "wrong_pin"}
    API->>AuthSvc: login_with_pin(username, pin, device_info)

    AuthSvc->>UserRepo: find_by_username(username)
    UserRepo-->>AuthSvc: User (login_attempts=4)

    AuthSvc->>AuthSvc: verify_pin() -> False
    AuthSvc->>AuthSvc: record_failed_attempt() -> LockoutResult(locked=True)

    AuthSvc->>UserRepo: save(user)
    AuthSvc->>Events: publish IDENTITY.AUTH.FAILED
    AuthSvc->>Events: publish IDENTITY.AUTH.LOCKED

    AuthSvc-->>API: raise DomainError("IDENTITY_003")
    API-->>Staff: 401 {error: "Invalid PIN"}

    Note over Staff: 5th attempt
    Staff->>API: POST /auth/pin {username, "wrong_pin_again"}
    API->>AuthSvc: login_with_pin()
    AuthSvc->>AuthSvc: is_locked() -> True
    AuthSvc-->>API: 423 {error: "Account locked"}
    API-->>Staff: 423 Account locked
```

---

## Flow 4: OTP Login (Full Flow)

```mermaid
sequenceDiagram
    actor Staff
    participant API1 as FastAPI /auth/otp/request
    participant API2 as FastAPI /auth/otp/verify
    participant AuthSvc as AuthService
    participant OtpSvc as OTPService
    participant CommSvc as CommunicationSvc
    participant Events as Event Bus

    Staff->>API1: POST /auth/otp/request {username, "login"}

    API1->>AuthSvc: request_otp(username)
    AuthSvc->>OtpSvc: generate() -> (raw_otp, code_hash)
    OtpSvc->>OtpSvc: store_otp(user_id, code_hash, expires_at)
    AuthSvc->>CommSvc: send_sms(phone, "Your OTP: 482916")

    AuthSvc->>Events: publish IDENTITY.OTP.SENT

    AuthSvc-->>API1: {message: "OTP sent"}
    API1-->>Staff: 200 OTP sent to phone

    Staff->>API2: POST /auth/otp/verify {username, "482916"}

    API2->>AuthSvc: verify_otp(username, otp)
    AuthSvc->>OtpSvc: find_by_user(user_id)
    OtpSvc->>OtpSvc: verify(otp, code_hash) -> True
    OtpSvc->>OtpSvc: mark_used()

    AuthSvc->>Events: publish IDENTITY.OTP.VERIFIED

    AuthSvc->>AuthSvc: create_session_and_tokens()
    AuthSvc->>Events: publish IDENTITY.USER.LOGIN

    AuthSvc-->>API2: LoginResult
    API2-->>Staff: 200 {access_token, refresh_token, user, session}
```

---

## Flow 5: Token Refresh with Rotation

```mermaid
sequenceDiagram
    actor Client
    participant API as FastAPI /auth/refresh
    participant AuthSvc as AuthService
    participant TokenRepo as TokenRepo
    participant SessionRepo as SessionRepo
    participant Events as Event Bus

    Client->>API: POST /auth/refresh {refresh_token}

    API->>AuthSvc: refresh_access_token(raw_token)
    AuthSvc->>AuthSvc: hash(raw_token) -> token_hash
    AuthSvc->>TokenRepo: find_by_hash(token_hash)
    TokenRepo-->>AuthSvc: RefreshToken (is_revoked=False, not expired)

    AuthSvc->>AuthSvc: is_valid() -> True

    AuthSvc->>TokenRepo: find_by_user(user_id)
    TokenRepo-->>AuthSvc: old_token

    Note over AuthSvc: Token Rotation
    AuthSvc->>AuthSvc: old_token.revoke()
    AuthSvc->>AuthSvc: create new RefreshToken aggregate

    AuthSvc->>SessionRepo: find_by_id(session_id)
    SessionRepo-->>AuthSvc: Session
    AuthSvc->>AuthSvc: session.refresh_activity()

    AuthSvc->>TokenRepo: save(old_token)  # revoked
    AuthSvc->>TokenRepo: save(new_token)
    AuthSvc->>SessionRepo: save(session)

    AuthSvc->>Events: publish IDENTITY.TOKEN.REFRESHED

    AuthSvc-->>API: {new_access_token, new_refresh_token}
    API-->>Client: 200 {access_token, refresh_token}

    Note over Client: Old refresh token is now revoked.
    Note over Client: If reused -> IDENTITY_007 error.
```

---

## Flow 6: Admin Creates User → Events Propagate

```mermaid
sequenceDiagram
    actor Admin
    participant API as FastAPI POST /users
    participant UserSvc as UserService
    participant UserRepo as UserRepo
    participant RoleRepo as RoleRepo
    participant Events as Event Bus

    Admin->>API: POST /users {username, full_name, role, department, phone}
    API->>UserSvc: create_user(data)

    UserSvc->>UserRepo: find_by_username(username)
    UserRepo-->>UserSvc: None (no duplicate)

    UserSvc->>RoleRepo: find_by_code(role_code)
    RoleRepo-->>UserSvc: Role (validated)

    Note over UserSvc: Generate temporary PIN
    UserSvc->>UserSvc: Create User aggregate
    UserSvc->>UserSvc: Hash temporary PIN with bcrypt

    UserSvc->>UserRepo: save(user)
    UserSvc->>Events: publish IDENTITY.USER.CREATED

    UserSvc-->>API: UserDTO (no pin_hash)
    API-->>Admin: 201 {user details}

    Note over Events: Downstream consumers react
    Events->>AuditSvc: IDENTITY.USER.CREATED -> log audit entry
    Events->>CommSvc: Send welcome message with temp PIN
```

---

## 7. Validation Checklist

| Flow | Validates | Verified |
|---|---|---|
| 1. PIN Login Happy Path | PIN format, hash verify, session create, token issue, event publish | [ ] |
| 2. Locked Account | Lock detection, correct error code, no side effects | [ ] |
| 3. Failure → Lockout | Attempt count, threshold trigger, event sequence | [ ] |
| 4. OTP Flow | Generate, store, deliver, verify, login, events | [ ] |
| 5. Token Refresh | Rotation, revocation, activity refresh, replay protection | [ ] |
| 6. Admin Create User | Duplicate check, role validation, temp PIN, event | [ ] |
