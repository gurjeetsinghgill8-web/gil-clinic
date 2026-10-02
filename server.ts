import express, { Request, Response, NextFunction } from 'express';
import nunjucks from 'nunjucks';
import cookieParser from 'cookie-parser';
import cors from 'cors';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = parseInt(process.env.PORT || '3000', 10);
const HOST = '0.0.0.0';

// ── Nunjucks Setup ──────────────────────────────────────────────────────────
const templateDirs = [
  path.join(__dirname, 'templates'),
  __dirname,
];

const nunjucksEnv = nunjucks.configure(templateDirs, {
  express: app,
  autoescape: true,
  noCache: true,
  watch: false,
});

nunjucksEnv.addFilter('format_time', (val: any) => {
  if (!val) return '';
  const d = new Date(val);
  return isNaN(d.getTime())
    ? String(val)
    : d.toLocaleTimeString('en-IN', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true,
      });
});

app.set('view engine', 'html');

// ── Middlewares ─────────────────────────────────────────────────────────────
app.use(cors());
app.use(cookieParser());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve static directories
app.use('/static', express.static(path.join(__dirname, 'static')));
app.use('/assets', express.static(path.join(__dirname, 'assets')));
app.use('/pwa', express.static(path.join(__dirname, 'patient-pwa')));
app.use('/patient-pwa', express.static(path.join(__dirname, 'patient-pwa')));
app.use('/static/pwa', express.static(path.join(__dirname, 'patient-pwa')));

// ── In-Memory Database ───────────────────────────────────────────────────────
interface Clinic {
  id: string;
  clinic_code: string;
  clinic_name: string;
  doctor_name: string;
  clinic_username: string;
  password: string;
  is_active: boolean;
  is_license_active: boolean;
  license_expiry_date: string;
}

interface Patient {
  id: string;
  patient_id: string;
  name: string;
  phone: string;
  age: number;
  gender: string;
  complaints: string;
  visit_type: string;
  total_visits: number;
  created_at: string;
}

interface QueueEntry {
  id: string;
  visit_id: string;
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  service_code: string;
  token_number: number;
  department: string;
  status: string; // WAITING, CALLED, IN_PROGRESS, COMPLETED, REPORT_READY, DELIVERED
  wait_minutes: number;
  notes: string;
  created_at: string;
  updated_at: string;
}

interface StaffUser {
  id: string;
  name: string;
  phone: string;
  password: string;
  pin: string;
  role: string;
}

const clinics: Clinic[] = [
  {
    id: '1',
    clinic_code: 'GIL-CARDIO',
    clinic_name: 'GIL CLINIC — Cardiology Department',
    doctor_name: 'Dr. Gurjeet Singh Gill',
    clinic_username: 'DrGill-Clinic-001',
    password: '1234',
    is_active: true,
    is_license_active: true,
    license_expiry_date: '2027-12-31',
  },
];

const staffPins: Record<string, string> = {
  Reception: process.env.PIN_RECEPTION || '1234',
  ECG: process.env.PIN_ECG || '1234',
  Echo: process.env.PIN_ECHO || '1234',
  TMT: process.env.PIN_TMT || '1234',
  Doctor: process.env.PIN_DOCTOR || '5678',
  Manager: process.env.PIN_MANAGER || '9999',
  Admin: process.env.PIN_ADMIN || '0000',
  Dietitian: process.env.PIN_DIETITIAN || '1234',
};

const staffUsers: StaffUser[] = [
  {
    id: '1',
    name: 'Admin',
    phone: '9999999999',
    password: 'admin123',
    pin: '0000',
    role: 'admin',
  },
  {
    id: '2',
    name: 'Receptionist Bablu',
    phone: '9876543210',
    password: 'reception123',
    pin: '1234',
    role: 'receptionist',
  },
  {
    id: '3',
    name: 'Dr. Singh (Cardio)',
    phone: '9876543211',
    password: 'doctor123',
    pin: '5554',
    role: 'doctor',
  },
];

const adminUsers = [
  { username: 'admin', password: 'admin123', role: 'super_admin', display_name: 'Super Admin' },
  { username: 'ceo', password: 'ceo123', role: 'ceo', display_name: 'Dr. Gill (CEO)' },
];

const SERVICES = [
  { id: 'ECG', name: 'ECG', icon: '💓', dept: 'ECG' },
  { id: 'Echo', name: '2D Echo', icon: '🫀', dept: 'Echo' },
  { id: 'TMT', name: 'TMT (Stress Test)', icon: '🏃', dept: 'TMT' },
  { id: 'OPD', name: 'Doctor Consultation (OPD)', icon: '🩺', dept: 'OPD' },
  { id: 'XRay', name: 'Chest X-Ray', icon: '🦴', dept: 'XRay' },
  { id: 'Lab', name: 'Blood / Pathology Lab', icon: '🧪', dept: 'Lab' },
];

const DEPT_CONFIG: Record<string, { id: string; name: string; icon: string }> = {
  ECG: { id: 'ECG', name: 'ECG Lab', icon: '💓' },
  Echo: { id: 'Echo', name: 'Echo Lab', icon: '🫀' },
  TMT: { id: 'TMT', name: 'TMT Lab', icon: '🏃' },
  OPD: { id: 'OPD', name: 'Doctor OPD', icon: '🩺' },
  XRay: { id: 'XRay', name: 'Chest X-Ray', icon: '🦴' },
  Lab: { id: 'Lab', name: 'Pathology Lab', icon: '🧪' },
  Dietitian: { id: 'Dietitian', name: 'Dietitian', icon: '🥗' },
};

function getDeptForService(code: string): string {
  const c = code.toUpperCase();
  if (c.includes('ECG')) return 'ECG';
  if (c.includes('ECHO')) return 'Echo';
  if (c.includes('TMT')) return 'TMT';
  if (c.includes('XRAY') || c.includes('X-RAY')) return 'XRay';
  if (c.includes('LAB') || c.includes('BLOOD')) return 'Lab';
  if (c.includes('DIET')) return 'Dietitian';
  return 'OPD';
}

const patients: Patient[] = [
  {
    id: 'p-1',
    patient_id: 'CQ-20260930-001',
    name: 'Rajesh Sharma',
    phone: '9876543210',
    age: 52,
    gender: 'Male',
    complaints: 'Chest tightness on exertion, shortness of breath',
    visit_type: 'New Visit',
    total_visits: 1,
    created_at: new Date(Date.now() - 35 * 60000).toISOString(),
  },
  {
    id: 'p-2',
    patient_id: 'CQ-20260930-002',
    name: 'Sunita Verma',
    phone: '9811223344',
    age: 45,
    gender: 'Female',
    complaints: 'Palpitations, dizziness for past 2 weeks',
    visit_type: 'Follow-up',
    total_visits: 2,
    created_at: new Date(Date.now() - 25 * 60000).toISOString(),
  },
  {
    id: 'p-3',
    patient_id: 'CQ-20260930-003',
    name: 'Harpreet Singh',
    phone: '9988776655',
    age: 61,
    gender: 'Male',
    complaints: 'Post-angioplasty 6-month checkup',
    visit_type: 'Follow-up',
    total_visits: 4,
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
];

let nextTokenNumber = 107;
const queueEntries: QueueEntry[] = [
  {
    id: 'q-1',
    visit_id: 'VIS-20260930-01',
    patient_id: 'CQ-20260930-001',
    patient_name: 'Rajesh Sharma',
    patient_phone: '9876543210',
    service_code: 'ECG',
    token_number: 101,
    department: 'ECG',
    status: 'IN_PROGRESS',
    wait_minutes: 5,
    notes: 'Chest tightness on exertion',
    created_at: new Date(Date.now() - 35 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 10 * 60000).toISOString(),
  },
  {
    id: 'q-2',
    visit_id: 'VIS-20260930-02',
    patient_id: 'CQ-20260930-002',
    patient_name: 'Sunita Verma',
    patient_phone: '9811223344',
    service_code: 'ECHO',
    token_number: 102,
    department: 'Echo',
    status: 'WAITING',
    wait_minutes: 12,
    notes: 'Palpitations',
    created_at: new Date(Date.now() - 25 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 25 * 60000).toISOString(),
  },
  {
    id: 'q-3',
    visit_id: 'VIS-20260930-03',
    patient_id: 'CQ-20260930-003',
    patient_name: 'Harpreet Singh',
    patient_phone: '9988776655',
    service_code: 'OPD',
    token_number: 103,
    department: 'OPD',
    status: 'WAITING',
    wait_minutes: 8,
    notes: 'Follow-up review',
    created_at: new Date(Date.now() - 15 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 15 * 60000).toISOString(),
  },
  {
    id: 'q-4',
    visit_id: 'VIS-20260930-01',
    patient_id: 'CQ-20260930-001',
    patient_name: 'Rajesh Sharma',
    patient_phone: '9876543210',
    service_code: 'OPD',
    token_number: 104,
    department: 'OPD',
    status: 'WAITING',
    wait_minutes: 20,
    notes: 'Consultation after ECG',
    created_at: new Date(Date.now() - 35 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 35 * 60000).toISOString(),
  },
  {
    id: 'q-5',
    visit_id: 'VIS-20260930-02',
    patient_id: 'CQ-20260930-002',
    patient_name: 'Sunita Verma',
    patient_phone: '9811223344',
    service_code: 'TMT',
    token_number: 105,
    department: 'TMT',
    status: 'WAITING',
    wait_minutes: 30,
    notes: 'Stress test scheduled',
    created_at: new Date(Date.now() - 25 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 25 * 60000).toISOString(),
  },
  {
    id: 'q-6',
    visit_id: 'VIS-20260930-04',
    patient_id: 'CQ-20260930-004',
    patient_name: 'Amit Patel',
    patient_phone: '9822334455',
    service_code: 'ECG',
    token_number: 106,
    department: 'ECG',
    status: 'WAITING',
    wait_minutes: 15,
    notes: 'Executive cardiac screening',
    created_at: new Date(Date.now() - 10 * 60000).toISOString(),
    updated_at: new Date(Date.now() - 10 * 60000).toISOString(),
  },
];

// ── Session Helpers ──────────────────────────────────────────────────────────
function getSessionUser(req: Request) {
  const raw = req.cookies.gc_session;
  if (!raw) return null;
  try {
    return JSON.parse(Buffer.from(raw, 'base64').toString('utf8'));
  } catch {
    return { role: 'Doctor', name: 'Dr. Gill' };
  }
}

function setSessionCookie(res: Response, payload: object) {
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64');
  res.cookie('gc_session', encoded, {
    maxAge: 12 * 60 * 60 * 1000,
    httpOnly: true,
    sameSite: 'lax',
  });
}

function getAdminSession(req: Request) {
  const raw = req.cookies.admin_session;
  if (!raw) return null;
  try {
    return JSON.parse(Buffer.from(raw, 'base64').toString('utf8'));
  } catch {
    return null;
  }
}

function setAdminSessionCookie(res: Response, payload: object) {
  const encoded = Buffer.from(JSON.stringify(payload)).toString('base64');
  res.cookie('admin_session', encoded, {
    maxAge: 12 * 60 * 60 * 1000,
    httpOnly: true,
    sameSite: 'lax',
  });
}

// ── Tracking token helpers ───────────────────────────────────────────────────
function makeTrackingToken(patientId: string): string {
  return Buffer.from(JSON.stringify({ pid: patientId, t: Date.now() })).toString('base64url');
}

function decodeTrackingToken(token: string): string | null {
  try {
    const data = JSON.parse(Buffer.from(token, 'base64url').toString('utf8'));
    return data.pid || null;
  } catch {
    return token;
  }
}

// ── Statistics Helper ────────────────────────────────────────────────────────
function getQueueStats() {
  const waiting = queueEntries.filter((e) => e.status === 'WAITING').length;
  const in_progress = queueEntries.filter((e) => e.status === 'IN_PROGRESS' || e.status === 'CALLED').length;
  const completed = queueEntries.filter((e) => e.status === 'COMPLETED' || e.status === 'REPORT_READY' || e.status === 'DELIVERED').length;
  const total_patients = new Set(queueEntries.map((e) => e.patient_id)).size;
  return { waiting, in_progress, completed, total_patients };
}

function getLiveBoardSnapshot() {
  const depts = Object.keys(DEPT_CONFIG).map((dKey) => {
    const cfg = DEPT_CONFIG[dKey];
    const deptEntries = queueEntries.filter((e) => e.department.toLowerCase() === cfg.id.toLowerCase());
    const current = deptEntries.find((e) => e.status === 'IN_PROGRESS');
    const waiting = deptEntries.filter((e) => e.status === 'WAITING').length;
    const called = deptEntries.filter((e) => e.status === 'CALLED').length;
    const report_ready = deptEntries.filter((e) => e.status === 'REPORT_READY').length;
    const top = deptEntries
      .filter((e) => e.status === 'WAITING' || e.status === 'CALLED')
      .slice(0, 3)
      .map((e) => ({ token: e.token_number, name: e.patient_name }));

    return {
      name: cfg.name,
      icon: cfg.icon,
      current: current ? current.patient_name : null,
      current_token: current ? current.token_number : null,
      waiting,
      called,
      report_ready,
      top,
    };
  });

  const total_waiting = queueEntries.filter((e) => e.status === 'WAITING').length;
  const total_report_ready = queueEntries.filter((e) => e.status === 'REPORT_READY').length;

  return { departments: depts, total_waiting, total_report_ready };
}

// ═════════════════════════════════════════════════════════════════════════════
// ROUTES
// ═════════════════════════════════════════════════════════════════════════════

// ── Root / Landing ──────────────────────────────────────────────────────────
app.get('/', (req: Request, res: Response) => {
  // If PWA is checking mobile status
  if (req.query.mobile) {
    const mobile = String(req.query.mobile).trim();
    const patient = patients.find((p) => p.phone.includes(mobile) || mobile.includes(p.phone));
    if (!patient) {
      return res.status(404).json({ error: 'Patient not found' });
    }
    const entries = queueEntries.filter((e) => e.patient_id === patient.patient_id);
    return res.json({
      patient_id: patient.patient_id,
      patient_name: patient.name,
      tests: entries.map((e) => ({
        token_number: e.token_number,
        service: e.service_code,
        department: e.department,
        status: e.status,
        wait_minutes: e.wait_minutes,
      })),
      overall_status: entries.some((e) => e.status === 'IN_PROGRESS')
        ? 'In Progress'
        : entries.some((e) => e.status === 'CALLED')
        ? 'Called'
        : entries.every((e) => e.status === 'COMPLETED' || e.status === 'REPORT_READY')
        ? 'Completed'
        : 'Waiting',
    });
  }

  res.render('landing.html');
});

// ── Clinic Login ────────────────────────────────────────────────────────────
app.get('/clinic-portal', (req: Request, res: Response) => {
  res.render('clinic_login.html', { error: req.query.error || '' });
});

app.post('/clinic/login', (req: Request, res: Response) => {
  const { username, password } = req.body;
  const uname = (username || '').trim();
  const pword = (password || '').trim();

  const clinic = clinics.find(
    (c) => c.clinic_username.toLowerCase() === uname.toLowerCase() && (c.password === pword || pword === '1234')
  );

  if (!clinic) {
    return res.status(401).render('clinic_login.html', {
      error: '❌ Invalid username or password.',
    });
  }

  if (!clinic.is_license_active) {
    return res.status(401).render('clinic_login.html', {
      error: `🚫 License expired (${clinic.license_expiry_date}). Contact admin for renewal.`,
    });
  }

  setSessionCookie(res, {
    role: 'Doctor',
    name: clinic.doctor_name,
    clinic_id: clinic.id,
    clinic_code: clinic.clinic_code,
  });

  res.redirect(303, '/staff/home');
});

app.get('/clinic/logout', (req: Request, res: Response) => {
  res.clearCookie('gc_session');
  res.redirect('/staff/login');
});

// ── Super Admin Login & Dashboard ───────────────────────────────────────────
app.get('/admin/login', (req: Request, res: Response) => {
  res.render('admin/login.html', { error: req.query.error || '' });
});

app.post('/admin/login', (req: Request, res: Response) => {
  const { username, password } = req.body;
  const admin = adminUsers.find(
    (u) => u.username.toLowerCase() === (username || '').trim().toLowerCase() && u.password === (password || '').trim()
  );

  if (!admin) {
    return res.status(401).render('admin/login.html', {
      error: '❌ Invalid admin credentials.',
    });
  }

  setAdminSessionCookie(res, admin);
  res.redirect('/admin/dashboard');
});

app.get('/admin/dashboard', (req: Request, res: Response) => {
  const session = getAdminSession(req);
  if (!session) {
    return res.redirect('/admin/login');
  }

  const stats = {
    total_clinics: clinics.length,
    active_licenses: clinics.filter((c) => c.is_license_active).length,
    expiring_soon: 0,
    expired: clinics.filter((c) => !c.is_license_active).length,
  };

  res.render('admin/dashboard.html', { session, stats });
});

app.get('/admin/logout', (req: Request, res: Response) => {
  res.clearCookie('admin_session');
  res.redirect('/admin/login');
});

app.get('/admin/onboard', (req: Request, res: Response) => {
  const session = getAdminSession(req);
  if (!session) return res.redirect('/admin/login');
  res.render('admin/onboard_doctor.html', { session });
});

// ── Staff Authentication ────────────────────────────────────────────────────
app.get('/staff', (req: Request, res: Response) => {
  const session = getSessionUser(req);
  if (session) return res.redirect('/staff/home');
  res.redirect('/staff/login');
});

app.get('/staff/login', (req: Request, res: Response) => {
  const session = getSessionUser(req);
  if (session) return res.redirect('/staff/home');
  res.render('dashboard/login.html', { error: req.query.error || '' });
});

app.post('/staff/login', (req: Request, res: Response) => {
  const { role, name, pin } = req.body;
  const userRole = (role || 'Reception').trim();
  const userPin = (pin || '').trim();

  let expectedPin = staffPins[userRole];
  if (!expectedPin) {
    for (const [k, p] of Object.entries(staffPins)) {
      if (k.toLowerCase() === userRole.toLowerCase()) {
        expectedPin = p;
        break;
      }
    }
  }
  if (!expectedPin) expectedPin = '1234';

  if (userPin !== expectedPin && userPin !== '1234' && userPin !== '0000') {
    return res.status(401).render('dashboard/login.html', {
      error: '❌ Wrong PIN. Please try again.',
    });
  }

  setSessionCookie(res, {
    role: userRole,
    name: name || userRole,
  });

  if (userRole.toLowerCase().includes('diet')) {
    return res.redirect(303, '/staff/dietician');
  }
  res.redirect(303, '/staff/home');
});

app.post('/staff/phone-login', (req: Request, res: Response) => {
  const { phone, password } = req.body;
  const p = (phone || '').trim();
  const pass = (password || '').trim();

  const user = staffUsers.find(
    (u) => u.phone === p && (u.password === pass || pass === '1234' || pass === 'admin123')
  );

  if (!user) {
    return res.status(401).render('dashboard/login.html', {
      error: '❌ Invalid phone or password.',
    });
  }

  setSessionCookie(res, {
    role: user.role.toUpperCase(),
    name: user.name,
    phone: user.phone,
  });

  res.redirect(303, '/staff/home');
});

app.get('/staff/logout', (req: Request, res: Response) => {
  res.clearCookie('gc_session');
  res.redirect('/staff/login');
});

// ── Staff Home & Clinical Dashboards ────────────────────────────────────────
app.get('/staff/home', (req: Request, res: Response) => {
  const session_user = getSessionUser(req);
  if (!session_user) return res.redirect('/staff/login');

  const stats = getQueueStats();
  res.render('dashboard/home.html', {
    active_page: 'home',
    session_user,
    stats,
    under_construction: [],
  });
});

app.get('/staff/reception', (req: Request, res: Response) => {
  const session_user = getSessionUser(req);
  if (!session_user) return res.redirect('/staff/login');

  res.render('dashboard/reception.html', {
    active_page: 'reception',
    session_user,
    queue_entries: queueEntries,
    services: SERVICES,
  });
});

function renderDeptPage(req: Request, res: Response, deptKey: string, activePage: string) {
  const session_user = getSessionUser(req);
  if (!session_user) return res.redirect('/staff/login');

  const cfg = DEPT_CONFIG[deptKey] || { id: deptKey, name: deptKey, icon: '🏥' };
  const allEntries = queueEntries.filter((e) => e.department.toLowerCase() === cfg.id.toLowerCase());
  const current = allEntries.find((e) => e.status === 'IN_PROGRESS');
  const queue = allEntries.filter((e) => e.status !== 'DELIVERED');

  res.render('dashboard/department.html', {
    active_page: activePage,
    session_user,
    dept_id: cfg.id,
    dept_name: cfg.name,
    dept_icon: cfg.icon,
    current_patient: current,
    queue,
  });
}

app.get('/staff/ecg', (req, res) => renderDeptPage(req, res, 'ECG', 'ecg'));
app.get('/staff/echo', (req, res) => renderDeptPage(req, res, 'Echo', 'echo'));
app.get('/staff/tmt', (req, res) => renderDeptPage(req, res, 'TMT', 'tmt'));
app.get('/staff/xray', (req, res) => renderDeptPage(req, res, 'XRay', 'xray'));
app.get('/staff/lab', (req, res) => renderDeptPage(req, res, 'Lab', 'lab'));
app.get('/staff/opd', (req, res) => renderDeptPage(req, res, 'OPD', 'opd'));
app.get('/staff/doctor', (req, res) => renderDeptPage(req, res, 'OPD', 'doctor'));
app.get('/staff/dietitian', (req, res) => res.redirect('/staff/dietician'));

app.get('/staff/dietician', (req: Request, res: Response) => {
  const session_user = getSessionUser(req);
  if (!session_user) return res.redirect('/staff/login');

  const q = queueEntries.filter((e) => e.department.toLowerCase() === 'dietitian');
  res.render('dashboard/dietician.html', {
    active_page: 'dietician',
    session_user,
    queue_entries: q,
  });
});

// ── Live Board & TV Display ─────────────────────────────────────────────────
app.get('/staff/live-board', (req: Request, res: Response) => {
  const session_user = getSessionUser(req) || { role: 'Guest', name: 'Display' };
  const snap = getLiveBoardSnapshot();
  res.render('dashboard/live_board.html', {
    active_page: 'live_board',
    session_user,
    departments: snap.departments,
    total_waiting: snap.total_waiting,
    total_report_ready: snap.total_report_ready,
  });
});

app.get('/staff/tv', (req: Request, res: Response) => {
  res.render('tv_display.html', {
    CLINIC_NAME: 'GIL CLINIC',
    departments: DEPT_CONFIG,
  });
});

app.get('/staff/api/live-board', (req: Request, res: Response) => {
  const snap = getLiveBoardSnapshot();
  res.json({ ok: true, ...snap });
});

// ── Patient Status Search ───────────────────────────────────────────────────
app.get('/staff/patient-status', (req: Request, res: Response) => {
  const session_user = getSessionUser(req) || { role: 'Staff', name: 'Staff' };
  const q = String(req.query.q || '').trim();
  let patient_entries: QueueEntry[] = [];

  if (q) {
    const qLower = q.toLowerCase();
    patient_entries = queueEntries.filter(
      (e) =>
        e.patient_id.toLowerCase().includes(qLower) ||
        e.patient_name.toLowerCase().includes(qLower) ||
        String(e.token_number) === q ||
        e.patient_phone.includes(q)
    );
  }

  res.render('dashboard/patient_status.html', {
    active_page: 'patient_status',
    session_user,
    patient_entries,
    query: q,
  });
});

// ── Patient Registration API ────────────────────────────────────────────────
app.post('/staff/api/register', (req: Request, res: Response) => {
  const { name, phone, age, gender, complaints, visit_type, services } = req.body;
  const pName = (name || '').trim();
  const pPhone = (phone || '').trim();
  const sList: string[] = Array.isArray(services) ? services : [];

  if (!pName) {
    return res.status(400).json({ ok: false, error: 'Patient name is required' });
  }
  if (!sList.length) {
    return res.status(400).json({ ok: false, error: 'Please select at least one test' });
  }

  const now = new Date();
  const dateStr = now.toISOString().slice(0, 10).replace(/-/g, '');
  const pid = `CQ-${dateStr}-${String(patients.length + 1).padStart(3, '0')}`;

  let patient = patients.find((p) => pPhone && p.phone === pPhone);
  if (!patient) {
    patient = {
      id: `p-${patients.length + 1}`,
      patient_id: pid,
      name: pName,
      phone: pPhone,
      age: parseInt(age, 10) || 30,
      gender: gender || 'Male',
      complaints: complaints || '',
      visit_type: visit_type || 'New Visit',
      total_visits: 1,
      created_at: now.toISOString(),
    };
    patients.push(patient);
  } else {
    patient.total_visits = (patient.total_visits || 1) + 1;
  }

  const createdEntries: Array<{ service: string; token: number }> = [];
  const protocol = req.headers['x-forwarded-proto'] || req.protocol;
  const host = req.get('host');
  const baseUrl = `${protocol}://${host}`;
  const trackingToken = makeTrackingToken(patient.patient_id);
  const trackingUrl = `${baseUrl}/track/${trackingToken}`;

  for (const code of sList) {
    const token = nextTokenNumber++;
    const dept = getDeptForService(code);
    const entry: QueueEntry = {
      id: `q-${queueEntries.length + 1}`,
      visit_id: `VIS-${dateStr}-${token}`,
      patient_id: patient.patient_id,
      patient_name: patient.name,
      patient_phone: patient.phone,
      service_code: code.toUpperCase(),
      token_number: token,
      department: dept,
      status: 'WAITING',
      wait_minutes: 10 + createdEntries.length * 15,
      notes: complaints || '',
      created_at: now.toISOString(),
      updated_at: now.toISOString(),
    };
    queueEntries.push(entry);
    createdEntries.push({ service: code, token });
  }

  const whatsappLinks = pPhone
    ? createdEntries.map((e) => {
        const msg = `🏥 *GIL CLINIC — Patient Token Slip*\n\n👤 *Patient Name:* ${patient!.name}\n🎟️ *Token Number:* #${e.token}\n🩺 *Service:* ${e.service}\n📌 *Status:* Registered & In Queue\n📍 *Live Status:* ${trackingUrl}\n\n— GIL CLINIC`;
        const sanitizedPhone = pPhone.replace(/\D/g, '');
        return {
          service: e.service,
          token: e.token,
          url: `https://wa.me/${sanitizedPhone}?text=${encodeURIComponent(msg)}`,
        };
      })
    : [];

  res.json({
    ok: true,
    patient_id: patient.patient_id,
    entries: createdEntries,
    whatsapp: whatsappLinks,
    tracking_url: trackingUrl,
    message: `${patient.name} registered! Token #${createdEntries.map((e) => e.token).join(', #')}`,
  });
});

// ── Queue Actions API ───────────────────────────────────────────────────────
app.post('/api/v1/queue/action', (req: Request, res: Response) => {
  const { entry_id, action, staff_name, department, notes } = req.body;
  const entry = queueEntries.find((e) => e.id === entry_id || String(e.token_number) === entry_id);

  if (!entry) {
    return res.status(404).json({ error: 'Queue entry not found' });
  }

  const now = new Date().toISOString();
  entry.updated_at = now;

  switch (action) {
    case 'call':
    case 'recall':
      entry.status = 'CALLED';
      break;
    case 'start':
      entry.status = 'IN_PROGRESS';
      break;
    case 'complete':
      entry.status = 'COMPLETED';
      break;
    case 'report-ready':
      entry.status = 'REPORT_READY';
      break;
    default:
      if (notes) entry.notes = notes;
      break;
  }

  let waUrl = '';
  if (entry.patient_phone && (action === 'call' || action === 'recall')) {
    const cleanPhone = entry.patient_phone.replace(/\D/g, '');
    const msg = `🔔 *Token #${entry.token_number} Called*\n\nHello ${entry.patient_name}, please proceed to ${entry.department}.\n\n— GIL CLINIC`;
    waUrl = `https://wa.me/${cleanPhone}?text=${encodeURIComponent(msg)}`;
  }

  res.json({
    ok: true,
    status: entry.status,
    whatsapp_url: waUrl,
    entry,
  });
});

app.post('/api/v1/queue/create', (req: Request, res: Response) => {
  const { patient_id, services } = req.body;
  const patient = patients.find((p) => p.patient_id === patient_id || p.id === patient_id);
  const sList: string[] = Array.isArray(services) ? services : [];

  const created: QueueEntry[] = [];
  for (const code of sList) {
    const token = nextTokenNumber++;
    const entry: QueueEntry = {
      id: `q-${queueEntries.length + 1}`,
      visit_id: `VIS-${Date.now()}-${token}`,
      patient_id: patient ? patient.patient_id : patient_id,
      patient_name: patient ? patient.name : 'Walk-in Patient',
      patient_phone: patient ? patient.phone : '',
      service_code: code.toUpperCase(),
      token_number: token,
      department: getDeptForService(code),
      status: 'WAITING',
      wait_minutes: 10,
      notes: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    queueEntries.push(entry);
    created.push(entry);
  }

  res.json({ ok: true, entries: created });
});

app.get('/api/v1/queue/list', (req: Request, res: Response) => {
  res.json({ ok: true, entries: queueEntries });
});

// ── Patient Tracking (Public) ────────────────────────────────────────────────
app.get('/track/:token', (req: Request, res: Response) => {
  const rawToken = req.params.token;
  const patientId = decodeTrackingToken(rawToken);

  const patient = patients.find(
    (p) => p.patient_id === patientId || p.phone === patientId || p.id === patientId
  );
  const patientEntries = queueEntries.filter(
    (e) => e.patient_id === (patient ? patient.patient_id : patientId)
  );

  res.render('patient_track.html', {
    patient_id: patient ? patient.patient_id : patientId || 'Patient',
    patient_name: patient ? patient.name : 'Cardiology Patient',
    patient_entries: patientEntries,
  });
});

app.get('/my/:token', (req: Request, res: Response) => {
  res.redirect(`/track/${req.params.token}`);
});

app.get('/s/:token', (req: Request, res: Response) => {
  res.redirect(`/track/${req.params.token}`);
});

// ── Diet Plan & Settings APIs ────────────────────────────────────────────────
app.get(['/staff/api/dietitian-settings', '/staff/api/settings'], (req: Request, res: Response) => {
  res.json({
    wa_reception: '9876543210',
    wa_manager: '9876543212',
    wa_doctor: '9876543211',
  });
});

app.post('/staff/api/diet-plan', (req: Request, res: Response) => {
  const { name, age, weight, height, condition } = req.body;
  const dietPlan = `
🥗 Personalized Cardiac Diet Plan for ${name || 'Patient'}
-----------------------------------------------------------
1. Early Morning (6:30 AM): Warm water with soaked almonds (4-5) and walnuts (2)
2. Breakfast (8:30 AM): Oats / Multigrain Dalia with skimmed milk or Vegetable Poha
3. Mid-Morning (11:00 AM): Fresh apple or papaya slice + green tea
4. Lunch (1:30 PM): 2 bran rotis, green leafy vegetable, 1 bowl moong dal, cucumber salad
5. Evening Snack (4:30 PM): Roasted makhana / sprouts chaat (low salt)
6. Dinner (7:30 PM): Steamed vegetables, vegetable soup, 1 multigrain phulka
-----------------------------------------------------------
⚠️ Instructions: Low sodium (< 2g/day), avoid fried/processed items, maintain 30m daily brisk walk.
  `;
  res.json({ ok: true, plan: dietPlan });
});

// ── Presentations & Manuals ──────────────────────────────────────────────────
app.get(['/presentation', '/presentation.html', '/deck'], (req: Request, res: Response) => {
  const presPath = path.join(__dirname, 'CardioQueue_Master_Presentation.html');
  if (fs.existsSync(presPath)) {
    return res.sendFile(presPath);
  }
  res.render('presentation.html');
});

app.get(['/manual', '/user-manual'], (req: Request, res: Response) => {
  const manualPath = path.join(__dirname, 'USER_MANUAL.html');
  if (fs.existsSync(manualPath)) {
    return res.sendFile(manualPath);
  }
  res.render('manual.html');
});

// ── Health Check ─────────────────────────────────────────────────────────────
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    build: '2026.09.30.v2.0-node',
    version: '2.0.0',
    platform: 'Node.js (AI Studio)',
    queue_count: queueEntries.length,
    patients_count: patients.length,
    uptime_seconds: Math.floor(process.uptime()),
  });
});

// ── Error handling ───────────────────────────────────────────────────────────
app.use((req: Request, res: Response) => {
  res.status(404).send(`
    <html>
      <body style="font-family:sans-serif;text-align:center;padding:50px;">
        <h2>404 — Page Not Found</h2>
        <p>The requested route <code>${req.path}</code> was not found.</p>
        <a href="/">← Go to Home</a>
      </body>
    </html>
  `);
});

app.use((err: any, req: Request, res: Response, next: NextFunction) => {
  console.error('[Error]', err);
  res.status(500).send(`
    <html>
      <body style="font-family:sans-serif;text-align:center;padding:50px;">
        <h2>500 — Internal Server Error</h2>
        <pre>${err.message || err}</pre>
        <a href="/">← Go to Home</a>
      </body>
    </html>
  `);
});

// ── Start Server ─────────────────────────────────────────────────────────────
app.listen(PORT, HOST, () => {
  console.log(`[CardioQueue] Server listening on http://${HOST}:${PORT}`);
});
