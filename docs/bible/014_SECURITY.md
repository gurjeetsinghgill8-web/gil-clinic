# 014 — SECURITY

*Security model, encryption, compliance, and data protection.*

---

## Authentication

- **Staff Login**: OTP-based (6-digit code sent to registered phone)
- **Admin Login**: OTP + password (backward compatible with V1)
- **PIN Option**: 4-6 digit PIN for quick access (stored as bcrypt hash)
- **Patient Portal**: One-click access via unique link (no password)
- **JWT**: RS256 signed tokens, 24-hour expiry, refresh token support
- **Rate Limit**: 5 OTP attempts = 30-minute lockout

## Authorization

- RBAC with hierarchical roles: Admin > Manager > Doctor > Staff
- Permission matrix: {resource, action} per role
- Department-scoped access for non-admin roles
- Permission check on every API call (middleware)
- Default-deny: no access unless explicitly granted

## Data Encryption

- **At Rest**: PII encrypted with AES-256-GCM using Fernet (Python cryptography library)
- **In Transit**: TLS 1.3 for all API traffic
- **Database**: Encrypted columns via application layer (not DB-level)
- **Backup**: Encrypted backup files with separate encryption key
- **Key Rotation**: Support for key rotation with versioned keys
- **Fields Encrypted**: name, phone, address, emergency_contact, medical_history

## Audit Trail

- Every data mutation logged: who, what, when, target
- Append-only: never modified or deleted
- Hash chaining for integrity verification
- 7-year retention (regulatory requirement)
- Separate PII access log (who accessed whose PII)
- All API requests logged (method, path, status, latency)

## Consent & Compliance

- Patient consent required before any data processing
- Consent types: registration, communication, data sharing, research
- Revocable: patient can withdraw consent anytime
- Data rights: export (PDF/JSON) and deletion (GDPR-style)
- IP logging for all admin/manager actions

## Infrastructure Security

- Secrets in environment variables or vault, never in code
- CORS restricted to known origins
- Rate limiting on all endpoints (1000 req/hr per user)
- SQL injection prevention via parameterized queries
- XSS prevention via Content-Security-Policy headers
- CSRF protection via double-submit cookie pattern
- Session timeout after 15 minutes of inactivity
