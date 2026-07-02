/**
 * CardioQueue — Reception Module
 * Registration Form + QR Code + Today's Patient List + Quick Stats.
 * Emergency buttons + Report-ready alerts + QR re-open.
 */

const R_TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"];
const STATUS_ICONS = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
const STATUS_LABELS = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };

// ─── Reception Dashboard ────────────────────────────────────────────────────────

async function renderReceptionDashboard(container) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading...</p></div>`;

    try {
        const stats = {};
        for (const test of R_TEST_TYPES) {
            stats[test] = await getDepartmentStats(test);
        }

        const todayPatients = await getTodayPatients();
        const totalToday = todayPatients.length;

        // Get active alerts for Reception
        const alerts = await getActiveAlerts("Reception");
        const reportAlerts = (alerts || []).filter(a => a.type === "report_ready");

        let totalWaiting = 0, totalInProgress = 0, totalDone = 0;
        for (const test of R_TEST_TYPES) {
            totalWaiting += stats[test].waiting || 0;
            totalInProgress += stats[test].in_progress || 0;
            totalDone += (stats[test].completed || 0) + (stats[test].report_ready || 0) + (stats[test].delivered || 0);
        }

        let html = `
            <div class="page-content">
                <h2>📊 Reception Dashboard</h2>
                <p class="subtitle">${new Date().toLocaleDateString("hi-IN", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</p>

                <!-- Report Ready Alerts -->
                ${reportAlerts.length > 0 ? `
                <div class="card" style="background:#F3E5F5;border-left:5px solid #9C27B0;margin-bottom:12px;">
                    <h4 style="color:#9C27B0;">📋 New Reports Ready (${reportAlerts.length})</h4>
                    ${reportAlerts.slice(0, 5).map(a => `
                        <div style="padding:4px 0;font-size:0.9rem;border-bottom:1px solid #e1bee7;">
                            🧪 ${a.testName || "Test"} — ${a.patientName} ${a.tokenNumber ? `#${a.tokenNumber}` : ""}
                            <span style="color:#888;font-size:0.75rem;">${a.createdAt ? new Date(a.createdAt).toLocaleTimeString() : ""}</span>
                        </div>
                    `).join("")}
                    <button class="btn btn-secondary btn-sm" style="margin-top:8px;" onclick="recDismissReportAlerts()">✅ Dismiss</button>
                </div>
                ` : ""}

                <div class="stats-row">
                    <div class="stat-card" style="background:#FFF3E0;">
                        <div class="stat-value">${totalWaiting}</div>
                        <div class="stat-label">🟡 Waiting</div>
                    </div>
                    <div class="stat-card" style="background:#E3F2FD;">
                        <div class="stat-value">${totalInProgress}</div>
                        <div class="stat-label">🟠 Active</div>
                    </div>
                    <div class="stat-card" style="background:#E8F5E9;">
                        <div class="stat-value">${totalDone}</div>
                        <div class="stat-label">✅ Done</div>
                    </div>
                    <div class="stat-card" style="background:#F3E5F5;">
                        <div class="stat-value">${totalToday}</div>
                        <div class="stat-label">📋 Today</div>
                    </div>
                </div>

                <h3 style="margin-top:16px;">🏥 Department Stats</h3>
                <div class="dept-stats">
        `;

        for (const test of R_TEST_TYPES) {
            const s = stats[test] || { waiting: 0, called: 0, in_progress: 0, completed: 0, report_ready: 0, delivered: 0 };
            const isOPD = test === "OPD";
            html += `
                <div class="card dept-stat" style="border-left:4px solid ${isOPD ? "#4CAF50" : "#667eea"};">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <h4>${isOPD ? "🩺 OPD" : test}</h4>
                        <button class="btn btn-sm" style="background:#ff1744;color:white;padding:2px 8px;font-size:0.7rem;"
                                onclick="recUrgent('${test}')">🆘</button>
                    </div>
                    <div class="dept-stat-row">
                        <span>🟡 ${s.waiting || 0} waiting</span>
                        <span>🟠 ${s.in_progress || 0} active</span>
                        <span>✅ ${(s.completed || 0) + (s.report_ready || 0)} done</span>
                    </div>
                </div>
            `;
        }

        html += `</div></div>`;
        container.innerHTML = html;

    } catch(e) {
        container.innerHTML = `<div class="page-content"><p class="error-msg">❌ Error: ${e.message}</p></div>`;
    }

    // Auto-refresh every 5s — also check for new report-ready alerts
    if (window.refreshInterval) clearInterval(window.refreshInterval);
    window.refreshInterval = setInterval(async () => {
        renderReceptionDashboard(container);
    }, 5000);
}

// ─── Emergency Urgent Button ────────────────────────────────────────────────────

async function recUrgent(department) {
    await sendAlert("urgent", `🆘 Reception: ${department} mein urgent patient hai, jaldi karo!`, "Reception", department);
    showToast(`🆘 Urgent request sent to ${department}`, "urgent");
    playAlertSound("urgent");
}

async function recDismissReportAlerts() {
    const alerts = await getActiveAlerts("Reception");
    for (const a of alerts) {
        if (a.type === "report_ready") {
            await dismissAlert(a.id);
        }
    }
    showToast("✅ Report alerts dismissed", "success");
}

// ─── Registration Form ─────────────────────────────────────────────────────────

function renderReceptionForm(container) {
    let html = `
        <div class="page-content">
            <h2>➕ New Patient Registration</h2>
            <div class="card form-card">
                <div class="form-group">
                    <label>Patient Name *</label>
                    <input type="text" id="reg-name" placeholder="Full name" autocomplete="off">
                </div>
                <div class="form-group">
                    <label>Mobile Number *</label>
                    <input type="text" id="reg-mobile" placeholder="10-digit number" maxlength="10" inputmode="numeric" autocomplete="off">
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>Age *</label>
                        <input type="number" id="reg-age" placeholder="Age" min="0" max="150">
                    </div>
                    <div class="form-group">
                        <label>Gender *</label>
                        <select id="reg-gender">
                            <option value="Male">Male</option>
                            <option value="Female">Female</option>
                            <option value="Other">Other</option>
                        </select>
                    </div>
                </div>
                <div class="form-group">
                    <label>Tests Required *</label>
                    <div class="test-checkboxes">
    `;

    for (const test of R_TEST_TYPES) {
        html += `
            <label class="checkbox-label">
                <input type="checkbox" class="test-checkbox" value="${test}">
                <span>${test === "OPD" ? "🩺 OPD (Consultation)" : test}</span>
            </label>
        `;
    }

    html += `
                    </div>
                </div>
                <button id="save-patient-btn" class="btn btn-primary btn-block">💾 Save & Generate QR</button>
                <div id="registration-result"></div>
            </div>
        </div>
    `;

    container.innerHTML = html;

    document.getElementById("save-patient-btn").addEventListener("click", async () => {
        const name = document.getElementById("reg-name").value.trim();
        const mobile = document.getElementById("reg-mobile").value.trim();
        const age = parseInt(document.getElementById("reg-age").value);
        const gender = document.getElementById("reg-gender").value;
        const selectedTests = [];
        document.querySelectorAll(".test-checkbox:checked").forEach(cb => selectedTests.push(cb.value));
        const resultDiv = document.getElementById("registration-result");

        // Validation
        if (!name) { resultDiv.innerHTML = `<p class="error-msg">⚠️ Name is required</p>`; return; }
        if (!mobile || mobile.length !== 10 || !/^\d+$/.test(mobile)) { resultDiv.innerHTML = `<p class="error-msg">⚠️ Valid 10-digit mobile required</p>`; return; }
        if (!age || age < 0 || age > 150) { resultDiv.innerHTML = `<p class="error-msg">⚠️ Valid age required</p>`; return; }
        if (selectedTests.length === 0) { resultDiv.innerHTML = `<p class="error-msg">⚠️ Select at least one test</p>`; return; }

        resultDiv.innerHTML = `<div class="spinner"></div><p>Saving...</p>`;

        try {
            const patient = await createPatient(name, mobile, age, gender);
            const createdTests = [];
            for (const test of selectedTests) {
                const t = await createTest(patient.patientId, test);
                if (t) createdTests.push(t);
            }

            const baseURL = window.location.origin + window.location.pathname.replace(/\/[^/]*$/, "/index.html");
            const qrURL = `${baseURL}?patient=${patient.patientId}`;

            resultDiv.innerHTML = `
                <div class="success-msg">✅ ${name} registered successfully!</div>
                <div class="card patient-result-card">
                    <div class="patient-result-header">
                        <div>
                            <h4>👤 ${patient.name}</h4>
                            <p>🆔 ${patient.patientId}</p>
                            <p>📱 ${patient.mobile}</p>
                        </div>
                    </div>
                    <div class="test-tokens">
                        ${createdTests.map(t => `<span class="token-badge">${t.testName} #${t.tokenNumber}</span>`).join(" ")}
                    </div>
                    <div id="qr-code-container" style="text-align:center;margin:16px 0;"></div>
                    <div style="text-align:center;margin-top:8px;">
                        <p style="font-size:0.8rem;color:#888;">📱 Patient को यह QR Code दिखाएं</p>
                    </div>
                    <div class="token-slip" style="margin-top:16px;">
                        <h4 style="text-align:center;">🖨️ Token Slip</h4>
                        <pre style="background:#f5f5f5;padding:12px;border-radius:8px;font-size:0.8rem;overflow-x:auto;">${generateTokenSlip(patient, createdTests)}</pre>
                    </div>
                </div>
            `;

            // Generate QR code
            generateQR("qr-code-container", qrURL, 180);

        } catch(e) {
            resultDiv.innerHTML = `<p class="error-msg">❌ Error: ${e.message}</p>`;
        }
    });
}

// ─── Today's Patient List (with QR Re-Open) ────────────────────────────────────

async function renderTodayPatients(container) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading...</p></div>`;

    try {
        const patients = await getTodayPatients();

        let html = `
            <div class="page-content">
                <h2>📋 Today's Patients</h2>
                <p class="subtitle">${patients.length} patients registered today</p>
                <div class="search-bar">
                    <input type="text" id="patient-search" placeholder="🔍 Search by name or mobile..." oninput="filterPatientList()">
                </div>
                <div id="patient-list-container">
        `;

        if (patients.length === 0) {
            html += `<div class="card"><p>📭 No patients registered today.</p></div>`;
        } else {
            for (const p of patients) {
                const tests = await getTestsForPatient(p.patientId);
                const urgentTests = tests.filter(t => t.status === "waiting" || t.status === "called");
                html += `
                    <div class="card patient-list-item" data-name="${p.name.toLowerCase()}" data-mobile="${p.mobile}">
                        <div class="patient-list-header">
                            <div>
                                <h4>👤 ${p.name}</h4>
                                <p>🆔 ${p.patientId} | 📱 ${p.mobile} | ${p.age}y ${p.gender}</p>
                            </div>
                        </div>
                        <div class="patient-list-tests">
                            ${tests.map(t => `
                                <span class="status-chip" style="background:${getStatusColor(t.status)};color:white;">
                                    ${STATUS_ICONS[t.status] || "❓"} ${t.testName}: ${STATUS_LABELS[t.status] || t.status}
                                </span>
                            `).join(" ")}
                        </div>
                        <div style="display:flex;gap:6px;margin-top:8px;flex-wrap:wrap;">
                            <button class="btn btn-sm btn-secondary" onclick="recShowQR('${p.patientId}')"
                                    style="font-size:0.75rem;padding:4px 10px;">📱 QR Code</button>
                            ${urgentTests.length > 0 ? urgentTests.map(t => `
                                <button class="btn btn-sm" style="background:#ff1744;color:white;font-size:0.75rem;padding:4px 10px;"
                                        onclick="recUrgentPatient('${t.testName}', '${p.name.replace(/'/g, "\\'")}', '${t.tokenNumber}', '${p.mobile}', '${p.patientId}')">
                                    🆘 ${t.testName}
                                </button>
                            `).join("") : ""}
                        </div>
                    </div>
                `;
            }
        }

        html += `</div></div>`;
        container.innerHTML = html;

    } catch(e) {
        container.innerHTML = `<div class="page-content"><p class="error-msg">❌ Error: ${e.message}</p></div>`;
    }

    // Auto-refresh every 10s
    if (window.refreshInterval) clearInterval(window.refreshInterval);
    window.refreshInterval = setInterval(async () => {
        renderTodayPatients(container);
    }, 10000);
}

// ─── QR Re-Open ─────────────────────────────────────────────────────────────────

async function recShowQR(patientId) {
    const patient = await getPatientById(patientId);
    if (!patient) {
        showToast("❌ Patient not found", "error");
        return;
    }
    showQRModal(patient);
}

// ─── Urgent for specific patient ───────────────────────────────────────────────

async function recUrgentPatient(testName, patientName, token, mobile, patientId) {
    await sendAlert("urgent",
        `🆘 ${patientName} (Token #${token}) needs urgent ${testName}!`,
        "Reception", testName,
        { patientId, patientName, testName, tokenNumber: token }
    );
    showToast(`🆘 Urgent sent for ${patientName} to ${testName}`, "urgent");
    playAlertSound("urgent");
}

// ─── Filter ─────────────────────────────────────────────────────────────────────

function filterPatientList() {
    const q = document.getElementById("patient-search").value.toLowerCase();
    document.querySelectorAll(".patient-list-item").forEach(item => {
        const name = item.dataset.name;
        const mobile = item.dataset.mobile;
        item.style.display = (!q || name.includes(q) || mobile.includes(q)) ? "block" : "none";
    });
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function getStatusColor(status) {
    const colors = { waiting: "#FFA500", called: "#2196F3", in_progress: "#FF9800", completed: "#4CAF50", report_ready: "#9C27B0", delivered: "#607D8B" };
    return colors[status] || "#999";
}

function generateTokenSlip(patient, tests) {
    const lines = [
        "=".repeat(40),
        "      CARDIOLOGY DEPARTMENT",
        "         GIL CLINIC",
        "=".repeat(40),
        "",
        `  Token: ${patient.patientId}`,
        `  Patient: ${patient.name}`,
        `  Date: ${new Date().toLocaleDateString("hi-IN")}`,
        "",
        "-".repeat(40),
        "  Tests:",
        ...tests.map(t => `    ${String(t.tokenNumber).padStart(3, "0")}  ${t.testName}  —  ${t.room}`),
        "",
        "-".repeat(40),
        "  Please wait for your call.",
        "  Watch the display board for updates.",
        "=".repeat(40)
    ];
    return lines.join("\n");
}
