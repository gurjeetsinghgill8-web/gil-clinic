/**
 * CardioQueue — Google Apps Script Backend
 * ==========================================
 * This script runs as a Google Apps Script Web App.
 * It uses a Google Sheet as the database for the clinic queue system.
 * 
 * SETUP INSTRUCTIONS (one-time, takes 5 minutes):
 * 1. Go to https://sheets.new — a new Google Sheet opens
 * 2. Go to Extensions → Apps Script
 * 3. Delete the default code, paste this entire file
 * 4. Save (Ctrl+S) — name it "CardioQueue Backend"
 * 5. Deploy → New Deployment → Type: Web App
 *    - Execute as: "Me" (you)
 *    - Who has access: "Anyone" (required for PWA to work)
 * 6. Click Deploy, then "Allow" permissions
 * 7. COPY THE WEB APP URL — you'll put it in the PWA
 * 
 * The sheet will automatically create these tabs:
 *   • Patients — all patient registrations
 *   • Tests   — all test entries
 */

// ─── CONFIG ─────────────────────────────────────────────────────────────────────
const SHEET_NAME = "CardioQueue";

// Column indices for Patients sheet (0-based)
const PAT_COL = {
  id: 0, patientId: 1, name: 2, mobile: 3, age: 4,
  gender: 5, registrationDate: 6, createdAt: 7
};

// Column indices for Tests sheet (0-based)
const TEST_COL = {
  id: 0, patientId: 1, testName: 2, status: 3, tokenNumber: 4,
  queuePosition: 5, room: 6, calledAt: 7, startedAt: 8,
  completedAt: 9, reportReadyAt: 10, deliveredAt: 11, createdAt: 12
};

// Column indices for Alerts sheet (0-based)
const ALERT_COL = {
  id: 0, type: 1, message: 2, fromRole: 3, toRole: 4,
  patientId: 5, patientName: 6, testName: 7, tokenNumber: 8,
  relatedTestId: 9, createdAt: 10, dismissedAt: 11
};

// ─── INIT — Auto-create sheets if missing ──────────────────────────────────────

function getOrCreateSheet_(sheetName, headers) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
    sheet.appendRow(headers);
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function ensureSheets_() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // Patients sheet
  let pSheet = ss.getSheetByName("Patients");
  if (!pSheet) {
    pSheet = ss.insertSheet("Patients");
    pSheet.appendRow(["id", "patientId", "name", "mobile", "age", "gender", "registrationDate", "createdAt"]);
    pSheet.setFrozenRows(1);
    pSheet.getRange("1:1").setFontWeight("bold");
  }
  
  // Tests sheet
  let tSheet = ss.getSheetByName("Tests");
  if (!tSheet) {
    tSheet = ss.insertSheet("Tests");
    tSheet.appendRow(["id", "patientId", "testName", "status", "tokenNumber", "queuePosition", "room", "calledAt", "startedAt", "completedAt", "reportReadyAt", "deliveredAt", "createdAt"]);
    tSheet.setFrozenRows(1);
    tSheet.getRange("1:1").setFontWeight("bold");
  }
  
  // Alerts sheet
  let aSheet = ss.getSheetByName("Alerts");
  if (!aSheet) {
    aSheet = ss.insertSheet("Alerts");
    aSheet.appendRow(["id", "type", "message", "fromRole", "toRole", "patientId", "patientName", "testName", "tokenNumber", "relatedTestId", "createdAt", "dismissedAt"]);
    aSheet.setFrozenRows(1);
    aSheet.getRange("1:1").setFontWeight("bold");
  }
  
  return { pSheet, tSheet, aSheet };
}

// ─── HELPER: Generate ID ───────────────────────────────────────────────────────

function generateId_() {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";
  let result = "";
  for (let i = 0; i < 16; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return result;
}

function todayStr_() {
  return Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
}

function nowISO_() {
  return new Date().toISOString();
}

// ─── PATIENT OPERATIONS ─────────────────────────────────────────────────────────

function createPatient_(data) {
  const { pSheet, tSheet } = ensureSheets_();
  const today = todayStr_();
  const now = nowISO_();
  
  // Count today's patients for ID
  const allData = pSheet.getDataRange().getValues();
  let todayCount = 0;
  for (let i = 1; i < allData.length; i++) {
    if (allData[i][PAT_COL.registrationDate] === today) todayCount++;
  }
  const seq = String(todayCount + 1).padStart(3, "0");
  const patientId = `CQ-${today.replace(/-/g, "")}-${seq}`;
  const id = generateId_();
  
  pSheet.appendRow([id, patientId, data.name, data.mobile, parseInt(data.age), data.gender, today, now]);
  
  return { id, patientId, name: data.name, mobile: data.mobile, age: parseInt(data.age), gender: data.gender, registrationDate: today, createdAt: now };
}

function getPatientById_(patientId) {
  const sheets = ensureSheets_();
  const data = sheets.pSheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][PAT_COL.patientId] === patientId) {
      return {
        id: data[i][PAT_COL.id],
        patientId: data[i][PAT_COL.patientId],
        name: data[i][PAT_COL.name],
        mobile: data[i][PAT_COL.mobile],
        age: data[i][PAT_COL.age],
        gender: data[i][PAT_COL.gender],
        registrationDate: data[i][PAT_COL.registrationDate],
        createdAt: data[i][PAT_COL.createdAt]
      };
    }
  }
  return null;
}

function getPatientByMobile_(mobile) {
  const sheets = ensureSheets_();
  const data = sheets.pSheet.getDataRange().getValues();
  let latest = null;
  for (let i = 1; i < data.length; i++) {
    if (data[i][PAT_COL.mobile] === mobile) {
      if (!latest || data[i][PAT_COL.createdAt] > latest.createdAt) {
        latest = {
          id: data[i][PAT_COL.id],
          patientId: data[i][PAT_COL.patientId],
          name: data[i][PAT_COL.name],
          mobile: data[i][PAT_COL.mobile],
          age: data[i][PAT_COL.age],
          gender: data[i][PAT_COL.gender],
          registrationDate: data[i][PAT_COL.registrationDate],
          createdAt: data[i][PAT_COL.createdAt]
        };
      }
    }
  }
  return latest;
}

function getTodayPatients_() {
  const sheets = ensureSheets_();
  const data = sheets.pSheet.getDataRange().getValues();
  const today = todayStr_();
  const result = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][PAT_COL.registrationDate] === today) {
      result.push({
        id: data[i][PAT_COL.id],
        patientId: data[i][PAT_COL.patientId],
        name: data[i][PAT_COL.name],
        mobile: data[i][PAT_COL.mobile],
        age: data[i][PAT_COL.age],
        gender: data[i][PAT_COL.gender],
        registrationDate: data[i][PAT_COL.registrationDate],
        createdAt: data[i][PAT_COL.createdAt]
      });
    }
  }
  return result;
}

function getAllPatients_() {
  const sheets = ensureSheets_();
  const data = sheets.pSheet.getDataRange().getValues();
  const result = [];
  for (let i = 1; i < data.length; i++) {
    result.push({
      id: data[i][PAT_COL.id],
      patientId: data[i][PAT_COL.patientId],
      name: data[i][PAT_COL.name],
      mobile: data[i][PAT_COL.mobile],
      age: data[i][PAT_COL.age],
      gender: data[i][PAT_COL.gender],
      registrationDate: data[i][PAT_COL.registrationDate],
      createdAt: data[i][PAT_COL.createdAt]
    });
  }
  return result;
}

// ─── TEST OPERATIONS ────────────────────────────────────────────────────────────

function getNextToken_(testName) {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  const patData = sheets.pSheet.getDataRange().getValues();
  
  const today = todayStr_();
  
  // Build today's patient IDs set
  const todayPatIds = new Set();
  for (let i = 1; i < patData.length; i++) {
    if (patData[i][PAT_COL.registrationDate] === today) {
      todayPatIds.add(patData[i][PAT_COL.patientId]);
    }
  }
  
  let maxToken = 0;
  for (let i = 1; i < testData.length; i++) {
    if (testData[i][TEST_COL.testName] === testName && todayPatIds.has(testData[i][TEST_COL.patientId])) {
      if (testData[i][TEST_COL.tokenNumber] > maxToken) {
        maxToken = testData[i][TEST_COL.tokenNumber];
      }
    }
  }
  return maxToken + 1;
}

function getQueueLength_(testName) {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  const patData = sheets.pSheet.getDataRange().getValues();
  
  const today = todayStr_();
  const todayPatIds = new Set();
  for (let i = 1; i < patData.length; i++) {
    if (patData[i][PAT_COL.registrationDate] === today) {
      todayPatIds.add(patData[i][PAT_COL.patientId]);
    }
  }
  
  let count = 0;
  for (let i = 1; i < testData.length; i++) {
    if (testData[i][TEST_COL.testName] === testName &&
        todayPatIds.has(testData[i][TEST_COL.patientId]) &&
        testData[i][TEST_COL.status] === "waiting") {
      count++;
    }
  }
  return count;
}

function createTest_(data) {
  const sheets = ensureSheets_();
  const token = getNextToken_(data.testName);
  const queuePos = getQueueLength_(data.testName) + 1;
  
  const rooms = { ECG: "ECG Room 1", Echo: "Echo Room 1", TMT: "TMT Room 1", Holter: "Holter Room", ABPM: "ABPM Room" };
  const room = rooms[data.testName] || `${data.testName} Room`;
  
  const id = generateId_();
  const now = nowISO_();
  
  sheets.tSheet.appendRow([id, data.patientId, data.testName, "waiting", token, queuePos, room, "", "", "", "", "", now]);
  
  return { id, patientId: data.patientId, testName: data.testName, status: "waiting", tokenNumber: token, queuePosition: queuePos, room, calledAt: null, startedAt: null, completedAt: null, reportReadyAt: null, deliveredAt: null, createdAt: now };
}

function getTestsForPatient_(patientId) {
  const sheets = ensureSheets_();
  const data = sheets.tSheet.getDataRange().getValues();
  const result = [];
  for (let i = 1; i < data.length; i++) {
    if (data[i][TEST_COL.patientId] === patientId) {
      result.push({
        id: data[i][TEST_COL.id],
        patientId: data[i][TEST_COL.patientId],
        testName: data[i][TEST_COL.testName],
        status: data[i][TEST_COL.status],
        tokenNumber: data[i][TEST_COL.tokenNumber],
        queuePosition: data[i][TEST_COL.queuePosition],
        room: data[i][TEST_COL.room],
        calledAt: data[i][TEST_COL.calledAt] || null,
        startedAt: data[i][TEST_COL.startedAt] || null,
        completedAt: data[i][TEST_COL.completedAt] || null,
        reportReadyAt: data[i][TEST_COL.reportReadyAt] || null,
        deliveredAt: data[i][TEST_COL.deliveredAt] || null,
        createdAt: data[i][TEST_COL.createdAt]
      });
    }
  }
  return result;
}

function getQueue_(testName, statusFilter) {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  const patData = sheets.pSheet.getDataRange().getValues();
  
  const today = todayStr_();
  
  // Build patient map
  const patMap = {};
  for (let i = 1; i < patData.length; i++) {
    if (patData[i][PAT_COL.registrationDate] === today) {
      patMap[patData[i][PAT_COL.patientId]] = {
        name: patData[i][PAT_COL.name],
        mobile: patData[i][PAT_COL.mobile],
        age: patData[i][PAT_COL.age],
        gender: patData[i][PAT_COL.gender]
      };
    }
  }
  
  let result = [];
  for (let i = 1; i < testData.length; i++) {
    const t = testData[i];
    if (t[TEST_COL.testName] === testName && t[TEST_COL.patientId] in patMap) {
      if (!statusFilter || t[TEST_COL.status] === statusFilter) {
        result.push({
          id: t[TEST_COL.id],
          patientId: t[TEST_COL.patientId],
          testName: t[TEST_COL.testName],
          status: t[TEST_COL.status],
          tokenNumber: t[TEST_COL.tokenNumber],
          queuePosition: t[TEST_COL.queuePosition],
          room: t[TEST_COL.room],
          calledAt: t[TEST_COL.calledAt] || null,
          startedAt: t[TEST_COL.startedAt] || null,
          completedAt: t[TEST_COL.completedAt] || null,
          reportReadyAt: t[TEST_COL.reportReadyAt] || null,
          deliveredAt: t[TEST_COL.deliveredAt] || null,
          createdAt: t[TEST_COL.createdAt],
          patients: patMap[t[TEST_COL.patientId]] || {}
        });
      }
    }
  }
  
  result.sort((a, b) => a.tokenNumber - b.tokenNumber);
  return result;
}

function updateTestStatus_(data) {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  
  const fieldMap = {
    called: 7,
    in_progress: 8,
    completed: 9,
    report_ready: 10,
    delivered: 11
  };
  
  const colIndex = fieldMap[data.status];
  if (colIndex === undefined) return { success: false, error: "Unknown status" };
  
  for (let i = 1; i < testData.length; i++) {
    if (testData[i][TEST_COL.id] === data.testId) {
      const row = i + 1; // 1-indexed for sheet
      // Update status
      sheets.tSheet.getRange(row, TEST_COL.status + 1).setValue(data.status);
      // Update timestamp
      sheets.tSheet.getRange(row, colIndex + 1).setValue(nowISO_());
      return { success: true };
    }
  }
  return { success: false, error: "Test not found" };
}

function getDepartmentStats_(testName) {
  const queue = getQueue_(testName);
  const stats = { waiting: 0, called: 0, in_progress: 0, completed: 0, report_ready: 0, delivered: 0 };
  queue.forEach(t => {
    if (t.status in stats) stats[t.status]++;
  });
  return stats;
}

function getCurrentPatient_(testName) {
  const queue = getQueue_(testName);
  const active = queue
    .filter(t => ["called", "in_progress"].includes(t.status))
    .sort((a, b) => {
      const aTime = a.calledAt || a.createdAt;
      const bTime = b.calledAt || b.createdAt;
      return aTime.localeCompare(bTime);
    });
  return active.length > 0 ? active[0] : null;
}

function getCompletedTests_() {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  const patData = sheets.pSheet.getDataRange().getValues();
  
  const today = todayStr_();
  const patMap = {};
  for (let i = 1; i < patData.length; i++) {
    if (patData[i][PAT_COL.registrationDate] === today) {
      patMap[patData[i][PAT_COL.patientId]] = {
        name: patData[i][PAT_COL.name],
        mobile: patData[i][PAT_COL.mobile],
        age: patData[i][PAT_COL.age],
        gender: patData[i][PAT_COL.gender]
      };
    }
  }
  
  const result = [];
  for (let i = 1; i < testData.length; i++) {
    const t = testData[i];
    if (t[TEST_COL.status] === "completed" && t[TEST_COL.patientId] in patMap) {
      result.push({
        id: t[TEST_COL.id],
        patientId: t[TEST_COL.patientId],
        testName: t[TEST_COL.testName],
        status: t[TEST_COL.status],
        tokenNumber: t[TEST_COL.tokenNumber],
        completedAt: t[TEST_COL.completedAt] || null,
        patients: patMap[t[TEST_COL.patientId]] || {}
      });
    }
  }
  result.sort((a, b) => (a.completedAt || "").localeCompare(b.completedAt || ""));
  return result;
}

function getReportReadyTests_() {
  const sheets = ensureSheets_();
  const testData = sheets.tSheet.getDataRange().getValues();
  const patData = sheets.pSheet.getDataRange().getValues();
  
  const today = todayStr_();
  const patMap = {};
  for (let i = 1; i < patData.length; i++) {
    if (patData[i][PAT_COL.registrationDate] === today) {
      patMap[patData[i][PAT_COL.patientId]] = {
        name: patData[i][PAT_COL.name],
        mobile: patData[i][PAT_COL.mobile]
      };
    }
  }
  
  const result = [];
  for (let i = 1; i < testData.length; i++) {
    const t = testData[i];
    if (t[TEST_COL.status] === "report_ready" && t[TEST_COL.patientId] in patMap) {
      result.push({
        id: t[TEST_COL.id],
        patientId: t[TEST_COL.patientId],
        testName: t[TEST_COL.testName],
        status: t[TEST_COL.status],
        tokenNumber: t[TEST_COL.tokenNumber],
        reportReadyAt: t[TEST_COL.reportReadyAt] || null,
        patients: patMap[t[TEST_COL.patientId]] || {}
      });
    }
  }
  result.sort((a, b) => (a.reportReadyAt || "").localeCompare(b.reportReadyAt || ""));
  return result;
}

// ─── ALERTS ─────────────────────────────────────────────────────────────────────

function sendAlert_(data) {
  const sheets = ensureSheets_();
  const id = generateId_();
  const now = nowISO_();
  
  sheets.aSheet.appendRow([id, data.type, data.message, data.fromRole, data.toRole,
    data.patientId || "", data.patientName || "", data.testName || "",
    data.tokenNumber || "", data.relatedTestId || "", now, ""]);
  
  return { success: true, id, createdAt: now };
}

function getActiveAlerts_(toRole) {
  const sheets = ensureSheets_();
  const data = sheets.aSheet.getDataRange().getValues();
  const result = [];
  const today = todayStr_();
  
  for (let i = 1; i < data.length; i++) {
    // Only undismissed alerts (dismissedAt empty)
    if (data[i][ALERT_COL.dismissedAt] !== "") continue;
    // Filter by target role
    if (data[i][ALERT_COL.toRole] !== toRole && data[i][ALERT_COL.toRole] !== "All") continue;
    // Only today's alerts
    const createdAt = data[i][ALERT_COL.createdAt] || "";
    if (!createdAt.startsWith(today)) continue;
    
    result.push({
      id: data[i][ALERT_COL.id],
      type: data[i][ALERT_COL.type],
      message: data[i][ALERT_COL.message],
      fromRole: data[i][ALERT_COL.fromRole],
      toRole: data[i][ALERT_COL.toRole],
      patientId: data[i][ALERT_COL.patientId],
      patientName: data[i][ALERT_COL.patientName],
      testName: data[i][ALERT_COL.testName],
      tokenNumber: data[i][ALERT_COL.tokenNumber],
      relatedTestId: data[i][ALERT_COL.relatedTestId],
      createdAt: data[i][ALERT_COL.createdAt]
    });
  }
  
  // Sort newest first
  result.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return result;
}

function dismissAlert_(alertId) {
  const sheets = ensureSheets_();
  const data = sheets.aSheet.getDataRange().getValues();
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][ALERT_COL.id] === alertId) {
      const row = i + 1;
      sheets.aSheet.getRange(row, ALERT_COL.dismissedAt + 1).setValue(nowISO_());
      return { success: true };
    }
  }
  return { success: false, error: "Alert not found" };
}

function dismissAlertsByTestId_(testId) {
  const sheets = ensureSheets_();
  const data = sheets.aSheet.getDataRange().getValues();
  let count = 0;
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][ALERT_COL.relatedTestId] === testId && data[i][ALERT_COL.dismissedAt] === "") {
      const row = i + 1;
      sheets.aSheet.getRange(row, ALERT_COL.dismissedAt + 1).setValue(nowISO_());
      count++;
    }
  }
  return { success: true, dismissed: count };
}

// ─── EXPORT ─────────────────────────────────────────────────────────────────────

function getAllDataForExport_() {
  const patients = getAllPatients_();
  const result = [];
  for (const p of patients) {
    const tests = getTestsForPatient_(p.patientId);
    if (tests.length === 0) {
      result.push({ patient: p, test: null });
    } else {
      for (const t of tests) {
        result.push({ patient: p, test: t });
      }
    }
  }
  return result;
}

// ─── ALL DEPARTMENTS STATS (for Manager) ─────────────────────────────────────

function getAllDepartmentsStats_() {
  const testTypes = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"];
  const result = {};
  let grandTotal = { waiting: 0, called: 0, in_progress: 0, completed: 0, report_ready: 0, delivered: 0, total: 0 };
  
  for (const test of testTypes) {
    const stats = getDepartmentStats_(test);
    result[test] = stats;
    for (const key of Object.keys(grandTotal)) {
      if (key !== "total") grandTotal[key] += stats[key] || 0;
    }
    grandTotal.total += Object.values(stats).reduce((a, b) => a + b, 0);
  }
  
  return { departments: result, grandTotal };
}

// ─── DOB CALCULATION ────────────────────────────────────────────────────────────

function calculateWaitTime_(testName, queuePosition) {
  const avgTimes = { ECG: 10, Echo: 20, TMT: 30, Holter: 15, ABPM: 15 };
  const avg = avgTimes[testName] || 15;
  if (!queuePosition || queuePosition <= 0) return 0;
  return Math.max(queuePosition - 1, 0) * avg;
}

// ═══════════════════════════════════════════════════════════════════════════════
//  WEB APP API
// ═══════════════════════════════════════════════════════════════════════════════
// The PWA calls this web app via HTTP GET/POST.
// 
// ACTION = first query parameter — tells us what to do.
//
// GET requests (read operations):
//   ?action=getTodayPatients
//   ?action=getAllPatients
//   ?action=getPatientById&patientId=XXX
//   ?action=getPatientByMobile&mobile=9876543210
//   ?action=getTestsForPatient&patientId=XXX
//   ?action=getQueue&testName=ECG&status=waiting
//   ?action=getDepartmentStats&testName=ECG
//   ?action=getCurrentPatient&testName=ECG
//   ?action=getCompletedTests
//   ?action=getReportReadyTests
//   ?action=calculateWaitTime&testName=ECG&queuePosition=3
//
// POST requests (write operations — body is JSON):
//   ?action=createPatient
//     Body: { "name": "...", "mobile": "...", "age": 30, "gender": "Male" }
//   ?action=createTest
//     Body: { "patientId": "...", "testName": "ECG" }
//   ?action=updateTestStatus
//     Body: { "testId": "...", "status": "called" }
//   ?action=getTestsByMobile
//     Body: { "mobile": "9876543210" }
//   ?action=getAllDataForExport
// ═══════════════════════════════════════════════════════════════════════════════

function doGet(e) {
  return handleRequest_(e, false);
}

function doPost(e) {
  return handleRequest_(e, true);
}

function handleRequest_(e, isPost) {
  try {
    // Ensure sheets exist
    ensureSheets_();
    
    let params = {};
    if (isPost) {
      // Parse POST body
      if (e && e.postData && e.postData.contents) {
        params = JSON.parse(e.postData.contents);
      }
    } else {
      // Parse GET query params
      if (e && e.parameter) {
        params = e.parameter;
      }
    }
    
    const action = params.action || (e ? e.parameter.action : null);
    if (!action) {
      return respondJson_({ error: "No action specified. Use ?action=..." });
    }
    
    switch (action) {
      // ── Patient reads ──
      case "getTodayPatients":
        return respondJson_(getTodayPatients_());
      case "getAllPatients":
        return respondJson_(getAllPatients_());
      case "getPatientById":
        return respondJson_(getPatientById_(params.patientId));
      case "getPatientByMobile":
        return respondJson_(getPatientByMobile_(params.mobile));
      
      // ── Patient writes ──
      case "createPatient":
        return respondJson_(createPatient_(params));
      
      // ── Test reads ──
      case "getTestsForPatient":
        return respondJson_(getTestsForPatient_(params.patientId));
      case "getTestsByMobile":
        return respondJson_(getTestsByMobile_(params));
      case "getQueue":
        return respondJson_(getQueue_(params.testName, params.status || null));
      case "getDepartmentStats":
        return respondJson_(getDepartmentStats_(params.testName));
      case "getCurrentPatient":
        return respondJson_(getCurrentPatient_(params.testName));
      case "getCompletedTests":
        return respondJson_(getCompletedTests_());
      case "getReportReadyTests":
        return respondJson_(getReportReadyTests_());
      case "calculateWaitTime":
        return respondJson_({ minutes: calculateWaitTime_(params.testName, parseInt(params.queuePosition) || 0) });
      
      // ── Test writes ──
      case "createTest":
        return respondJson_(createTest_(params));
      case "updateTestStatus":
        return respondJson_(updateTestStatus_(params));
      
      // ── Alerts ──
      case "sendAlert":
        return respondJson_(sendAlert_(params));
      case "getActiveAlerts":
        return respondJson_(getActiveAlerts_(params.toRole));
      case "dismissAlert":
        return respondJson_(dismissAlert_(params.alertId));
      case "dismissAlertsByTestId":
        return respondJson_(dismissAlertsByTestId_(params.testId));
      
      // ── All Departments Stats (for Manager) ──
      case "getAllDepartmentsStats":
        return respondJson_(getAllDepartmentsStats_());
      
      // ── Export ──
      case "getAllDataForExport":
        return respondJson_(getAllDataForExport_());
      
      // ── Health check ──
      case "ping":
        return respondJson_({ status: "ok", time: nowISO_(), sheet: SHEET_NAME });
      
      default:
        return respondJson_({ error: `Unknown action: ${action}` });
    }
  } catch (err) {
    return respondJson_({ error: err.toString() });
  }
}

// ─── Helper: getTestsByMobile ──────────────────────────────────────────────────

function getTestsByMobile_(params) {
  const patient = getPatientByMobile_(params.mobile);
  if (!patient) return [];
  return getTestsForPatient_(patient.patientId);
}

// ─── Helper: JSON Response ─────────────────────────────────────────────────────

function respondJson_(data) {
  const output = ContentService.createTextOutput();
  
  // Support JSONP callback for environments with CORS restrictions
  const outputStr = JSON.stringify(data);
  output.setContent(outputStr);
  output.setMimeType(ContentService.MimeType.JSON);
  
  // Set CORS headers via the service
  return output;
}

// Also add doOptions for CORS preflight (though not strictly needed for GAS)
function doOptions(e) {
  return respondJson_({ status: "ok" });
}
