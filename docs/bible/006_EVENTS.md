# 006 — EVENT CATALOG

*Complete catalog of all domain events.*
*Organized by domain with publisher, consumer, and payload.*

---

## Event Naming Convention

Format: `{DOMAIN}.{ENTITY}.{ACTION}`
Examples: PATIENT.REGISTERED, QUEUE.TOKEN_CALLED, BILLING.PAYMENT_SUCCESS

## Event Flow Pattern

1. Domain aggregate changes state
2. Event published to event bus (Redis pub/sub)
3. All consumers receive event
4. Each consumer handles or ignores based on subscription
5. Dead letter queue catches failures

---

## 1. PATIENT Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| PATIENT.REGISTERED | PatientSvc | QueueSvc, AuditSvc, AnalyticsSvc, NotificationSvc | {patientId, name, phone, registeredAt} |
| PATIENT.UPDATED | PatientSvc | AuditSvc | {patientId, changedFields} |
| PATIENT.MERGED | PatientSvc | QueueSvc, ClinicalSvc, BillingSvc, AuditSvc | {survivorId, mergedId} |
| PATIENT.CONSENT_CHANGED | PatientSvc | CommunicationSvc, NotificationSvc | {patientId, consentGiven} |
| PATIENT.DATA_DELETED | PatientSvc | AuditSvc | {patientId, deletedAt} |
| PATIENT.EMERGENCY_CONTACT_UPDATED | PatientSvc | AuditSvc | {patientId, contactChanged} |

## 2. QUEUE Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| QUEUE.TOKEN_CREATED | QueueSvc | WorkflowSvc, AnalyticsSvc, AuditSvc | {token, patientId, dept, position} |
| QUEUE.TOKEN_CALLED | QueueSvc | WorkflowSvc, NotificationSvc, DisplaySvc | {token, patientId, dept, counter} |
| QUEUE.TOKEN_SKIPPED | QueueSvc | WorkflowSvc, AuditSvc | {token, patientId, dept, reason} |
| QUEUE.TOKEN_COMPLETED | QueueSvc | WorkflowSvc, AnalyticsSvc, AuditSvc | {token, patientId, dept, duration} |
| QUEUE.TOKEN_ABSENT | QueueSvc | WorkflowSvc, AuditSvc | {token, patientId, dept, attempts} |
| QUEUE.TOKEN_REQUEUED | QueueSvc | WorkflowSvc, AuditSvc | {token, patientId, dept, newPosition} |
| QUEUE.TOKEN_CANCELLED | QueueSvc | WorkflowSvc, NotificationSvc, AuditSvc | {token, patientId, reason} |
| QUEUE.DEPT_PAUSED | QueueSvc | WorkflowSvc, DisplaySvc | {dept, reason} |
| QUEUE.DEPT_RESUMED | QueueSvc | WorkflowSvc, DisplaySvc | {dept} |
| QUEUE.DOCTOR_CHANGED | QueueSvc | WorkflowSvc, DisplaySvc | {dept, oldDoctor, newDoctor} |
| QUEUE.COUNTER_CLOSED | QueueSvc | WorkflowSvc, DisplaySvc | {dept, counter, redirectTo} |

## 3. WORKFLOW Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| WORKFLOW.VISIT_CREATED | WorkflowSvc | QueueSvc, AnalyticsSvc, AuditSvc | {visitId, patientId, type} |
| WORKFLOW.VISIT_TRANSITIONED | WorkflowSvc | ClinicalSvc, BillingSvc, AnalyticsSvc, AuditSvc | {visitId, fromState, toState, actor} |
| WORKFLOW.VISIT_COMPLETED | WorkflowSvc | BillingSvc, AnalyticsSvc, AuditSvc | {visitId, duration} |
| WORKFLOW.VISIT_ARCHIVED | WorkflowSvc | AuditSvc | {visitId, archivedAt} |
| WORKFLOW.EMERGENCY_TRIGGERED | WorkflowSvc | QueueSvc, NotificationSvc, IdentitySvc | {visitId, patientId, priority} |

## 4. CLINICAL Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| CLINICAL.TEST_ORDERED | ClinicalSvc | QueueSvc, NotificationSvc, AuditSvc | {testId, patientId, testType} |
| CLINICAL.SAMPLE_COLLECTED | ClinicalSvc | WorkflowSvc, AuditSvc | {testId, collectedAt} |
| CLINICAL.LAB_STARTED | ClinicalSvc | WorkflowSvc, AuditSvc | {testId, startedAt} |
| CLINICAL.LAB_FINISHED | ClinicalSvc | WorkflowSvc, NotificationSvc, AuditSvc | {testId, isCritical} |
| CLINICAL.REPORT_READY | ClinicalSvc | NotificationSvc, CommunicationSvc, BillingSvc, AuditSvc | {reportId, patientId, testType, pdfUrl} |
| CLINICAL.REPORT_SIGNED | ClinicalSvc | WorkflowSvc, NotificationSvc, AuditSvc | {reportId, signedBy, signedAt} |
| CLINICAL.PRESCRIPTION_CREATED | ClinicalSvc | InventorySvc, BillingSvc, AuditSvc | {prescriptionId, items[]} |
| CLINICAL.VITALS_RECORDED | ClinicalSvc | AnalyticsSvc, AuditSvc | {vitalsId, patientId, values} |
| CLINICAL.CRITICAL_VALUE_ALERT | ClinicalSvc | NotificationSvc, IdentitySvc | {testId, value, doctorId} |

## 5. BILLING Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| BILLING.BILL_CREATED | BillingSvc | WorkflowSvc, AnalyticsSvc, AuditSvc | {billId, patientId, total} |
| BILLING.BILL_VOIDED | BillingSvc | InventorySvc, AnalyticsSvc, AuditSvc | {billId, reason} |
| BILLING.PAYMENT_STARTED | BillingSvc | AnalyticsSvc, AuditSvc | {billId, amount, method} |
| BILLING.PAYMENT_SUCCESS | BillingSvc | InventorySvc, WorkflowSvc, NotificationSvc, AnalyticsSvc, AuditSvc | {billId, amount, method, transactionId} |
| BILLING.PAYMENT_FAILED | BillingSvc | NotificationSvc, AnalyticsSvc, AuditSvc | {billId, amount, reason} |
| BILLING.PARTIAL_PAYMENT | BillingSvc | WorkflowSvc, AnalyticsSvc, AuditSvc | {billId, amount, balance} |
| BILLING.REFUND_INITIATED | BillingSvc | AuditSvc | {billId, amount, reason} |
| BILLING.REFUND_COMPLETED | BillingSvc | NotificationSvc, AnalyticsSvc, AuditSvc | {billId, amount, transactionId} |
| BILLING.GST_INVOICE_GENERATED | BillingSvc | CommunicationSvc, AuditSvc | {invoiceNo, patientId, pdfUrl} |
| BILLING.OUTSTANDING_REMINDER | BillingSvc | NotificationSvc, CommunicationSvc | {patientId, balance} |

## 6. INVENTORY Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| INVENTORY.STOCK_RECEIVED | InventorySvc | AuditSvc | {batchId, itemId, quantity} |
| INVENTORY.STOCK_DISPENSED | InventorySvc | BillingSvc, AuditSvc | {batchId, itemId, quantity, billRef} |
| INVENTORY.STOCK_ADJUSTED | InventorySvc | AuditSvc | {batchId, itemId, diff, reason} |
| INVENTORY.STOCK_RETURNED | InventorySvc | BillingSvc, AuditSvc | {batchId, itemId, quantity, billRef} |
| INVENTORY.LOW_STOCK_ALERT | InventorySvc | NotificationSvc, IdentitySvc | {itemId, currentQty, reorderLevel} |
| INVENTORY.BATCH_EXPIRING | InventorySvc | NotificationSvc, IdentitySvc | {batchId, itemId, expiryDate, daysLeft} |
| INVENTORY.BATCH_EXPIRED | InventorySvc | AuditSvc | {batchId, itemId, expiredQty} |
| INVENTORY.AUDIT_CREATED | InventorySvc | AuditSvc | {auditId, itemCount} |
| INVENTORY.AUDIT_COMPLETED | InventorySvc | AuditSvc | {auditId, varianceCount} |

## 7. APPOINTMENT Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| APPOINTMENT.SCHEDULED | AppointmentSvc | PatientSvc, AuditSvc | {appointmentId, patientId, doctorId, slot} |
| APPOINTMENT.CONFIRMED | AppointmentSvc | NotificationSvc, AuditSvc | {appointmentId, patientId} |
| APPOINTMENT.CANCELLED | AppointmentSvc | NotificationSvc, WorkflowSvc, AuditSvc | {appointmentId, reason} |
| APPOINTMENT.NO_SHOW | AppointmentSvc | AnalyticsSvc, AuditSvc | {appointmentId, patientId} |
| APPOINTMENT.CHECKED_IN | AppointmentSvc | QueueSvc, WorkflowSvc, AuditSvc | {appointmentId, patientId} |
| APPOINTMENT.COMPLETED | AppointmentSvc | AnalyticsSvc, AuditSvc | {appointmentId, duration} |
| APPOINTMENT.REMINDER_SENT | AppointmentSvc | CommunicationSvc, AuditSvc | {appointmentId, channel} |
| APPOINTMENT.SLOT_BLOCKED | AppointmentSvc | AuditSvc | {doctorId, slot, reason} |

## 8. COMMUNICATION Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| COMMUNICATION.MESSAGE_SENT | CommunicationSvc | NotificationSvc, AnalyticsSvc, AuditSvc | {messageId, channel, recipient, status} |
| COMMUNICATION.MESSAGE_DELIVERED | CommunicationSvc | NotificationSvc, AuditSvc | {messageId, channel, deliveredAt} |
| COMMUNICATION.MESSAGE_FAILED | CommunicationSvc | NotificationSvc, AuditSvc | {messageId, channel, error} |
| COMMUNICATION.MESSAGE_READ | CommunicationSvc | AnalyticsSvc, AuditSvc | {messageId, readAt} |
| COMMUNICATION.TEMPLATE_CREATED | CommunicationSvc | AuditSvc | {templateId, name, channel} |

## 9. NOTIFICATION Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| NOTIFICATION.PUSH_SENT | NotificationSvc | AnalyticsSvc, AuditSvc | {notificationId, userId, title} |
| NOTIFICATION.PUSH_DELIVERED | NotificationSvc | AnalyticsSvc, AuditSvc | {notificationId, deliveredAt} |
| NOTIFICATION.PUSH_OPENED | NotificationSvc | AnalyticsSvc, AuditSvc | {notificationId, openedAt} |
| NOTIFICATION.DEVICE_REGISTERED | NotificationSvc | AuditSvc | {deviceId, userId, platform} |
| NOTIFICATION.USER_PREFERENCE_UPDATED | NotificationSvc | AuditSvc | {userId, preferences} |

## 10. AI Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| AI.TRIAGE_REQUESTED | AISvc | QueueSvc, AuditSvc | {requestId, patientId, symptoms} |
| AI.TRIAGE_COMPLETED | AISvc | QueueSvc, NotificationSvc, AuditSvc | {requestId, priority, recommendation} |
| AI.DIET_PLAN_GENERATED | AISvc | ClinicalSvc, AuditSvc | {planId, patientId, approved} |
| AI.REPORT_EXPLAINED | AISvc | PatientSvc, AuditSvc | {requestId, reportId, explanation} |
| AI.PRESCRIPTION_SUGGESTED | AISvc | ClinicalSvc, AuditSvc | {requestId, suggestions[], confidence} |
| AI.VOICE_CALL_STARTED | AISvc | CommunicationSvc, AuditSvc | {callId, patientId} |
| AI.VOICE_CALL_COMPLETED | AISvc | ClinicalSvc, AuditSvc | {callId, summary} |
| AI.PROVIDER_FAILOVER | AISvc | IdentitySvc, AuditSvc | {failedProvider, fallbackProvider} |
| AI.CONTEXT_EXCEEDED | AISvc | AuditSvc | {requestId, contextSize} |

## 11. ANALYTICS Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| ANALYTICS.DASHBOARD_REFRESHED | AnalyticsSvc | AuditSvc | {dashboardId, metrics} |
| ANALYTICS.REPORT_GENERATED | AnalyticsSvc | CommunicationSvc, AuditSvc | {reportId, format, url} |
| ANALYTICS.ALERT_TRIGGERED | AnalyticsSvc | NotificationSvc, IdentitySvc, AuditSvc | {alertId, metric, value, threshold} |

## 12. AUDIT Domain Events

| Event | Publisher | Consumers | Payload |
|---|---|---|---|
| AUDIT.CONSENT_RECORDED | AuditSvc | AnalyticsSvc | {patientId, consentType, given} |
| AUDIT.DATA_RIGHTS_REQUESTED | AuditSvc | IdentitySvc, NotificationSvc | {patientId, requestType} |
| AUDIT.DATA_RIGHTS_FULFILLED | AuditSvc | CommunicationSvc, AuditSvc | {patientId, requestType, url} |
| AUDIT.CHAIN_VERIFIED | AuditSvc | AnalyticsSvc, AuditSvc | {verified, brokenLinks} |
| AUDIT.SECURITY_ALERT | AuditSvc | IdentitySvc, NotificationSvc | {alertType, userId, ipAddress} |
