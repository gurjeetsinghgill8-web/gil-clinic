# 025 - FEATURE FLAGS

*Complete catalog of feature flags across all tiers.*
*AI agents must respect these flags for UI visibility, API access, and license enforcement.*

---

## Tier Definitions

| Tier | Code | Description | Monthly Price (INR) |
|---|---|---|---|
| Free | FREE | Basic clinic operations, up to 100 patients/month | 0 |
| Starter | STARTER | Growing clinic, up to 500 patients/month | 999 |
| Professional | PRO | Full-featured, unlimited patients | 2999 |
| Enterprise | ENTERPRISE | Multi-clinic, custom integrations | Custom |
| Experimental | EXPERIMENTAL | Beta features, not for production | N/A |

---

## Feature Flag States

| State | Description |
|---|---|
| ENABLED | Visible and usable |
| DISABLED | Hidden from UI, blocked at API |
| BETA | Visible with badge, usable |
| COMING_SOON | Visible but disabled, shows coming soon |
| HIDDEN | Not visible at all in this tier |
| EXPERIMENTAL | Visible only with dev mode |

---

## Feature Flag Matrix

| # | Feature | FREE | STARTER | PRO | ENTERPRISE | EXPERIMENTAL |
|---|---|---|---|---|---|---|
| 1 | Patient Registration | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 2 | Patient Search | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 3 | Basic Queue Management | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 4 | Token Display Board | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 5 | Department Management | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 6 | Doctor Dashboard | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 7 | Basic Reports | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 8 | Patient History | DISABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 9 | Bulk Patient Import | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 10 | Patient Export | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 11 | WhatsApp Notifications | DISABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 12 | SMS Notifications | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 13 | Email Notifications | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 14 | Voice Call (Critical) | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 15 | AI Diet Plan | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 16 | AI Report Explainer | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 17 | AI Triage | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 18 | AI Voice Agent | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 19 | AI Prescription Suggest | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 20 | Appointment Booking | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 21 | Online Booking Portal | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 22 | Inventory Management | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 23 | Pharmacy Dispensing | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 24 | GST Billing | DISABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 25 | Insurance Claims | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 26 | Multi-Branch Support | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 27 | Custom Branding | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 28 | Audit Logs | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 29 | Advanced Analytics | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 30 | API Access | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 31 | Webhooks | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 32 | Priority Support | DISABLED | DISABLED | DISABLED | ENABLED | DISABLED |
| 33 | Dark Mode | ENABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 34 | PWA Offline Mode | DISABLED | ENABLED | ENABLED | ENABLED | ENABLED |
| 35 | IPD Management | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 36 | Lab Integration | DISABLED | DISABLED | ENABLED | ENABLED | ENABLED |
| 37 | Radiology Integration | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 38 | HR & Payroll | DISABLED | DISABLED | DISABLED | ENABLED | ENABLED |
| 39 | Compliance Reports | DISABLED | DISABLED | DISABLED | ENABLED | DISABLED |
| 40 | Firewatch (beta) | DISABLED | DISABLED | DISABLED | DISABLED | ENABLED |

---

## Flag Format in Code



## Flag Evaluation Order

1. License tier (highest priority)
2. User role override
3. Environment override (dev/staging/prod)
4. Default flag state

## Database Schema


