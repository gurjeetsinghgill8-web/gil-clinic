/**
 * CardioQueue Patient PWA — Main Application
 * ============================================
 * Mobile-first patient status tracker with auto-refresh and notifications.
 */

// ─── Configuration ────────────────────────────────────────────
const CONFIG = {
    BASE_URL: window.location.origin,
    REFRESH_INTERVAL: 5000,  // 5 seconds
    POLL_INTERVAL: 30000,    // 30 seconds (background)
};

// ─── State ────────────────────────────────────────────────────
let state = {
    mobile: "",
    patientData: null,
    statusHash: "",
    refreshInterval: null,
};

// ─── DOM References ───────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const splashScreen = $("splash-screen");
const appContainer = $("app");
const mobileScreen = $("mobile-input-screen");
const statusScreen = $("status-screen");
const mobileInput = $("mobile-input");
const searchBtn = $("search-btn");
const errorMsg = $("error-msg");
const patientName = $("patient-name");
const patientId = $("patient-id");
const statusBadge = $("status-badge");
const patientInfo = $("patient-info");
const testsContainer = $("tests-container");
const backBtn = $("back-btn");
const installBanner = $("install-banner");

// ─── PWA Install Handler ──────────────────────────────────────
let deferredPrompt = null;
window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    installBanner.style.display = "block";
});

installBanner.addEventListener("click", async () => {
    if (deferredPrompt) {
        deferredPrompt.prompt();
        const result = await deferredPrompt.userChoice;
        if (result.outcome === "accepted") {
            installBanner.style.display = "none";
        }
        deferredPrompt = null;
    }
});

// ─── Service Worker Registration ──────────────────────────────
if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js")
        .then(() => console.log("[PWA] Service Worker registered"))
        .catch((err) => console.log("[PWA] SW registration failed:", err));
}

// ─── Notification Permission ──────────────────────────────────
function requestNotificationPermission() {
    if ("Notification" in window && Notification.permission === "default") {
        Notification.requestPermission();
    }
}

// ─── Audio Alert (Web Audio API — no file needed) ─────────────
function playAlert() {
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
}

// ─── Show Notification ────────────────────────────────────────
function showNotification(title, body) {
    playAlert();
    if ("vibrate" in navigator) {
        navigator.vibrate([200, 100, 200]);
    }
    if ("Notification" in window && Notification.permission === "granted") {
        new Notification(title, {
            body: body,
            icon: "https://img.icons8.com/color/48/hospital.png",
            badge: "https://img.icons8.com/color/48/hospital.png",
            tag: "cq-" + Date.now(),
            requireInteraction: true,
            vibrate: [200, 100, 200],
        });
    }
}

// ─── API Call ──────────────────────────────────────────────────
async function fetchPatientStatus(mobile) {
    try {
        const url = `${CONFIG.BASE_URL}/?mobile=${mobile}&api=1`;
        const response = await fetch(url, {
            headers: { "Cache-Control": "no-cache" },
        });
        if (!response.ok) return null;
        // Try to parse as JSON
        const text = await response.text();
        try {
            return JSON.parse(text);
        } catch(e) {
            // Response is HTML — extract data from DOM
            return null;
        }
    } catch(e) {
        console.error("Fetch error:", e);
        return null;
    }
}

// Since Streamlit returns HTML, we use a different approach:
// The status page embeds data in a JSON script tag or we redirect
// to the main app with patient param.
// For now, we redirect to the main Streamlit app with mobile param.

function redirectToStatus(mobile) {
    window.location.href = `${CONFIG.BASE_URL}/?mobile=${mobile}`;
}

// ─── Render Patient Status ────────────────────────────────────
function renderStatus(data) {
    if (!data || !data.found) {
        errorMsg.textContent = "❌ Patient not found. Please check your mobile number.";
        errorMsg.style.display = "block";
        return;
    }

    const patient = data.patient;
    const tests = data.tests || [];

    // Patient info
    patientName.textContent = patient.name || "Unknown";
    patientId.textContent = patient.patient_id || "";

    // Primary status
    const primaryStatus = tests.length > 0 ? tests[0].status : "waiting";
    const statusLabels = {
        waiting: "⏳ Waiting",
        called: "🔵 Called",
        in_progress: "🟠 In Progress",
        completed: "✅ Completed",
        report_ready: "📋 Report Ready",
        delivered: "📄 Delivered",
    };
    statusBadge.textContent = statusLabels[primaryStatus] || primaryStatus;

    // Build hash for change detection
    const newHash = tests.map(t => `${t.test_name}:${t.status}`).join("|");
    if (state.statusHash && state.statusHash !== newHash) {
        showNotification("🔄 Status Updated", `Your status has changed to: ${statusLabels[primaryStatus] || primaryStatus}`);
    }
    state.statusHash = newHash;

    // Update SW with latest hash
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.ready.then(reg => {
            if (reg.active) {
                reg.active.postMessage({
                    type: "UPDATE_STATUS_HASH",
                    statusHash: newHash,
                });
            }
        });
    }

    // Tests
    testsContainer.innerHTML = "";
    const statusOrder = ["waiting", "called", "in_progress", "completed", "report_ready", "delivered"];
    const statusColors = {
        waiting: "#FF9800",
        called: "#2196F3",
        in_progress: "#FF5722",
        completed: "#4CAF50",
        report_ready: "#9C27B0",
        delivered: "#607D8B",
    };

    tests.forEach(test => {
        const testName = test.test_name;
        const status = test.status;
        const token = test.token_number || 0;
        const waitTime = test.wait_time || 0;
        const color = statusColors[status] || "#667eea";
        const label = statusLabels[status] || status;

        const idx = statusOrder.indexOf(status);
        const progress = idx >= 0 ? ((idx + 1) / statusOrder.length * 100) : 0;

        const card = document.createElement("div");
        card.className = "test-card";
        card.style.borderLeftColor = color;
        card.innerHTML = `
            <div class="test-header">
                <span class="test-name">${testName}</span>
                <span class="test-status" style="color:${color};">${label}</span>
            </div>
            <div class="test-meta">🎫 Token #${token} | ⏱️ ~${waitTime} min</div>
            <div class="progress-bar">
                <div class="progress-fill" style="width:${progress}%;"></div>
            </div>
        `;
        testsContainer.appendChild(card);
    });

    // Switch to status screen
    mobileScreen.style.display = "none";
    statusScreen.classList.add("visible");

    // Start auto-refresh
    if (state.refreshInterval) clearInterval(state.refreshInterval);
    state.refreshInterval = setInterval(() => {
        fetchPatientStatus(state.mobile).then(renderStatus);
    }, CONFIG.REFRESH_INTERVAL);

    // Register with SW for background tracking
    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.ready.then(reg => {
            if (reg.active) {
                reg.active.postMessage({
                    type: "TRACK_PATIENT",
                    mobile: state.mobile,
                    statusHash: newHash,
                });
            }
        });
    }
}

// ─── Search Handler ───────────────────────────────────────────
function handleSearch() {
    const mobile = mobileInput.value.trim();
    if (!mobile || mobile.length !== 10 || !/^\d{10}$/.test(mobile)) {
        errorMsg.textContent = "⚠️ Please enter a valid 10-digit mobile number";
        errorMsg.style.display = "block";
        return;
    }
    errorMsg.style.display = "none";
    state.mobile = mobile;
    redirectToStatus(mobile);
}

searchBtn.addEventListener("click", handleSearch);
mobileInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") handleSearch();
});

// Auto-numeric keyboard on mobile
mobileInput.addEventListener("input", () => {
    mobileInput.value = mobileInput.value.replace(/\D/g, "");
    if (mobileInput.value.length === 10) {
        handleSearch();
    }
});

// ─── Back Button ──────────────────────────────────────────────
backBtn.addEventListener("click", () => {
    if (state.refreshInterval) clearInterval(state.refreshInterval);
    state.refreshInterval = null;
    statusScreen.classList.remove("visible");
    mobileScreen.style.display = "block";
    mobileInput.value = "";
    mobileInput.focus();

    if ("serviceWorker" in navigator) {
        navigator.serviceWorker.ready.then(reg => {
            if (reg.active) {
                reg.active.postMessage({ type: "UNTRACK_PATIENT" });
            }
        });
    }
});

// ─── Auto-detect from URL param ───────────────────────────────
function initFromURL() {
    const params = new URLSearchParams(window.location.search);
    const mobile = params.get("mobile");
    const source = params.get("source");

    if (source === "pwa") {
        // Opened from PWA — show the app directly
        splashScreen.classList.add("hidden");
        appContainer.classList.add("visible");
        requestNotificationPermission();
        mobileInput.focus();
        return;
    }

    if (mobile && mobile.length === 10) {
        state.mobile = mobile;
        // Fetch data and show status
        fetchPatientStatus(mobile).then(data => {
            splashScreen.classList.add("hidden");
            appContainer.classList.add("visible");
            requestNotificationPermission();
            if (data && data.found) {
                renderStatus(data);
            } else {
                errorMsg.textContent = "❌ Patient not found with this number.";
                errorMsg.style.display = "block";
                mobileInput.focus();
            }
        });
        return;
    }

    // Normal start
    setTimeout(() => {
        splashScreen.classList.add("hidden");
        appContainer.classList.add("visible");
        requestNotificationPermission();
        mobileInput.focus();
    }, 1500);
}

// ─── Start App ────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", initFromURL);
