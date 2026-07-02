/**
 * CardioQueue — Google Sheets Database Wrapper
 * ==============================================
 * All data operations go through this module.
 * Uses a Google Apps Script Web App as the backend API.
 * Google Sheet acts as the shared database — all devices see the same data.
 * 
 * BEFORE USING: Set GOOGLE_SCRIPT_URL below to your deployed Web App URL.
 * See: pwa/google-apps-script/Code.gs for deployment instructions.
 * 
 * How it works:
 *   • Each phone calls this API via HTTPS (mobile data or WiFi)
 *   • Google Sheet stores all data in the cloud
 *   • All phones share the same sheet → automatic sync
 *   • No server needed, no setup cost, free forever
 */

// ═══════════════════════════════════════════════════════════════════════════════
//  IMPORTANT: Paste your Google Apps Script Web App URL here after deployment
// ═══════════════════════════════════════════════════════════════════════════════
// Step 1: Go to https://sheets.google.com and create a new sheet
// Step 2: Extensions → Apps Script → paste Code.gs content → Deploy as Web App
// Step 3: Copy the Web App URL and paste it below
// ═══════════════════════════════════════════════════════════════════════════════

let GOOGLE_SCRIPT_URL = localStorage.getItem("cardioqueue_gs_url") || "";

// You can also hardcode it here after setup:
// const GOOGLE_SCRIPT_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec";

// ─── Configuration URL setter (called from settings) ────────────────────────────

function setGoogleScriptUrl(url) {
    GOOGLE_SCRIPT_URL = url.trim().replace(/\/$/, "");
    localStorage.setItem("cardioqueue_gs_url", GOOGLE_SCRIPT_URL);
    return GOOGLE_SCRIPT_URL;
}

function getGoogleScriptUrl() {
    return GOOGLE_SCRIPT_URL;
}

// ─── API Helper ─────────────────────────────────────────────────────────────────

/**
 * Calls the Google Apps Script Web App.
 * @param {string} action - The action name (maps to a function in Code.gs)
 * @param {object} params - Parameters to send
 * @param {boolean} isPost - Use POST for writes, GET for reads
 */
async function callAPI(action, params = {}, isPost = false) {
    if (!GOOGLE_SCRIPT_URL) {
        throw new Error("GOOGLE_SCRIPT_URL not set. Configure URL first.");
    }

    const url = GOOGLE_SCRIPT_URL + (GOOGLE_SCRIPT_URL.includes("?") ? "&" : "?") + "action=" + encodeURIComponent(action);
    params.action = action;

    try {
        let response;
        if (isPost) {
            // POST: Send JSON body, read response as text (Apps Script returns JSONP-like response)
            response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(params)
            });
        } else {
            // GET: Append params to URL
            const query = new URLSearchParams(params).toString();
            response = await fetch(`${GOOGLE_SCRIPT_URL}?${query}`, {
                method: "GET"
            });
        }

        const text = await response.text();
        
        // Apps Script Web Apps sometimes return JSON wrapped in HTML/script tags
        // or with a Google Apps Script callback wrapper
        
        // Try direct JSON parse first
        try {
            return JSON.parse(text);
        } catch(e) {
            // Try to extract JSON from HTML response
            // Google Apps Script sometimes wraps in <pre> or callback
            const jsonMatch = text.match(/(\{.*\}|\[.*\])/s);
            if (jsonMatch) {
                try {
                    return JSON.parse(jsonMatch[1]);
                } catch(e2) {}
            }
            
            // Try text-based responses
            if (text.includes("ping") || text.includes("ok")) {
                return { status: "ok", raw: text.substring(0, 100) };
            }
            
            console.warn("Raw response:", text.substring(0, 300));
            throw new Error(`Could not parse server response. Raw: ${text.substring(0, 100)}`);
        }
    } catch (err) {
        console.error(`API Error (${action}):`, err);
        throw err;
    }
}

/**
 * Cached API call with deduplication.
 * Uses localStorage cache briefly to avoid redundant calls.
 */
const apiCache = {};
const CACHE_TTL = 2000; // 2 seconds

async function callAPICached(action, params = {}, isPost = false, bypassCache = false) {
    const cacheKey = `${action}_${JSON.stringify(params)}`;
    
    if (!bypassCache && !isPost && apiCache[cacheKey] && Date.now() - apiCache[cacheKey].time < CACHE_TTL) {
        return apiCache[cacheKey].data;
    }
    
    const data = await callAPI(action, params, isPost);
    
    if (!isPost) {
        apiCache[cacheKey] = { data, time: Date.now() };
    }
    
    return data;
}

// ─── Constants ──────────────────────────────────────────────────────────────────

const DB_TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"];
const DB_STATUS_ORDER = ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"];

// ─── Validators ─────────────────────────────────────────────────────────────────

function validateMobile(mobile) {
    return mobile && /^\d{10}$/.test(mobile.trim());
}

function validateName(name) {
    return name && name.trim().length >= 2;
}

// ─── PATIENT CRUD ───────────────────────────────────────────────────────────────

async function createPatient(name, mobile, age, gender) {
    if (!validateName(name)) throw new Error("Name must be at least 2 characters");
    if (!validateMobile(mobile)) throw new Error("Valid 10-digit mobile number required");
    if (!age || age < 0 || age > 150) throw new Error("Valid age (0-150) required");
    
    return callAPI("createPatient", {
        name: name.trim(),
        mobile: mobile.trim(),
        age: parseInt(age),
        gender: gender
    }, true);
}

async function getPatientById(patientId) {
    return callAPI("getPatientById", { patientId });
}

async function getPatientByMobile(mobile) {
    if (!validateMobile(mobile)) return null;
    return callAPI("getPatientByMobile", { mobile: mobile.trim() });
}

async function getTodayPatients() {
    return callAPI("getTodayPatients", {});
}

async function getAllPatients() {
    return callAPI("getAllPatients", {});
}

// ─── TEST CRUD ──────────────────────────────────────────────────────────────────

async function createTest(patientId, testName) {
    return callAPI("createTest", { patientId, testName }, true);
}

async function getTestsForPatient(patientId) {
    return callAPI("getTestsForPatient", { patientId });
}

async function getTestsByMobile(mobile) {
    return callAPI("getTestsByMobile", { mobile: mobile.trim() });
}

async function getQueue(testName, statusFilter) {
    return callAPI("getQueue", { testName, status: statusFilter || "" });
}

async function updateTestStatus(testId, newStatus) {
    return callAPI("updateTestStatus", { testId, status: newStatus }, true);
}

async function getCurrentPatient(testName) {
    return callAPI("getCurrentPatient", { testName });
}

async function getCompletedTests() {
    return callAPI("getCompletedTests", {});
}

async function getReportReadyTests() {
    return callAPI("getReportReadyTests", {});
}

async function getDepartmentStats(testName) {
    return callAPI("getDepartmentStats", { testName });
}

async function getAllDataForExport() {
    return callAPI("getAllDataForExport", {}, true);
}

// ─── ALERTS / NOTIFICATIONS ─────────────────────────────────────────────────────

async function sendAlert(type, message, fromRole, toRole, patientData = {}) {
    return callAPI("sendAlert", {
        type, message, fromRole, toRole,
        patientId: patientData.patientId || "",
        patientName: patientData.patientName || "",
        testName: patientData.testName || "",
        tokenNumber: patientData.tokenNumber || "",
        relatedTestId: patientData.relatedTestId || ""
    }, true);
}

async function getActiveAlerts(toRole) {
    return callAPI("getActiveAlerts", { toRole });
}

async function dismissAlert(alertId) {
    return callAPI("dismissAlert", { alertId }, true);
}

async function dismissAlertsByTestId(testId) {
    return callAPI("dismissAlertsByTestId", { testId }, true);
}

// ─── ALL DEPARTMENTS (for Manager) ─────────────────────────────────────────────

async function getAllDepartmentsStats() {
    return callAPI("getAllDepartmentsStats", {});
}

// ─── TOAST NOTIFICATION ─────────────────────────────────────────────────────────

/**
 * Show a toast notification at the top of the screen.
 * Auto-dismisses after 4 seconds.
 */
function showToast(message, type = "info") {
    const container = document.getElementById("alert-toast-container");
    if (!container) return;
    
    const colors = { info: "#2196F3", success: "#4CAF50", warning: "#FF9800", error: "#f44336", urgent: "#ff1744" };
    const bgColor = colors[type] || colors.info;
    
    const toast = document.createElement("div");
    toast.style.cssText = `
        background: ${bgColor};
        color: white;
        padding: 12px 16px;
        border-radius: 12px;
        margin-bottom: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
        font-size: 0.95rem;
        font-weight: 500;
        animation: slideDown 0.3s ease;
        pointer-events: auto;
        cursor: pointer;
        max-width: 100%;
        word-break: break-word;
    `;
    toast.textContent = message;
    
    container.appendChild(toast);
    
    // Add animation style if not exists
    if (!document.getElementById("toast-anim-style")) {
        const style = document.createElement("style");
        style.id = "toast-anim-style";
        style.textContent = `
            @keyframes slideDown { from { transform: translateY(-100px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
            @keyframes slideUp { from { transform: translateY(0); opacity: 1; } to { transform: translateY(-100px); opacity: 0; } }
        `;
        document.head.appendChild(style);
    }
    
    // Auto dismiss after 4s
    setTimeout(() => {
        toast.style.animation = "slideUp 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
    
    // Dismiss on click
    toast.addEventListener("click", () => {
        toast.style.animation = "slideUp 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    });
}

/**
 * Play a notification sound for alerts.
 */
function playAlertSound(type = "alert") {
    try {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.connect(gain);
        gain.connect(ctx.destination);
        
        if (type === "urgent") {
            // Rapid beeps for urgent
            osc.frequency.value = 1200;
            osc.type = "square";
            gain.gain.value = 0.2;
            osc.start();
            setTimeout(() => { osc.frequency.value = 800; }, 150);
            setTimeout(() => { osc.frequency.value = 1200; }, 300);
            osc.stop(ctx.currentTime + 0.5);
        } else if (type === "success") {
            osc.frequency.value = 660;
            osc.type = "sine";
            gain.gain.value = 0.3;
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        } else {
            osc.frequency.value = 880;
            osc.type = "sine";
            gain.gain.value = 0.3;
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        }
        
        if (navigator.vibrate) {
            navigator.vibrate(type === "urgent" ? [200,100,200] : 200);
        }
    } catch(e) {}
}

// ─── QR MODAL ───────────────────────────────────────────────────────────────────

/**
 * Show the QR modal overlay with a patient's QR code.
 */
function showQRModal(patient) {
    const modal = document.getElementById("qr-modal");
    const body = document.getElementById("qr-modal-body");
    if (!modal || !body) return;
    
    const baseURL = window.location.origin + window.location.pathname.replace(/\/[^/]*$/, "/index.html");
    const qrURL = `${baseURL}?patient=${patient.patientId}`;
    
    body.innerHTML = `
        <div class="qr-modal-patient">
            <h3>👤 ${patient.name}</h3>
            <p style="color:#888;margin:4px 0;">🆔 ${patient.patientId} | 📱 ${patient.mobile}</p>
        </div>
        <div id="qr-modal-code" style="text-align:center;margin:16px 0;"></div>
        <div style="margin-top:8px;">
            <button class="btn btn-secondary btn-sm" onclick="copyQRURL()">📋 Copy Link</button>
            <button class="btn btn-primary btn-sm" onclick="shareQR()">📤 Share</button>
        </div>
        <p style="font-size:0.75rem;color:#aaa;margin-top:8px;">Patient ko QR scan karne dein ya link share karein</p>
        <div id="qr-copy-feedback" style="font-size:0.8rem;margin-top:4px;"></div>
    `;
    
    // Generate QR
    try {
        new QRCode(document.getElementById("qr-modal-code"), {
            text: qrURL,
            width: 200,
            height: 200,
            colorDark: "#000000",
            colorLight: "#ffffff",
            correctLevel: QRCode.CorrectLevel.H
        });
    } catch(e) {
        document.getElementById("qr-modal-code").innerHTML = `<p style="color:red;">QR Error</p>`;
    }
    
    // Store URL for copy/share
    window._qrUrl = qrURL;
    
    modal.style.display = "flex";
}

/**
 * Close the QR modal.
 */
function closeQRModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const modal = document.getElementById("qr-modal");
    if (modal) modal.style.display = "none";
}

/**
 * Copy QR URL to clipboard.
 */
function copyQRURL() {
    const url = window._qrUrl || "";
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(() => {
            document.getElementById("qr-copy-feedback").textContent = "✅ Copied!";
        }).catch(() => fallbackCopy(url));
    } else {
        fallbackCopy(url);
    }
}

function fallbackCopy(text) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    document.getElementById("qr-copy-feedback").textContent = "✅ Copied!";
}

/**
 * Share QR URL via native share.
 */
async function shareQR() {
    const url = window._qrUrl || "";
    if (navigator.share) {
        try {
            await navigator.share({ title: "CardioQueue - Patient Status", url: url });
        } catch(e) {}
    } else {
        copyQRURL();
    }
}

// ─── CALCULATIONS (local, no API call needed) ───────────────────────────────────

function calculateWaitTime(testName, queuePosition) {
    const avgTimes = { ECG: 10, Echo: 20, TMT: 30, Holter: 15, ABPM: 15 };
    const avg = avgTimes[testName] || 15;
    if (!queuePosition || queuePosition <= 0) return 0;
    return Math.max(queuePosition - 1, 0) * avg;
}

// ─── CONFIGURATION SCREEN ───────────────────────────────────────────────────────

function renderConfigScreen(container) {
    const currentUrl = getGoogleScriptUrl();
    container.innerHTML = `
        <div class="page-content">
            <h2>⚙️ Settings</h2>
            <div class="card form-card">
                <div class="form-group">
                    <label>Google Apps Script URL</label>
                    <input type="url" id="gs-url-input" 
                           value="${currentUrl}" 
                           placeholder="https://script.google.com/macros/s/.../exec"
                           style="font-size:0.8rem;word-break:break-all;">
                    <p style="font-size:0.75rem;color:#888;margin-top:4px;">
                        Yeh URL aapko Google Apps Script Web App deploy karne ke baad milega.
                    </p>
                </div>
                <button id="save-gs-url" class="btn btn-primary btn-block">💾 Save URL</button>
                <div id="gs-url-result"></div>
            </div>
            <div class="card" style="margin-top:12px;">
                <h4>🔗 Test Connection</h4>
                <button id="test-gs-connection" class="btn btn-secondary btn-block">📡 Test Connection</button>
                <div id="gs-test-result" style="margin-top:8px;"></div>
            </div>
        </div>
    `;

    document.getElementById("save-gs-url").addEventListener("click", () => {
        const url = document.getElementById("gs-url-input").value.trim();
        if (!url) {
            document.getElementById("gs-url-result").innerHTML = `<p class="error-msg">⚠️ Please enter a URL</p>`;
            return;
        }
        setGoogleScriptUrl(url);
        document.getElementById("gs-url-result").innerHTML = `<p class="success-msg">✅ URL saved!</p>`;
    });

    document.getElementById("test-gs-connection").addEventListener("click", async () => {
        const resultDiv = document.getElementById("gs-test-result");
        resultDiv.innerHTML = `<div class="spinner"></div><p>Testing...</p>`;
        try {
            // Save URL first
            const url = document.getElementById("gs-url-input").value.trim();
            if (url) setGoogleScriptUrl(url);
            
            const result = await callAPI("ping");
            resultDiv.innerHTML = `<p class="success-msg">✅ Connected! Server time: ${result.time || "ok"}</p>`;
        } catch(e) {
            resultDiv.innerHTML = `<p class="error-msg">❌ Connection failed: ${e.message}</p>`;
        }
    });
}

// ─── Status Display Helpers ─────────────────────────────────────────────────────

function formatStatusDisplay(status) {
    const icons = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
    const labels = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };
    return `${icons[status] || "❓"} ${labels[status] || status}`;
}
