# 🏥 GHOS / CardioQueue — Real-Time Queue Prediction, Multi-Branch Cloud Sync & Marketplace Blueprint
## Enterprise Architecture & Mathematical Specification v3.5

**Scope:**  
1. **Dynamic Real-Time Waiting Time (EWT) Engine** (Ride-Hailing Arrival Estimation Analogy)  
2. **Cloud-Based Multi-Branch Synchronization & Zero-Trust Privacy Infrastructure**  
3. **Centralized City/Specialty Marketplace & Partner Priority Dispatch Logic**  

---

# SECTION 1: REAL-TIME WAITING TIME LOGIC STRATEGY (RIDE-HAILING ARRIVAL ESTIMATION)

Traditional clinic appointment models fail because consultation times are inherently variable and non-linear. GHOS models OPD throughput using the same stochastic control principles that power modern ride-hailing arrival engines (Uber ETA / Routing Engines).

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        RIDE-HAILING (UBER) vs. CLINICAL OPD ANALOGY                    │
├────────────────────────────────┬───────────────────────────────────────────────────────┤
│ RIDE-HAILING ETA COMPONENT     │ CLINIC OUTPATIENT THROUGHPUT ANALOGY                  │
├────────────────────────────────┼───────────────────────────────────────────────────────┤
│ Base Distance & Road Speeds    │ Historical Average Consultation Duration (by Doctor)  │
│ Traffic Jam / Congestion Index │ Current Chamber Friction (Long Case / Procedure Delay)│
│ Red Lights / Intersections     │ Inter-Consultation Transition Lag (Disinfection, Room)│
│ En-Route Pickups (Carpool)     │ Ancillary Diagnostic Divergence (ECG, Echo, Lab)     │
│ Driver Velocity Feedback       │ Real-Time Service Velocity $V_{t}$ (Last 5 Patients)  │
│ Dispatch Window Calculation    │ "Just-In-Time" Departure Alert for Patient at Home     │
└────────────────────────────────┴───────────────────────────────────────────────────────┘
```

---

## 1.1 Mathematical Formulation of the Estimated Waiting Time (EWT)

Let patient $P_{target}$ hold token position $k$ in the queue (with $k-1$ patients ahead).  
The Estimated Waiting Time $EWT(k, t)$ at evaluation timestamp $t$ is formulated as:

$$EWT(k, t) = \underbrace{\Big( T_{remaining}(P_{current}) \Big)}_{\text{Current In-Chamber Residual}} + \sum_{i=1}^{k-1} \underbrace{\hat{D}_{i}(t)}_{\text{Predicted Duration of Ahead Patients}} + \sum \underbrace{\hat{T}_{proc}(i)}_{\text{Parallel Test Delays}} + \underbrace{\delta_{overhead} \cdot (k-1)}_{\text{Turnaround Lag}} + \underbrace{\Omega(t)}_{\text{Surge / Emergency Buffer}}$$

### Parameter Breakdown

#### 1. Baseline Historical Duration ($\overline{T}_{base}$)
Calculated using a Bayesian Priors model combining:
- The Global Specialty Mean (e.g., Cardiology new visit = 16.5 min, Follow-up = 8.2 min).
- The Doctor's Personal Historical Median $\widetilde{T}_{doc}$ (exponentially smoothed across their previous 100 consultations).

$$\overline{T}_{base}(doc, type) = \alpha \cdot \widetilde{T}_{doc}(type) + (1 - \alpha) \cdot \mu_{specialty}(type) \quad (\text{where } \alpha = 0.85)$$

#### 2. Real-Time Chamber Velocity ($V_{t}$ — "Traffic Adjustment")
Rather than assuming the doctor moves at historical speed, GHOS computes the **Instantaneous Service Velocity Ratio** over the last $m=5$ completed consultations today:

$$V_{t} = \frac{\sum_{j=1}^{m} \text{Actual Duration}_j}{\sum_{j=1}^{m} \overline{T}_{base}(j)}$$

- If $V_{t} > 1.25$: The doctor is running behind schedule (high case complexity). Ahead consultations are dynamically scaled up by $V_{t}$.
- If $V_{t} < 0.85$: The doctor is running ahead of schedule (routine report clearances). Ahead consultations are dynamically compressed.

#### 3. Patient Complexity Multiplier ($C_i$)
Each patient $i$ ahead in the queue is weighted by pre-consultation attributes captured at registration/intake:
- **First Visit / Complex Cardiac Complaints** (Chest Pain, Angina): $C_i = 1.35$
- **Routine Follow-Up / Medication Refill**: $C_i = 0.70$
- **Investigation Review (ECG/Echo already done)**: $C_i = 0.80$
- **Elderly / High Fall Risk (>70 years)**: $C_i = 1.20$

$$\hat{D}_i(t) = \overline{T}_{base}(doc, type_i) \times C_i \times V_{t}$$

#### 4. Current In-Chamber Residual ($T_{remaining}$)
If patient $P_{current}$ entered the doctor's room at timestamp $t_{start}$:

$$T_{elapsed} = t - t_{start}$$
$$T_{remaining} = \max\Big( 2.0\text{ min}, \quad \big(\hat{D}_{current} - T_{elapsed}\big) \times \Phi(T_{elapsed}) \Big)$$

Where $\Phi$ is an overdue dampener: if a consultation exceeds predicted time by 200%, the probability of immediate completion increases monotonically rather than projecting infinite duration.

---

## 1.2 Live Queue State Machine & Ride-Hailing Event Pipeline

```
  [REGISTERED / HOME]
          │
          ▼
   (EWT > 45 mins)  ───► Virtual Waiting Room: Patient stays at home / office
          │
          ▼  (EWT reaches Transit Time + 12 min)
  [DEPARTURE ALERT] ───► WhatsApp & Web Audio: "Start journey now to arrive at Token #14"
          │
          ▼
  [CLINIC CHECK-IN] ───► Geofence / Reception Scan: Verified Present in Physical Lobby
          │
          ▼
    [CALLED (T-2)]  ───► Chime: "Please proceed to Corridor outside Room 2"
          │
          ▼
    [IN CHAMBER]    ───► Door Closed / Sensor: $t_{start}$ logged, live timer starts
          │
          ▼
    [COMPLETED]     ───► Rx issued, $t_{end}$ logged, velocity $V_t$ recalculated
```

### Proactive Notification Triggers
1. **The "Uber Departure Ping"**:  
   If Patient $A$ is 6 km away (estimated 18 minutes by Google Distance Matrix / OSRM API), the platform fires a departure alert when $EWT \le 18\text{ min} + 8\text{ min buffer}$.  
   *Result: Patient enters the clinic just 2 patients before their turn, achieving near-zero waiting hall congestion.*
2. **Dynamic Delay Surge Alerts**:  
   If an emergency Code-Blue occurs, the doctor taps `[ ⏸️ Emergency Pause: 15 min ]`. The system instantly recalculates EWT for all 20 downstream patients and broadcasts an automated WhatsApp update with the updated target time.

---

# SECTION 2: MULTI-BRANCH CLOUD SYNCHRONIZATION & ZERO-TRUST SECURITY

For networks operating across multiple cities (e.g. Delhi - South Ext, Jodhpur - Shastri Nagar, Ahmedabad - Satellite), the architecture uses a **Hybrid Edge-Cloud Topology**:

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │                    CENTRAL CLOUD CONTROL PLANE (GCP / AWS)              │
 │  • Global Tenant Directory           • Federated Identity (IAM / OAuth)│
 │  • Central Marketplace & Search      • Encrypted Health Passport Vault │
 │  • Master Audit Ledger               • Cross-Branch Synchronization Bus│
 └─────────────────▲──────────────────────────────▲───────────────────────┘
                   │  TLS 1.3 / gRPC             │  TLS 1.3 / gRPC
                   │  Event Stream               │  Event Stream
                   ▼                             ▼
 ┌────────────────────────────────┐  ┌────────────────────────────────────┐
 │   BRANCH A: DELHI CENTRAL      │  │     BRANCH B: JODHPUR CLINIC       │
 │   (Local Edge Appliance / K8s) │  │    (Local Edge Appliance / K8s)    │
 ├────────────────────────────────┤  ├────────────────────────────────────┤
 │ • In-Memory Fast Queue Engine  │  │  • In-Memory Fast Queue Engine     │
 │ • Offline SQLite/Postgres Edge │  │  • Offline SQLite/Postgres Edge    │
 │ • Local Reception/Tech Tablets │  │  • Local Reception/Tech Tablets    │
 │ • TV Display Audio Chime Box   │  │  • TV Display Audio Chime Box      │
 └────────────────────────────────┘  └────────────────────────────────────┘
```

---

## 2.1 Synchronization Strategy: Event-Driven Conflict-Free Architecture

1. **Local-First Autonomy (Zero Clinic Downtime)**:  
   Each branch maintains an independent Edge Datastore. If the city's fiber optic link fails, the branch reception, doctor OPD, and TV display operate uninterrupted using local Wi-Fi.
2. **Asynchronous Outbox Pattern**:  
   All local state mutations (`TokenCreated`, `PatientCalled`, `VitalsRecorded`, `RxFinalized`) are committed to a transactional local outbox table.
3. **Change Data Capture (CDC) & Pub/Sub Event Streaming**:  
   When connectivity is restored, events stream to the Central Event Bus (Apache Kafka / Google Cloud Pub/Sub) with idempotent `UUIDv7` keys.
4. **Conflict-Free Replicated Data Types (CRDTs)**:  
   Queue state changes use LWW-Element-Set (Last-Write-Wins with logical vector clocks) to prevent duplicate token collisions across branches.

---

## 2.2 Data Privacy & Regulatory Compliance (DISHA, ABDM & HIPAA Equivalent)

### 1. Dual-Layer Encryption
- **In Transit**: All branch-to-cloud communications enforce TLS 1.3 with strict mutual authentication (mTLS).
- **At Rest**: AES-256-GCM encryption with Branch-Specific KMS Keys. The central database cannot decrypt patient clinical findings without the branch clinic's tenant token.

### 2. Pseudonymization & Identity Isolation
Patient Identifiable Information (PII — Name, Phone, Aadhaar) is segregated from Protected Health Information (PHI — ECG Traces, Clinical Notes, Diagnosis):
- **PII Vault**: Stored in a specialized tokenized database partition.
- **PHI Repository**: Indexed solely by an anonymous cryptographic Subject ID (`sub_9f81a7b2...`). Even database administrators cannot correlate cardiac diagnoses to named individuals without access to the secure KMS token vault.

---

## 2.3 Granular Role-Based Access Control (RBAC) Matrix

| Resource / Action | Super Admin (CEO) | Branch Doctor | Receptionist | Lab Tech (ECG/Echo) | Visiting Specialist | Patient (PWA) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Clinic SaaS Licenses** | Full Admin | No Access | No Access | No Access | No Access | No Access |
| **All-Branch Live Overview** | Read-Only | No Access | No Access | No Access | No Access | No Access |
| **Branch Queue Management** | Read-Only | Full Access (Own) | Call / Register | Department Only | Assigned Patients | View Own Token |
| **Longitudinal Medical History** | No Access | Full Access | No Access | Test History Only | 24-hr Token Access | View Own Card |
| **1-Click Prescribing** | No Access | Write (Signed) | No Access | No Access | Write (Assigned) | Read (View PDF) |
| **Patient Contact Details (Phone)**| Masked | Visible | Visible | Masked | Masked | Own Record |

---

# SECTION 3: CENTRALIZED APPOINTMENT & CITY MARKETPLACE DISCOVERY

The Marketplace serves as the digital front door for patients across India, engineered with an explicit **Partner Advantage Algorithm** that drives patient volume to GHOS SaaS client clinics while accommodating unpartnered medical centers.

```
       [PATIENT OPENS MARKETPLACE]
                   │
                   ▼
       [SELECT CITY: DELHI / JODHPUR / AHMEDABAD]
                   │
                   ▼
       [SELECT SPECIALTY OR DESCRIBE SYMPTOM]
                   │
                   ▼
 ┌────────────────────────────────────────────────────────┐
 │           ALGORITHMIC RANKING CONTROLLER               │
 ├────────────────────────────────────────────────────────┤
 │                                                        │
 │  🥇 TIER 1: VERIFIED GHOS CLIENT CLINICS (TOP 100%)    │
 │     • Live Chamber Telemetry (Doctor In Room)          │
 │     • Active Queue Position & Precise EWT              │
 │     • Instant 1-Tap Token Booking                      │
 │     • Direct EHR Sync with Patient Health Card         │
 │                                                        │
 │  🥈 TIER 2: EXTERNAL REGISTERED DIRECTORY (BELOW)      │
 │     • Clinic Address, Doctor Degrees, Public Rating    │
 │     • Walk-in Only / Call-to-Book Certificate Notice   │
 │     • Digital Referral Routing Form                    │
 │     • "Nudge Doctor to Live Queue" Viral Lead Gen     │
 └────────────────────────────────────────────────────────┘
```

---

## 3.1 Search & Matching Mechanics

### 1. Geo-Spatial Radius Search
Patients input their location or enable GPS. The system computes bounding-box geohashes ($H3$ hexagonal spatial index, resolution 7) to identify doctors within a 15 km radius.

### 2. Multi-Lingual Symptom Parsing (NLP / Rule-Based)
Patients can search via colloquial terms:
- Input: *"Chhati mein dard aur paseena"* (Chest pain & sweating)  
  $\rightarrow$ Maps to: **Cardiology (Urgent / Red-Flag Priority)**
- Input: *"Ghutne mein sujan"* (Knee swelling)  
  $\rightarrow$ Maps to: **Orthopedics**
- Input: *"Bache ko tez bukhar"* (Child high fever)  
  $\rightarrow$ Maps to: **Pediatrics**

---

## 3.2 Tier-1 Partner Clinic Privileges & Real-Time Booking

When a partner clinic is displayed:
1. **Live Room Telemetry Card**:
   - `[ 🟢 DR. GURJEET S. GILL — IN CHAMBER (OPD 2) ]`
   - `Live Progress: Token #18 inside • 3 ahead in queue`
   - `Live Wait Time: ~21 Minutes`
2. **Instant Queue Injection**:
   - Patient taps **"⚡ Join Live Queue Now"**.
   - No advance payment gateway barrier: creates immediate validated digital token `#22`.
   - Patient receives a secure tracking link (`/track/TOKEN_ID`) containing live EWT, directions, and audio alert configurations.
   - The patient's symptom summary is pushed directly to the Doctor's app interface.

---

## 3.3 External Clinic Handling & Bidirectional Referral Architecture

When a patient browses doctors outside the GHOS SaaS network:

### 1. Transparent Walk-In / Phone Disclosure
To maintain credibility and avoid patient deception:
- Card Styling: Neutral matte finish without live tracking badges.
- Prominent Notice:  
  `⚠️ Unverified Queue Network: This clinic operates traditional offline walk-in tokens. Real-time waiting time and instant queue tracking are unavailable. Call clinic reception directly or visit in person.`
- Primary CTA: `[ 📞 Call Clinic Desk ]` + `[ 📍 Navigate on Map ]`.

### 2. Digital Referral Gateway for External Doctors
If a GHOS partner doctor (e.g., Cardiologist in Jodhpur) needs to refer a patient to a specialized Cardiothoracic Surgeon in Delhi who is not yet on the SaaS platform:
- The referring doctor clicks `[ ↗️ Generate External Referral Slip ]`.
- GHOS generates a tamper-proof **Cross-Clinic Medical Referral Slip** (PDF / Web link) with a cryptographic QR code.
- When the external Delhi surgeon scans the QR code on any phone browser:
  - An encrypted 1-time view opens displaying the patient's ECG trace, 2D Echo summary, and reason for referral.
  - The page displays: *"Referral courtesy of GHOS Network. Would you like to accept this patient into your schedule?"*
- **Viral B2B Doctor Acquisition**: The external surgeon experiences the speed of the digital summary and is offered a 30-day trial of GHOS Clinic Operating System.

---

# SECTION 4: COMPLETE DATA CONTRACT SCHEMAS

### 1. Real-Time Queue Telemetry Contract
```typescript
interface QueueTelemetryRecord {
  branch_id: string;               // e.g., "DELHI-CENTRAL-01"
  clinic_code: string;             // e.g., "GIL-CARDIO-DL"
  doctor_id: string;
  doctor_name: string;
  chamber_status: "IN_CONSULTATION" | "PROCEDURE" | "ON_BREAK" | "EMERGENCY_HOLD";
  current_token_number: number;
  total_waiting: number;
  rolling_avg_duration_seconds: number;
  current_patient_started_at: string; // ISO 8601 UTC
  velocity_ratio: number;             // Actual / Expected (<1.0 fast, >1.0 delayed)
  emergency_buffer_minutes: number;
  active_tokens: Array<{
    token_number: number;
    patient_id: string;
    category: "NEW" | "FOLLOWUP" | "REPORT" | "EMERGENCY";
    estimated_arrival_window: string;
    estimated_call_time: string;
    status: "WAITING" | "CALLED" | "IN_PROGRESS" | "COMPLETED";
  }>;
}
```

### 2. Central Marketplace Search Result Contract
```typescript
interface DoctorMarketplaceEntity {
  doctor_id: string;
  name: string;
  city: "Delhi" | "Jodhpur" | "Ahmedabad" | string;
  specialty: "Cardiology" | "General Medicine" | "Orthopedics" | string;
  qualifications: string;
  experience_years: number;
  clinic_name: string;
  address: string;
  coordinates: { lat: number; lng: number };
  tier: "GHOS_PARTNER" | "EXTERNAL_DIRECTORY";
  
  // Populated exclusively for GHOS_PARTNER clinics
  live_telemetry?: {
    is_doctor_active: boolean;
    current_token: number;
    queue_length: number;
    estimated_wait_minutes: number;
    instant_booking_available: boolean;
  };

  // Populated for EXTERNAL_DIRECTORY clinics
  external_contact?: {
    reception_phone: string;
    booking_instructions: string;
    verification_status: "UNVERIFIED_OFFLINE";
  };
}
```

---

# SECTION 5: IMPLEMENTATION PHASING MATRIX

```
PHASE 1: Core EWT Logic Engine
├── Step 1.1: Historical consultation duration aggregator (per doctor / specialty)
├── Step 1.2: Moving-average velocity calculator ($V_t$) on /api/v1/queue
└── Step 1.3: Dynamic EWT projection display on patient tracking portal (/track/:token)

PHASE 2: Ride-Hailing Style Dispatch & Proactive Alerts
├── Step 2.1: Transit time estimator integration (Google Maps Distance Matrix / OSRM)
├── Step 2.2: T-3 patient arrival departure ping via WhatsApp deep-link
└── Step 2.3: Audio Chime & Emergency Delay Surge Broadcast module

PHASE 3: Multi-Branch Cloud Sync Architecture
├── Step 3.1: Branch Edge Outbox event publisher
├── Step 3.2: Central Cloud Pub/Sub aggregator with CRDT resolution
└── Step 3.3: AES-256 field-level PHI encryption & ABHA/DISHA privacy boundary

PHASE 4: Centralized Multi-City Discovery Marketplace
├── Step 4.1: City / Specialty discovery gateway with partner clinic boost ranking
├── Step 4.2: 1-Tap Live Token Reservation directly into partner clinic queue
└── Step 4.3: External Doctor Directory & Cryptographic Referral Slip Generator
```

---
*Architectural specification completed. System ready for staged execution upon confirmation.*
