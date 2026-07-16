# 004 — Identity Engine: Domain Model

*Domain-Driven Design — pure domain layer with NO infrastructure dependencies.*

---

## 1. Aggregate: User

The **User** aggregate is the root of identity. It manages authentication state, lockout logic, and delegates to `Role` for authorization.

### Domain Entity

```python
@dataclass
class User:
    id: UUID          # UUIDv7
    username: str
    full_name: str
    role_code: str
    department: str | None
    phone: str
    email: str | None
    is_active: bool
    login_attempts: int
    locked_until: datetime | None
    last_login: datetime | None
    created_at: datetime
    updated_at: datetime

    # Private — never exposed outside domain
    _pin_hash: str | None = None
    _password_hash: str | None = None
```

### Domain Behavior (methods on User)

```python
class User:
    def verify_pin(self, pin: str, pin_hasher: PinHasher) -> bool:
        """Validate PIN against stored hash."""
        if not self._pin_hash:
            return False
        return pin_hasher.verify(pin, self._pin_hash)

    def is_locked(self) -> bool:
        """Check if account is currently locked."""
        if not self.locked_until:
            return False
        return self.locked_until > datetime.now(UTC)

    def record_failed_attempt(self) -> LockoutResult:
        """Increment login attempts. Return LockoutResult if threshold hit."""
        self.login_attempts += 1
        if self.login_attempts >= 5:
            self.locked_until = datetime.now(UTC) + timedelta(minutes=30)
            return LockoutResult(locked=True, until=self.locked_until)
        return LockoutResult(locked=False)

    def record_successful_login(self, device_id: str) -> Session:
        """Reset login attempts, create new session."""
        self.login_attempts = 0
        self.locked_until = None
        self.last_login = datetime.now(UTC)
        return Session(
            id=uuid7(),
            user_id=self.id,
            device_id=device_id,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )

    def unlock(self) -> None:
        """Manually unlock account (admin action)."""
        self.locked_until = None
        self.login_attempts = 0

    def change_pin(self, old_pin: str, new_pin: str, hasher: PinHasher) -> None:
        """Verify old PIN, set new PIN hash."""
        if not self.verify_pin(old_pin, hasher):
            raise DomainError("IDENTITY_003", "Current PIN is incorrect")
        self._validate_pin_format(new_pin)
        self._pin_hash = hasher.hash(new_pin)

    def deactivate(self) -> None:
        """Soft-delete user."""
        self.is_active = False

    @staticmethod
    def _validate_pin_format(pin: str) -> None:
        if not (4 <= len(pin) <= 6) or not pin.isdigit():
            raise DomainError("IDENTITY_001", "PIN must be 4-6 digits")
```

---

## 2. Value Object: Role

Role is a value object — immutable, identified by code.

```python
@dataclass(frozen=True)
class Role:
    code: str
    name: str
    hierarchy_level: int
    permissions: frozenset[Permission]

    def has_permission(self, resource: str, action: str) -> bool:
        for p in self.permissions:
            if p.resource == resource and p.action == action:
                return p.is_granted
        return False  # Default-deny

    def can_access(self, target_hierarchy: int) -> bool:
        return self.hierarchy_level >= target_hierarchy
```

---

## 3. Value Object: Permission

```python
@dataclass(frozen=True)
class Permission:
    resource: str    # e.g. "patients", "users", "billing"
    action: str      # e.g. "read", "write", "delete", "admin"
    is_granted: bool = True
```

---

## 4. Aggregate: Session (separate aggregate)

Session is its own aggregate — manages device trust, expiry, revocation.

```python
@dataclass
class Session:
    id: UUID
    user_id: UUID
    device_id: str | None
    device_name: str | None
    user_agent: str | None
    ip_address: str | None
    last_activity: datetime
    is_trusted: bool
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None

    @property
    def is_active(self) -> bool:
        if self.revoked_at:
            return False
        return self.expires_at > datetime.now(UTC)

    @property
    def is_timed_out(self) -> bool:
        idle = datetime.now(UTC) - self.last_activity
        return idle > timedelta(minutes=15)

    def revoke(self) -> None:
        self.revoked_at = datetime.now(UTC)

    def refresh_activity(self) -> None:
        self.last_activity = datetime.now(UTC)

    def trust_device(self) -> None:
        self.is_trusted = True
```

---

## 5. Aggregate: RefreshToken (separate aggregate)

RefreshToken is its own aggregate — NOT stored inside User. This enables:
- Multiple refresh tokens per user (multi-device)
- Token rotation (old token revoked on use)
- Clean revocation without touching User aggregate

```python
@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str
    session_id: UUID | None
    device_id: str | None
    is_revoked: bool
    expires_at: datetime
    created_at: datetime
    revoked_at: datetime | None

    @property
    def is_valid(self) -> bool:
        if self.is_revoked:
            return False
        return self.expires_at > datetime.now(UTC)

    def revoke(self) -> None:
        self.is_revoked = True
        self.revoked_at = datetime.now(UTC)
```

---

## 6. Domain Service: AuthenticationService

Orchestrates authentication across aggregates. This is where domain logic lives that spans multiple aggregates.

```python
class AuthenticationService:
    def __init__(self, user_repo, session_repo, token_repo,
                 pin_hasher, otp_service, token_service, event_publisher):
        ...

    def login_with_pin(self, username: str, pin: str, device_info: DeviceInfo) -> LoginResult:
        user = self.user_repo.find_by_username(username)
        if not user:
            raise DomainError("IDENTITY_008", "User not found")
        if not user.is_active:
            raise DomainError("IDENTITY_006", "User deactivated")
        if user.is_locked():
            raise DomainError("IDENTITY_002", "Account locked")

        if not user.verify_pin(pin, self.pin_hasher):
            result = user.record_failed_attempt()
            self.user_repo.save(user)
            if result.locked:
                self.event_publisher.publish("IDENTITY.ACCOUNT_LOCKED", {...})
            raise DomainError("IDENTITY_003", "Invalid PIN")

        # Check max sessions
        active_sessions = self.session_repo.find_active_by_user(user.id)
        if len(active_sessions) >= 5:
            oldest = min(active_sessions, key=lambda s: s.last_activity)
            oldest.revoke()
            self.session_repo.save(oldest)

        session = user.record_successful_login(device_info.device_id)
        session.device_name = device_info.device_name
        session.user_agent = device_info.user_agent
        session.ip_address = device_info.ip_address

        access_token = self.token_service.create_access_token(user, session.id)
        refresh_token_entity = self.token_service.create_refresh_token(user.id, session.id, device_info.device_id)

        self.user_repo.save(user)
        self.session_repo.save(session)
        self.token_repo.save(refresh_token_entity)

        self.event_publisher.publish("IDENTITY.USER_LOGIN", {
            "user_id": str(user.id),
            "session_id": str(session.id),
        })

        return LoginResult(
            user=user,
            session=session,
            access_token=access_token,
            refresh_token=refresh_token_entity,
        )

    def refresh_access_token(self, raw_token: str) -> LoginResult:
        """Refresh token with rotation — old token revoked, new one issued."""
        token_hash = self.token_service.hash(raw_token)
        stored = self.token_repo.find_by_hash(token_hash)
        if not stored or not stored.is_valid:
            raise DomainError("IDENTITY_007", "Invalid or expired refresh token")

        user = self.user_repo.find_by_id(stored.user_id)
        if not user or not user.is_active:
            raise DomainError("IDENTITY_006", "User deactivated")

        # Rotate: revoke old, create new
        stored.revoke()
        session = self.session_repo.find_by_id(stored.session_id)
        if session and session.is_active:
            session.refresh_activity()

        new_access = self.token_service.create_access_token(user, stored.session_id)
        new_refresh = self.token_service.create_refresh_token(user.id, stored.session_id, stored.device_id)

        self.token_repo.save(stored)   # revoked
        self.token_repo.save(new_refresh)
        if session:
            self.session_repo.save(session)

        self.event_publisher.publish("IDENTITY.TOKEN_REFRESHED", {
            "user_id": str(user.id),
            "old_token_id": str(stored.id),
            "new_token_id": str(new_refresh.id),
        })

        return LoginResult(user=user, session=session,
                           access_token=new_access, refresh_token=new_refresh)
```

---

## 7. Domain Events (in the domain layer)

```python
@dataclass
class IdentityEvent:
    event_name: str
    aggregate_id: UUID
    timestamp: datetime
    payload: dict

# Concrete events as type aliases:
USER_CREATED       = IdentityEvent  # event_name="IDENTITY.USER_CREATED"
USER_LOGIN         = IdentityEvent  # event_name="IDENTITY.USER_LOGIN"
ACCOUNT_LOCKED     = IdentityEvent  # event_name="IDENTITY.ACCOUNT_LOCKED"
ACCOUNT_UNLOCKED   = IdentityEvent  # event_name="IDENTITY.ACCOUNT_UNLOCKED"
PIN_CHANGED        = IdentityEvent  # event_name="IDENTITY.PIN_CHANGED"
SESSION_REVOKED    = IdentityEvent  # event_name="IDENTITY.SESSION_REVOKED"
OTP_SENT           = IdentityEvent  # event_name="IDENTITY.OTP_SENT"
OTP_VERIFIED       = IdentityEvent  # event_name="IDENTITY.OTP_VERIFIED"
ROLE_ASSIGNED      = IdentityEvent  # event_name="IDENTITY.ROLE_ASSIGNED"
```

---

## 8. Domain Service Interfaces (ports)

```python
class PinHasher(Protocol):
    def hash(self, pin: str) -> str: ...
    def verify(self, pin: str, hashed: str) -> bool: ...

class TokenService(Protocol):
    def create_access_token(self, user: User, session_id: UUID) -> str: ...
    def create_refresh_token(self, user_id: UUID, session_id: UUID | None, device_id: str | None) -> RefreshToken: ...
    def hash(self, token: str) -> str: ...
    def decode(self, token: str) -> dict: ...

class OtpService(Protocol):
    def generate(self) -> tuple[str, str]: ...
    def verify(self, otp: str, code_hash: str) -> bool: ...

class EventPublisher(Protocol):
    def publish(self, event_name: str, payload: dict) -> None: ...
```

---

## 9. Clean Architecture Boundary

```
        Domain (this file)           |  Application (use cases)     | Infrastructure
        =================            |  =====================       | ==============
        User, Session,               |  LoginUseCase               | SqlAlchemyUserRepo
        RefreshToken, Role,          |  CreateUserUseCase          | JwtTokenService
        Permission (entities)        |  RevokeSessionUseCase       | BcryptPinHasher
                                     |                              | RedisEventPublisher
        AuthenticationService        |                              |
        (domain service)             |                              |
                                     |                              |
        PinHasher (port)             |                              |
        TokenService (port)          |                              |
        EventPublisher (port)        |                              |
```

The domain layer has ZERO imports from `infrastructure` or `application`. Ports (protocols/interfaces) are defined in domain and implemented in infrastructure.
