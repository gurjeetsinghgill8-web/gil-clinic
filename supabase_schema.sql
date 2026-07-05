-- ============================================================
-- CardioQueue — Supabase Database Schema  v2.1
-- ============================================================
-- CHANGES v2.1:
--   • tests: added pending_alert, alert_message  (BRICK 1)
--   • Added: users table                         (replaces hard-coded staff)
--   • Added: departments table                   (BRICK 6 dynamic depts)
--   • Added: clinic_settings table               (BRICK 5 multi-tenant)
-- ============================================================
-- Run this entire SQL in your Supabase SQL Editor to set up
-- all tables, indexes, and Row Level Security policies.
-- ============================================================

-- ─── 1. PATIENTS TABLE ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT UNIQUE NOT NULL,          -- e.g., "CQ-20260630-001"
    name TEXT NOT NULL,
    mobile VARCHAR(10) NOT NULL,
    age INTEGER NOT NULL,
    gender TEXT NOT NULL CHECK (gender IN ('Male', 'Female', 'Other')),
    registration_date DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for fast mobile lookup
CREATE INDEX IF NOT EXISTS idx_patients_mobile ON patients(mobile);
CREATE INDEX IF NOT EXISTS idx_patients_date ON patients(registration_date);
CREATE INDEX IF NOT EXISTS idx_patients_patient_id ON patients(patient_id);


-- ─── 2. TESTS TABLE ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS tests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    test_name TEXT NOT NULL CHECK (test_name IN ('ECG', 'Echo', 'TMT', 'Holter', 'ABPM')),
    status TEXT NOT NULL DEFAULT 'waiting'
        CHECK (status IN ('waiting', 'called', 'in_progress', 'completed', 'report_ready', 'delivered')),
    token_number INTEGER NOT NULL,           -- Daily sequential per test type
    queue_position INTEGER DEFAULT 0,
    room TEXT NOT NULL,
    called_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    report_ready_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    -- BRICK 1: DB-poll alert system (staff → patient phone)
    pending_alert INTEGER NOT NULL DEFAULT 0,
    alert_message TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for queue queries
CREATE INDEX IF NOT EXISTS idx_tests_patient_id ON tests(patient_id);
CREATE INDEX IF NOT EXISTS idx_tests_test_name ON tests(test_name);
CREATE INDEX IF NOT EXISTS idx_tests_status ON tests(status);
CREATE INDEX IF NOT EXISTS idx_tests_token ON tests(test_name, token_number);


-- ─── 3. MESSAGES TABLE (Notification Log) ───────────────────────────────────

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    mobile VARCHAR(10) NOT NULL,
    message_type TEXT NOT NULL CHECK (message_type IN ('registration', 'called', 'completed', 'report_ready')),
    message_text TEXT NOT NULL,
    sent_via TEXT NOT NULL DEFAULT 'none' CHECK (sent_via IN ('none', 'browser', 'whatsapp')),
    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_patient ON messages(patient_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages(sent_at);


-- ─── 4. DAILY TOKEN RESET FUNCTION (optional) ───────────────────────────────
-- Run this via Supabase cron or manually each day to reset tokens.
-- Actually, our token generation in Python handles daily reset via
-- looking at today's max token, so this is just a safety net.

CREATE OR REPLACE FUNCTION reset_daily_sequence()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    -- Token reset is handled application-side in utils/db.py
    -- This function is a placeholder for future cron-based cleanup
    -- e.g., archiving old records
    DELETE FROM messages WHERE sent_at < NOW() - INTERVAL '90 days';
END;
$$;


-- ─── 5. ROW LEVEL SECURITY ─────────────────────────────────────────────────

-- Enable RLS on all tables
ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
ALTER TABLE tests ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Allow anon key to read/write (for Phase 1 simplicity)
-- In production, replace with proper auth policies
CREATE POLICY "Allow all operations for anon" ON patients
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon" ON tests
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY "Allow all operations for anon" ON messages
    FOR ALL USING (true) WITH CHECK (true);


-- ─── 6. USERS TABLE (Staff Accounts) ───────────────────────────────────────
-- Stores all staff logins (receptionist, ECG tech, doctor, admin)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'receptionist', 'ecg', 'echo', 'tmt', 'opd', 'holter', 'abpm', 'doctor', 'manager')),
    password TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations for anon" ON users
    FOR ALL USING (true) WITH CHECK (true);


-- ─── 7. DEPARTMENTS TABLE (BRICK 6 — Dynamic Depts) ─────────────────────────
-- Admin can add/remove departments without touching code.

CREATE TABLE IF NOT EXISTS departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,               -- e.g. "ECG", "Echo", "Ultrasound"
    display_name TEXT NOT NULL,              -- e.g. "ECG Room"
    room TEXT NOT NULL DEFAULT '',           -- default room label
    avg_time_minutes INTEGER NOT NULL DEFAULT 15,
    icon TEXT NOT NULL DEFAULT '📋',
    active INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_depts_name ON departments(name);
CREATE INDEX IF NOT EXISTS idx_depts_active ON departments(active);

ALTER TABLE departments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations for anon" ON departments
    FOR ALL USING (true) WITH CHECK (true);

-- Default departments for GIL CLINIC (run once)
INSERT INTO departments (name, display_name, room, avg_time_minutes, icon, sort_order)
VALUES
    ('ECG',   'ECG',        'ECG Room 1',  10, '❤️',  1),
    ('Echo',  'Echo',       'Echo Room 1', 20, '🫀',  2),
    ('TMT',   'TMT',        'TMT Room 1',  30, '🏃',  3),
    ('OPD',   'OPD',        'OPD Room 1',  15, '🩺',  4),
    ('Holter','Holter',     'ECG Room 1',  10, '📟',  5),
    ('ABPM',  'ABPM',       'ECG Room 1',  10, '💉',  6)
ON CONFLICT (name) DO NOTHING;


-- ─── 8. CLINIC SETTINGS TABLE (BRICK 5 — Multi-Tenant SaaS) ─────────────────
-- One row per clinic deployment. Drives all white-label config.

CREATE TABLE IF NOT EXISTS clinic_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id TEXT UNIQUE NOT NULL DEFAULT 'default',
    clinic_name TEXT NOT NULL DEFAULT 'GIL CLINIC',
    specialty TEXT NOT NULL DEFAULT 'Cardiology',
    logo_emoji TEXT NOT NULL DEFAULT '🏥',
    phone TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    owner_username TEXT NOT NULL DEFAULT 'admin',
    plan_type TEXT NOT NULL DEFAULT 'basic'
        CHECK (plan_type IN ('free', 'basic', 'pro', 'enterprise')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE clinic_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all operations for anon" ON clinic_settings
    FOR ALL USING (true) WITH CHECK (true);

-- Insert default clinic row (idempotent)
INSERT INTO clinic_settings (clinic_id, clinic_name, specialty, logo_emoji)
VALUES ('default', 'GIL CLINIC', 'Cardiology', '🏥')
ON CONFLICT (clinic_id) DO NOTHING;


-- ─── 9. SAMPLE DATA (for testing) ──────────────────────────────────────────
-- Uncomment to insert sample data:

-- INSERT INTO patients (patient_id, name, mobile, age, gender)
-- VALUES
--     ('CQ-20260630-001', 'Rajesh Kumar', '9876543210', 45, 'Male'),
--     ('CQ-20260630-002', 'Sunita Devi', '9876543211', 52, 'Female'),
--     ('CQ-20260630-003', 'Amit Singh', '9876543212', 38, 'Male');
--
-- INSERT INTO tests (patient_id, test_name, token_number, queue_position, room)
-- VALUES
--     ('CQ-20260630-001', 'ECG',  1, 1, 'ECG Room 1'),
--     ('CQ-20260630-001', 'Echo', 1, 1, 'Echo Room 1'),
--     ('CQ-20260630-002', 'ECG',  2, 2, 'ECG Room 1'),
--     ('CQ-20260630-003', 'TMT',  1, 1, 'TMT Room 1');
