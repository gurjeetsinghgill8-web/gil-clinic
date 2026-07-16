# 003 — SYSTEM ARCHITECTURE

*Modular Monolith with clean architecture layers.*
*Designed for future microservice extraction.*

---

## Architecture Pattern

GHOS follows a **Modular Monolith** pattern with strict Clean Architecture layers.
This means a single deployable unit with clear internal boundaries.
Microservices are extracted only when a module needs independent scaling or team.

```
ghos-v2/
├── domain/          # Pure business logic, no frameworks
│   ├── identity/
│   ├── patient/
│   ├── queue/
│   ├── workflow/
│   ├── clinical/
│   ├── billing/
│   ├── inventory/
│   ├── appointment/
│   ├── communication/
│   ├── notification/
│   ├── ai/
│   ├── analytics/
│   └── audit/
├── application/     # Use cases, DTOs, ports
├── infrastructure/  # DB, external APIs, event bus
└── presentation/    # API, WebSocket, background jobs
```

## Dependency Rules

- domain/ depends on NOTHING (no framework, no DB)
- application/ depends on domain/ only
- infrastructure/ depends on application/
- presentation/ depends on application/
- NO layer may import from a higher layer
- NO circular dependencies between domains
- Cross-domain communication via events ONLY

## Future Microservice Extraction

When GHOS reaches 50+ clinics or specific modules need independent scaling:

| Module | Extraction Trigger | Independent Resources |
|---|---|---|
| Queue Engine | High throughput (>1000 req/s) | Redis cluster + WS gateway |
| Notification Engine | Multi-channel delivery | Celery workers |
| AI Engine | GPU compute needed | GPU nodes + model registry |
| Communication Engine | Carrier API rate limits | Dedicated celery workers |
| Analytics Engine | Heavy aggregations | Read replica + OLAP |
| Identity Engine | Multi-tenant auth | Auth0/Keycloak |

## Event Bus

- **Phase 1 (Modular Monolith)**: Redis pub/sub with in-process handlers
- **Phase 2 (Microservices)**: Kafka with consumer groups
- Outbox pattern: events published AFTER DB commit
- Dead letter queue for failed events
- Event schema versioning for backward compatibility

## Database Strategy

- Single PostgreSQL database with separate schemas per domain
- Schema names: identity, patient, queue, workflow, clinical, billing, inventory, appointment, communication, notification, ai, analytics, audit
- No cross-schema foreign keys (referential integrity in application layer)
- UUIDv7 primary keys (time-sortable, no collisions)
- Alembic for schema migrations
- Read replicas for analytics queries

---
