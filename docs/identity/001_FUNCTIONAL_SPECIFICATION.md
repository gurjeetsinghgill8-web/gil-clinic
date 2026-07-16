# 001 — Identity Engine: Functional Specification

*Foundation engine for the GHOS platform.*
*Zero dependencies — every other engine depends on Identity.*

---

## 1. Purpose

The Identity Engine manages all users, roles, permissions, authentication, and authorization across the GHOS platform. It is the first engine built because every other engine depends on it for access control.

## 2. Scope

### In Scope
- Staff user management (CRUD)
- Role-based access control (RBAC)
- Permission matrix: {resource, action} per role
- PIN authentication (4-6 digits, bcrypt hash)
- OTP authentication (6-digit, 5-min expiry)
- Password authentication (admin, backward compatible)
- JWT token management (access + refresh tokens)
- Session management (multi-device, device trust)
- Account lockout policy (5 failures = 30-min lock)
- Event publishing (USER_CREATED, USER_LOGIN, etc.)
- Default seed users on first launch
- Department-scoped access

### Out of Scope
- Patient-facing authentication (handled by Patient Engine)
- OAuth / SSO / Passkeys (future extraction)
- Biometric authentication (future)
- External identity provider integration (future)
- Passwordless magic links (future)

## 3. Actors

| Actor | Description | Level |
|---|---|---|
| ADMIN | Full system access, manage users and roles | 100 |
| MANAGER | Operational management, staff oversight | 80 |
| DOCTOR | Clinical consultation, patient care | 60 |
| NURSE | Patient care support | 50 |
| RECEPTIONIST | Front desk, patient registration | 40 |
| TECHNICIAN | Test / lab operations | 40 |
| PHARMACIST | Pharmacy operations | 40 |
| LAB_TECH | Lab sample processing | 40 |
| RADIOLOGIST | Imaging operations | 40 |

## 4. User Stories

| ID | Story | Priority |
|---|---|---|
| US-IDN-01 | As an Admin, I can create staff users with roles so they can access the system | CRITICAL |
| US-IDN-02 | As a staff member, I can log in with my PIN so I can start my shift quickly | CRITICAL |
| US-IDN-03 | As a staff member, I can request OTP when I forget my PIN | HIGH |
| US-IDN-04 | As an Admin, I can assign/change roles so staff access is correct | HIGH |
| US-IDN-05 | As an Admin, I can deactivate staff who no longer work here | HIGH |
| US-IDN-06 | As a staff member, I can change my PIN for security | MEDIUM |
| US-IDN-07 | As an Admin, I can view all active sessions and revoke suspicious ones | HIGH |
| US-IDN-08 | As a staff member, I am locked out after 5 failed attempts | CRITICAL |
| US-IDN-09 | As an Admin, I can unlock a locked account | MEDIUM |
| US-IDN-10 | As a system, I can publish events so other engines react to identity changes | CRITICAL |

## 5. Business Rules

| Rule ID | Rule | Priority | Reference |
|---|---|---|---|
| IDN-001 | Staff login via OTP or PIN. No passwords for staff. | HIGH | 002_BUSINESS_RULES.md |
| IDN-002 | Admin login via OTP + password (backward compatible with V1). | HIGH | 002_BUSINESS_RULES.md |
| IDN-003 | PIN must be 4-6 numeric digits. | MEDIUM | 002_BUSINESS_RULES.md |
| IDN-004 | Roles: Admin, Doctor, Receptionist, Technician, Nurse, Manager, Pharmacist, Lab Tech. | HIGH | 002_BUSINESS_RULES.md |
| IDN-005 | Permission check on every API call. | CRITICAL | 002_BUSINESS_RULES.md |
| IDN-006 | Role hierarchy: Admin > Manager > Doctor > Staff. | HIGH | 002_BUSINESS_RULES.md |
| IDN-007 | Staff can access only assigned departments. | HIGH | 002_BUSINESS_RULES.md |
| IDN-008 | Default seed users created when table empty. | MEDIUM | 002_BUSINESS_RULES.md |
| AUD-006 | Failed login attempts > 5 = account lockout 30 min. | HIGH | 002_BUSINESS_RULES.md |
| AUD-007 | Session timeout after 15 min of inactivity. | MEDIUM | 002_BUSINESS_RULES.md |

## 6. Functional Requirements

| FR ID | Requirement | Business Rule |
|---|---|---|
| FR-01 | User must have: id (UUIDv7), username, full_name, role, department, pin_hash, phone, is_active | IDN-001, IDN-004 |
| FR-02 | PIN must be validated as 4-6 numeric digits before hashing | IDN-003 |
| FR-03 | PIN stored as bcrypt hash, never plaintext | IDN-001 |
| FR-04 | OTP is 6-digit numeric, generated randomly, stored as hash | IDN-001 |
| FR-05 | OTP expires after 300 seconds (5 minutes) | IDN-001 |
| FR-06 | Max 5 OTP verification attempts before 30-min lockout | AUD-006 |
| FR-07 | JWT access token expires after 24 hours | IDN-001 |
| FR-08 | Refresh token expires after 7 days | IDN-001 |
| FR-09 | Session timeout after 15 minutes of inactivity | AUD-007 |
| FR-10 | Account lockout automatically unlocks after 30 minutes | AUD-006 |
| FR-11 | Admin can unlock locked accounts manually | AUD-006 |
| FR-12 | Roles have hierarchy_level for permission inheritance | IDN-006 |
| FR-13 | Permissions are {resource, action} tuples per role | IDN-005 |
| FR-14 | Default-deny: no access unless explicitly granted | IDN-005 |
| FR-15 | Department-scoped: non-admin users access only their dept | IDN-007 |
| FR-16 | Seed 8 default users when identity.user table is empty | IDN-008 |
| FR-17 | Publish events on user create, login, OTP events, lockout | IDN-005 |
| FR-18 | Support multiple active sessions per user (multi-device) | AUD-007 |

## 7. Non-Functional Requirements

| NFR ID | Requirement | Target |
|---|---|---|
| NFR-01 | Authentication response time | < 200ms p95 |
| NFR-02 | OTP delivery latency | < 5 seconds |
| NFR-03 | Token validation overhead | < 5ms per request |
| NFR-04 | Concurrent login support | 1000 concurrent |
| NFR-05 | Account lockout precision | < 1 second |
| NFR-06 | Audit log write latency | < 50ms |
| NFR-07 | Password/PIN hash algorithm | bcrypt (cost=12) |
| NFR-08 | Token signing algorithm | RS256 (2048-bit key) |
| NFR-09 | Encryption standard | AES-256-GCM |
| NFR-10 | Uptime | 99.9% |

## 8. Authentication Flow

```
                   PIN FLOW                          OTP FLOW
                   ========                          ========

 Staff enters PIN                    Staff requests OTP
        |                                  |
        v                                  v
 Validate format (4-6 digits)       Generate 6-digit OTP
        |                                  |
        v                                  v
 Hash input PIN                      Store OTP hash in DB
        |                                  |
        v                                  v
 Compare with stored hash            Send OTP via Communication Engine
        |                                  |
        v                                  v
 Match?                              Staff enters OTP
  YES -> Issue JWT                       |
  NO  -> Increment attempts              v
         Lock if >= 5 failures     Verify OTP hash + expiry
                                           |
                                           v
                                     Valid + not expired?
                                      YES -> Issue JWT + clear OTP
                                      NO  -> Increment failures
                                             Lock if >= 5
```

## 9. Authorization Model (RBAC)

```
User --> Role --> Permissions

 Permission = {resource, action}

 Role hierarchy:
   ADMIN (100)  -- inherits all
   MANAGER (80) -- inherits Doctor + Staff
   DOCTOR (60)  -- inherits Staff
   NURSE (50)   -- inherits Staff
   STAFF (40)   -- base level

 Department scope:
   Admin    -> ALL departments
   Manager  -> assigned departments
   Doctor   -> assigned departments
   Staff    -> assigned departments
```

## 10. PIN Policy

| Property | Value |
|---|---|
| Length | 4-6 numeric digits |
| Hash algorithm | bcrypt (cost=12) |
| Storage | Hashed only, never plaintext |
| Validation | Digits only, no letters/special chars |
| Change | Requires old PIN verification |
| Reset | Admin can reset via OTP to registered phone |
| Max attempts before lockout | 5 |
| Lockout duration | 30 minutes |

## 11. OTP Policy

| Property | Value |
|---|---|
| Length | 6 numeric digits |
| Generation | Cryptographically secure random |
| Expiry | 300 seconds (5 minutes) |
| Storage | SHA-256 hash (not plaintext) |
| Max attempts | 5 before account lockout |
| Resend cooldown | 30 seconds |
| Delivery | Via Communication Engine (SMS/WhatsApp) |
| Rate limit | 3 OTP requests per 10 minutes per user |

## 12. Session Policy

| Property | Value |
|---|---|
| Max sessions per user | 5 (simultaneous) |
| Access token expiry | 24 hours |
| Refresh token expiry | 7 days |
| Inactivity timeout | 15 minutes |
| Device tracking | device_id, device_name, user_agent |
| Revocation | Admin can revoke any session |
| Automatic cleanup | Expired sessions cleaned every hour |
| Refresh token rotation | New refresh token issued on each refresh |

## 13. Account Lock Rules

| Condition | Action | Recovery |
|---|---|---|
| 5 failed PIN attempts | Lock 30 minutes | Wait or admin unlock |
| 5 failed OTP attempts | Lock 30 minutes | Wait or admin unlock |
| Account inactive 90 days | Auto-disable | Admin reactivation |
| Suspicious IP detected | Temporary lock (15 min) | OTP verification |

## 14. Password/PIN Reset Flow

1. Staff requests "Forgot PIN"
2. System sends OTP to registered phone
3. Staff enters OTP
4. System verifies OTP
5. Staff enters new PIN (4-6 digits, twice)
6. System hashes and stores new PIN
7. System publishes PIN_CHANGED event
8. System logs audit entry

## 15. Security Requirements

| SR ID | Requirement | Standard |
|---|---|---|
| SR-01 | All passwords/PINs hashed with bcrypt (cost=12) | OWASP |
| SR-02 | OTP stored as SHA-256 hash | OWASP |
| SR-03 | JWT signed with RS256 (2048-bit RSA key) | RFC 7519 |
| SR-04 | TLS 1.3 for all API traffic | OWASP |
| SR-05 | Rate limiting on all auth endpoints | OWASP |
| SR-06 | SQL injection prevention via parameterized queries | OWASP |
| SR-07 | XSS prevention via Content-Security-Policy | OWASP |
| SR-08 | CORS restricted to known origins | OWASP |
| SR-09 | Secrets in environment variables, never in code | OWASP |
| SR-10 | Account enumeration prevention (generic error messages) | OWASP |

## 16. Audit Requirements

| AR ID | Event | Data Logged |
|---|---|---|
| AR-01 | User created | actor, new_user_id, role, timestamp |
| AR-02 | User updated | actor, changed_fields, timestamp |
| AR-03 | User disabled | actor, target_user, reason, timestamp |
| AR-04 | Login success | user_id, ip_address, device, timestamp |
| AR-05 | Login failure | user_id, ip_address, attempt_count, timestamp |
| AR-06 | Account locked | user_id, reason, timestamp |
| AR-07 | Account unlocked | actor, target_user, timestamp |
| AR-08 | PIN changed | user_id, timestamp |
| AR-09 | Role assigned | actor, target_user, new_role, timestamp |
| AR-10 | Session revoked | actor, target_user, device, timestamp |

## 17. Error Mapping

| Error Code | Condition | HTTP Status | User Message |
|---|---|---|---|
| IDENTITY_001 | Invalid PIN format | 400 | PIN 4-6 digits ka hona chahiye |
| IDENTITY_002 | Account locked | 423 | 5 failures, 30 min lock |
| IDENTITY_003 | Invalid credentials | 401 | Galat PIN/password |
| IDENTITY_004 | OTP expired | 410 | OTP expire. Naya request karein |
| IDENTITY_005 | Max OTP attempts | 429 | Max attempts. 30 min wait |
| IDENTITY_006 | Unauthorized | 403 | Permission nahi hai |
| IDENTITY_007 | Session expired | 401 | Session expire. Phir login karein |
| IDENTITY_008 | User not found | 404 | User nahi mila |
| IDENTITY_009 | Duplicate username | 409 | Username already exists |
| IDENTITY_010 | Role not found | 404 | Role exist nahi karta |
| IDENTITY_011 | Cannot delete last admin | 403 | Last admin delete nahi kar sakte |

## 18. Event Mapping

| Event | Trigger | Consumers |
|---|---|---|
| IDENTITY.USER_CREATED | Staff created | Audit, Analytics |
| IDENTITY.USER_UPDATED | Staff updated | Audit |
| IDENTITY.USER_DISABLED | Staff deactivated | Audit, Notification |
| IDENTITY.USER_LOGIN | Successful login | Audit, Analytics |
| IDENTITY.USER_LOGOUT | User logs out | Audit |
| IDENTITY.OTP_SENT | OTP requested | Audit |
| IDENTITY.OTP_VERIFIED | OTP validated | Audit |
| IDENTITY.TOKEN_REFRESHED | Token refreshed | Audit |
| IDENTITY.ROLE_ASSIGNED | Role changed | Audit, Queue |
| IDENTITY.LOGIN_FAILED | Failed attempt | Audit |
| IDENTITY.ACCOUNT_LOCKED | Account locked | Audit, Notification |
| IDENTITY.ACCOUNT_UNLOCKED | Account unlocked | Audit |
| IDENTITY.PIN_CHANGED | PIN reset | Audit |
| IDENTITY.SESSION_EXPIRED | Session timed out | Audit |
| IDENTITY.SECURITY_ALERT | Suspicious activity | Audit, Notification |

## 19. Acceptance Criteria

| AC ID | Criterion | Verified |
|---|---|---|
| AC-01 | Admin can create staff with role and department | [ ] |
| AC-02 | Staff can log in with 4-6 digit PIN | [ ] |
| AC-03 | Staff can request OTP for PIN reset | [ ] |
| AC-04 | 5 failed attempts lock account for 30 min | [ ] |
| AC-05 | JWT issued on successful auth expires in 24h | [ ] |
| AC-06 | Refresh token issued and works for 7 days | [ ] |
| AC-07 | Admin can deactivate and reactivate users | [ ] |
| AC-08 | Role assignment changes permissions immediately | [ ] |
| AC-09 | All auth endpoints rate limited | [ ] |
| AC-10 | All auth events published to event bus | [ ] |
| AC-11 | Seed users created when table empty | [ ] |
| AC-12 | Account enumeration not possible | [ ] |
| AC-13 | Session timeout after 15 min inactivity | [ ] |
| AC-14 | Admin can revoke any active session | [ ] |
| AC-15 | Multi-device login works (up to 5 sessions) | [ ] |
