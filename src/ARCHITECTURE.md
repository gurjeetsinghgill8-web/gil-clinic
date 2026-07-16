# GHOS Identity Engine — Architecture Overview

## Clean Architecture Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                           │
│  FastAPI Routers │ Middleware │ Schemas │ Error Handlers         │
│                                                                  │
│  Dependencies: application layer only                            │
│  NO direct domain access (except through use cases)              │
├─────────────────────────────────────────────────────────────────┤
│                     APPLICATION LAYER                            │
│  Use Cases │ DTOs │ Unit of Work │ Command/Query Handlers        │
│                                                                  │
│  Dependencies: domain layer only                                 │
│  Orchestrates domain services + infrastructure ports             │
├─────────────────────────────────────────────────────────────────┤
│                     DOMAIN LAYER                                 │
│  Entities │ Value Objects │ Aggregates │ Domain Services         │
│  Ports (Protocols) │ Domain Events │ Exceptions                  │
│                                                                  │
│  Dependencies: NONE (pure Python stdlib)                         │
│  NO imports from application, infrastructure, or presentation    │
├─────────────────────────────────────────────────────────────────┤
│                     INFRASTRUCTURE LAYER                          │
│  SQLAlchemy Models │ Repositories │ JWT Service │ bcrypt         │
│  Redis Client │ Outbox Publisher │ Settings                      │
│                                                                  │
│  Implements: domain ports                                        │
│  Dependencies: domain layer only                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Event-Driven Communication

```
  IDENTITY ENGINE                EVENT BUS                OTHER ENGINES
  ┌──────────────┐          ┌──────────────┐          ┌──────────────┐
  │ User Login   │ ──────►  │  IDENTITY.   │ ──────►  │ Audit Engine │
  │ User Created │ ──────►  │  USER.*      │ ──────►  │ Analytics    │
  │ OTP Sent     │ ──────►  │  OTP.*       │ ──────►  │ Notification │
  │ Locked       │ ──────►  │  AUTH.*      │ ──────►  │ Queue Engine │
  │ Role Changed │ ──────►  │  ROLE.*      │          │ (future)     │
  └──────────────┘          └──────────────┘          └──────────────┘
  
  Outbox Pattern:
  1. Domain service → writes event to outbox table (same DB txn)
  2. Outbox relay → reads PENDING events → publishes to Redis
  3. Consumers → subscribe to Redis channels
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| UUIDv7 primary keys | Time-sortable, globally unique, no sequential guessing |
| Separate aggregates | User, Session, RefreshToken are independent aggregates — enables clean revocation, multi-device, token rotation |
| bcrypt cost=12 | OWASP recommended — balances security and performance |
| RS256 (not HS256) | Asymmetric — signing key not needed by verifiers |
| Outbox pattern | Guarantees event delivery without 2PC |
| Refresh token rotation | Old token revoked on use — replay attack prevention |
| Default-deny RBAC | No access unless explicitly granted — zero-trust |
| AES-256-GCM for PII | Application-layer encryption, not DB-level |

## Import Rules

| From ↓ | Can import → |
|---|---|
| domain/* | Python stdlib only |
| application/* | domain/* |
| infrastructure/* | domain/*  |
| presentation/* | application/*, domain/*  |

**No circular imports allowed.** CI/CD pipeline will enforce this with `pytest-arch`.

## Module Dependencies (within Identity Engine)

```
auth_routes.py ──> login_use_case.py ──> authentication_service.py ──> user.py
                  verify_otp_use_case.py ──> otp_service.py (port)     session.py
                  create_user_use_case.py ──> user.py                   refresh_token.py
```

Each dependency arrow is one-way only. See `docs/identity/009_IMPLEMENTATION_PLAN.md` for complete dependency graph.
