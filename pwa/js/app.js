/**
 * CardioQueue PWA — Main Application
 * =====================================
 * Handles routing, login, navigation, and screen management.
 * All data operations go through db.js (IndexedDB).
 * No server, no cloud, no internet needed.
 */
(function() {
    "use strict";

    // ─── Constants ─────────────────────────────────────────────────────────────
    const PASSWORDS = {
        Reception: "recep123",
        ECG: "ecg123",
        Echo: "echo123",
        TMT: "tmt123",
        Doctor: "doc123"
    };

    const TEST_TYPES = ["ECG", "Echo", "TMT", "Holter", "ABPM"];

    let currentRole = null;
    let currentView = "dashboard";
    let refreshInterval = null;

    // ─── Screen Management ─────────────────────────────────────────────────────

    function showScreen(screenId) {
        document.querySelectorAll(".screen").forEach(s => s.classList.remove("active"));
        const screen = document.getElementById(screenId);
        if (screen) screen.classList.add("active");
    }

    // ─── Login ─────────────────────────────────────────────────────────────────

    function initLogin() {
        const roleSelect = document.getElementById("role-select");
        const passwordGroup = document.getElementById("password-group");
        const loginBtn = document.getElementById("login-btn");
        const loginError = document.getElementById("login-error");

        // Toggle password field based on role
        roleSelect.addEventListener("change", () => {
            if (roleSelect.value === "Patient") {
                passwordGroup.style.display = "none";
            } else {
                passwordGroup.style.display = "block";
            }
            loginError.textContent = "";
        });

        loginBtn.addEventListener("click", async () => {
            const role = roleSelect.value;
            loginError.textContent = "";

            if (role === "Patient") {
                // No password needed — go to patient lookup
                currentRole = "Patient";
                localStorage.setItem("cardioqueue_role", "Patient");
                showScreen("app-shell");
                document.getElementById("bottom-nav").style.display = "none";
                document.getElementById("header-text").textContent = "🔍 Patient Status";
                renderPatientLookup();
                return;
            }

            const password = document.getElementById("password-input").value;
            const expected = PASSWORDS[role];

            if (password === expected) {
                currentRole = role;
                localStorage.setItem("cardioqueue_role", role);
                localStorage.setItem("cardioqueue_role_expires", Date.now() + 86400000); // 24h
                showScreen("app-shell");
                document.getElementById("bottom-nav").style.display = "flex";
                document.getElementById("header-text").textContent = `📋 ${role}`;
                document.getElementById("menu-btn").style.display = "none";
                showView("dashboard");
            } else {
                loginError.textContent = "❌ गलत पासवर्ड / Incorrect password";
            }
        });
    }

    // ─── View Router ───────────────────────────────────────────────────────────

    function showView(view, params) {
        currentView = view;
        const main = document.getElementById("main-content");

        // Clear any existing refresh
        if (refreshInterval) {
            clearInterval(refreshInterval);
            refreshInterval = null;
        }

        switch (view) {
            case "dashboard":
                renderDashboard(main);
                break;
            case "register":
                renderRegistration(main);
                break;
            case "patients":
                renderPatientList(main);
                break;
            case "export":
                renderExport(main);
                break;
            default:
                renderDashboard(main);
        }

        // Update nav active state
        document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
        const activeBtn = document.querySelector(`.nav-btn[data-view="${view}"]`);
        if (activeBtn) activeBtn.classList.add("active");
    }

    // ─── Navigation ────────────────────────────────────────────────────────────

    function initNavigation() {
        document.querySelectorAll(".nav-btn").forEach(btn => {
            btn.addEventListener("click", () => {
                const view = btn.dataset.view;
                if (view === "logout") {
                    logout();
                    return;
                }
                showView(view);
            });
        });
    }

    function logout() {
        if (refreshInterval) clearInterval(refreshInterval);
        currentRole = null;
        localStorage.removeItem("cardioqueue_role");
        localStorage.removeItem("cardioqueue_role_expires");
        document.getElementById("bottom-nav").style.display = "none";
        showScreen("login-screen");
        document.getElementById("password-input").value = "";
    }

    // ─── PWA Install Handler ───────────────────────────────────────────────────

    let deferredInstallPrompt = null;

    function initPWAInstall() {
        window.addEventListener("beforeinstallprompt", (e) => {
            e.preventDefault();
            deferredInstallPrompt = e;
            document.getElementById("install-btn").style.display = "block";
            document.getElementById("install-banner").style.display = "flex";
        });

        document.getElementById("install-btn").addEventListener("click", installPWA);
        document.getElementById("install-banner-btn").addEventListener("click", installPWA);
        document.getElementById("install-dismiss").addEventListener("click", () => {
            document.getElementById("install-banner").style.display = "none";
        });
    }

    function installPWA() {
        if (!deferredInstallPrompt) return;
        deferredInstallPrompt.prompt();
        deferredInstallPrompt.userChoice.then(() => {
            deferredInstallPrompt = null;
            document.getElementById("install-btn").style.display = "none";
            document.getElementById("install-banner").style.display = "none";
        });
    }

    // ─── Render Helpers ────────────────────────────────────────────────────────

    function renderDashboard(container) {
        container.innerHTML = `<div class="page-loading"><div class="spinner"></div><p>Loading dashboard...</p></div>`;
        if (currentRole === "Reception") {
            renderReceptionDashboard(container);
        } else if (["ECG", "Echo", "TMT"].includes(currentRole)) {
            renderTechnicianDashboard(container, currentRole);
        } else if (currentRole === "Doctor") {
            renderDoctorDashboard(container);
        } else {
            container.innerHTML = `<div class="page-content"><h2>👋 Welcome ${currentRole}</h2><p>Select an option from the bottom navigation.</p></div>`;
        }
    }

    function renderRegistration(container) {
        if (currentRole === "Reception") {
            renderReceptionForm(container);
        } else {
            container.innerHTML = `<div class="page-content"><p>⚠️ Only Reception can register patients.</p></div>`;
        }
    }

    function renderPatientList(container) {
        renderTodayPatients(container);
    }

    function renderExport(container) {
        container.innerHTML = `
            <div class="page-content">
                <h2>📤 Export Data</h2>
                <p>डेटा Excel/CSV फ़ाइल में export करें / Export data to CSV file</p>
                <div class="card" style="margin-top: 16px;">
                    <button class="btn btn-primary btn-block" onclick="exportTodayCSV()">
                        📅 आज का डेटा / Today's Data
                    </button>
                </div>
                <div class="card" style="margin-top: 12px;">
                    <button class="btn btn-secondary btn-block" onclick="exportPatientsCSV()">
                        📦 सारा डेटा / All Data
                    </button>
                </div>
                <div class="info-box" style="margin-top: 20px;">
                    <p>💡 CSV फ़ाइल mobile में download होगी। आप इसे email, WhatsApp या कहीं भी share कर सकते हैं।</p>
                    <p style="font-size:0.8rem;margin-top:8px;">The CSV file will download to your phone. You can share it via email, WhatsApp, or anywhere.</p>
                </div>
            </div>
        `;
    }

    // ─── Patient Lookup (for Patient role) ─────────────────────────────────────

    function renderPatientLookup() {
        const main = document.getElementById("main-content");
        main.innerHTML = `
            <div class="page-content">
                <div class="patient-lookup">
                    <h2>🔍 अपना स्टेटस देखें</h2>
                    <p>अपना रजिस्टर्ड मोबाइल नंबर डालें</p>
                    <div class="form-group">
                        <input type="text" id="patient-mobile-input" 
                               placeholder="10 अंकों का मोबाइल नंबर" 
                               maxlength="10" inputmode="numeric" autocomplete="off">
                    </div>
                    <button id="patient-lookup-btn" class="btn btn-primary btn-block">
                        🔍 Check Status
                    </button>
                    <div id="patient-result"></div>
                </div>
            </div>
        `;

        document.getElementById("patient-lookup-btn").addEventListener("click", async () => {
            const mobile = document.getElementById("patient-mobile-input").value.trim();
            const resultDiv = document.getElementById("patient-result");
            if (!mobile || mobile.length !== 10 || !/^\d+$/.test(mobile)) {
                resultDiv.innerHTML = `<p class="error-msg">⚠️ कृपया सही 10 अंकों का मोबाइल नंबर डालें</p>`;
                return;
            }
            resultDiv.innerHTML = `<div class="spinner"></div><p>Searching...</p>`;
            const patient = await getPatientByMobile(mobile);
            if (!patient) {
                resultDiv.innerHTML = `<p class="error-msg">❌ कोई मरीज़ नहीं मिला / No patient found with this number</p>`;
                return;
            }
            const tests = await getTestsForPatient(patient.patientId);
            renderPatientStatus(resultDiv, patient, tests);
            // Start auto-refresh
            if (refreshInterval) clearInterval(refreshInterval);
            refreshInterval = setInterval(async () => {
                const updatedTests = await getTestsForPatient(patient.patientId);
                const resDiv = document.getElementById("patient-result");
                if (resDiv) renderPatientStatus(resDiv, patient, updatedTests);
            }, 5000);
        });
    }

    // ─── ─── PATIENT STATUS RENDERER (shared) ──────────────────────────────────

    function renderPatientStatus(container, patient, tests) {
        if (!tests || tests.length === 0) {
            container.innerHTML = `<div class="card"><p>📭 कोई टेस्ट नहीं / No tests registered</p></div>`;
            return;
        }

        const statusOrder = ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"];
        const statusColors = {
            waiting: "#FFA500", called: "#2196F3", in_progress: "#FF9800",
            completed: "#4CAF50", report_ready: "#9C27B0", delivered: "#607D8B"
        };
        const statusIcons = { waiting: "🟡", called: "🔵", in_progress: "🟠", completed: "✅", report_ready: "📋", delivered: "📄" };
        const statusLabels = { waiting: "Waiting", called: "Called", in_progress: "In Progress", completed: "Completed", report_ready: "Report Ready", delivered: "Delivered" };

        let maxProgress = 0;
        let statusHash = "";
        tests.forEach(t => {
            const idx = statusOrder.indexOf(t.status);
            if (idx >= 0) {
                maxProgress = Math.max(maxProgress, (idx + 1) / statusOrder.length);
                statusHash += `${t.testName}:${t.status}|`;
            }
        });

        let html = `
            <div class="patient-status-dashboard">
                <div class="card patient-info-card">
                    <div class="patient-info-header">
                        <div>
                            <h3>👤 ${patient.name}</h3>
                            <p class="patient-id">🆔 ${patient.patientId}</p>
                        </div>
                        <div class="status-badge" style="background:${statusColors[tests[0].status] || "#666"};color:white;">
                            ${statusIcons[tests[0].status] || "❓"} ${statusLabels[tests[0].status] || tests[0].status}
                        </div>
                    </div>
                </div>

                <div class="live-indicator">
                    <span class="pulse-dot"></span>
                    <span>Live — अपडेट हो रहा है / Auto-updating</span>
                </div>

                <div class="progress-section">
                    <p><strong>Overall Progress</strong></p>
                    <div class="progress-bar">
                        <div class="progress-fill" style="width:${maxProgress * 100}%;"></div>
                    </div>
                    <p class="progress-text">${Math.round(maxProgress * 100)}%</p>
                </div>

                <div id="status-hash" style="display:none;" data-hash="${statusHash}"></div>
        `;

        tests.forEach(t => {
            const waitTime = calculateWaitTime(t.testName, t.queuePosition || 0);
            const pos = t.queuePosition || 0;
            const color = statusColors[t.status] || "#E0E0E0";
            const icon = statusIcons[t.status] || "❓";
            const label = statusLabels[t.status] || t.status;
            let testProgress = 0;
            const idx = statusOrder.indexOf(t.status);
            if (idx >= 0) testProgress = (idx + 1) / statusOrder.length;

            html += `
                <div class="card test-card" style="border-left: 5px solid ${color};">
                    <div class="test-card-header">
                        <div>
                            <h4>${t.testName}</h4>
                            <p class="test-meta">🏠 ${t.room} | 🎫 Token #${t.tokenNumber}</p>
                        </div>
                        <div class="test-status">${icon} <strong>${label}</strong></div>
                    </div>
                    <div class="test-details">
                        ${["waiting", "called"].includes(t.status) ? `<span>⏱️ ~${waitTime} min ${pos ? `| Position #${pos}` : ""}</span>` : ""}
                        ${t.status === "in_progress" ? '<span>🔄 In Progress...</span>' : ""}
                        ${t.status === "completed" ? '<span>✅ Done</span>' : ""}
                        ${t.status === "report_ready" ? '<span>📋 Collect at Counter</span>' : ""}
                        ${t.status === "delivered" ? '<span>📄 Delivered</span>' : ""}
                    </div>
                    <div class="progress-bar small">
                        <div class="progress-fill" style="width:${testProgress * 100}%;"></div>
                    </div>
                </div>
            `;
        });

        // Summary
        const allCompleted = tests.every(t => ["completed", "report_ready", "delivered"].includes(t.status));
        const anyInProgress = tests.some(t => t.status === "in_progress");
        const anyCalled = tests.some(t => t.status === "called");
        let summaryMsg = "";
        if (allCompleted) summaryMsg = "🎉 सभी टेस्ट पूरे! काउंटर से रिपोर्ट लें / All tests complete! Collect reports.";
        else if (anyInProgress) summaryMsg = "🔄 टेस्ट चल रहे हैं / Tests in progress";
        else if (anyCalled) summaryMsg = "🔵 आपको बुलाया गया है! / You've been called!";
        else summaryMsg = `⏳ कृपया प्रतीक्षा करें / Please wait`;

        html += `
                <div class="card summary-card">
                    <p><strong>${summaryMsg}</strong></p>
                </div>
            </div>
        `;

        container.innerHTML = html;
    }

    // ─── Expose globals for inline onclick ─────────────────────────────────────

    window.renderPatientLookup = renderPatientLookup;
    window.renderPatientStatus = renderPatientStatus;

    // ─── Init ──────────────────────────────────────────────────────────────────

    async function init() {
        // Register service worker
        if ("serviceWorker" in navigator) {
            try {
                await navigator.serviceWorker.register("service-worker.js");
            } catch(e) {
                console.log("SW registration failed:", e);
            }
        }

        // Check URL for patient param (QR scan)
        const urlParams = new URLSearchParams(window.location.search);
        const patientId = urlParams.get("patient");

        if (patientId) {
            // QR scan auto-load — show patient status directly
            const patient = await getPatientById(patientId);
            if (patient) {
                const tests = await getTestsForPatient(patient.patientId);
                currentRole = "Patient";
                showScreen("app-shell");
                document.getElementById("bottom-nav").style.display = "none";
                document.getElementById("header-text").textContent = "🔍 Patient Status";
                const main = document.getElementById("main-content");
                main.innerHTML = `<div class="page-content"><div id="qr-patient-result"></div></div>`;
                renderPatientStatus(document.getElementById("qr-patient-result"), patient, tests);
                // Auto-refresh
                refreshInterval = setInterval(async () => {
                    const updatedTests = await getTestsForPatient(patient.patientId);
                    const resDiv = document.getElementById("qr-patient-result");
                    if (resDiv) renderPatientStatus(resDiv, patient, updatedTests);
                }, 5000);
                return;
            }
        }

        // Check for saved login
        const savedRole = localStorage.getItem("cardioqueue_role");
        const savedExpires = localStorage.getItem("cardioqueue_role_expires");

        if (savedRole && savedExpires && Date.now() < parseInt(savedExpires)) {
            if (savedRole === "Patient") {
                currentRole = "Patient";
                showScreen("app-shell");
                document.getElementById("bottom-nav").style.display = "none";
                document.getElementById("header-text").textContent = "🔍 Patient Status";
                renderPatientLookup();
                return;
            } else {
                currentRole = savedRole;
                showScreen("app-shell");
                document.getElementById("bottom-nav").style.display = "flex";
                document.getElementById("header-text").textContent = `📋 ${savedRole}`;
                showView("dashboard");
                return;
            }
        }

        // Show login
        showScreen("login-screen");
        initLogin();
        initNavigation();
        initPWAInstall();
    }

    // Start app when DOM is ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }

})();
