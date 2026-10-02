# Identity Engine — Dependency Map

## File-Level Dependency Graph

```
PRESENTATION LAYER
==================
auth_routes.py
  ├── login_use_case (application)
  ├── request_otp_use_case (application)
  ├── verify_otp_use_case (application)
  ├── refresh_token_use_case (application)
  └── schemas/auth_schemas (presentation)

user_routes.py
  ├── create_user_use_case (application)
  ├── update_user_use_case (application)
  ├── deactivate_user_use_case (application)
  ├── reactivate_user_use_case (application)
  └── schemas/user_schemas (presentation)

session_routes.py
  ├── revoke_session_use_case (application)
  └── schemas/session_schemas (presentation)

role_routes.py
  ├── assign_role_use_case (application)
  └── schemas/user_schemas (presentation)

jwt_middleware.py
  ├── jwt_token_service (infrastructure)
  └── user entity (domain)

error_handlers.py
  └── domain_error (domain/exceptions)

APPLICATION LAYER
=================
login_use_case.py
  ├── authentication_service (domain)
  ├── user entity (domain)
  ├── session entity (domain)
  ├── pin_hasher port (domain)
  └── event_publisher port (domain)

create_user_use_case.py
  ├── user entity (domain)
  ├── role entity (domain)
  ├── pin_hasher port (domain)
  └── event_publisher port (domain)

revoke_session_use_case.py
  ├── session entity (domain)
  └── event_publisher port (domain)

request_otp_use_case.py
  ├── otp_service port (domain)
  └── event_publisher port (domain)

DOMAIN LAYER
============
user.py
  └── Python stdlib (dataclasses, datetime, uuid)

session.py
  └── Python stdlib (dataclasses, datetime, uuid)

refresh_token.py
  └── Python stdlib (dataclasses, datetime, uuid)

authentication_service.py
  ├── user entity
  ├── session entity
  ├── refresh_token entity
  ├── pin_hasher port
  ├── token_service port
  ├── event_publisher port
  └── lockout_result value object

INFRASTRUCTURE LAYER
====================
user_repository.py
  ├── user entity (domain)
  ├── user_model (infrastructure/models)
  └── database (shared/infrastructure)

jwt_token_service.py
  ├── token_service port (domain)
  ├── user entity (domain)
  └── settings (infrastructure/config)

bcrypt_pin_hasher.py
  └── pin_hasher port (domain)

outbox_publisher.py
  ├── event_publisher port (domain)
  ├── outbox_model (infrastructure/models)
  ├── database (shared/infrastructure)
  └── redis_client (shared/infrastructure)
```

## Strict Layer Rules

```
presentation/ ──> application/ ──> domain/
                     │                  │
                     └──> infrastructure/
                          (implements ports)
```

- **Presentation** imports application + domain (entities for type hints only)
- **Application** imports domain only
- **Infrastructure** imports domain only (implements ports)
- **Domain** imports NOTHING outside Python stdlib

## Violation Detection

Run `pytest tests/unit/identity/test_architecture.py` to verify:
- No infrastructure imports in domain layer
- No presentation imports in application layer
- No circular dependencies
- All ports have exactly one implementation
