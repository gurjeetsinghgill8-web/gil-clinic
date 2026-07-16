# 003 — Identity Engine: API Specification

*OpenAPI-ready REST specification. Base path: `/api/v1/identity`*

---

## 1. Standards

| Property | Value |
|---|---|
| Base URL | `/api/v1/identity` |
| Format | JSON |
| Auth header | `Authorization: Bearer {jwt}` |
| Error format | `{"error": {"code": "IDENTITY_001", "message": "...", "details": {...}}}` |
| Pagination | `?page=1&per_page=20` → `{"data": [...], "meta": {"page": 1, "per_page": 20, "total": 100}}` |
| Idempotency | `Idempotency-Key` header on POST/PUT |
| Rate limit | `X-RateLimit-*` headers on all responses |

---

## 2. Authentication Endpoints

### 2.1 `POST /auth/pin` — PIN Login

Staff logs in using PIN.

**Request:**
```json
{
  "username": "receptionist",
  "pin": "1234"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": "0190a1b2-...",
    "username": "receptionist",
    "full_name": "Receptionist",
    "role": "RECEPTIONIST",
    "department": "Reception"
  },
  "session": {
    "id": "0190a1b3-...",
    "device_id": "browser-chrome-123",
    "expires_at": "2026-07-13T10:00:00Z"
  }
}
```

**Errors:** IDENTITY_001 (invalid PIN format), IDENTITY_002 (locked), IDENTITY_003 (wrong PIN)

**Audit:** AR-04 (success), AR-05 (failure), AR-06 (if locked)

---

### 2.2 `POST /auth/otp/request` — Request OTP

Staff requests OTP for login or PIN reset.

**Request:**
```json
{
  "username": "receptionist",
  "purpose": "login"
}
```

`purpose`: `login` | `pin_reset`

**Response (200):**
```json
{
  "message": "OTP sent to registered phone",
  "expires_in": 300
}
```

**Errors:** IDENTITY_008 (user not found), RATE_LIMIT_ERROR (>3 OTPs per 10 min)

**Audit:** AR-XX (OTP_SENT)

**Event:** IDENTITY.OTP_SENT

---

### 2.3 `POST /auth/otp/verify` — Verify OTP

Staff enters OTP to complete login.

**Request:**
```json
{
  "username": "receptionist",
  "otp": "482916"
}
```

**Response (200):** Same as PIN login response.

Redirects to PIN reset flow if `purpose=pin_reset`.

**Errors:** IDENTITY_004 (expired), IDENTITY_005 (max attempts), IDENTITY_002 (locked)

**Event:** IDENTITY.OTP_VERIFIED, IDENTITY.USER_LOGIN

---

### 2.4 `POST /auth/password` — Admin Password Login

Admin login with password (backward compatible).

**Request:**
```json
{
  "username": "admin",
  "password": "gurjas@123"
}
```

**Response (200):** Same as PIN login.

**Note:** Only ADMIN role allowed. Staff must use PIN/OTP.

---

### 2.5 `POST /auth/refresh` — Refresh Token

Exchange refresh token for new access token.

**Request:**
```json
{
  "refresh_token": "eyJ..."
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

**Errors:** IDENTITY_007 (expired), IDENTITY_003 (invalid)

**Event:** IDENTITY.TOKEN_REFRESHED

---

### 2.6 `POST /auth/logout` — Logout

Revoke current session and refresh token.

**Headers:** `Authorization: Bearer {jwt}`

**Request:**
```json
{}
```

**Response (200):** `{"message": "Logged out successfully"}`

**Event:** IDENTITY.USER_LOGOUT

---

## 3. User Management Endpoints

### 3.1 `GET /users` — List Users

**Role:** ADMIN, MANAGER

**Query:** `?role=DOCTOR&department=Cardiology&is_active=true&page=1&per_page=20`

**Response (200):**
```json
{
  "data": [
    {
      "id": "0190a1b2-...",
      "username": "dr.sharma",
      "full_name": "Dr. Sharma",
      "role": "DOCTOR",
      "department": "Cardiology",
      "phone": "9999999990",
      "is_active": true,
      "last_login": "2026-07-12T09:30:00Z",
      "created_at": "2026-07-01T00:00:00Z"
    }
  ],
  "meta": {"page": 1, "per_page": 20, "total": 5}
}
```

---

### 3.2 `POST /users` — Create User

**Role:** ADMIN

**Request:**
```json
{
  "username": "dr.sharma",
  "full_name": "Dr. Sharma",
  "role_code": "DOCTOR",
  "department": "Cardiology",
  "phone": "9999999990",
  "email": "dr.sharma@clinic.com"
}
```

**Response (201):** Full user object (no pin_hash returned)

**Errors:** IDENTITY_009 (duplicate username)

**Event:** IDENTITY.USER_CREATED

---

### 3.3 `GET /users/{id}` — Get User

**Role:** ADMIN, MANAGER, self

**Response (200):** Full user object

---

### 3.4 `PUT /users/{id}` — Update User

**Role:** ADMIN

**Request:** Partial update — send only changed fields.

```json
{
  "full_name": "Dr. Sharma Updated",
  "department": "Neurology"
}
```

**Event:** IDENTITY.USER_UPDATED

---

### 3.5 `DELETE /users/{id}` — Deactivate User

**Role:** ADMIN

**Note:** Soft-delete — sets `is_active=false`. Cannot delete last admin.

**Response (200):** `{"message": "User deactivated"}`

**Errors:** IDENTITY_011 (cannot delete last admin)

**Event:** IDENTITY.USER_DISABLED

---

### 3.6 `PUT /users/{id}/reactivate` — Reactivate User

**Role:** ADMIN

**Event:** IDENTITY.USER_REACTIVATED

---

## 4. Role Management Endpoints

### 4.1 `GET /roles` — List Roles

**Role:** ADMIN

**Response (200):** All roles with hierarchy_level

---

### 4.2 `PUT /users/{id}/role` — Assign Role

**Role:** ADMIN

**Request:**
```json
{
  "role_code": "DOCTOR"
}
```

**Event:** IDENTITY.ROLE_ASSIGNED

---

## 5. Session Management Endpoints

### 5.1 `GET /sessions` — List Active Sessions

**Role:** ADMIN (all users), MANAGER (dept users), self (own)

**Response:**
```json
{
  "data": [
    {
      "id": "0190a1b3-...",
      "user_id": "0190a1b2-...",
      "device_name": "Chrome 120 / Windows 11",
      "ip_address": "192.168.1.100",
      "last_activity": "2026-07-12T10:00:00Z",
      "is_trusted": true,
      "created_at": "2026-07-12T08:00:00Z"
    }
  ]
}
```

---

### 5.2 `DELETE /sessions/{id}` — Revoke Session

**Role:** ADMIN, self

**Event:** IDENTITY.SESSION_REVOKED

---

### 5.3 `DELETE /sessions` — Revoke All User Sessions

**Role:** ADMIN, self

**Request:**
```json
{
  "user_id": "0190a1b2-...",
  "exclude_current": true
}
```

Useful when password/PIN is changed or account compromised.

---

## 6. PIN Management Endpoints

### 6.1 `PUT /users/{id}/pin` — Change PIN

**Role:** self (requires old PIN)

**Request:**
```json
{
  "old_pin": "1234",
  "new_pin": "5678"
}
```

**Event:** IDENTITY.PIN_CHANGED

---

### 6.2 `POST /users/{id}/pin/reset` — Admin Reset PIN

**Role:** ADMIN

Generates temporary PIN, forces change on next login.

**Event:** IDENTITY.PIN_RESET

---

## 7. Permission Endpoints

### 7.1 `GET /permissions` — List All Permissions

**Role:** ADMIN

**Response:**
```json
{
  "data": [
    {"role": "DOCTOR", "resource": "patients", "action": "read", "granted": true},
    {"role": "DOCTOR", "resource": "patients", "action": "write", "granted": true}
  ]
}
```

---

### 7.2 `PUT /permissions` — Bulk Update Permissions

**Role:** ADMIN

**Request:**
```json
{
  "permissions": [
    {"role_code": "RECEPTIONIST", "resource": "patients", "action": "delete", "granted": false}
  ]
}
```

---

## 8. OTP Rate Limit Headers

Every OTP endpoint returns:

```
X-RateLimit-Limit: 3
X-RateLimit-Remaining: 2
X-RateLimit-Reset: 1636682400
```

---

## 9. Error Response Format

```json
{
  "error": {
    "code": "IDENTITY_002",
    "message": "Account locked. 30 minutes remaining.",
    "details": {
      "locked_until": "2026-07-12T10:30:00Z",
      "remaining_seconds": 1800
    },
    "trace_id": "abc-123-def"
  }
}
```

---

## 10. Full Endpoint Summary

| Method | Path | Role | Event | FR Ref |
|---|---|---|---|---|
| POST | /auth/pin | All | IDENTITY.USER_LOGIN | FR-01, FR-02, FR-03 |
| POST | /auth/otp/request | All | IDENTITY.OTP_SENT | FR-04, FR-05 |
| POST | /auth/otp/verify | All | IDENTITY.OTP_VERIFIED | FR-04, FR-05, FR-06 |
| POST | /auth/password | ADMIN | IDENTITY.USER_LOGIN | FR-01 |
| POST | /auth/refresh | All | IDENTITY.TOKEN_REFRESHED | FR-07, FR-08 |
| POST | /auth/logout | All | IDENTITY.USER_LOGOUT | FR-09, FR-18 |
| GET | /users | ADMIN, MGR | — | FR-01 |
| POST | /users | ADMIN | IDENTITY.USER_CREATED | FR-16 |
| GET | /users/{id} | ADMIN, MGR, self | — | FR-01 |
| PUT | /users/{id} | ADMIN | IDENTITY.USER_UPDATED | FR-01 |
| DELETE | /users/{id} | ADMIN | IDENTITY.USER_DISABLED | FR-01 |
| PUT | /users/{id}/reactivate | ADMIN | IDENTITY.USER_REACTIVATED | FR-01 |
| PUT | /users/{id}/role | ADMIN | IDENTITY.ROLE_ASSIGNED | FR-12, FR-13 |
| PUT | /users/{id}/pin | self | IDENTITY.PIN_CHANGED | FR-02, FR-03 |
| POST | /users/{id}/pin/reset | ADMIN | IDENTITY.PIN_RESET | FR-02, FR-03 |
| GET | /sessions | ADMIN, MGR, self | — | FR-09, FR-18 |
| DELETE | /sessions/{id} | ADMIN, self | IDENTITY.SESSION_REVOKED | FR-18 |
| DELETE | /sessions | ADMIN, self | IDENTITY.SESSION_REVOKED | FR-18 |
| GET | /roles | ADMIN | — | FR-12 |
| GET | /permissions | ADMIN | — | FR-13, FR-14 |
| PUT | /permissions | ADMIN | — | FR-13, FR-14 |
| POST | /audit/login-history | ADMIN | — | AR-04, AR-05 |
