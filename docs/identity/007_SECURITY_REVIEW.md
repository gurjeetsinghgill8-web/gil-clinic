# 007 — Identity Engine: Security Review

*Threat model, OWASP Top 10, and mitigation strategies.*

---

## 1. Threat Model

### 1.1 Assets

| Asset | Sensitivity | Consequence of Breach |
|---|---|---|
| PIN hash | HIGH | Account takeover |
| Password hash | HIGH | Admin account takeover |
| JWT signing key | CRITICAL | Forge any token |
| Session tokens | HIGH | Session hijacking |
| OTP codes | MEDIUM | Account takeover (with phone access) |
| User PII (phone, email) | MEDIUM | Privacy breach |
| Permission matrix | MEDIUM | Unauthorized privilege escalation |

### 1.2 Threat Actors

| Actor | Motivation | Capability |
|---|---|---|
| External attacker | Account takeover, data theft | Scans, brute force, phishing |
| Malicious insider | Privilege escalation | Has valid credentials |
| Compromised staff | Lateral movement | Valid session token |
| Third-party API | Abuse rate limits | Automated requests |

### 1.3 STRIDE Analysis

| Category | Threat | Mitigation |
|---|---|---|
| Spoofing | Brute force PIN guessing | Rate limit, lockout after 5 failures |
| Tampering | Modify permission matrix | RBAC enforced server-side, audit trail |
| Repudiation | Deny login action | ALL auth events logged to append-only audit |
| Info disclosure | Extract user list | Rate limiting on GET /users, pagination logs |
| DoS | Flood OTP endpoint | Rate limit: 3 OTP per 10 min per user |
| Elevation | Assign self admin role | ADMIN-only role mutation, audit check |

---

## 2. OWASP Top 10 Mitigations

| OWASP | Risk | Mitigation |
|---|---|---|
| A01 Broken Access Control | Staff accesses another dept's data | Department-scoped RBAC, default-deny |
| A02 Cryptographic Failures | PIN hash leaked | bcrypt (cost=12), salt per hash |
| A03 Injection | SQL injection via username | Parameterized queries (SQLAlchemy) |
| A04 Insecure Design | Session fixation | New session ID on every login |
| A05 Security Misconfiguration | Debug endpoints exposed | Separate config for dev/prod |
| A06 Vulnerable Components | Old library with CVE | Dependabot + monthly updates |
| A07 Auth Failures | Weak PIN "0000" | 4-6 digit validation (no repeats > 3 digits) |
| A08 Data Integrity | JWT forged | RS256 with 2048-bit key rotation |
| A09 Logging Failures | Logs missing crucial events | Each auth action logged with trace ID |
| A10 SSRF | Internal network scan | No URL fetching in identity engine |

---

## 3. JWT Token Security

| Property | Decision | Rationale |
|---|---|---|
| Algorithm | RS256 | Asymmetric — signing key not needed by verifiers |
| Key size | 2048-bit RSA | NIST recommended minimum |
| Key rotation | Every 90 days | Reduces exposure window |
| Payload | `{sub, role, session_id, iat, exp}` | Minimal — never include PII |
| Expiry | 24 hours (access), 7 days (refresh) | Balances UX with security |
| Storage | Access: memory; Refresh: httpOnly cookie | XSS-resistant |

### 3.1 Token Claims

```json
{
  "sub": "0190a1b2-...",
  "role": "DOCTOR",
  "session_id": "0190a1b3-...",
  "iat": 1720771200,
  "exp": 1720857600,
  "jti": "unique-token-id"
}
```

---

## 4. PIN & OTP Security

### 4.1 PIN

| Measure | Implementation |
|---|---|
| Storage | bcrypt hash, cost=12 |
| Input validation | 4-6 digits, reject if >3 consecutive identical digits |
| Rate limit | Max 5 attempts before 30-min lockout |
| Transmission | TLS 1.3 only |
| Never logged | PIN values never appear in logs |

### 4.2 OTP

| Measure | Implementation |
|---|---|
| Generation | `secrets.randbelow(10**6)` padded to 6 digits |
| Storage | SHA-256 hash, not plaintext |
| Expiry | 300 seconds, server-enforced |
| Max attempts | 5, then lockout |
| Resend throttle | 30-second cooldown |
| Rate limit | 3 requests per 10 minutes |

---

## 5. Session Security

| Measure | Implementation |
|---|---|
| Session ID | UUIDv7, unguessable |
| Max concurrent | 5 sessions per user |
| Inactivity timeout | 15 minutes |
| Device fingerprint | UA string + IP + device_id |
| Trust mechanism | Optional device trust after successful login |
| Revocation | Admin can revoke any session |
| Cleanup | Hourly cron deletes expired sessions |

---

## 6. Account Enumeration Prevention

**Bad response — DO NOT USE:**
```json
// Login failure
{"error": "User not found"}  // Reveals which usernames exist
// vs
{"error": "Invalid credentials"}  // Same for all failures
```

**Good response — USE THIS:**
```json
// Unknown username
{"error": {"code": "IDENTITY_003", "message": "Galat PIN/password"}}
// Wrong PIN for known user
{"error": {"code": "IDENTITY_003", "message": "Galat PIN/password"}}
```

All authentication failures return the **same error code** (IDENTITY_003) with the **same message** — whether the username exists or not, whether the PIN is wrong or the account doesn't exist.

---

## 7. API Security

| Endpoint | Rate Limit | Auth Required |
|---|---|---|
| POST /auth/pin | 10/min per IP | No |
| POST /auth/otp/request | 3/10min per user | No |
| POST /auth/otp/verify | 5/10min per user | No |
| POST /auth/refresh | 10/min per IP | No |
| POST /auth/logout | 10/min per user | Yes |
| GET /users | 30/min per user | Yes |
| POST /users | 10/min per admin | Yes |

---

## 8. Secrets Management

| Secret | Storage | Rotation |
|---|---|---|
| JWT private key | Env var `GHOS_JWT_PRIVATE_KEY` | 90 days |
| JWT public key | Env var `GHOS_JWT_PUBLIC_KEY` | 90 days |
| DB connection string | Env var `GHOS_DB_URL` | On credential change |
| Encryption key | Env var `GHOS_ENCRYPTION_KEY` | 180 days |
| Redis password | Env var `GHOS_REDIS_PASSWORD` | 90 days |

Never store secrets in:
- Source code
- Config files in repo
- Environment variables in CI logs
- Error messages / stack traces

---

## 9. Compliance Mapping

| Requirement | Standard | How Identity Meets It |
|---|---|---|
| Data encryption at rest | ISO 27001 | AES-256-GCM on PII columns |
| Access control | ISO 27001 | RBAC + department scope |
| Audit trail | ISO 27001 | All auth events logged |
| Least privilege | ISO 27001 | Default-deny permissions |
| Session management | HIPAA | 15-min timeout, max 5 sessions |
| Account lockout | HIPAA | 5 failures = 30-min lock |
| PIN complexity | HIPAA | 4-6 digits, no trivial patterns |

---

## 10. Penetration Test Checklist

| Test | Expected Result | Status |
|---|---|---|
| Brute force PIN (1000 attempts) | Locked after 5 | [ ] |
| Brute force OTP (1000 attempts) | Locked after 5 | [ ] |
| JWT token forgery (RS256→HS256 downgrade) | Rejected | [ ] |
| Replay old refresh token | Rejected (revoked) | [ ] |
| SQL injection in username field | Parameterized query prevents | [ ] |
| XSS in user profile fields | Sanitized by CSP + encoding | [ ] |
| CORS misconfiguration | Only known origins allowed | [ ] |
| Account enumeration via timing | Stable timing (hash then compare) | [ ] |
| Privilege escalation (self-role-assign) | Rejected, admin-only | [ ] |
| Session fixation | New session ID per login | [ ] |
