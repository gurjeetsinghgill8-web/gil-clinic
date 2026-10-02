# GHOS Identity Engine

**Foundation engine for Gurjeet's Hospital Operating System.**

Zero dependencies — every other engine depends on Identity.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                     │
│   FastAPI Routes · Middleware · Schemas · Error Handlers │
├─────────────────────────────────────────────────────────┤
│                    Application Layer                      │
│   Use Cases · DTOs · Unit of Work · Command/Query        │
├─────────────────────────────────────────────────────────┤
│                     Domain Layer                          │
│   Entities · Value Objects · Aggregates · Services       │
│   Ports (interfaces) · Domain Events · Exceptions         │
├─────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                    │
│   SQLAlchemy · Redis · JWT · bcrypt · Outbox Publisher   │
└─────────────────────────────────────────────────────────┘
```

## Dependency Rule

- **Domain** → Zero imports from application/infrastructure/presentation
- **Application** → Imports domain only
- **Infrastructure** → Implements domain ports (Protocols)
- **Presentation** → Imports application + domain

## Key Aggregates

| Aggregate | Table | Notes |
|---|---|---|
| User | identity.users | Root aggregate. PIN, lockout, login |
| Session | identity.user_sessions | Separate aggregate. Multi-device |
| RefreshToken | identity.refresh_tokens | Separate aggregate. Token rotation |

## Authentication Methods

| Method | Who | Storage |
|---|---|---|
| PIN | Staff | bcrypt (cost=12), 4-6 digits |
| OTP | Staff (PIN reset) | SHA-256, 6 digits, 5 min expiry |
| Password | Admin only | bcrypt, backward compatible |

## Communication

- **Identity publishes events only** — never makes direct calls to other engines
- Events: 19 `IDENTITY.*` event types via outbox pattern
- Consumers: Audit, Analytics, Notification, Queue engines

## Project Structure

```
src/
├── domain/identity/        — Pure Python DDD (no infrastructure)
├── application/identity/   — Use cases, DTOs, CQRS
├── infrastructure/identity/ — SQLAlchemy, JWT, bcrypt, Redis
├── presentation/identity/  — FastAPI routes, middleware
└── shared/                 — Cross-cutting: base classes, DB, Redis

tests/
├── unit/identity/          — 40+ domain unit tests
├── integration/identity/   — 15+ API + DB tests
├── e2e/identity/           — 5+ full flow tests
└── fixtures/identity/      — Test data factories

alembic/                    — Versioned DB migrations
docker/identity/            — Dockerfile + compose
configs/                    — Dev/prod/test YAML configs
scripts/                    — Seed + migration helpers
docs/identity/              — 10 design documents (locked)
```
