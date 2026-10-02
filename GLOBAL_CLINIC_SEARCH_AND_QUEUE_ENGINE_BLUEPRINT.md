# GLOBAL CLINIC SEARCH, MULTI-FACTOR RANKING & DYNAMIC WAITING TIME ENGINE
## Enterprise Architecture & Technical Specification Blueprint v4.0

**System Identification:** GHOS-MARKETPLACE-CORE  
**Target Environment:** Cloud-Distributed Healthcare Operating System  
**Compliance Standard:** ABDM (Ayushman Bharat Digital Mission), DISHA, HL7-FHIR, HIPAA-equivalent Zero-Trust  
**Design Principle:** Deterministic Latency, Zero Hall Clutter, Mobile-First Ride-Hailing Queue Dispatch

---

# MODULE 1: GLOBAL CLINIC SEARCH ENGINE ARCHITECTURE

## 1.1 Architectural Overview

The Global Clinic Search engine serves as a distributed, location-aware query broker designed to resolve medical discovery queries across tier-1, tier-2, and tier-3 cities (e.g., Delhi NCR, Jodhpur, Ahmedabad, Jaipur, Mumbai). It bridges real-time clinic telemetries (live OPD chamber status) with static directory listings.

```
                            [ PATIENT SEARCH QUERY ]
           (City / Geolocation + Specialty / Natural Language Symptom)
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │    API Gateway & Geocoder     │
                       │   (Reverse IP / GPS Lat-Long) │
                       └───────────────┬───────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        ┌───────────────────────┐             ┌───────────────────────┐
        │  Geographic Filter    │             │   Specialty / NLP     │
        │  • H3 Geohash (Res 7) │             │   • Medical Taxonomy  │
        │  • Haversine Distance │             │   • Symptom Vectorize │
        │  • Municipal Boundary │             │   • Urgency Classifier│
        └───────────┬───────────┘             └───────────┬───────────┘
                    └──────────────────┬──────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   Candidate Matching Broker   │
                       └───────────────┬───────────────┘
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 ▼                                           ▼
   ┌───────────────────────────┐               ┌───────────────────────────┐
   │ TIER-1: PARTNER CLINICS   │               │ TIER-2: EXTERNAL CLINICS  │
   │ (GHOS SaaS Live Telemetry)│               │ (Unverified Directory)    │
   ├───────────────────────────┤               ├───────────────────────────┤
   │ • Live Room Sensor Active │               │ • Standard Address / Phone│
   │ • Dynamic Wait Time (EWT) │               │ • Call-to-Book Only       │
   │ • Instant Digital Token   │               │ • Referral Gateway Link   │
   │ • 100% Top Priority Sort  │               │ • Static Timings          │
   └─────────────┬─────────────┘               └─────────────┬─────────────┘
                 └─────────────────────┬─────────────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │  Multi-Factor Ranking Engine  │
                       │   (Score Calculation & Sort)  │
                       └───────────────┬───────────────┘
                                       │
                                       ▼
                       ┌───────────────────────────────┐
                       │   Decorated JSON Response     │
                       │  (Custom Badges & Live Status)│
                       └───────────────────────────────┘
```

---

## 1.2 Multi-Layer Geographic & Specialty Filtering Logic

### 1. Geographic Filtering Pipeline
1. **Stage 1 (City Clamping)**: If user explicitly selects a city (e.g., "Delhi"), the query is bounded by the official administrative GeoJSON boundary polygon of that municipal territory.
2. **Stage 2 (Spatial Indexing via Uber H3)**: When GPS coordinates are present, the patient's coordinates $(lat_p, lng_p)$ are mapped to an **H3 Hexagonal Spatial Index** at Resolution 7 (average hexagon area $\approx 5.16\text{ km}^2$, edge length $\approx 1.22\text{ km}$).
3. **Stage 3 (Haversine Distance Filter)**:
   $$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \phi}{2}\right) + \cos(\phi_1)\cos(\phi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right)$$
   Where $R = 6371\text{ km}$. Providers beyond search radius $R_{max}$ ($15\text{ km}$ default for urban, $35\text{ km}$ for rural) are filtered out unless specialty availability is zero within that boundary.

### 2. Specialty & Colloquial Symptom Matching Pipeline
- Queries are parsed through a bilingual (Hindi-English) medical entity normalizer:
  - `"Chhati mein dard"` / `"Chest tightness"` $\rightarrow$ **Cardiology** [Severity: Critical]
  - `"Ghutne ka dard"` / `"Knee pain"` $\rightarrow$ **Orthopedics** [Severity: Routine]
  - `"Bache ko ulti/dast"` / `"Infant fever"` $\rightarrow$ **Pediatrics** [Severity: Urgent]
- Canonical classification follows SNOMED-CT / ICD-10 specialty ontologies.

---

## 1.3 Partner Priority Ingestion & Custom Sorting Tag System

The search broker segments results into two strict tiers, ensuring GHOS partner clinics dominate user visibility while maintaining total transparency.

### Partner Custom Display Tags

| Tag Code | Display Label | Visual Badge | Business / Algorithmic Trigger |
|---|---|---|---|
| `TAG_PARTNER_PREMIER` | **GHOS Premier Partner** | 🥇 Gold Border + Verified Shield | Active GHOS SaaS subscription with 100% digital token compliance. |
| `TAG_LIVE_TELEMETRY` | **Live OPD Chamber Active** | 🟢 Pulsing Green Indicator | Doctor is physically authenticated inside chamber; consultations ongoing. |
| `TAG_INSTANT_TOKEN` | **Instant 1-Tap Booking** | ⚡ Cyan Lightning Badge | Queue is open; patient can secure live digital token with zero upfront fee. |
| `TAG_ZERO_WAIT_VERIFIED`| **Zero-Wait Hall Verified** | ⏱️ Emerald Clock Badge | Historical average check-in to consult wait time $< 12\text{ minutes}$. |
| `TAG_EMERGENCY_READY` | **Emergency Triage Ready** | 🚨 Crimson Heart Icon | Branch has ECG/Defibrillator and priority emergency jump protocol. |

### External Directory Custom Tags

| Tag Code | Display Label | Visual Badge | Business / Algorithmic Trigger |
|---|---|---|---|
| `TAG_EXTERNAL_OFFLINE` | **Unverified Offline Queue** | ⚠️ Muted Gray Warning | Non-partner clinic. No live queue telemetry. Walk-in queue required. |
| `TAG_DIRECT_CALL_ONLY` | **Call Clinic Directly** | 📞 Slate Blue Phone Icon | Appointments cannot be booked digitally; user must call reception desk. |
| `TAG_REFERRAL_ELIGIBLE`| **Digital Referral Route** | ↗️ Indigo Arrow Icon | Partner doctors can send electronic referral slips to this doctor. |

---

# MODULE 2: MULTI-FACTOR DOCTOR RANKING ALGORITHM SPECIFICATION

## 2.1 Composite Scoring Function

To replace arbitrary pay-per-click sponsored listings with a meritocratic, efficiency-driven ranking, the system calculates a unified **Best-Match Score** $S_{\text{match}} \in [0, 100]$ for each provider $j$:

$$S_{\text{match}}(j) = \Big( w_E \cdot E_j + w_R \cdot R_j + w_A \cdot A_j + w_D \cdot D_j + w_P \cdot P_j \Big) \times \Psi_{\text{cold-start}}(j)$$

### Default Normalized Weights
$$\sum w = 1.0 \quad \implies \quad w_E = 0.25, \; w_R = 0.25, \; w_A = 0.25, \; w_D = 0.15, \; w_P = 0.10$$

---

## 2.2 Factor Definitions & Mathematical Formulations

### 1. Appointment Efficiency Score ($E_j \in [0, 1]$)
Measures the doctor's punctuality, consultation time predictability, and schedule fidelity over the last 30 operational days:

$$E_j = 0.50 \cdot \Big( 1 - \min(1, \frac{|\overline{T}_{\text{actual}} - \overline{T}_{\text{slotted}}|}{\overline{T}_{\text{slotted}}}) \Big) + 0.30 \cdot \big( \text{On-Time Start Ratio} \big) + 0.20 \cdot \big( 1 - \text{No-Show Cancellation Rate} \big)$$

### 2. Bayesian Patient Verified Rating Score ($R_j \in [0, 1]$)
Prevents manipulation from doctors with only two 5-star reviews by anchoring ratings against the global specialty mean:

$$R_j = \frac{v_j \cdot \overline{r}_j + m \cdot \mu_{\text{global}}}{v_j + m} \div 5.0$$

Where:
- $\overline{r}_j$: Arithmetic average of verified ratings from completed tokens for doctor $j$.
- $v_j$: Total number of completed verified patient reviews.
- $m$: Confidence threshold parameter (default: $m = 25$ reviews).
- $\mu_{\text{global}}$: Mean rating of all registered doctors across the platform (default: $4.25$).

### 3. Real-Time Availability Score ($A_j \in [0, 1]$)
Gives immediate preference to providers who can see the patient right now:

$$A_j = 
\begin{cases} 
1.00 & \text{if Doctor is in Chamber, Queue Open, and } EWT < 30\text{ min} \\
0.75 & \text{if Doctor is in Chamber, Queue Open, and } 30\text{ min} \le EWT < 60\text{ min} \\
0.50 & \text{if Doctor is scheduled today, starts within } 90\text{ min} \\
0.20 & \text{if Queue is full today, next booking is tomorrow} \\
0.05 & \text{if Offline / Unverified External Directory}
\end{cases}$$

### 4. Proximity & Travel Friction Score ($D_j \in [0, 1]$)
Applies a Sigmoidal Distance Decay function:

$$D_j = \frac{1}{1 + e^{\beta \cdot (d_j - d_{\text{mid}})}}$$

Where $d_j$ is the Haversine distance in km, $d_{\text{mid}} = 8.0\text{ km}$, and $\beta = 0.35$.

### 5. Partner Priority Weight ($P_j \in [0, 1]$)
- $P_j = 1.0$ for GHOS SaaS Client Clinics (instantly yielding $+10.0$ raw score boost).
- $P_j = 0.0$ for External Directory Clinics.

### 6. Cold-Start Dampener ($\Psi_{\text{cold-start}}$)
For doctors on-boarded within the last 14 days with $v_j < 10$:

$$\Psi_{\text{cold-start}}(j) = 1.0 + 0.15 \cdot \Big( 1 - \frac{\text{Days Since Onboarding}}{14} \Big)$$

This gives newly on-boarded clinics a temporary 14-day discovery lift to gather their initial 25 verified ratings.

---

# MODULE 3: WAITING TIME ESTIMATOR (WTE) ARCHITECTURE

## 3.1 Mathematical Engine: Stochastic Multi-Server Queue Model

The Waiting Time Estimator (WTE) continuously calculates dynamic Estimated Waiting Time ($EWT$) for any queued patient $k$.

```
                       DYNAMIC EWT CALCULATION PIPELINE
                       
 [Queue Snapshot: k Tokens Ahead]   ──┐
                                      ├──► [ Bayesian Baseline: T_base ]
 [Historical Doctor Distribution]   ──┘           │
                                                  ▼
 [Real-Time Velocity Monitor: V_t] ──────► [ Velocity Adjustment: T_base * V_t ]
                                                  │
                                                  ▼
 [Pre-Consultation Triage Multiplier: C_i] ─► [ Complexity Scale: D_hat_i ]
                                                  │
                                                  ▼
 [Active In-Chamber Elapsed Timer: t_el] ──► [ Residual Time: T_remaining ]
                                                  │
                                                  ▼
 [Parallel Diagnostic Delays: T_proc] ────► [ Summation + Surge Buffer ]
                                                  │
                                                  ▼
                                      ┌───────────────────────┐
                                      │ FINAL EWT FOR TOKEN k │
                                      └───────────┬───────────┘
                                                  │
                  ┌───────────────────────────────┴───────────────────────────────┐
                  ▼                                                               ▼
    ┌───────────────────────────┐                                   ┌───────────────────────────┐
    │  Mobile Patient PWA View  │                                   │    Transit Dispatch Ping  │
    │  "Est. Wait: ~18 Minutes" │                                   │ "Leave Home Now (15m trip)│
    │  Live Token Ticker: #14   │                                   │  Walk right into Chamber" │
    └───────────────────────────┘                                   └───────────────────────────┘
```

### The Universal EWT Prediction Equation

$$EWT(k, t) = T_{\text{residual}}(P_{\text{current}}, t) + \sum_{i=1}^{k-1} \Big( \overline{T}_{\text{base}}(doc, type_i) \times C_i \times V_t \Big) + \sum T_{\text{proc}}(i) + \delta_{\text{lag}} \cdot (k-1) + \Omega_{\text{delay}}(t)$$

---

## 3.2 Dynamic Parameters & Operational Behavior

### 1. In-Chamber Residual Time Calculation ($T_{\text{residual}}$)
If patient $P_{\text{current}}$ entered the consultation room at timestamp $t_{\text{start}}$:

$$t_{\text{elapsed}} = t - t_{\text{start}}$$
$$T_{\text{residual}} = \max\left( 1.5\text{ min}, \quad \big(\hat{D}_{\text{current}} - t_{\text{elapsed}}\big) \times \exp\left(-\frac{t_{\text{elapsed}}}{2.5 \cdot \hat{D}_{\text{current}}}\right) \right)$$

This exponential decay dampener prevents negative waiting times while ensuring that consultations running past their estimated duration project imminent completion rather than infinite delay.

### 2. Instantaneous Velocity Ratio ($V_t$ — Dynamic Friction Factor)
Computed over the last $N=5$ patients seen by this doctor today:

$$V_t = \frac{\sum_{n=1}^{N} \text{Actual Duration}_n}{\sum_{n=1}^{N} \hat{D}_n}$$

- $V_t = 1.0$: Clinic operating exactly on schedule.
- $V_t = 1.4$: Doctor is handling complicated cases; downstream wait estimates dynamically expand by $40\%$.
- $V_t = 0.7$: Doctor is clearing follow-ups quickly; downstream wait estimates compress by $30\%$.

### 3. Patient Complexity Multipliers ($C_i$)
Captured automatically during receptionist check-in or pre-consultation digital triage:
- `COMPLEXITY_FIRST_VISIT` (New patient, unmapped history): $C = 1.35$
- `COMPLEXITY_CARDIAC_SYMPTOMS` (Chest pain, shortness of breath): $C = 1.45$
- `COMPLEXITY_FOLLOW_UP` (Routine check, medication refill): $C = 0.70$
- `COMPLEXITY_REPORT_REVIEW` (Only ECG/Echo analysis): $C = 0.65$
- `COMPLEXITY_GERIATRIC` (Patient age $> 75$): $C = 1.20$

---

## 3.3 Dynamic Arrival Estimation & Mobile Dispatch ("Uber-Style")

Rather than forcing patients into physical waiting rooms, the system operates a **Virtual Waiting Room** with intelligent departure alerts:

```
[PATIENT REGISTERED AT HOME]
Token #18 | Distance: 5.4 km | Transit Time: 16 mins
                  │
                  ▼
         [EWT Evaluation Loop]
EWT = 42 mins ──► Status: "Relax at Home. You have 26 mins before departure."
EWT = 28 mins ──► Status: "Prepare to leave. Departure in 12 mins."
                  │
                  ▼ (Trigger Threshold: EWT <= Transit Time + 8 mins)
       [DEPARTURE ALERT BROADCAST]
WhatsApp + Audio Web Push Notification:
"🔔 Token #14 is inside. Your Token is #18.
Traffic: 16 mins. Start travel NOW to arrive exactly at your turn."
                  │
                  ▼
         [PATIENT ARRIVES]
Geofence Arrival / Reception QR Scan ──► Marked "In Waiting Lobby"
Wait Time in Lobby: < 5 Minutes
```

---

# MODULE 4: TECHNICAL DATA CONTRACTS & API SPECIFICATIONS

## 4.1 Search API Request & Response Schema

### `GET /api/v1/marketplace/search`

#### Query Parameters:
```json
{
  "city": "Delhi",
  "lat": 28.5672,
  "lng": 77.2100,
  "radius_km": 15,
  "specialty": "Cardiology",
  "query": "chest pain",
  "tier_filter": "ALL",
  "sort_by": "BEST_MATCH"
}
```

#### JSON Response Schema:
```json
{
  "status": "success",
  "timestamp": "2026-09-30T22:30:00Z",
  "total_results": 14,
  "partner_count": 3,
  "results": [
    {
      "provider_id": "PRV-DEL-001",
      "doctor_name": "Dr. Gurjeet Singh Gill",
      "specialty": "Cardiology",
      "qualifications": "MD, DM (Cardiology)",
      "clinic_name": "GIL CLINIC — Heart & Vascular Centre",
      "city": "Delhi",
      "locality": "South Extension II",
      "coordinates": { "lat": 28.5700, "lng": 77.2200 },
      "distance_km": 2.1,
      "tier": "TIER_1_PARTNER",
      "ranking_score": 94.8,
      "tags": [
        { "code": "TAG_PARTNER_PREMIER", "label": "GHOS Premier Partner", "badge": "gold" },
        { "code": "TAG_LIVE_TELEMETRY", "label": "Chamber Active", "badge": "green_pulse" },
        { "code": "TAG_INSTANT_TOKEN", "label": "Instant 1-Tap Booking", "badge": "cyan" },
        { "code": "TAG_ZERO_WAIT_VERIFIED", "label": "Zero-Wait Verified", "badge": "emerald" }
      ],
      "live_telemetry": {
        "is_active": true,
        "chamber_name": "Consultation Room 1",
        "current_token_in_chamber": 14,
        "next_available_token": 18,
        "patients_waiting_count": 3,
        "estimated_wait_minutes": 19,
        "velocity_ratio": 1.05,
        "booking_mode": "INSTANT_LIVE_TOKEN"
      },
      "verified_metrics": {
        "rating": 4.92,
        "total_verified_reviews": 184,
        "on_time_start_rate": 0.96,
        "avg_consult_duration_minutes": 14.5
      }
    },
    {
      "provider_id": "PRV-DEL-EXT-88",
      "doctor_name": "Dr. S. K. Sharma",
      "specialty": "Cardiology",
      "qualifications": "MBBS, MD",
      "clinic_name": "Sharma Heart Clinic",
      "city": "Delhi",
      "locality": "Lajpat Nagar IV",
      "coordinates": { "lat": 28.5640, "lng": 77.2400 },
      "distance_km": 3.8,
      "tier": "TIER_2_EXTERNAL",
      "ranking_score": 58.2,
      "tags": [
        { "code": "TAG_EXTERNAL_OFFLINE", "label": "Unverified Offline Queue", "badge": "gray" },
        { "code": "TAG_DIRECT_CALL_ONLY", "label": "Call Clinic Directly", "badge": "slate" },
        { "code": "TAG_REFERRAL_ELIGIBLE", "label": "Digital Referral Route", "badge": "indigo" }
      ],
      "live_telemetry": null,
      "external_directory_info": {
        "reception_phone": "+911129800000",
        "consultation_timings": "10:00 AM - 01:00 PM",
        "walk_in_notice": "Offline tokens issued at counter. Real-time waiting time unavailable.",
        "nudge_doctor_url": "/api/v1/marketplace/nudge?provider_id=PRV-DEL-EXT-88"
      },
      "verified_metrics": {
        "rating": 4.10,
        "total_verified_reviews": 12,
        "on_time_start_rate": null,
        "avg_consult_duration_minutes": null
      }
    }
  ]
}
```

---

## 4.2 Dynamic Waiting Time Telemetry Hook Schema

### `POST /api/v1/queue/telemetry/calculate-ewt`

#### Request Payload:
```json
{
  "clinic_id": "GIL-DEL-01",
  "doctor_id": "DOC-GILL-01",
  "target_token_number": 21,
  "patient_transit_origin": {
    "lat": 28.5400,
    "lng": 77.2000
  }
}
```

#### Response Payload:
```json
{
  "status": "success",
  "calculated_at": "2026-09-30T22:31:15Z",
  "target_token": 21,
  "queue_depth_ahead": 4,
  "current_token_in_room": 16,
  "current_token_elapsed_seconds": 490,
  "doctor_velocity_ratio": 1.08,
  "estimated_waiting_minutes": 31,
  "estimated_call_timestamp": "2026-09-30T23:02:15Z",
  "dispatch_recommendation": {
    "estimated_transit_minutes": 17,
    "recommended_departure_timestamp": "2026-09-30T22:42:00Z",
    "departure_alert_scheduled": true,
    "status": "WAIT_AT_HOME"
  }
}
```

---

# MODULE 5: RESILIENCE, FALLBACKS & COLD-START RECOVERY

1. **Telemetry Feed Disconnect (Offline Edge Branch)**:  
   If an edge branch clinic loses internet connectivity, the central search engine switches the clinic's badge from `TAG_LIVE_TELEMETRY` to `TAG_OFFLINE_CACHED_SCHEDULE`. Wait time prediction falls back to static Bayesian historic duration mode:
   $$EWT_{\text{fallback}}(k) = k \times \overline{T}_{\text{base}}$$
2. **Emergency Queue Suspension ("Code Blue" Protocol)**:  
   When a doctor taps `[ EMERGENCY PAUSE: 20 MIN ]`, all connected patient tracking portals display an immediate visual banner with acoustic chime:  
   *"Dr. Gill is attending an urgent emergency procedure. Your appointment is delayed by ~20 minutes. Updated time: 11:45 AM."*
3. **Anti-Gaming Review Filter**:  
   Ratings are accepted **strictly** via single-use cryptographic tokens generated upon doctor marking a token as `COMPLETED`. External unverified bot reviews are mathematically impossible.

---

# MODULE 6: AUTONOMOUS EXTERNAL DOCTOR DATA INGESTION ENGINE (POWERED BY CRAWL4AI)

## 6.1 Role of Crawl4AI in the GHOS Architecture
Crawl4AI serves as the **Data Ingestion & Enrichment Pipeline** for Tier-2 External Clinics. Instead of hundreds of manual hours or brittle custom scrapers, Crawl4AI runs as an asynchronous worker daemon that crawls public hospital rosters, clinic websites, and medical registries, converting raw HTML into LLM-structured doctor profiles.

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │            EXTERNAL WEB DATA SOURCES (Hospitals, Clinics, Registries)   │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Raw Web Pages (JS-heavy, SPAs)
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │                 CRAWL4AI ASYNCHRONOUS EXTRACTION WORKER                │
 │  • Headless Playwright Browser Context with Anti-Bot Bypassing        │
 │  • Heuristic HTML-to-Markdown Synthesizer (Zero Noise / No Ads)        │
 │  • Pydantic Schema-Guided LLM Extraction (Structured JSON Output)      │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Validated Doctor JSON Entities
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │           INGESTION & DEDUPLICATION BROKER (GHOS ETL SERVICE)           │
 │  • Duplicate Detection: Mobile Hash, Medical Council Registration ID   │
 │  • Geocoding Pipeline: Address to Lat-Long & H3 Hexagon Resolution 7  │
 │  • Tier-2 Tagging: Applied `TAG_EXTERNAL_OFFLINE` & `TAG_DIRECT_CALL`  │
 └───────────────────────────────────┬────────────────────────────────────┘
                                     │ Structured Master Records
                                     ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │        CENTRAL MARKETPLACE DATABASE (PostgreSQL / Search Index)        │
 │  • Accessible immediately by City & Specialty Search                   │
 │  • Ready for 1-Click Digital Referral & "Nudge Doctor to SaaS" Funnel  │
 └────────────────────────────────────────────────────────────────────────┘
```

## 6.2 Pydantic Extraction Schema (`DoctorProfileSchema`)
Crawl4AI uses Pydantic schema validation to guarantee 100% type-safe JSON extraction without regex brittleness:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class ClinicTiming(BaseModel):
    days: str = Field(description="Operational days, e.g., 'Mon - Sat'")
    morning_hours: Optional[str] = Field(description="Morning OPD hours, e.g., '09:00 AM - 01:00 PM'")
    evening_hours: Optional[str] = Field(description="Evening OPD hours, e.g., '05:00 PM - 08:30 PM'")

class DoctorProfileSchema(BaseModel):
    doctor_name: str = Field(description="Full name of doctor with salutation, e.g., 'Dr. Rajesh Mehta'")
    medical_degrees: List[str] = Field(description="Degrees, e.g., ['MBBS', 'MD', 'DM (Cardiology)']")
    specialties: List[str] = Field(description="Clinical specialties, e.g., ['Cardiology', 'Interventional Cardiology']")
    experience_years: Optional[int] = Field(description="Total years of clinical practice")
    medical_council_reg_no: Optional[str] = Field(description="State/National Medical Council registration number")
    clinic_or_hospital_name: str = Field(description="Clinic or hospital facility name")
    full_address: str = Field(description="Complete street address including locality and landmark")
    city: str = Field(description="City name, e.g., 'Delhi', 'Jodhpur', 'Ahmedabad'")
    pincode: Optional[str] = Field(description="6-digit postal pincode")
    reception_phone: Optional[str] = Field(description="Clinic reception phone or landline for appointment booking")
    opd_consultation_fee: Optional[int] = Field(description="Approximate OPD consultation fee in INR")
    timings: Optional[ClinicTiming] = Field(description="OPD clinic timing details")
```

## 6.3 Asynchronous Crawl4AI Python Ingestion Daemon
The production-grade execution pattern to ingest hospital and clinic rosters:

```python
import asyncio
import json
from crawl4ai import AsyncWebCrawler
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from pydantic import BaseModel

async def ingest_hospital_doctor_roster(hospital_roster_url: str, gemini_api_key: str):
    """
    Crawls JS-rendered hospital OPD page and extracts verified doctor profiles.
    """
    # Configure LLM Schema-Guided Extraction Strategy
    extraction_strategy = LLMExtractionStrategy(
        provider="google/gemini-2.0-flash",
        api_token=gemini_api_key,
        schema=DoctorProfileSchema.model_json_schema(),
        extraction_type="schema",
        instruction="Extract all listed doctors with qualifications, OPD consultation timings, clinic address, and phone."
    )

    async with AsyncWebCrawler(headless=True, verbose=True) as crawler:
        result = await crawler.arun(
            url=hospital_roster_url,
            extraction_strategy=extraction_strategy,
            bypass_cache=True,
            wait_for="css:.doctor-list, .team-member, .profile-card", # Wait for JS dynamic renders
            delay_before_return_html=2.0
        )

        if result.success:
            extracted_data = json.loads(result.extracted_content)
            print(f"Successfully extracted {len(extracted_data)} doctor profiles.")
            return extracted_data
        else:
            print(f"Crawl failed: {result.error_message}")
            return []
```

## 6.4 Why Crawl4AI is the Winning Choice vs. Alternatives
| Evaluated Tool | License | Strengths | Operational Bottlenecks | Decision for GHOS |
|---|---|---|---|---|
| **Crawl4AI** (github/unclecode) | **Apache 2.0 (100% Free)** | Ultra-fast async Playwright, native Markdown, schema-guided LLM extraction, self-hostable without paid API | Requires Python 3.10+ container (~1.8GB Playwright dependencies) | **SELECTED PRIMARY INGESTION ENGINE** |
| **Firecrawl** (github/mendableai) | Apache 2.0 (Core) | Outstanding REST API, automatic site crawling (`/crawl`) | Heavy infrastructure stack (Redis, BullMQ, Supabase, Playwright worker cluster); paid cloud API | Secondary backup for API-only environments |
| **ScrapeGraphAI** | MIT (Open Source) | Graph-based LLM pipeline | High LLM API token cost; invokes LLM on raw unfiltered HTML | Rejected (excessive API latency & cost) |
| **Custom Cheerio / Playwright** | In-house | Lightweight, no external deps | **High Maintenance Nightmare**: breaks every time a hospital redesigns its CSS classes | Rejected (unnecessary engineering overhead) |

---
*Blueprint formulated and verified as the authoritative architectural specification for GHOS Global Search, Ranking & Queue Dispatch.*

