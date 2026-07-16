# 005 — Identity Engine: Event Specification

*Identity publishes events only — never makes direct calls to downstream engines.*

---

## 1. Design Principle

**Identity Engine communicates via events ONLY.** When a login happens, Identity does NOT call the Queue Engine or Patient Engine directly. It publishes an event, and any interested engine consumes it asynchronously.

```
  Identity Engine          Event Bus            Queue Engine
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │ User Login  │────>│  IDENTITY.   │────>│  Handle      │
  │ Event       │     │  USER_LOGIN  │     │  Staff Login │
  └─────────────┘     └──────────────┘     └──────────────┘
```

---

## 2. Event Table: IDENTITY Domain

All event names use the format: `IDENTITY.{ENTITY}.{ACTION}`

| # | Event | Publisher | Consumers | Payload | Trigger |
|---|---|---|---|---|---|
| 01 | IDENTITY.USER.CREATED | IdentitySvc | AuditSvc, AnalyticsSvc | `{userId, username, role, department, timestamp}` | Staff created via API |
| 02 | IDENTITY.USER.UPDATED | IdentitySvc | AuditSvc | `{userId, changedFields[], timestamp}` | Staff profile updated |
| 03 | IDENTITY.USER.DISABLED | IdentitySvc | AuditSvc, NotificationSvc | `{userId, reason, timestamp}` | Staff deactivated |
| 04 | IDENTITY.USER.REACTIVATED | IdentitySvc | AuditSvc | `{userId, timestamp}` | Staff reactivated |
| 05 | IDENTITY.USER.LOGIN | IdentitySvc | AuditSvc, AnalyticsSvc | `{userId, sessionId, deviceId, ip, timestamp}` | Successful PIN/OTP/password login |
| 06 | IDENTITY.USER.LOGOUT | IdentitySvc | AuditSvc | `{userId, sessionId, timestamp}` | User logs out |
| 07 | IDENTITY.OTP.SENT | IdentitySvc | AuditSvc | `{userId, purpose, timestamp}` | OTP requested |
| 08 | IDENTITY.OTP.VERIFIED | IdentitySvc | AuditSvc | `{userId, purpose, timestamp}` | OTP validated successfully |
| 09 | IDENTITY.TOKEN.REFRESHED | IdentitySvc | AuditSvc | `{userId, oldTokenId, newTokenId, timestamp}` | Access token refreshed |
| 10 | IDENTITY.ROLE.ASSIGNED | IdentitySvc | AuditSvc, QueueSvc | `{userId, oldRole, newRole, timestamp}` | Role changed by admin |
| 11 | IDENTITY.AUTH.FAILED | IdentitySvc | AuditSvc | `{userId, method, attemptCount, timestamp}` | Failed login attempt |
| 12 | IDENTITY.AUTH.LOCKED | IdentitySvc | AuditSvc, NotificationSvc | `{userId, lockedUntil, timestamp}` | Account locked (5 failures) |
| 13 | IDENTITY.AUTH.UNLOCKED | IdentitySvc | AuditSvc | `{userId, unlockedBy, timestamp}` | Account unlocked (admin/expiry) |
| 14 | IDENTITY.PIN.CHANGED | IdentitySvc | AuditSvc | `{userId, timestamp}` | PIN changed by user or admin |
| 15 | IDENTITY.SESSION.EXPIRED | IdentitySvc | AuditSvc | `{userId, sessionId, reason, timestamp}` | Session timed out or expired |
| 16 | IDENTITY.SESSION.REVOKED | IdentitySvc | AuditSvc | `{userId, sessionId, revokedBy, timestamp}` | Session revoked by admin |
| 17 | IDENTITY.SECURITY.ALERT | IdentitySvc | AuditSvc, NotificationSvc | `{userId, alertType, details, timestamp}` | Suspicious activity detected |
| 18 | IDENTITY.DEVICE.TRUSTED | IdentitySvc | AuditSvc | `{userId, sessionId, deviceId, timestamp}` | Device marked as trusted |
| 19 | IDENTITY.DEVICE.UNTRUSTED | IdentitySvc | AuditSvc | `{userId, deviceId, timestamp}` | Device trust revoked |

---

## 3. Event Schema (CloudEvents 1.0)

All events follow the CloudEvents specification.

```json
{
  "specversion": "1.0",
  "id": "uuidv7-event-id",
  "source": "/api/v1/identity",
  "type": "IDENTITY.USER.LOGIN",
  "datacontenttype": "application/json",
  "subject": "0190a1b2-...",
  "time": "2026-07-12T10:00:00Z",
  "data": {
    "userId": "0190a1b2-...",
    "sessionId": "0190a1b3-...",
    "deviceId": "browser-chrome-123",
    "ip": "192.168.1.100",
    "timestamp": "2026-07-12T10:00:00Z"
  }
}
```

---

## 4. Event Patterns

| Pattern | How Identity Uses It |
|---|---|
| Fire-and-forget | Most events — USER_LOGIN, PIN_CHANGED, SESSION_EXPIRED |
| At-least-once delivery | Event bus guarantees delivery with retries |
| Outbox pattern | Events written to DB in same transaction, then published by outbox relay |
| Idempotent consumers | Events must be idempotent — consuming twice has same effect as once |

---

## 5. Event-to-Business-Rule Mapping

| Event | Business Rule(s) |
|---|---|
| IDENTITY.USER.CREATED | IDN-008 (seed users) |
| IDENTITY.USER.LOGIN | IDN-001, IDN-002 |
| IDENTITY.AUTH.LOCKED | AUD-006 |
| IDENTITY.ROLE.ASSIGNED | IDN-004, IDN-005, IDN-006 |
| IDENTITY.PIN.CHANGED | IDN-003 |
| IDENTITY.SESSION.EXPIRED | AUD-007 |

---

## 6. Outbox Table Design

Events are persisted in an outbox table as part of the same DB transaction as the domain operation.

```sql
CREATE TABLE identity.outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX idx_outbox_status ON identity.outbox(status) WHERE status = 'PENDING';
```

The outbox relay (background worker):
1. Reads PENDING events (ordered by created_at)
2. Publishes to Redis pub/sub
3. Marks as PUBLISHED
4. Cleans up after 24 hours

---

## 7. Events Not Generated by Identity

Identity does NOT publish events related to:
- Patient registration (Patient Engine → PATIENT.REGISTERED)
- Queue updates (Queue Engine → QUEUE.*)
- Billing (Billing Engine → BILLING.*)

Identity only publishes events about its own domain: users, sessions, authentication, roles, and permissions.
