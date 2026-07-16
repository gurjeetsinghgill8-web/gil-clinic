# 013 — DECISION LOG

*Architecture Decision Records (ADRs).*
*Every major technical decision documented with context, alternatives, and rationale.*

---

## ADR-001: Modular Monolith over Microservices
- **Date**: 2026-07-12
- **Context**: V2 architecture design. Team size = 1 developer.
- **Decision**: Start as Modular Monolith, extract microservices later.
- **Alternatives**: Full microservices (rejected: operational overhead, debugging complexity, premature scaling)
- **Rationale**: Single developer + AI tooling = fast iteration. Deploy as one unit. Extract Queue/Notification/AI/Communication when scaling requires it.
- **Consequences**: Must enforce strict layer boundaries. No shortcuts crossing layers.

## ADR-002: PostgreSQL over SQLite (V1)
- **Date**: 2026-07-12
- **Context**: V1 used SQLite with JSON fallback. V2 needs concurrent access, schema per domain, and reliability.
- **Decision**: PostgreSQL 16 with separate schemas per domain.
- **Alternatives**: SQLite (rejected: no concurrent writes), MySQL (rejected: weaker JSONB support), MongoDB (rejected: need ACID)
- **Rationale**: PostgreSQL = mature, ACID compliant, JSONB for flexible fields, pgcrypto for encryption, full-text search, excellent Python support via asyncpg.
- **Consequences**: Requires Docker for local dev. Slightly more memory than SQLite. Worth it.

## ADR-003: Redis over RabbitMQ for Events
- **Date**: 2026-07-12
- **Context**: Event bus needed for inter-domain communication.
- **Decision**: Redis pub/sub (migrate to Kafka if needed).
- **Alternatives**: RabbitMQ (rejected: simpler not needed yet), Kafka (rejected: overkill at current scale)
- **Rationale**: Redis already in stack for caching. Pub/sub works for current volume. Kafka later when 50+ clinics.
- **Consequences**: Redis messages are not persisted. Use outbox pattern. Dead letter queue for failures.

## ADR-004: UUIDv7 over Auto-Increment IDs
- **Date**: 2026-07-12
- **Context**: Primary key strategy for distributed system.
- **Decision**: UUIDv7 (time-sortable UUIDs).
- **Alternatives**: Auto-increment (rejected: no merge safety), UUIDv4 (rejected: B-tree fragmentation)
- **Rationale**: Time-sortable = good index performance. No collisions. Merge-safe across instances.
- **Consequences**: 16-byte keys. Slightly larger indexes. Acceptable trade-off.

## ADR-005: FastAPI over Django REST Framework
- **Date**: 2026-07-12
- **Context**: Python web framework for V2.
- **Decision**: FastAPI (async-first, auto-docs, Pydantic validation).
- **Alternatives**: Django REST (rejected: heavy, synchronous), Flask (rejected: no native async)
- **Rationale**: FastAPI = async by default, automatic OpenAPI docs, Pydantic for validation, great WebSocket support, excellent performance.
- **Consequences**: Must use async DB driver (asyncpg, not psycopg2). Smaller ecosystem than Django but sufficient.

## ADR-006: JWT + OTP over Session Auth
- **Date**: 2026-07-12
- **Context**: Authentication method for staff and patients.
- **Decision**: JWT tokens with OTP verification. No passwords for staff (backward-compatible admin password).
- **Alternatives**: Session-based (rejected: stateful, harder to scale), OAuth2 (rejected: no external IdP needed)
- **Rationale**: JWT = stateless, easy to validate, works with mobile apps. OTP = no passwords to forget, secure enough for clinic staff.
- **Consequences**: Token refresh needed every 24h. OTP delivery requires SMS/WhatsApp service.

## ADR-007: Next.js over React SPA
- **Date**: 2026-07-12
- **Context**: Frontend framework for V2.
- **Decision**: Next.js (React with SSR, App Router).
- **Alternatives**: React SPA (rejected: SEO, slower initial load), SvelteKit (rejected: smaller ecosystem)
- **Rationale**: SSR for fast initial load. App Router for nested layouts. React ecosystem for component libraries. Great DX with TypeScript.
- **Consequences**: Higher server resource usage than SPA. Worth it for UX.

## ADR-008: Alembic over Raw SQL Migrations
- **Date**: 2026-07-12
- **Context**: Database migration tool.
- **Decision**: Alembic with SQLAlchemy 2.0.
- **Alternatives**: Raw SQL scripts (rejected: manual, error-prone), Flyway (rejected: Java ecosystem)
- **Rationale**: Alembic integrates with SQLAlchemy. Auto-generation of migrations. Python-native. Industry standard for Python projects.
- **Consequences**: Must maintain migration chain. Never edit existing migrations.
