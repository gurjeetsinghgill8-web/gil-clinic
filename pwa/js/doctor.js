/**
 * CardioQueue — Doctor Module
 * Manages report lifecycle: Review completed tests → Mark Report Ready → Mark Delivered.
 */

async function renderDoctorDashboard(container) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading...</p></div>`;

    try {
        const completed = await getCompletedTests();
        const reportReady = await getReportReadyTests();

        let html = `
            <div class="page-content">
                <h2>🩺 Doctor Dashboard</h2>
                <p class="subtitle">${new Date().toLocaleString("hi-IN")}</p>

                <div class="stats-row">
                    <div class="stat-card" style="background:#E3F2FD;">
                        <div class="stat-value">${completed.length}</div>
                        <div class="stat-label">📋 Pending Reports</div>
                    </div>
                    <div class="stat-card" style="background:#F3E5F5;">
                        <div class="stat-value">${reportReady.length}</div>
                        <div class="stat-label">📤 Ready to Deliver</div>
                    </div>
                </div>
        `;

        // ─── Pending Reports (completed, awaiting report_ready) ───────────────
        html += `
                <h3 style="margin-top:16px;">📋 Pending Reports (${completed.length})</h3>
        `;

        if (completed.length === 0) {
            html += `<div class="card"><p>✅ No pending reports.</p></div>`;
        } else {
            for (const t of completed) {
                const p = t.patients || {};
                html += `
                    <div class="card pending-item" style="border-left:5px solid #4CAF50;">
                        <div class="pending-item-header">
                            <div>
                                <h4>👤 ${p.name || "Unknown"}</h4>
                                <p>🧪 ${t.testName} | 🎫 Token #${t.tokenNumber} | 📱 ${p.mobile || ""}</p>
                            </div>
                            <button class="btn btn-primary btn-sm" onclick="doctorMarkReady('${t.id}', '${(p.name || "").replace(/'/g, "\\'")}', '${t.testName}', '${p.mobile || ""}', '${t.patientId}')">
                                📋 Report Ready
                            </button>
                        </div>
                    </div>
                `;
            }
        }

        // ─── Reports Ready for Delivery ───────────────────────────────────────
        html += `
                <h3 style="margin-top:16px;">📤 Reports Ready for Delivery (${reportReady.length})</h3>
        `;

        if (reportReady.length === 0) {
            html += `<div class="card"><p>✅ No reports ready for delivery.</p></div>`;
        } else {
            for (const t of reportReady) {
                const p = t.patients || {};
                html += `
                    <div class="card pending-item" style="border-left:5px solid #9C27B0;">
                        <div class="pending-item-header">
                            <div>
                                <h4>👤 ${p.name || "Unknown"}</h4>
                                <p>🧪 ${t.testName} | 🎫 Token #${t.tokenNumber} | 📱 ${p.mobile || ""}</p>
                            </div>
                            <button class="btn btn-success btn-sm" onclick="doctorDeliver('${t.id}')">
                                📄 Delivered
                            </button>
                        </div>
                    </div>
                `;
            }
        }

        html += `</div>`;
        container.innerHTML = html;

    } catch(e) {
        container.innerHTML = `<div class="page-content"><p class="error-msg">❌ Error: ${e.message}</p></div>`;
    }

    // Auto-refresh every 10s
    if (window.refreshInterval) clearInterval(window.refreshInterval);
    window.refreshInterval = setInterval(async () => {
        renderDoctorDashboard(container);
    }, 10000);
}

// ─── Doctor Actions ────────────────────────────────────────────────────────────

async function doctorMarkReady(testId, patientName, testName, mobile, patientId) {
    const success = await updateTestStatus(testId, "report_ready");
    if (success) {
        alert(`📋 Report ready for ${patientName} — ${testName}`);
        if (navigator.vibrate) navigator.vibrate(100);
    } else {
        alert("❌ Failed to mark report ready");
    }
}

async function doctorDeliver(testId) {
    const success = await updateTestStatus(testId, "delivered");
    if (success) {
        alert("📄 Report marked as delivered");
    } else {
        alert("❌ Failed to mark delivered");
    }
}
