/**
 * CardioQueue — Doctor Module
 * Manages report lifecycle: Review completed tests → Mark Report Ready → Mark Delivered.
 * NEW: OPD queue (consultation management)
 * NEW: Sends report_ready alert to Reception
 */

async function renderDoctorDashboard(container) {
    container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading...</p></div>`;

    try {
        const completed = await getCompletedTests();
        const reportReady = await getReportReadyTests();
        const opdWaiting = await getQueue("OPD", "waiting");
        const opdCurrent = await getCurrentPatient("OPD");

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
                    <div class="stat-card" style="background:#E8F5E9;">
                        <div class="stat-value">${opdWaiting.length}</div>
                        <div class="stat-label">🩺 OPD Waiting</div>
                    </div>
                </div>

                <!-- ═══════════ OPD SECTION ═══════════ -->
                <h3 style="margin-top:16px;">🩺 OPD Queue (${opdWaiting.length})</h3>
        `;

        // Current OPD Patient
        if (opdCurrent) {
            const p = opdCurrent.patients || {};
            html += `
                <div class="card" style="border-left:5px solid #4CAF50;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <h4>👤 ${p.name || "Unknown"}</h4>
                            <p>🎫 Token #${opdCurrent.tokenNumber} | 📱 ${p.mobile || ""}</p>
                        </div>
                        <div>
                            <button class="btn btn-success btn-sm" onclick="doctorCompleteOPD('${opdCurrent.id}', '${(p.name || "").replace(/'/g, "\\'")}', '${p.mobile || ""}', '${opdCurrent.patientId}')">
                                ✅ Done
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else if (opdWaiting.length > 0) {
            // Show call button for first waiting OPD
            const first = opdWaiting[0];
            const p = first.patients || {};
            html += `
                <div class="card" style="border-left:5px solid #FFA500;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <h4>👤 ${p.name || "Unknown"}</h4>
                            <p>🎫 Token #${first.tokenNumber} | 📱 ${p.mobile || ""}</p>
                        </div>
                        <button class="btn btn-primary btn-sm" onclick="doctorCallOPD('${first.id}', '${(p.name || "").replace(/'/g, "\\'")}')">
                            🔵 Call for OPD
                        </button>
                    </div>
                </div>
            `;
            // List remaining
            for (let i = 1; i < opdWaiting.length; i++) {
                const w = opdWaiting[i];
                const px = w.patients || {};
                html += `
                    <div class="card waiting-item" style="padding:8px 12px;margin-top:4px;">
                        <div style="display:flex;justify-content:space-between;">
                            <span>👤 ${px.name || "Unknown"} — 🎫 #${w.tokenNumber}</span>
                            <span style="color:#888;font-size:0.8rem;">⏳ ${calculateWaitTime("OPD", w.queuePosition || 0)} min</span>
                        </div>
                    </div>
                `;
            }
        } else {
            html += `<div class="card"><p>✅ No OPD patients waiting.</p></div>`;
        }

        // ═══════════ PENDING REPORTS ═══════════
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

        // ═══════════ REPORTS READY ═══════════
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

// ─── OPD Actions ────────────────────────────────────────────────────────────────

async function doctorCallOPD(testId, patientName) {
    const success = await updateTestStatus(testId, "called");
    if (success) {
        showToast(`🔵 Called ${patientName} for OPD consultation`, "info");
        playAlertSound("success");
        if (navigator.vibrate) navigator.vibrate(200);
    } else {
        showToast("❌ Failed to call patient", "error");
    }
}

async function doctorCompleteOPD(testId, patientName, mobile, patientId) {
    const success = await updateTestStatus(testId, "completed");
    if (success) {
        showToast(`✅ OPD complete for ${patientName}`, "success");
        playAlertSound("success");
        if (navigator.vibrate) navigator.vibrate(100);
    } else {
        showToast("❌ Failed to complete OPD", "error");
    }
}

// ─── Doctor Actions ─────────────────────────────────────────────────────────────

async function doctorMarkReady(testId, patientName, testName, mobile, patientId) {
    const success = await updateTestStatus(testId, "report_ready");
    if (success) {
        showToast(`📋 Report ready for ${patientName} — ${testName}`, "success");
        if (navigator.vibrate) navigator.vibrate(100);
        
        // Send alert to Reception that report is ready
        await sendAlert("report_ready",
            `📋 ${patientName} — ${testName} report ready`,
            "Doctor", "Reception",
            { patientId, patientName, testName, relatedTestId: testId }
        );
    } else {
        showToast("❌ Failed to mark report ready", "error");
    }
}

async function doctorDeliver(testId) {
    const success = await updateTestStatus(testId, "delivered");
    if (success) {
        showToast("📄 Report marked as delivered", "success");
    } else {
        showToast("❌ Failed to mark delivered", "error");
    }
}
