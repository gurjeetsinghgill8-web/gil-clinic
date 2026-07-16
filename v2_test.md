# GHOS Version 2 Architecture Document

*AI-First Hospital Operating System for India*
*Reference: V1 Streamlit (104 modules, 67 DB tables)*
*Date: 2026-07-12*

---

## 1. Domain Architecture

### Core Principle

Hospital is composed of **Engines**, not pages.
Each engine is an independent domain service with its own database schema,
API surface, event contracts, and lifecycle.
Engines communicate exclusively through events -- never through direct
imports or shared state.

### The 13 Engines

| Domain / Engine | Responsibility | V1 Source |
|---|---|---|
| **Identity Engine** | Users, roles, permissions, auth (JWT+OTP), staff | users, rbac_roles, hr_staff tables; utils/rbac.py | ok this works
