/* CardioQueue Staff Dashboard — Client-side JS
   Uses fetch() polling instead of WebSocket — works on ALL mobile networks */

// ── Clock ──────────────────────────────────────────────────────────────────
function updateClock() {
  const el = document.getElementById('live-clock');
  if (el) {
    const now = new Date();
    el.textContent = now.toLocaleTimeString('en-IN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true
    });
  }
}
setInterval(updateClock, 1000);
updateClock();

// ── Mobile Sidebar ─────────────────────────────────────────────────────────
const sidebar  = document.getElementById('sidebar');
const overlay  = document.getElementById('sidebar-overlay');
const menuBtn  = document.getElementById('menu-toggle');

function openSidebar() {
  sidebar && sidebar.classList.add('open');
  overlay && overlay.classList.add('active');
}
function closeSidebar() {
  sidebar && sidebar.classList.remove('open');
  overlay && overlay.classList.remove('active');
}
menuBtn  && menuBtn.addEventListener('click', openSidebar);
overlay  && overlay.addEventListener('click', closeSidebar);

// ── Auto-Refresh (polling every 10s — replaces WebSocket) ──────────────────
const REFRESH_INTERVAL = 10000; // 10 seconds
let refreshTimer = null;
let progressTimer = null;

function startProgressBar() {
  const bar = document.querySelector('.refresh-progress');
  if (!bar) return;
  bar.style.transition = 'none';
  bar.style.width = '0%';
  requestAnimationFrame(() => {
    bar.style.transition = `width ${REFRESH_INTERVAL}ms linear`;
    bar.style.width = '100%';
  });
}

function scheduleRefresh() {
  startProgressBar();
  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(() => {
    if (window.autoRefreshEnabled !== false) {
      window.location.reload();
    }
  }, REFRESH_INTERVAL);
}

if (document.querySelector('[data-auto-refresh]')) {
  scheduleRefresh();
}

// Manual refresh button
document.querySelectorAll('[data-refresh-btn]').forEach(btn => {
  btn.addEventListener('click', () => window.location.reload());
});

// ── Action Buttons — POST via fetch ────────────────────────────────────────
document.querySelectorAll('[data-action]').forEach(btn => {
  btn.addEventListener('click', async function(e) {
    e.preventDefault();
    const action  = this.dataset.action;
    const entryId = this.dataset.entryId;
    const notes   = this.dataset.notes || '';
    const dept    = this.dataset.dept || '';

    this.disabled = true;
    this.style.opacity = '0.6';

    try {
      const resp = await fetch('/api/v1/queue/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          entry_id: entryId,
          action: action,
          staff_name: window.STAFF_NAME || 'Staff',
          department: dept,
          notes: notes
        })
      });
      if (resp.ok) {
        window.location.reload();
      } else {
        const err = await resp.json();
        showToast('Error: ' + (err.detail || 'Action failed'), 'danger');
        this.disabled = false;
        this.style.opacity = '1';
      }
    } catch(err) {
      showToast('Network error. Check connection.', 'danger');
      this.disabled = false;
      this.style.opacity = '1';
    }
  });
});

// ── Reception: Create Queue ────────────────────────────────────────────────
const queueForm = document.getElementById('create-queue-form');
if (queueForm) {
  queueForm.addEventListener('submit', async function(e) {
    e.preventDefault();
    const btn = this.querySelector('[type=submit]');
    btn.disabled = true;
    btn.textContent = '⏳ Registering...';

    const data = {
      patient_id: document.getElementById('patient_id').value,
      services: Array.from(document.querySelectorAll('input[name=service]:checked')).map(c => c.value),
      created_by: window.STAFF_NAME || 'Reception'
    };

    if (!data.services.length) {
      showToast('Please select at least one test', 'warning');
      btn.disabled = false;
      btn.textContent = '➕ Register Patient';
      return;
    }

    try {
      const resp = await fetch('/api/v1/queue/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (resp.ok) {
        const result = await resp.json();
        showToast(`✅ Patient registered! Token: ${result.entries?.map(e=>e.token_number).join(', ')}`, 'success');
        this.reset();
        document.querySelectorAll('input[name=service]:checked').forEach(c => c.checked = false);
        setTimeout(() => window.location.reload(), 1500);
      } else {
        const err = await resp.json();
        showToast('Error: ' + (err.detail || 'Registration failed'), 'danger');
      }
    } catch(err) {
      showToast('Network error. Please retry.', 'danger');
    }
    btn.disabled = false;
    btn.textContent = '➕ Register Patient';
  });
}

// ── Toast Notification ────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const existing = document.getElementById('toast-notif');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'toast-notif';
  toast.style.cssText = `
    position: fixed; bottom: 24px; right: 24px; z-index: 9999;
    background: ${type === 'success' ? '#38a169' : type === 'danger' ? '#e53e3e' : '#d69e2e'};
    color: white; padding: 14px 20px; border-radius: 12px;
    font-weight: 600; font-size: 14px; max-width: 320px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    animation: slideIn 0.3s ease;
  `;
  toast.textContent = msg;

  const style = document.createElement('style');
  style.textContent = '@keyframes slideIn { from { transform: translateX(100px); opacity:0; } to { transform: translateX(0); opacity:1; } }';
  document.head.appendChild(style);

  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Under Construction popup ───────────────────────────────────────────────
function showUnderConstruction(name) {
  const ov = document.createElement('div');
  ov.className = 'uc-overlay';
  ov.innerHTML = `
    <div class="uc-card">
      <div class="uc-emoji">🚧</div>
      <div class="uc-title">Under Construction</div>
      <div class="uc-sub"><strong>${name}</strong> is being built.<br>It will be available soon!</div>
      <button class="btn btn-outline btn-full" onclick="this.closest('.uc-overlay').remove()">← Go Back</button>
    </div>
  `;
  document.body.appendChild(ov);
}

document.querySelectorAll('[data-uc]').forEach(el => {
  el.addEventListener('click', e => {
    e.preventDefault();
    showUnderConstruction(el.dataset.uc);
  });
});

// ── Staff Login ────────────────────────────────────────────────────────────
const staffBtns = document.querySelectorAll('.staff-btn');
staffBtns.forEach(btn => {
  btn.addEventListener('click', function() {
    staffBtns.forEach(b => b.classList.remove('selected'));
    this.classList.add('selected');
    document.getElementById('role-input').value = this.dataset.role;
    document.getElementById('name-input').value = this.dataset.name;
  });
});

// Pin input — auto-submit on 4 digits
const pinInput = document.getElementById('pin-input');
if (pinInput) {
  pinInput.addEventListener('input', function() {
    if (this.value.length >= 4) {
      this.form && this.form.submit();
    }
  });
}
