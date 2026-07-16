# 005 — DATABASE

*Complete database schema for all 13 domains.*
*PostgreSQL with separate schemas per domain.*

---

## Conventions

- All tables use UUIDv7 primary keys
- All tables have created_at and updated_at timestamps
- Soft delete via deleted_at column where applicable
- Indexes on all foreign key columns and frequently queried fields
- No cross-schema foreign keys
- JSONB for flexible metadata fields
- Encrypted columns use pgcrypto or application-level encryption

## Schema: identity

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username VARCHAR(100) UNIQUE NOT NULL,
  full_name VARCHAR(200) NOT NULL,
  role VARCHAR(50) NOT NULL,
  department VARCHAR(50),
  pin_hash VARCHAR(255),
  phone VARCHAR(20) UNIQUE,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(50) UNIQUE NOT NULL,
  description TEXT,
  hierarchy_level INT NOT NULL
);

CREATE TABLE permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  role_id UUID REFERENCES roles(id),
  resource VARCHAR(100) NOT NULL,
  action VARCHAR(50) NOT NULL,
  UNIQUE(role_id, resource, action)
);

CREATE TABLE otp_codes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  code VARCHAR(6) NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## Schema: patient

```sql
CREATE TABLE patients (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id VARCHAR(20) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  phone VARCHAR(20) NOT NULL,
  dob DATE,
  gender VARCHAR(10),
  address JSONB,
  blood_group VARCHAR(5),
  emergency_contact JSONB,
  pii_encrypted JSONB,
  consent_given BOOLEAN DEFAULT false,
  consent_date TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_name ON patients(name);
```

## Schema: queue

```sql
CREATE TABLE queue_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token VARCHAR(20) NOT NULL,
  patient_id UUID NOT NULL,
  department VARCHAR(50) NOT NULL,
  status VARCHAR(20) DEFAULT 'waiting',
  priority INT DEFAULT 0,
  called_count INT DEFAULT 0,
  entered_at TIMESTAMPTZ DEFAULT now(),
  called_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  UNIQUE(department, token, date_trunc('day', entered_at))
);

CREATE INDEX idx_queue_dept_status ON queue_entries(department, status);
CREATE INDEX idx_queue_patient ON queue_entries(patient_id);

CREATE TABLE token_sequence (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  department VARCHAR(50) NOT NULL,
  date DATE NOT NULL,
  last_seq INT DEFAULT 0,
  UNIQUE(department, date)
);
```

## Schema: workflow

```sql
CREATE TABLE visits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL,
  current_state VARCHAR(50) NOT NULL,
  visit_type VARCHAR(20) DEFAULT 'standard',
  entered_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE state_transitions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  visit_id UUID NOT NULL,
  from_state VARCHAR(50),
  to_state VARCHAR(50) NOT NULL,
  actor_id UUID,
  reason TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## Schema: clinical

```sql
CREATE TABLE test_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  visit_id UUID NOT NULL,
  test_type VARCHAR(100) NOT NULL,
  values JSONB NOT NULL,
  signed_by UUID,
  signed_at TIMESTAMPTZ,
  is_critical BOOLEAN DEFAULT false,
  report_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE prescriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  visit_id UUID NOT NULL,
  doctor_id UUID NOT NULL,
  items JSONB NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE vitals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  patient_id UUID NOT NULL,
  bp_systolic INT,
  bp_diastolic INT,
  heart_rate INT,
  temperature DECIMAL(4,1),
  spo2 INT,
  recorded_at TIMESTAMPTZ DEFAULT now()
);
```

## Schema: billing

```sql
CREATE TABLE bills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  invoice_no VARCHAR(30) UNIQUE NOT NULL,
  patient_id UUID NOT NULL,
  visit_id UUID,
  items JSONB NOT NULL,
  subtotal DECIMAL(12,2) NOT NULL,
  discount DECIMAL(12,2) DEFAULT 0,
  tax DECIMAL(12,2) DEFAULT 0,
  total DECIMAL(12,2) NOT NULL,
  paid DECIMAL(12,2) DEFAULT 0,
  balance DECIMAL(12,2) DEFAULT 0,
  status VARCHAR(20) DEFAULT 'pending',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  bill_id UUID NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  method VARCHAR(30) NOT NULL,
  reference_no VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT now()
);
```

## Schema: inventory

```sql
CREATE TABLE categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(100) NOT NULL,
  parent_id UUID REFERENCES categories(id),
  requires_batch BOOLEAN DEFAULT true,
  requires_expiry BOOLEAN DEFAULT true,
  is_cold_chain BOOLEAN DEFAULT false
);

CREATE TABLE items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku VARCHAR(50) UNIQUE NOT NULL,
  name VARCHAR(200) NOT NULL,
  generic_name VARCHAR(200),
  category_id UUID REFERENCES categories(id),
  manufacturer VARCHAR(200),
  unit VARCHAR(20) NOT NULL,
  reorder_level INT DEFAULT 10,
  reorder_qty INT DEFAULT 50,
  hsn_code VARCHAR(20),
  is_active BOOLEAN DEFAULT true
);

CREATE TABLE batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  item_id UUID REFERENCES items(id),
  batch_no VARCHAR(100) NOT NULL,
  mfg_date DATE,
  expiry_date DATE NOT NULL,
  quantity INT NOT NULL,
  unit_rate DECIMAL(12,2),
  mrp DECIMAL(12,2),
  is_cold_chain BOOLEAN DEFAULT false
);
```

## Schema: audit

```sql
CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type VARCHAR(100) NOT NULL,
  actor_id UUID,
  actor_type VARCHAR(20),
  target_type VARCHAR(50),
  target_id UUID,
  payload JSONB,
  hash VARCHAR(64) NOT NULL,
  prev_hash VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT now()
);
```

(Other schema definitions available in individual domain modules.)
