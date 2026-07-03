/**
 * CardioQueue — Manager Module
 * ==============================
 * Manager sees ALL departments on one screen.
 * Can send messages/reminders to any technician.
 * Can override patient priority.
 */

const MGR_TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"];
const MGR_STATUS_ICONS = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
const MGR_STATUS_LABELS = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };

// ─── Manager Dashboard ──────────────────────────────────────────────────────────

async function renderManagerDashboard(container) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading Manager Dashboard...</p></div>`;

    try {
        const allStats = await getAllDepartmentsStats();
        const todayPatients = await getTodayPatients();
        const alerts = await getActiveAlerts("Manager");

        const gt = allStats.grandTotal || {};
        const depts = allStats.departments || {};

        let html = `
            <div class="page-content">
                <h2>👑 Manager Dashboard</h2>
                <p class="subtitle">${new Date().toLocaleString("hi-IN")}</p>

                <!-- Grand Totals -->
                <div class="stats-row">
                    <div class="stat-card" style="background:#FFF3E0;">
                        <div class="stat-value">${gt.waiting || 0}</div>
                        <div class="stat-label">🟡 Waiting</div>
                    </div>
                    <div class="stat-card" style="background:#E3F2FD;">
                        <div class="stat-value">${gt.called || 0}</div>
                        <div class="stat-label">🔵 Called</div>
                    </div>
                    <div class="stat-card" style="background:#FFE0B2;">
                        <div class="stat-value">${gt.in_progress || 0}</div>
                        <div class="stat-label">🟠 Active</div>
                    </div>
                    <div class="stat-card" style="background:#E8F5E9;">
                        <div class="stat-value">${gt.completed || 0}</div>
                        <div class="stat-label">✅ Done</div>
                    </div>
                    <div class="stat-card" style="background:#F3E5F5;">
                        <div class="stat-value">${todayPatients.length}</div>
                        <div class="stat-label">📋 Today</div>
                    </div>
                </div>

                <!-- Active Alerts -->
                ${alerts && alerts.length > 0 ? `
                <div class="card" style="background:#fff3e0;border-left:5px solid #ff1744;margin-top:12px;">
                    <h4 style="color:#d32f2f;">🚨 Active Alerts (${alerts.length})</h4>
                    ${alerts.map(a => `
                        <div style="padding:8px;border-bottom:1px solid #eee;font-size:0.9rem;">
                            <strong>${a.type === "urgent" ? "🆘" : "🔔"} ${a.message}</strong>
                            <span style="color:#888;font-size:0.8rem;"> — ${a.fromRole} • ${a.createdAt ? new Date(a.createdAt).toLocaleTimeString() : ""}</span>
                        </div>
                    `).join("")}
                    <button class="btn btn-secondary btn-sm" style="margin-top:8px;" onclick="mgrDismissAllAlerts()">✅ Dismiss All</button>
                </div>
                ` : ""}

                <!-- Department Breakdown -->
                <h3 style="margin-top:16px;">🏥 Department Overview</h3>
                <div class="dept-grid">
        `;

        for (const test of MGR_TEST_TYPES) {
            const s = depts[test] || { waiting: 0, called: 0, in_progress: 0, completed: 0, report_ready: 0, delivered: 0 };
            const total = Object.values(s).reduce((a, b) => a + b, 0);
            const color = test === "OPD" ? "#4CAF50" : "#667eea";

            html += `
                <div class="card dept-card" style="border-left:4px solid ${color};margin-top:8px;">
                    <div class="dept-card-header" style="display:flex;justify-content:space-between;align-items:center;">
                        <h4>${test === "OPD" ? "🩺 OPD" : `📊 ${test}`} <span style="font-size:0.8rem;color:#888;">(${total})</span></h4>
                        <div>
                            <button class="btn btn-sm" style="background:#ff1744;color:white;padding:4px 8px;font-size:0.75rem;"
                                    onclick="mgrSendUrgent('${test}')">🆘 Urgent</button>
                        </div>
                    </div>
                    <div class="dept-stat-row" style="display:flex;gap:8px;font-size:0.8rem;margin-top:4px;flex-wrap:wrap;">
                        <span>🟡 ${s.waiting || 0}</span>
                        <span>🔵 ${s.called || 0}</span>
                        <span>🟠 ${s.in_progress || 0}</span>
                        <span>✅ ${s.completed || 0}</span>
                        <span>📋 ${s.report_ready || 0}</span>
                        <span>📄 ${s.delivered || 0}</span>
                    </div>
                </div>
            `;
        }

        html += `
                </div>

                <!-- Quick Actions -->
                <h3 style="margin-top:16px;">⚡ Quick Actions</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
                    <button class="btn btn-secondary" onclick="mgrBroadcast('All technicians, please clear the pending queue.')">📢 Broadcast to All</button>
                    <button class="btn btn-secondary" onclick="mgrAlertReadyReports()">📋 Pending Reports Alert</button>
                </div>
            </div>
        `;

        container.innerHTML = html;

    } catch(e) {
        container.innerHTML = `<div class="page-content"><p class="error-msg">❌ Error: ${e.message}</p></div>`;
    }

    // Auto-refresh every 8s
    if (window.refreshInterval) clearInterval(window.refreshInterval);
    window.refreshInterval = setInterval(async () => {
        renderManagerDashboard(container);
    }, 8000);
}

// ─── Manager Actions ────────────────────────────────────────────────────────────

async function mgrSendUrgent(department) {
    await sendAlert("urgent", `🆘 Manager: ${department} mein jaldi karo!`, "Manager", department);
    showToast(`🆘 Urgent message sent to ${department}`, "urgent");
    playAlertSound("urgent");
}

async function mgrBroadcast(message) {
    const roles = ["ECG", "Echo", "TMT", "Holter", "ABPM", "OPD"];
    for (const role of roles) {
        await sendAlert("broadcast", `📢 ${message}`, "Manager", role);
    }
    showToast(`📢 Broadcast sent to all departments`, "success");
    playAlertSound("success");
}

async function mgrAlertReadyReports() {
    const reports = await getReportReadyTests();
    if (reports.length === 0) {
        showToast("✅ No pending reports to deliver", "success");
        return;
    }
    // Alert reception about pending reports
    await sendAlert("report_ready", `📋 ${reports.length} reports ready for delivery!`, "Manager", "Reception");
    showToast(`📋 Alerted Reception about ${reports.length} pending reports`, "success");
    playAlertSound("success");
}

async function mgrDismissAllAlerts() {
    const alerts = await getActiveAlerts("Manager");
    for (const a of alerts) {
        await dismissAlert(a.id);
    }
    showToast("✅ All alerts dismissed", "success");
}

// ─── Expose Globally ───────────────────────────────────────────────────────────

window.renderManagerDashboard = renderManagerDashboard;
window.mgrSendUrgent = mgrSendUrgent;
window.mgrBroadcast = mgrBroadcast;
window.mgrAlertReadyReports = mgrAlertReadyReports;
window.mgrDismissAllAlerts = mgrDismissAllAlerts;
