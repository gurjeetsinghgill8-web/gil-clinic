# 000 — PROJECT DNA

## Name
**GHOS** — Gurjeet's Hospital Operating System

## Vision
The best AI-first Hospital Operating System for India.
Built by a single developer, powered by AI, designed for scale.

## Philosophy
- Hospital is composed of **Engines**, not pages.
- Engines communicate exclusively through events.
- Everything must be modular. Everything must be replaceable.
- Never build another Streamlit app. Build a healthcare platform.
- AI is not a feature — it is the foundation.
- India-first: designed for Indian hospitals, clinics, and regulations.

## Core Principles

1. **Domain-Driven Design** — Each engine is a bounded context.
2. **Event-Driven Architecture** — Services communicate via events, not direct calls.
3. **Clean Architecture** — Domain depends on nothing. Application depends on Domain. Infrastructure depends on Application.
4. **Modular Monolith First** — Start as modular monolith, extract microservices only when needed.
5. **AI-Native** — Every component is designed to be AI-generated, AI-tested, AI-maintained.
6. **Zero Dark Patterns** — Never ask same data twice. Never lose patient state. Never block the doctor.
7. **Security by Design** — PII encrypted at rest and in transit. Audit everything. Consent before processing.
8. **Offline Resilience** — Core clinical operations must work even with intermittent connectivity.

## Non-Negotiables

- Patient is always the aggregate root.
- Queue never goes negative.
- Every state transition is logged.
- No hardcoded secrets in code.
- No cross-schema foreign keys in DB.
- Every event has an immutable audit trail.
- No PII in logs or event payloads.
- Mobile-first UI. One-hand operation.
- Doctor typing must be minimized.
- Three-click rule: patient data never more than 3 clicks away.

## Product Language
- Always **Patient** (never Customer)
- Always **Receptionist** (never Operator)
- Always **Token** (never Ticket)
- Always **Doctor** (never Provider)
- Always **Clinic** (never Branch)
- Always **Test** (never Procedure)
- Always **Report** (never Result Document)

## Technology Stack
- **Frontend**: Next.js (React), React Native (Mobile)
- **Backend**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL (primary), Redis (cache/queue/events)
- **ORM**: SQLAlchemy 2.0 + Alembic migrations
- **Auth**: JWT + OTP (no passwords for staff)
- **Events**: Redis pub/sub (Kafka when scaled)
- **Background**: Celery + Redis broker
- **AI**: OpenAI / Gemini / Ollama (provider-agnostic)
- **Storage**: S3-compatible (object storage for reports)
- **Deployment**: Docker + Docker Compose (K8s when scaled)
