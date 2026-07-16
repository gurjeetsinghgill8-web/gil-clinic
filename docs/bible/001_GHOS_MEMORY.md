# 001 — GHOS MEMORY

*AI Context File — Every agent reads this first.*
*Last updated: 2026-07-12*

---

## Project State
- **Phase**: V1 complete (104 modules, 67 SQLite tables) + V2 Architecture designed
- **V1 Status**: Fully functional Streamlit app with 43 utilities + 61 pages
- **V2 Status**: Architecture defined, documentation suite (GHOS Bible) under construction
- **Current Task**: Building GHOS Bible — 20 comprehensive documentation files

## Architecture Summary
- **Pattern**: Modular Monolith → Future Microservices
- **Layers**: domain/ → application/ → infrastructure/ → presentation/
- **13 Engines**: Identity, Patient, Queue, Workflow, Clinical, Billing, Inventory, Appointment, Communication, Notification, AI, Analytics, Audit/Security
- **16-week migration plan** from V1 Streamlit to V2

## Key Technical Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Architecture | Modular Monolith | Single developer, AI-assisted, simple deploy |
| Backend | FastAPI | Async, auto-docs, Python ecosystem |
| Frontend | Next.js | React, SSR, great DX |
| Database | PostgreSQL | Reliability, JSONB, full-text search |
| Cache/Events | Redis | Pub/sub, queue, fast |
| Background Jobs | Celery | Mature, Redis broker |
| Auth | JWT + OTP | No passwords for staff |
| AI Providers | OpenAI/Gemini/Ollama | Provider-agnostic via AI Gateway |
| Migration | 16-week phased | Parallel run, cutover |

## Active Development Patterns
- All new code follows Clean Architecture (domain → application → infrastructure → presentation)
- Events are always published after DB commit (outbox pattern)
- All PII is encrypted using AES-256-GCM before storage
- Every API endpoint has rate limiting and audit logging
- Frontend components are in the design system before use

## Repository Conventions
- Python: 3.11+, type hints required, black formatting
- Commits: conventional commits (feat:, fix:, docs:, refactor:)
- Testing: pytest, 90%+ coverage target
- AI prompts live in MASTER_PROMPTS.md, not in code comments
- Business rules live in BUSINESS_RULES.md, not hardcoded
- Events are cataloged in EVENTS.md before implementation

## Current Milestone
- **GHOS Bible**: 20 documents covering architecture, rules, events, prompts, design, ops
- **Next**: V2 implementation begins — Queue Engine first

## Document Classification

Documents are classified by lifecycle stage:

| Category | Documents | Description |
|---|---|---|
| **CORE** | 000-014 | Foundation documents. Rarely change. Define system invariants. |
| **ACTIVE** | 015-025 | Current development. May change during V2 implementation. |
| **DEPRECATED** | (none) | Obsolete documents. Kept for history, not used by AI. |
| **EXPERIMENTAL** | (none) | Draft documents for future features. Not for production AI agents. |

### CORE Documents (000-014)

These documents define the invariant rules of the system. AI agents MUST read these before any task:
- **000** PROJECT_DNA - Vision, philosophy, language
- **001** GHOS_MEMORY - This file, current state
- **002** BUSINESS_RULES - 188 rules across all domains
- **003** SYSTEM_ARCHITECTURE - Layers, dependencies, event bus
- **004** DOMAIN_MODEL - Entities, aggregates, relationships
- **005** DATABASE - Complete schema, migrations
- **006** EVENTS - 400+ domain events
- **007** STATE_MACHINE - Valid state transitions
- **008** API - REST + WebSocket endpoints
- **009** DESIGN_SYSTEM - Colors, typography, components
- **010** UX_RULEBOOK - Interaction patterns
- **011** AI_RULEBOOK - Code gen quality rules
- **012** MASTER_PROMPTS - 500+ AI prompts
- **013** DECISION_LOG - 8 ADRs
- **014** SECURITY - Auth, RBAC, encryption

### ACTIVE Documents (015-025)

These documents are under active development and may change during V2 implementation:
- **015** DEPLOYMENT - Docker, CI/CD
- **016** TESTING - Test strategy
- **017** RELEASE - Versioning
- **018** CHANGELOG - Version history
- **019** FUTURE - Roadmap
- **020** ERROR_CATALOG - Error codes (98 defined)
- **021** LANGUAGE_AND_TERMINOLOGY - Naming conventions
- **022** DEPENDENCY_GRAPH - Engine dependencies
- **023** CAPABILITY_MATRIX - Role permissions
- **024** CONFIGURATION - Settings catalog
- **025** FEATURE_FLAGS - Tier features

## Current Milestone
- **GHOS Bible**: 26 documents (000-025) covering architecture, rules, events, prompts, errors, design, ops
- **28 new documents added in this cycle**: ERROR_CATALOG, LANGUAGE, DEPENDENCY_GRAPH, CAPABILITY_MATRIX, CONFIGURATION, FEATURE_FLAGS
- **Next**: V2 implementation begins - Queue Engine first
