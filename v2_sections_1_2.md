# GHOS Version 2 Architecture Document

*AI-First Hospital Operating System for India*
*Reference: V1 Streamlit (104 modules, 67 DB tables)*
*Date: 2026-07-12*

---

## 1. Domain Architecture

### Core Principle

Hospital is composed of **Engines**, not pages.
Each engine is an independent domain service.
Engines communicate exclusively through events.

### The 13 Engines

| Domain / Engine | Responsibility | V1 Source |
|---|---|---|
| **Identity Engine** | Users, roles, permissions, auth, staff | users, rbac_roles, hr_staff |
| **Patient Engine** | Registration, demographics, PII | patients table; encryption.py |
| **Queue Engine** | Token gen, dept queues, status transitions | tests table; queue.py |
| **Workflow Engine** | Visit lifecycle, routing, state machine | Dept flows; get_available_actions() |
| **Clinical Engine** | Results, reports, prescriptions, vitals | lab_results, prescriptions tables |
| **Billing Engine** | Invoices, payments, GST, discounts | bills, gst_invoices; billing.py |
| **Inventory Engine** | Items, batches, stock, purchase orders | inventory_* tables; inventory.py |
| **Appointment Engine** | Slots, scheduling, reminders | appointments, time_slots |
| **Communication Engine** | Templates, multi-channel routing | whatsapp_templates; utils/whatsapp.py |
| **Notification Engine** | Event mapping, priority, push | push_notifications; push_notifications.py |
| **AI Engine** | LLM gateway, diet, report, triage, voice | all ai_*; utils/ai_*.py |
| **Analytics Engine** | Aggregations, reports, KPIs, ML | feedback_stats, system_metrics |
| **Audit & Security** | Audit log, encryption, consent, rights | audit_log_v2, consent_records |

### Bounded Context Relationships

- **Patient Engine** is the aggregate root -- all engines reference patient_id
- **Queue Engine** orchestrates Workflow Engine + Notification Engine
- **Billing Engine** consumes Patient + Clinical + Inventory
- **AI Engine** is a facade -- routes to AI providers
- **Communication Engine** is channel-agnostic
- **Audit Engine** is an observing context
