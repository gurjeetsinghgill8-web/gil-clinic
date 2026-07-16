# 023 — CAPABILITY MATRIX

*Complete feature-to-role permission matrix.*
*AI agents must use this matrix for all authorization checks, UI visibility, and API access control.*

---

## Roles

| Role | Code | Description | Hierarchy Level |
|---|---|---|---|
| Admin | ADMIN | Full system access | 100 |
| Manager | MGR | Operational management | 80 |
| Doctor | DOC | Clinical consultation | 60 |
| Nurse | NUR | Patient care support | 50 |
| Receptionist | REC | Front desk operations | 40 |
| Technician | TEC | Test/lab operations | 40 |
| Pharmacist | PHA | Pharmacy operations | 40 |
| Lab Tech | LAB | Lab sample processing | 40 |
| Radiologist | RAD | Imaging operations | 40 |
| Patient | PAT | Self-service portal | 10 |
| AI Agent | AI | Automated operations | 20 |

---

## Capability Matrix

| # | Feature | ADMIN | MGR | DOC | NUR | REC | TEC | PHA | LAB | RAD | PAT | AI |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Create Patient | Y | Y | Y | Y | Y | X | X | X | X | X | Y |
| 2 | View Patient | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| 3 | Update Patient | Y | Y | Y | Y | Y | X | X | X | X | Y | X |
| 4 | Delete Patient | Y | X | X | X | X | X | X | X | X | X | X |
| 5 | Search Patients | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| 6 | Register Walk-in | Y | Y | Y | Y | Y | X | X | X | X | X | X |
| 7 | Import Bulk Patients | Y | Y | X | X | X | X | X | X | X | X | Y |
| 8 | View Patient History | Y | Y | Y | Y | Y | X | X | X | X | Y | X |
| 9 | Export Patient Data | Y | Y | X | X | X | X | X | X | X | Y | X |

| 10 | Generate Token | Y | Y | Y | Y | Y | X | X | X | X | X | X |
| 11 | Call Next Patient | Y | Y | Y | Y | X | Y | X | X | X | X | X |
| 12 | Skip Patient | Y | Y | Y | Y | X | Y | X | X | X | X | X |
| 13 | Complete Patient | Y | Y | Y | Y | X | Y | X | X | X | X | X |
| 14 | Re-queue Patient | Y | Y | Y | Y | X | X | X | X | X | X | X |
| 15 | View Queue | Y | Y | Y | Y | Y | Y | X | X | X | X | X |
| 16 | Pause/Resume Queue | Y | Y | X | X | X | X | X | X | X | X | X |
| 17 | Emergency Override | Y | Y | Y | X | X | X | X | X | X | X | Y |
| 18 | View Wait Times | Y | Y | Y | Y | Y | Y | X | X | X | Y | X |

| 19 | Create Visit | Y | Y | Y | Y | Y | X | X | X | X | X | X |
| 20 | Transition Visit State | Y | Y | Y | Y | X | X | X | X | X | X | X |
| 21 | View Visit Timeline | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | X |
| 22 | Archive Visit | Y | Y | X | X | X | X | X | X | X | X | X |

| 23 | Record Test Results | Y | X | Y | X | X | Y | X | Y | Y | X | X |
| 24 | Sign Report | Y | X | Y | X | X | X | X | X | X | X | X |
| 25 | View Reports | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | X |
| 26 | Write Prescription | Y | X | Y | X | X | X | X | X | X | X | X |
| 27 | View Prescriptions | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | X |
| 28 | Record Vital Signs | Y | X | Y | Y | X | X | X | X | X | X | X |
| 29 | Alert Critical Values | Y | Y | Y | Y | X | Y | X | Y | Y | X | Y |

| 30 | Create Bill | Y | Y | X | X | Y | X | X | X | X | X | X |
| 31 | View Bill | Y | Y | Y | Y | Y | X | Y | X | X | Y | X |
| 32 | Process Payment | Y | Y | X | X | Y | X | Y | X | X | X | X |
| 33 | Process Refund | Y | Y | X | X | X | X | X | X | X | X | X |
| 34 | Void Bill | Y | Y | X | X | X | X | X | X | X | X | X |
| 35 | Generate GST Invoice | Y | Y | X | X | X | X | X | X | X | X | X |
| 36 | View Financial Reports | Y | Y | X | X | X | X | X | X | X | X | X |

| 37 | View Inventory | Y | Y | Y | X | X | X | Y | X | X | X | X |
| 38 | Add Stock Item | Y | Y | X | X | X | X | X | X | X | X | X |
| 39 | Receive Stock | Y | Y | X | X | X | X | Y | X | X | X | X |
| 40 | Dispense Medicine | Y | X | Y | Y | X | X | Y | X | X | X | X |
| 41 | Run Stock Audit | Y | Y | X | X | X | X | X | X | X | X | X |

| 42 | Book Appointment | Y | Y | Y | X | Y | X | X | X | X | Y | X |
| 43 | Cancel Appointment | Y | Y | Y | X | Y | X | X | X | X | Y | X |
| 44 | View Schedule | Y | Y | Y | Y | Y | X | X | X | X | Y | X |
| 45 | Block/Unblock Slots | Y | Y | Y | X | X | X | X | X | X | X | X |

| 46 | Send WhatsApp | Y | Y | Y | X | Y | X | X | X | X | X | Y |
| 47 | Send SMS | Y | Y | Y | X | Y | X | X | X | X | X | Y |
| 48 | Send Email | Y | Y | Y | X | Y | X | X | X | X | X | Y |
| 49 | Send Push Notification | Y | Y | Y | X | Y | X | X | X | X | X | Y |
| 50 | View Communication Log | Y | Y | Y | X | Y | X | X | X | X | X | X |
| 51 | Manage Templates | Y | Y | X | X | X | X | X | X | X | X | X |

| 52 | Generate AI Diet Plan | Y | X | Y | X | X | X | X | X | X | Y | Y |
| 53 | Explain AI Report | Y | X | Y | X | X | X | X | X | X | Y | Y |
| 54 | AI Triage | Y | Y | Y | X | X | X | X | X | X | X | Y |
| 55 | AI Voice Agent | Y | X | Y | X | X | X | X | X | X | Y | Y |
| 56 | AI Prescription Suggest | Y | X | Y | X | X | X | X | X | X | X | Y |

| 57 | View Dashboard | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | X |
| 58 | Export Reports | Y | Y | Y | X | Y | X | X | X | X | X | X |
| 59 | View Audit Log | Y | Y | X | X | X | X | X | X | X | X | X |
| 60 | Manage Users | Y | Y | X | X | X | X | X | X | X | X | X |
| 61 | Manage Roles | Y | X | X | X | X | X | X | X | X | X | X |
| 62 | System Configuration | Y | Y | X | X | X | X | X | X | X | X | X |
| 63 | View System Health | Y | Y | Y | X | X | X | X | X | X | X | Y |
| 64 | Manage Backups | Y | Y | X | X | X | X | X | X | X | X | X |
| 65 | View Feature Flags | Y | Y | X | X | X | X | X | X | X | X | X |

---

## Permission Check Rules

1. **Hierarchy**: Level 100 (Admin) can do everything lower levels can
2. **Override**: Admin can grant specific feature access to any role
3. **Department scoped**: Doctor/Nurse/Technician access is limited to assigned departments
4. **Patient scoped**: Patient role can only access their own data
5. **AI scoped**: AI role can only perform features marked with Y, and requires audit logging
6. **API enforcement**: Every API endpoint checks permission matrix
7. **UI enforcement**: UI elements are hidden/disabled based on role
8. **Deny by default**: Any feature not explicitly granted is denied
