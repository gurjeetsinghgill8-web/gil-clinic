# 022 — DEPENDENCY GRAPH

*Complete dependency map across all 13 engines.*
*AI agents must respect these dependencies during code generation, refactoring, and microservice extraction.*

---

## Core Principle

- **domain/ layer**: Engine A can import Engine B domain entities ONLY if B is a dependency
- **application/ layer**: Use cases orchestrate across dependencies
- **infrastructure/ layer**: Repositories depend on domain entities
- **Cross-engine communication**: Events ONLY (no direct imports)
- **NO circular dependencies** — enforced by CI/CD pipeline

## Dependency Matrix

```
Engine          IDN  PAT  QUE  WKF  CLN  BIL  INV  APP  COM  NOT  AI   ANL  AUD
──────          ───  ───  ───  ───  ───  ───  ───  ───  ───  ───  ───  ───  ───
Identity (IDN)  --   X    X    X    X    X    X    X    X    X    X    X    X
Patient (PAT)    Y   --    X    X    X    X    X    X    X    X    X    X    X
Queue (QUE)      Y    Y   --    Y    X    X    X    X    X    Y    X    X    Y
Workflow (WKF)   Y    Y    Y   --    X    X    X    X    X    Y    X    X    Y
Clinical (CLN)   Y    Y    Y    Y   --    X    X    X    X    Y    Y    X    Y
Billing (BIL)    Y    Y    X    Y    Y   --    Y    X    X    X    X    X    Y
Inventory (INV)  Y    X    X    X    X    Y   --    X    X    X    X    X    Y
Appoint. (APP)   Y    Y    Y    Y    X    X    X   --    X    Y    X    X    Y
Comm. (COM)      Y    Y    X    X    X    X    X    X   --    Y    X    X    Y
Notify (NOT)     Y    X    X    X    X    X    X    X    Y   --    X    X    Y
AI               Y    Y    X    X    Y    X    X    X    X    X   --    X    Y
Analytics (ANL)  Y    Y    Y    Y    Y    Y    Y    Y    Y    Y    Y   --    Y
Audit (AUD)      X    X    X    X    X    X    X    X    X    X    X    X   --
```

**Legend:** Y = Depends On | X = No Dependency | -- = Self

## Detailed Dependencies

### Identity Engine

- **Depends on**: Nothing
- **Depended by**: Patient, Queue, Workflow, Clinical, Billing, Inventory, Appointment, Communication, Notification, AI, Analytics
- **Why**: Foundation engine — users, roles, permissions needed everywhere
- **Extraction trigger**: First microservice candidate (Auth0/Keycloak replacement)

### Patient Engine

- **Depends on**: Identity
- **Depended by**: Queue, Workflow, Clinical, Billing, Appointment, Communication, AI, Analytics
- **Why**: Patient is the aggregate root — almost every operation references a patient
- **Extraction trigger**: Extract when patient volume exceeds 100K records

### Queue Engine

- **Depends on**: Identity, Patient, Workflow, Notification
- **Depended by**: Workflow, Clinical, Appointment, Analytics
- **Why**: Queue orchestrates token lifecycle; needs doctors, patients, state, alerts
- **Extraction trigger**: High-throughput extraction (>1000 req/s)

### Workflow Engine

- **Depends on**: Identity, Patient, Queue, Notification
- **Depended by**: Clinical, Billing, Appointment, Analytics
- **Why**: Visit state machine; transitions driven by Queue events
- **Extraction trigger**: Extract with Queue Engine

### Clinical Engine

- **Depends on**: Identity, Patient, Queue, Workflow, Notification, AI
- **Depended by**: Billing, Analytics
- **Why**: Central engine — needs doctor, patient, queue, visit state, AI suggestions, alerts
- **Extraction trigger**: Extract when lab/radiology volume grows

### Billing Engine

- **Depends on**: Identity, Patient, Workflow, Clinical, Inventory, Audit
- **Depended by**: Analytics
- **Why**: Needs patient info, visit context, clinical items, inventory prices
- **Extraction trigger**: Extract with Financial compliance needs

### Inventory Engine

- **Depends on**: Identity, Billing, Audit
- **Depended by**: Clinical, Billing
- **Why**: Needs staff, billing for payment, audit trail
- **Extraction trigger**: Extract when multi-location inventory needed

### Appointment Engine

- **Depends on**: Identity, Patient, Queue, Workflow, Notification
- **Depended by**: Analytics
- **Why**: Needs doctors, patients, queue position, visit creation, reminders
- **Extraction trigger**: Extract when online booking scales

### Communication Engine

- **Depends on**: Identity, Patient, Notification, Audit
- **Depended by**: Notification, AI
- **Why**: Needs sender identity, recipient, delivery channel, audit
- **Extraction trigger**: Extract when multi-channel at scale

### Notification Engine

- **Depends on**: Identity, Communication, Audit
- **Depended by**: Queue, Workflow, Clinical, Appointment, Analytics
- **Why**: Needs user preferences, delivery via Communication, audit logging
- **Extraction trigger**: Extract with dedicated Celery workers

### AI Engine

- **Depends on**: Identity, Patient, Clinical, Audit
- **Depended by**: Clinical, Analytics
- **Why**: Needs user context, patient data, clinical results, audit trail
- **Extraction trigger**: Extract when GPU compute needed

### Analytics Engine

- **Depends on**: ALL 12 other engines
- **Depended by**: None (sink engine)
- **Why**: Sink engine — aggregates data from every domain for reporting
- **Extraction trigger**: Reads from read replicas only

### Audit Engine

- **Depends on**: Nothing
- **Depended by**: All engines (via events)
- **Why**: Append-only log — receives events, never reads other engines
- **Extraction trigger**: Extract with immutable log storage

## Circular Dependency Rules

1. **Identity** — MUST have zero dependencies (foundation)
2. **Audit** — MUST have zero dependencies (observing context, event-sourced)
3. **Patient → Queue → Workflow** — Linear chain, no cycles
4. **Clinical → Billing** — One direction only. Billing uses events from Clinical
5. **AI → Clinical** — AI generates suggestions, Clinical consumes them. No synchronous calls
6. **Communication → Notification → Queue** — One-way event flow only

## Microservice Extraction Priority

Based on dependency graph, extraction order:

| Order | Engine | Reason |
|---|---|---|
| 1 | Identity | Zero dependencies, foundational |
| 2 | Audit | Zero dependencies, observing only |
| 3 | Patient | Only depends on Identity |
| 4 | Queue | Depends on Patient, Workflow, Notification |
| 5 | Notification | Many depend on it |
| 6 | Clinical | Central engine |
| 7 | Billing | Depends on many |
| 8 | Others | Based on scaling needs |