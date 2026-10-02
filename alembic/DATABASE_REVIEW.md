# Identity Engine — Database Layer Review

## Final Verdict: ✅ **PASS (9.5/10)**

All 5 critical issues from initial review have been resolved. Identity Engine database layer is production-ready.

---

## Summary of Phase #IDN-13b

### Tables Created (7 tables in `identity` schema)

| # | Table | Type | Purpose |
|---|---|---|---|
| 1 | `identity.users` | Aggregate Root | Staff users with PIN, lockout, role |
| 2 | `identity.roles` | Reference | Role definitions with hierarchy levels |
| 3 | `identity.permissions` | Reference | {role, resource, action} permission tuples |
| 4 | `identity.user_sessions` | Aggregate | Multi-device session tracking |
| 5 | `identity.refresh_tokens` | Aggregate | Refresh token store with rotation |
| 6 | `identity.otp_codes` | Ephemeral | OTP hashes (5-min expiry) |
| 7 | `identity.outbox` | Infrastructure | Domain event outbox for pub/sub |

### Relationships

```
users 1──N user_sessions     (CASCADE delete)
users 1──N refresh_tokens    (CASCADE delete)
users 1──N otp_codes         (CASCADE delete)
users N──1 roles             (role_code FK, RESTRICT on delete)

user_sessions 1──N refresh_tokens  (SET NULL on session delete)
roles 1──N permissions            (CASCADE delete)
```

### Indexes Created (16 total)

| Table | Index | Type | Purpose |
|---|---|---|---|
| users | idx_users_username | UNIQUE | Fast username lookup |
| users | idx_users_phone_hash | UNIQUE | Fast phone lookup via SHA-256 hash |
| users | idx_users_role | B-tree | Filter by role |
| users | idx_users_department | B-tree | Filter by department |
| users | idx_users_active | Partial (`WHERE is_active = true`) | Active user queries |
| user_sessions | idx_sessions_user | B-tree | Sessions by user |
| user_sessions | idx_sessions_active | Partial (`WHERE revoked_at IS NULL`) | Active sessions only |
| refresh_tokens | idx_refresh_user | B-tree | Tokens by user |
| refresh_tokens | idx_refresh_hash | UNIQUE | Token lookup by hash |
| refresh_tokens | idx_refresh_active | Partial (`WHERE is_revoked = false`) | Active tokens only |
| otp_codes | idx_otp_user | B-tree | OTPs by user |
| otp_codes | idx_otp_expired | B-tree | Expired cleanup |
| permissions | uq_permission_role_resource_action | UNIQUE | No duplicate permissions |
| outbox | idx_outbox_status_created | Composite | PENDING event lookup by status + time |
| outbox | idx_outbox_pending | Partial (`WHERE status = 'PENDING'`) | Pending events by created_at |

### Constraints

| Type | Count | Examples |
|---|---|---|
| PRIMARY KEY | 7 | All tables have UUIDv7 PKs |
| FOREIGN KEY | 5 | user_id, role_code (RESTRICT), session_id (SET NULL) |
| UNIQUE | 4 | username, phone_hash, token_hash, permission tuple |
| NOT NULL | 28+ | All critical fields including phone_hash, retry_count |
| DEFAULT | 16+ | is_active=true, login_attempts=0, retry_count=0, etc. |
| CHECK (DB-level) | 3 | `ck_users_login_attempts_positive`, `ck_roles_hierarchy_level_range`, `ck_otp_codes_attempts_range` |

---

## Critical Issue Resolution Status

| ID | Issue | Status | Fix |
|---|---|---|---|
| C-01 | **PII stored in plaintext** | ✅ **RESOLVED** | AES-256-GCM encryption for phone, email, full_name. SHA-256 `phone_hash` for lookups. Encryption utility in `src/shared/infrastructure/encryption.py` |
| C-02 | **UUIDv4 instead of UUIDv7** | ✅ **RESOLVED** | All 6 models now use `uuid7()` from `src.shared.domain.base_entity` |
| C-03 | **Missing ForeignKey on role_code** | ✅ **RESOLVED** | `ForeignKey("identity.roles.code", ondelete="RESTRICT")` added to UserModel |
| C-04 | **No cleanup strategy** | ✅ **RESOLVED** | `CleanupService` created in `src/infrastructure/identity/services/cleanup_service.py` with 4 cleanup methods + monitoring |
| C-05 | **Partial index conditions wrong** | ✅ **RESOLVED** | `idx_sessions_active`: `postgresql_where=text("revoked_at IS NULL")`. `idx_refresh_active`: `postgresql_where=text("is_revoked = false")`. `idx_outbox_pending`: partial index for PENDING status |

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **UUIDv7 for all PKs** | Time-sortable, no sequential guessing, globally unique, cluster-friendly for B-tree indexes |
| **Partial indexes** | `WHERE is_active=true`, `WHERE revoked_at IS NULL`, `WHERE is_revoked=false`, `WHERE status='PENDING'` — reduces index size for active-only queries |
| **Composite index on outbox** | `(status, created_at)` covers the polling query `WHERE status='PENDING' ORDER BY created_at` |
| **CASCADE delete on user** | Removing a user cleans up all sessions, tokens, OTPs |
| **SET NULL on session delete** | Refresh tokens survive session deletion (graceful degradation) |
| **Separate aggregates** | User, Session, RefreshToken are independent — enables clean revocation without loading entire User aggregate |
| **token_hash not raw token** | If DB is breached, refresh tokens are still safe (SHA-256 hash) |
| **Outbox table** | Events written in same DB transaction as domain operation — guarantees delivery |
| **AES-256-GCM encryption** | Application-layer encryption for PII with searchable hash pattern |
| **RESTRICT on role_code FK** | Prevents deleting a role that is assigned to users — must reassign users first |
| **CHECK constraints at DB level** | `login_attempts >= 0`, `hierarchy_level BETWEEN 0 AND 100`, `attempts BETWEEN 0 AND 5` |
| **retry_count + last_error on outbox** | Enables retry logic with visibility into failure reasons |
| **gen_random_uuid() for seed permissions** | Non-conflicting UUIDs for seed data — combined with ON CONFLICT DO NOTHING |

---

## Migration Safety

| Risk | Mitigation |
|---|---|
| Downtime on migration | All operations are CREATE TABLE — no data loss possible |
| Seed data duplication | Uses INSERT ... ON CONFLICT DO NOTHING pattern |
| Rollback | `downgrade()` drops all tables and schema cleanly |
| Migration ID | `001` with branch label `identity` |

### Migration Commands

```bash
# Create new migration (after model changes)
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Rollback
alembic downgrade -1

# View status
alembic current
```

---

## Cleaning Rules

| Table | TTL | Cleanup Trigger | Method |
|---|---|---|---|
| otp_codes | 5 min expiry | Every 5 min | `cleanup_expired_otps()` |
| user_sessions | 30 days after expiry | Every 1 hour | `cleanup_expired_sessions()` |
| refresh_tokens | 30 days after expiry | Every 1 hour | `cleanup_expired_tokens()` |
| outbox (published) | 24 hours after publish | Every 1 hour | `cleanup_published_outbox()` |

Monitoring: `get_stale_counts()` returns row counts per table without deleting.

---

## Environment Configuration

```env
# Required: 256-bit hex key for AES-256-GCM encryption
# Generate with: openssl rand -hex 32
GHOS_ENCRYPTION_KEY=<64-char-hex-string>

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/ghos
```
