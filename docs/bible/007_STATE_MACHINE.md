# 007 — STATE MACHINE

*All state machines with valid transitions, guards, and actions.*

---

## Patient Visit State Machine

```
Registered ──> Waiting ──> Called ──> InConsultation ──> Prescribed ──> Billing ──> Completed ──> Archived
                                                      |                |
                                                      v                v
                                                   LabOrdered      Pharmacy
                                                      |                |
                                                      v                v
                                                   LabSampleCollected Dispensed
                                                      |                |
                                                      v                v
                                                   ReportReady    Billing
                                                      |                |
                                                      v                v
                                                   DoctorSigns    Completed
                                                      |                |
                                                      v                |
                                                   Billing <───────────┘
```

### Valid Transitions

| From | To | Guard | Event |
|---|---|---|---|
| Registered | Waiting | Patient checked in | PATIENT_CHECKED_IN |
| Waiting | Called | Dept ready, doctor available | DOCTOR_CALLED |
| Called | InConsultation | Patient entered room | CONSULTATION_STARTED |
| Called | Waiting | Patient not present (skip) | PATIENT_SKIPPED |
| InConsultation | Prescribed | Doctor finished consult | CONSULTATION_DONE |
| InConsultation | LabOrdered | Lab tests needed | LAB_ORDERED |
| LabOrdered | LabSampleCollected | Sample taken | SAMPLE_COLLECTED |
| LabSampleCollected | ReportReady | Lab processing done | LAB_COMPLETED |
| ReportReady | DoctorSigns | Doctor reviews report | REPORT_SIGNED |
| DoctorSigns | Billing | Report signed, bill generated | BILL_GENERATED |
| Prescribed | Pharmacy | Medicines prescribed | PHARMACY_SENT |
| Pharmacy | Dispensed | Medicines given | DISPENSED |
| Dispensed | Billing | Pharmacy items billed | BILL_GENERATED |
| Prescribed | Billing | No pharmacy items | BILL_GENERATED |
| Billing | Completed | Payment done | PAYMENT_COMPLETED |
| Completed | Archived | 90 days inactivity | AUTO_ARCHIVED |

### Special States

| State | Description | Entry Action |
|---|---|---|
| Emergency | Fast-track state | Skip queue, notify senior doctor |
| Cancelled | Patient cancelled visit | Log reason, remove from queue |
| Absent | Patient not reachable | Mark absent, free slot |

## Token State Machine

```
Created ──> Waiting ──> Called ──> InProgress ──> Completed
              |            |
              v            v
           Skipped     Absent
              |
              v
           Waiting (re-queued)
```

### Valid Transitions

| From | To | Guard |
|---|---|---|
| Created | Waiting | Patient registered, queue joined |
| Waiting | Called | Doctor clicks Call Next |
| Waiting | Skipped | Doctor clicks Skip |
| Skipped | Waiting | Re-queued at end |
| Called | InProgress | Patient enters room |
| Called | Absent | Patient not present after 3 calls |
| Called | Waiting | Patient not present, not absent (re-call later) |
| InProgress | Completed | Consultation done |

## Bill State Machine

```
Draft ──> Pending ──> Paid ──> Settled
  |          |          |
  v          v          v
Voided    Partial    Refunded
```

### Valid Transitions

| From | To | Guard |
|---|---|---|
| Draft | Pending | Bill finalized |
| Draft | Voided | Bill cancelled before payment |
| Pending | Paid | Full payment received |
| Pending | Partial | Partial payment received |
| Partial | Paid | Remaining balance paid |
| Paid | Settled | No disputes after 7 days |
| Paid | Refunded | Return/cancellation with approval |

## Appointment State Machine

```
Scheduled ──> Confirmed ──> CheckedIn ──> Completed
  |              |              |
  v              v              v
Cancelled     NoShow         InConsultation
```
