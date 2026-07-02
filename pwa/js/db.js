/**
 * CardioQueue — IndexedDB Wrapper
 * ==================================
 * All database operations go through this module.
 * Data is stored entirely on-device — no cloud, no server.
 * 
 * Stores:
 *   patients - { id, patientId, name, mobile, age, gender, registrationDate, createdAt }
 *   tests    - { id, patientId, testName, status, tokenNumber, queuePosition, room,
 *                calledAt, startedAt, completedAt, reportReadyAt, deliveredAt, createdAt }
 */
const DB_NAME = "CardioQueueDB";
const DB_VERSION = 1;

// ─── Open / Initialize Database ────────────────────────────────────────────────

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);

        req.onupgradeneeded = (event) => {
            const db = event.target.result;

            // Patients store
            if (!db.objectStoreNames.contains("patients")) {
                const store = db.createObjectStore("patients", { keyPath: "id", autoIncrement: true });
                store.createIndex("patientId", "patientId", { unique: true });
                store.createIndex("mobile", "mobile", { unique: false });
                store.createIndex("registrationDate", "registrationDate", { unique: false });
            }

            // Tests store
            if (!db.objectStoreNames.contains("tests")) {
                const store = db.createObjectStore("tests", { keyPath: "id", autoIncrement: true });
                store.createIndex("patientId", "patientId", { unique: false });
                store.createIndex("testName", "testName", { unique: false });
                store.createIndex("status", "status", { unique: false });
                store.createIndex("tokenNumber", "tokenNumber", { unique: false });
                store.createIndex("patientId_testName", ["patientId", "testName"], { unique: true });
            }
        };

        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

// ─── Generators ─────────────────────────────────────────────────────────────────

function generatePatientId(count) {
    const today = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const seq = String(count + 1).padStart(3, "0");
    return `CQ-${today}-${seq}`;
}

function todayStr() {
    return new Date().toISOString().slice(0, 10);
}

function nowISO() {
    return new Date().toISOString();
}

// ─── PATIENT CRUD ───────────────────────────────────────────────────────────────

async function createPatient(name, mobile, age, gender) {
    const db = await openDB();
    const tx = db.transaction("patients", "readwrite");
    const store = tx.objectStore("patients");

    // Get today's count for ID generation
    const index = store.index("registrationDate");
    const range = IDBKeyRange.only(todayStr());
    const countReq = index.count(range);
    const count = await new Promise((res) => { countReq.onsuccess = () => res(countReq.result); });

    const patient = {
        patientId: generatePatientId(count),
        name: name.trim(),
        mobile: mobile.trim(),
        age: parseInt(age),
        gender: gender,
        registrationDate: todayStr(),
        createdAt: nowISO()
    };

    const req = store.add(patient);
    return new Promise((resolve, reject) => {
        req.onsuccess = () => { patient.id = req.result; resolve(patient); };
        req.onerror = () => reject(req.error);
        tx.oncomplete = () => db.close();
    });
}

async function getPatientById(patientId) {
    const db = await openDB();
    const tx = db.transaction("patients", "readonly");
    const index = tx.objectStore("patients").index("patientId");
    const req = index.get(patientId);
    return new Promise((resolve) => {
        req.onsuccess = () => { resolve(req.result || null); db.close(); };
        req.onerror = () => { resolve(null); db.close(); };
    });
}

async function getPatientByMobile(mobile) {
    const db = await openDB();
    const tx = db.transaction("patients", "readonly");
    const index = tx.objectStore("patients").index("mobile");
    const range = IDBKeyRange.only(mobile);
    const req = index.openCursor(range, "prev");
    return new Promise((resolve) => {
        req.onsuccess = () => {
            const cursor = req.result;
            resolve(cursor ? cursor.value : null);
            db.close();
        };
        req.onerror = () => { resolve(null); db.close(); };
    });
}

async function getTodayPatients() {
    const db = await openDB();
    const tx = db.transaction("patients", "readonly");
    const index = tx.objectStore("patients").index("registrationDate");
    const range = IDBKeyRange.only(todayStr());
    const req = index.getAll(range);
    return new Promise((resolve) => {
        req.onsuccess = () => { resolve(req.result || []); db.close(); };
        req.onerror = () => { resolve([]); db.close(); };
    });
}

async function getAllPatients() {
    const db = await openDB();
    const tx = db.transaction("patients", "readonly");
    const req = tx.objectStore("patients").getAll();
    return new Promise((resolve) => {
        req.onsuccess = () => { resolve(req.result || []); db.close(); };
        req.onerror = () => { resolve([]); db.close(); };
    });
}

// ─── TEST CRUD ──────────────────────────────────────────────────────────────────

async function getNextToken(testName) {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const testStore = tx.objectStore("tests");
    const testIdx = testStore.index("testName");
    const patStore = tx.objectStore("patients");
    const dateIdx = patStore.index("registrationDate");

    // Get all tests for this testName
    const allTestsReq = testIdx.getAll(testName);
    const allTests = await new Promise((res) => { allTestsReq.onsuccess = () => res(allTestsReq.result || []); });

    // Get today's patient IDs
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });
    const todayPatIds = new Set(todayPatients.map(p => p.patientId));

    // Filter tests belonging to today's patients
    const todayTests = allTests.filter(t => todayPatIds.has(t.patientId));
    const maxToken = todayTests.reduce((max, t) => Math.max(max, t.tokenNumber || 0), 0);
    
    db.close();
    return maxToken + 1;
}

async function getQueueLength(testName) {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const testIdx = tx.objectStore("tests").index("testName");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const allTestsReq = testIdx.getAll(testName);
    const allTests = await new Promise((res) => { allTestsReq.onsuccess = () => res(allTestsReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });
    const todayPatIds = new Set(todayPatients.map(p => p.patientId));

    const waiting = allTests.filter(t => todayPatIds.has(t.patientId) && t.status === "waiting");
    db.close();
    return waiting.length;
}

async function createTest(patientId, testName) {
    const db = await openDB();
    const tx = db.transaction("tests", "readwrite");
    const store = tx.objectStore("tests");

    const token = await getNextToken(testName);
    const queuePos = (await getQueueLength(testName)) + 1;

    const rooms = { ECG: "ECG Room 1", Echo: "Echo Room 1", TMT: "TMT Room 1", Holter: "Holter Room", ABPM: "ABPM Room" };

    const test = {
        patientId: patientId,
        testName: testName,
        status: "waiting",
        tokenNumber: token,
        queuePosition: queuePos,
        room: rooms[testName] || `${testName} Room`,
        calledAt: null,
        startedAt: null,
        completedAt: null,
        reportReadyAt: null,
        deliveredAt: null,
        createdAt: nowISO()
    };

    const req = store.add(test);
    return new Promise((resolve, reject) => {
        req.onsuccess = () => { test.id = req.result; resolve(test); };
        req.onerror = () => reject(req.error);
        tx.oncomplete = () => db.close();
    });
}

async function getTestsForPatient(patientId) {
    const db = await openDB();
    const tx = db.transaction("tests", "readonly");
    const index = tx.objectStore("tests").index("patientId");
    const req = index.getAll(patientId);
    return new Promise((resolve) => {
        req.onsuccess = () => { resolve(req.result || []); db.close(); };
        req.onerror = () => { resolve([]); db.close(); };
    });
}

async function getTestsByMobile(mobile) {
    const patient = await getPatientByMobile(mobile);
    if (!patient) return [];
    return getTestsForPatient(patient.patientId);
}

async function getQueue(testName, statusFilter) {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const testIdx = tx.objectStore("tests").index("testName");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const allTestsReq = testIdx.getAll(testName);
    const allTests = await new Promise((res) => { allTestsReq.onsuccess = () => res(allTestsReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });

    const todayPatMap = {};
    todayPatients.forEach(p => { todayPatMap[p.patientId] = p; });

    let filtered = allTests.filter(t => t.patientId in todayPatMap);
    if (statusFilter) {
        filtered = filtered.filter(t => t.status === statusFilter);
    }
    filtered.sort((a, b) => a.tokenNumber - b.tokenNumber);

    const result = filtered.map(t => ({
        ...t,
        patients: todayPatMap[t.patientId] || {}
    }));

    db.close();
    return result;
}

async function updateTestStatus(testId, newStatus) {
    const db = await openDB();
    const tx = db.transaction("tests", "readwrite");
    const store = tx.objectStore("tests");
    const req = store.get(testId);

    return new Promise((resolve) => {
        req.onsuccess = () => {
            const test = req.result;
            if (!test) { resolve(false); db.close(); return; }

            test.status = newStatus;
            const fieldMap = {
                called: "calledAt",
                in_progress: "startedAt",
                completed: "completedAt",
                report_ready: "reportReadyAt",
                delivered: "deliveredAt"
            };
            if (fieldMap[newStatus]) {
                test[fieldMap[newStatus]] = nowISO();
            }

            const updateReq = store.put(test);
            updateReq.onsuccess = () => { resolve(true); db.close(); };
            updateReq.onerror = () => { resolve(false); db.close(); };
        };
        req.onerror = () => { resolve(false); db.close(); };
    });
}

async function getCurrentPatient(testName) {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const testIdx = tx.objectStore("tests").index("testName");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const allTestsReq = testIdx.getAll(testName);
    const allTests = await new Promise((res) => { allTestsReq.onsuccess = () => res(allTestsReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });

    const todayPatMap = {};
    todayPatients.forEach(p => { todayPatMap[p.patientId] = p; });

    const active = allTests
        .filter(t => t.patientId in todayPatMap && ["called", "in_progress"].includes(t.status))
        .sort((a, b) => {
            const aTime = a.calledAt || a.createdAt;
            const bTime = b.calledAt || b.createdAt;
            return aTime.localeCompare(bTime);
        });

    db.close();
    if (active.length === 0) return null;
    return { ...active[0], patients: todayPatMap[active[0].patientId] };
}

async function getCompletedTests() {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const statusIdx = tx.objectStore("tests").index("status");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const completedReq = statusIdx.getAll("completed");
    const completed = await new Promise((res) => { completedReq.onsuccess = () => res(completedReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });

    const todayPatMap = {};
    todayPatients.forEach(p => { todayPatMap[p.patientId] = p; });

    const result = completed
        .filter(t => t.patientId in todayPatMap)
        .sort((a, b) => (a.completedAt || "").localeCompare(b.completedAt || ""))
        .map(t => ({ ...t, patients: todayPatMap[t.patientId] }));

    db.close();
    return result;
}

async function getReportReadyTests() {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const statusIdx = tx.objectStore("tests").index("status");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const readyReq = statusIdx.getAll("report_ready");
    const ready = await new Promise((res) => { readyReq.onsuccess = () => res(readyReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });

    const todayPatMap = {};
    todayPatients.forEach(p => { todayPatMap[p.patientId] = p; });

    const result = ready
        .filter(t => t.patientId in todayPatMap)
        .sort((a, b) => (a.reportReadyAt || "").localeCompare(b.reportReadyAt || ""))
        .map(t => ({ ...t, patients: todayPatMap[t.patientId] }));

    db.close();
    return result;
}

async function getDepartmentStats(testName) {
    const db = await openDB();
    const tx = db.transaction(["tests", "patients"], "readonly");
    const testIdx = tx.objectStore("tests").index("testName");
    const dateIdx = tx.objectStore("patients").index("registrationDate");

    const allTestsReq = testIdx.getAll(testName);
    const allTests = await new Promise((res) => { allTestsReq.onsuccess = () => res(allTestsReq.result || []); });
    const todayPatsReq = dateIdx.getAll(todayStr());
    const todayPatients = await new Promise((res) => { todayPatsReq.onsuccess = () => res(todayPatsReq.result || []); });

    const todayPatIds = new Set(todayPatients.map(p => p.patientId));
    const todayTests = allTests.filter(t => todayPatIds.has(t.patientId));

    const stats = { waiting: 0, called: 0, in_progress: 0, completed: 0, report_ready: 0, delivered: 0 };
    todayTests.forEach(t => { if (t.status in stats) stats[t.status]++; });

    db.close();
    return stats;
}

// ─── CALCULATIONS ───────────────────────────────────────────────────────────────

function calculateWaitTime(testName, queuePosition) {
    const avgTimes = { ECG: 10, Echo: 20, TMT: 30, Holter: 15, ABPM: 15 };
    const avg = avgTimes[testName] || 15;
    if (!queuePosition || queuePosition <= 0) return 0;
    return Math.max(queuePosition - 1, 0) * avg;
}

function formatStatusDisplay(status) {
    const icons = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
    const labels = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };
    return `${icons[status] || "❓"} ${labels[status] || status}`;
}
