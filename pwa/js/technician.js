/**
 * CardioQueue — Technician Module
 * Shared dashboard for ECG, Echo, TMT technicians.
 * Features: Current Patient, Waiting List, Call/Start/Complete actions.
 */

const TECH_STATUS_ICONS = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
const TECH_STATUS_LABELS = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };
const TECH_AVG_TIMES = { ECG: 10, Echo: 20, TMT: 30, Holter: 15, ABPM: 15 };

async function renderTechnicianDashboard(container, testName) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading ${testName}...</p></div>`;

    try {
        const current = await getCurrentPatient(testName);
        const waitingList = await getQueue(testName, "waiting");
        const stats = await getDepartmentStats(testName);

        const totalPatients = Object.values(stats).reduce((a, b) => a + b, 0);

        let html = `
            <div class="page-content">
                <h2>📊 ${testName} Dashboard</h2>
                <p class="subtitle">${new Date().toLocaleString("hi-IN")}</p>

                <div class="stats-row">
                    <div class="stat-card" style="background:#FFF3E0;">
                        <div class="stat-value">${stats.waiting || 0}</div>
                        <div class="stat-label">🟡 Waiting</div>
                    </div>
                    <div class="stat-card" style="background:#E3F2FD;">
                        <div class="stat-value">${stats.called || 0}</div>
                        <div class="stat-label">🔵 Called</div>
                    </div>
                    <div class="stat-card" style="background:#FFE0B2;">
                        <div class="stat-value">${stats.in_progress || 0}</div>
                        <div class="stat-label">🟠 Active</div>
                    </div>
                    <div class="stat-card" style="background:#E8F5E9;">
                        <div class="stat-value">${stats.completed || 0}</div>
                        <div class="stat-label">✅ Done</div>
                    </div>
                    <div class="stat-card" style="background:#F3E5F5;">
                        <div class="stat-value">${totalPatients}</div>
                        <div class="stat-label">📋 Total</div>
                    </div>
                </div>

                <h3 style="margin-top:16px;">🟢 Current Patient</h3>
        `;

        if (current) {
            const p = current.patients || {};
            const elapsed = current.calledAt ? Math.floor((Date.now() - new Date(current.calledAt).getTime()) / 60000) : 0;
            const color = current.status === "called" ? "#2196F3" : "#FF9800";

            html += `
                <div class="card current-patient-card" style="border-left: 5px solid ${color};">
                    <div class="current-patient-header">
                        <div>
                            <h3>👤 ${p.name || "Unknown"}</h3>
                            <p>🎫 Token #${current.tokenNumber} | 📱 ${p.mobile || ""} | ${p.age || ""}y</p>
                        </div>
                        <div class="status-badge" style="background:${color};color:white;">
                            ${TECH_STATUS_ICONS[current.status]} ${TECH_STATUS_LABELS[current.status]}
                        </div>
                    </div>
                    <div class="current-patient-actions">
                        ${current.status === "called" ? `
                            <button class="btn btn-primary" onclick="techStartTest('${current.id}')">▶️ Start Test</button>
                            <button class="btn btn-secondary" onclick="techCompleteTest('${current.id}', '${(p.name || "").replace(/'/g, "\\'")}', '${testName}', '${p.mobile || ""}', '${current.patientId}')">✅ Complete</button>
                        ` : ""}
                        ${current.status === "in_progress" ? `
                            <button class="btn btn-success" onclick="techCompleteTest('${current.id}', '${(p.name || "").replace(/'/g, "\\'")}', '${testName}', '${p.mobile || ""}', '${current.patientId}')">✅ Complete Test</button>
                        ` : ""}
                        <span class="elapsed-time">⏱️ ${elapsed} min</span>
                    </div>
                </div>
            `;
        } else {
            html += `<div class="card"><p>👀 No patient currently being served in ${testName}.</p></div>`;
        }

        // ─── Waiting List ─────────────────────────────────────────────────────
        html += `
                <h3 style="margin-top:16px;">⏳ Waiting List (${waitingList.length})</h3>
        `;

        if (waitingList.length === 0) {
            html += `<div class="card"><p>✅ No patients waiting for ${testName}.</p></div>`;
        } else {
            for (const w of waitingList) {
                const p = w.patients || {};
                const waitTime = calculateWaitTime(testName, w.queuePosition || 0);
                const registeredTime = w.createdAt ? Math.floor((Date.now() - new Date(w.createdAt).getTime()) / 60000) : 0;

                html += `
                    <div class="card waiting-item">
                        <div class="waiting-item-header">
                            <div>
                                <h4>${p.name || "Unknown"}</h4>
                                <p>🎫 Token #${w.tokenNumber} | 📱 ${p.mobile || ""} | ${p.age || ""}y</p>
                            </div>
                            <div class="waiting-actions">
                                <button class="btn btn-primary btn-sm" onclick="techCallPatient('${w.id}', '${(p.name || "").replace(/'/g, "\\'")}', '${testName}', '${w.tokenNumber}', '${p.mobile || ""}', '${w.patientId}')">
                                    🔵 Call
                                </button>
                            </div>
                        </div>
                        <div class="waiting-meta">
                            <span>⏱️ Est: ~${waitTime} min</span>
                            <span>📍 #${w.queuePosition}</span>
                            <span>⏳ Waiting: ${registeredTime} min</span>
                        </div>
                    </div>
                `;
            }
        }

        html += `
                <div class="card info-box" style="margin-top:16px;">
                    <p>ℹ️ <strong>${testName}</strong> | Avg time: ${TECH_AVG_TIMES[testName] || 15} min | Room: ${testName} Room 1</p>
                </div>
            </div>
        `;

        container.innerHTML = html;

    } catch(e) {
        container.innerHTML = `<div class="page-content"><p class="error-msg">❌ Error: ${e.message}</p></div>`;
    }

    // Auto-refresh every 5s
    if (window.refreshInterval) clearInterval(window.refreshInterval);
    window.refreshInterval = setInterval(async () => {
        renderTechnicianDashboard(container, testName);
    }, 5000);
}

// ─── Technician Actions ────────────────────────────────────────────────────────

async function techCallPatient(testId, patientName, testName, token, mobile, patientId) {
    const success = await updateTestStatus(testId, "called");
    if (success) {
        // Trigger notification sound
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 880;
            osc.type = "sine";
            gain.gain.value = 0.3;
            osc.start();
            osc.stop(ctx.currentTime + 0.3);
        } catch(e) {}
        if (navigator.vibrate) navigator.vibrate(200);
        alert(`🔵 Called ${patientName} to ${testName} Room`);
    } else {
        alert("❌ Failed to call patient");
    }
}

async function techStartTest(testId) {
    const success = await updateTestStatus(testId, "in_progress");
    if (success) {
        alert("🟠 Test started");
    } else {
        alert("❌ Failed to start test");
    }
}

async function techCompleteTest(testId, patientName, testName, mobile, patientId) {
    const success = await updateTestStatus(testId, "completed");
    if (success) {
        alert(`✅ ${testName} completed for ${patientName}`);
        // Trigger notification
        try {
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.frequency.value = 660;
            osc.type = "sine";
            gain.gain.value = 0.3;
            osc.start();
            osc.stop(ctx.currentTime + 0.2);
        } catch(e) {}
        if (navigator.vibrate) navigator.vibrate(100);
    } else {
        alert("❌ Failed to complete test");
    }
}
