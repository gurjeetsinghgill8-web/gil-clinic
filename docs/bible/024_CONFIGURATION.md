# 024 - CONFIGURATION

*Complete catalog of all configurable settings across all engines.*
*AI agents must read configuration from here, never hardcode values.*

---

## Configuration Pattern

All configuration follows this pattern:
- **Key**: Dot-separated path
- **Value**: Typed (string, integer, boolean, float, JSON)
- **Scope**: System / Clinic / Department / Doctor / Patient
- **Source**: Environment variables > Database > Defaults
- **Override**: Admin UI > API > Config file

---

## 1. General System Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| system.name | string | GHOS | System display name | System |
| system.timezone | string | Asia/Kolkata | Default timezone | System |
| system.max_login_attempts | int | 5 | Max failed login attempts | System |
| system.session_timeout_minutes | int | 15 | Idle session timeout | System |
## 2. Identity Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| identity.otp_length | int | 6 | OTP digit length | System |
| identity.otp_expiry_seconds | int | 300 | OTP validity duration | System |
| identity.otp_max_attempts | int | 5 | Max OTP verification attempts | System |
| identity.pin_length_min | int | 4 | Minimum PIN digits | System |
| identity.pin_length_max | int | 6 | Maximum PIN digits | System |
| identity.jwt_expiry_hours | int | 24 | JWT token validity | System |
| identity.jwt_refresh_expiry_days | int | 7 | Refresh token validity | System |
| identity.default_role | string | RECEPTIONIST | Default role | Clinic |
| identity.seed_admin_username | string | admin | Default admin | System |

## 3. Patient Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| patient.id_prefix | string | GHOS- | Patient ID prefix | System |
| patient.id_digit_length | int | 6 | Patient ID digit length | System |
| patient.phone_required | bool | true | Phone mandatory | Clinic |
| patient.minor_age_threshold | int | 18 | Guardian age threshold | System |
| patient.consent_required | bool | true | Consent mandatory | Clinic |
| patient.data_retention_days | int | 3650 | Retention (10 years) | System |

## 4. Queue Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| queue.max_waiting_per_dept | int | 50 | Max waiting per dept | Clinic |
| queue.auto_skip_minutes | int | 15 | Auto-skip timeout | Clinic |
| queue.call_attempts_before_skip | int | 3 | Attempts before skip | Clinic |
| queue.token_digit_length | int | 4 | Token digits | System |
| queue.emergency_priority | int | 1 | Emergency priority | Clinic |
| queue.vip_priority | int | 2 | VIP priority | Clinic |
| queue.normal_priority | int | 3 | Normal priority | Clinic |
| queue.refresh_interval_seconds | int | 5 | Display refresh | Clinic |

## 5. Workflow Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| workflow.visit_timeout_minutes | int | 1440 | Max visit (24h) | Clinic |
| workflow.auto_archive_days | int | 90 | Auto-archive after | Clinic |
| workflow.reopen_window_days | int | 30 | Reopen window | Clinic |
| workflow.emergency_fast_track | bool | true | Emergency bypass | Clinic |

## 6. Clinical Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| clinical.report_require_signature | bool | true | Doctor signature | Clinic |
| clinical.sample_collection_timeout_minutes | int | 120 | Sample timeout | Clinic |
| clinical.radiology_upload_timeout_hours | int | 24 | Upload timeout | Clinic |
| clinical.drug_interaction_threshold | int | 3 | Min meds for check | Clinic |
| clinical.pediatric_weight_required | bool | true | Weight for peds | Clinic |
| clinical.critical_value_alert | bool | true | Alert on critical | System |
## 7. Billing Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| billing.gst_enabled | bool | true | GST enabled | Clinic |
| billing.gst_default_rate | float | 18.0 | Default GST | Clinic |
| billing.invoice_prefix | string | INV- | Invoice prefix | Clinic |
| billing.discount_max_percentage | float | 100.0 | Max discount | Clinic |
| billing.partial_payment_allowed | bool | true | Partial payments | Clinic |
| billing.insurance_enabled | bool | false | Insurance claims | Clinic |
| billing.outstanding_alert_on_register | bool | true | Balance alert | Clinic |

## 8. Inventory Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| inventory.dispense_method | string | FEFO | Dispense method | Clinic |
| inventory.low_stock_alert_enabled | bool | true | Low stock alert | Clinic |
| inventory.expiry_alert_days | int | 30 | Expiry alert | Clinic |
| inventory.auto_purchase_order | bool | false | Auto PO | Clinic |
| inventory.cold_chain_tracking | bool | false | Cold tracking | Clinic |

## 9. Appointment Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| appointment.slot_duration_minutes | int | 15 | Slot duration | Doctor |
| appointment.max_per_day | int | 50 | Max per doctor | Doctor |
| appointment.cancel_window_minutes | int | 120 | Cancel window | Clinic |
| appointment.no_show_timeout_minutes | int | 15 | No-show timeout | Clinic |
| appointment.walk_in_allowed | bool | true | Walk-in allowed | Clinic |

## 10. Communication Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| communication.whatsapp_enabled | bool | true | WhatsApp primary | Clinic |
| communication.sms_fallback | bool | true | SMS fallback | Clinic |
| communication.email_enabled | bool | true | Email for reports | Clinic |
| communication.voice_call_enabled | bool | true | Voice for critical | Clinic |
| communication.curfew_start | string | 21:00 | Curfew start (9 PM) | Clinic |
| communication.curfew_end | string | 08:00 | Curfew end (8 AM) | Clinic |
| communication.consent_required | bool | true | Consent required | System |
| communication.max_retry_count | int | 3 | Max retries | System |

## 11. Notification Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| notification.push_enabled | bool | true | Push channel | Clinic |
| notification.browser_notification | bool | true | Browser fallback | Clinic |
| notification.sound_enabled | bool | true | Sound on notify | User |
| notification.vibration_enabled | bool | true | Vibration on notify | User |
| notification.auto_refresh_seconds | int | 5 | Polling interval | User |

## 12. AI Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| ai.provider_primary | string | openai | Primary AI provider | Clinic |
| ai.provider_fallback | string | gemini | Fallback AI provider | Clinic |
| ai.circuit_breaker_threshold | int | 3 | Failures for breaker | System |
| ai.circuit_breaker_timeout_seconds | int | 300 | Breaker reset | System |
| ai.context_window_limit | int | 8000 | Max tokens | System |
| ai.diet_plan_requires_approval | bool | true | Diet plan approval | Clinic |
| ai.report_explain_language | string | hi | Explain language | Clinic |
| ai.triage_enabled | bool | true | AI triage | Clinic |
| ai.voice_agent_enabled | bool | true | Voice agent | Clinic |

## 13. Analytics Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| analytics.cache_ttl_seconds | int | 30 | Dashboard cache | System |
| analytics.max_date_range_days | int | 365 | Max date range | System |
| analytics.export_formats | string | PDF,CSV,XLSX | Export formats | Clinic |

## 14. Audit Configuration

| Key | Type | Default | Description | Scope |
|---|---|---|---|---|
| audit.retention_years | int | 7 | Audit log retention | System |
| audit.chain_verification_enabled | bool | true | Hash chain check | System |
| audit.chain_verify_schedule | string | daily | Verify frequency | System |

---
## Environment Variables

| Variable | Maps to Config Key |
|---|---|
| GHOS_DB_URL | system.database_url |
| GHOS_REDIS_URL | system.redis_url |
| GHOS_JWT_SECRET | identity.jwt_secret |
| GHOS_ENCRYPTION_KEY | system.encryption_key |
| GHOS_AI_OPENAI_KEY | ai.openai_api_key |
| GHOS_AI_GEMINI_KEY | ai.gemini_api_key |
| GHOS_SMS_API_KEY | communication.sms_api_key |
| GHOS_WHATSAPP_API_KEY | communication.whatsapp_api_key |
| GHOS_EMAIL_API_KEY | communication.email_api_key |
| GHOS_STORAGE_BUCKET | system.storage_bucket |
| GHOS_LOG_LEVEL | system.log_level |
