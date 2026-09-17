#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# GIL CLINIC — PERMANENT FREE deploy (Oracle Cloud Always Free / any Ubuntu VM)
#
# Ek command, aur app hamesha ke liye chalu:
#     sudo bash deploy/permanent/bootstrap.sh --domain gilclinic.duckdns.org
#
# Ye script (idempotent — jitni baar chalao, kuch todega nahi):
#   1. System packages + Python venv (Docker ki zaroorat nahi)
#   2. App clone/update  → /opt/gilclinic     (git pull)
#   3. Data **permanent disk** par → /opt/gilclinic/data  (SQLite + backups)
#   4. .env secure secrets ke saath (kabhi overwrite nahi hota)
#   5. systemd service  → crash par auto-restart + boot par auto-start
#   6. **Auto-heal watchdog** → app HANG ho jaye (crash na ho) to bhi restart
#      (systemd ka Restart=always sirf crash par chalta hai — ye uska ilaaj hai)
#   7. **Caddy** → free permanent HTTPS (Let's Encrypt) + domain
#      (DuckDNS free subdomain ya sslip.io — bina paisa, bina card)
#   8. **Off-site backup** → roz 2 baar data ko private GitHub repo me (₹0, permanent)
#   9. `gilclinic-update` command → naya code deploy karne ke liye ek command
#  10. End me health check + saaf Hinglish summary
#
# Options:
#   --domain <host>     public HTTPS domain (DuckDNS/sslip.io/apna domain)
#   --port <n>          internal port (default 8000)
#   --repo <url>        git repo (default niche REPO_URL)
#   --no-caddy          sirf IP:PORT par chalao (HTTPS nahi)
#   --backup-repo <url> private GitHub repo for off-site backups (optional)
#
# Oracle VM par SRF ye 2 cheezein console se karni hoti hain (script unhe yaad dilata hai):
#   * Security List / NSG me port 80 + 443 (ya 8000) open
#   * Public IP ko **Reserved** karein (free) — warna VM restart par IP badal sakta hai
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

APP_DIR=/opt/gilclinic
DATA_DIR=${APP_DIR}/data
BACKUP_DIR=${DATA_DIR}/backups
SERVICE=gilclinic
PORT=8000
DOMAIN=""
USE_CADDY=1
REPO_URL="https://github.com/gurjeetsinghgill8-web/gil-clinic.git"
BACKUP_REPO=""
SCRIPT_VERSION="2026-09-17"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --port) PORT="${2:-8000}"; shift 2 ;;
    --repo) REPO_URL="${2:-}"; shift 2 ;;
    --backup-repo) BACKUP_REPO="${2:-}"; shift 2 ;;
    --no-caddy) USE_CADDY=0; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

log()  { echo -e "\n==> $*"; }
warn() { echo -e "   [WARN] $*"; }
ok()   { echo -e "   [OK] $*"; }

if [ "$(id -u)" -ne 0 ]; then
  echo "Root/sudo se chalayein:  sudo bash deploy/permanent/bootstrap.sh --domain <domain>"
  exit 1
fi

# ── 1. packages ───────────────────────────────────────────────────────────────
log "[1/10] System packages…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -qq
apt-get install -y -qq python3 python3-pip python3-venv git curl ca-certificates cron \
  debian-keyring debian-archive-keyring apt-transport-https >/dev/null

# ── 2. app code ───────────────────────────────────────────────────────────────
log "[2/10] App code → ${APP_DIR}"
if [ -d "${APP_DIR}/.git" ]; then
  git -C "${APP_DIR}" fetch --depth=1 origin main >/dev/null 2>&1 || true
  git -C "${APP_DIR}" reset --hard origin/main >/dev/null 2>&1 || git -C "${APP_DIR}" pull --ff-only || true
  ok "code update ho gaya"
else
  git clone --depth=1 "${REPO_URL}" "${APP_DIR}"
  ok "code clone ho gaya"
fi
mkdir -p "${DATA_DIR}" "${BACKUP_DIR}" "${DATA_DIR}/logs"

# ── 3. .env (kabhi overwrite nahi) ────────────────────────────────────────────
log "[3/10] Environment file"
if [ -f "${APP_DIR}/.env" ]; then
  ok ".env pehle se hai — chheda nahi (secrets safe)"
else
  SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/')
  AI_SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '\n=+/')
  ADMIN_PASS="Gil$(head -c 6 /dev/urandom | base64 | tr -d '\n=+/')"
  cat > "${APP_DIR}/.env" <<EOF
# ── GIL CLINIC (permanent VM) — ${SCRIPT_VERSION} ─────────────────────────────
# Data PERMANENT disk par (VM reboot/deploy par kabhi nahi udta)
GHOS_DB_URL=sqlite:///${DATA_DIR}/ghos_prod.db
GHOS_DB_URL_ASYNC=sqlite+aiosqlite:///${DATA_DIR}/ghos_prod.db
SECRET_KEY=${SECRET}
GHOS_AI_KEYS_SECRET=${AI_SECRET}
SUPER_ADMIN_PASSWORD=${ADMIN_PASS}
CEO_PASSWORD=${ADMIN_PASS}
SYSTEM_AI_FALLBACK_ENABLED=false
# Patient links ka public address — bootstrap isko domain/IP se set karta hai
APP_BASE_URL=
EOF
  ok ".env bana diya (admin password: ${ADMIN_PASS})"
fi

# ── 4. python venv + deps ─────────────────────────────────────────────────────
log "[4/10] Python venv + dependencies (2-4 minute lag sakte hain)…"
if [ ! -x "${APP_DIR}/venv/bin/python" ]; then
  python3 -m venv "${APP_DIR}/venv"
fi
"${APP_DIR}/venv/bin/pip" install -q --upgrade pip
"${APP_DIR}/venv/bin/pip" install -q -r "${APP_DIR}/requirements.txt"
ok "dependencies ready"

# ── 5. systemd service ────────────────────────────────────────────────────────
log "[5/10] systemd service (boot par auto-start + crash par restart)…"
cat > "/etc/systemd/system/${SERVICE}.service" <<EOF
[Unit]
Description=GIL CLINIC — Smart OPD + Patient Portal (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
# Har boot se pehle data ka safety copy (kuch bhi galat ho to wapas ja sakte hain)
ExecStartPre=/bin/sh -c 'mkdir -p ${BACKUP_DIR} && cp ${DATA_DIR}/ghos_prod.db ${BACKUP_DIR}/pre-boot-\$(date +%%Y%%m%%d-%%H%%M%%S).db 2>/dev/null || true'
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn main_v2:app --host 0.0.0.0 --port ${PORT} --workers 1 --timeout-keep-alive 30
Restart=always
RestartSec=5
# Crash-loop se bachne ke liye: 5 min me 10 baar se zyada restart par ruk jao
StartLimitIntervalSec=300
StartLimitBurst=10
# Thoda saaf environment (memory leaks se bachne ke liye)
TimeoutStopSec=20
KillSignal=SIGINT

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "${SERVICE}" >/dev/null 2>&1 || true
systemctl restart "${SERVICE}"
ok "service chalu"

# ── 6. AUTO-HEAL watchdog (crash nahi, HANG ka ilaaj) ─────────────────────────
log "[6/10] Auto-heal watchdog (app hang ho to bhi apne aap theek)…"
cat > /usr/local/bin/${SERVICE}-watchdog <<EOF
#!/usr/bin/env bash
# /health 3 baar fail → service restart (aur log likho)
URL="http://127.0.0.1:${PORT}/health"
for i in 1 2 3; do
  if curl -fsS --max-time 8 "\$URL" >/dev/null 2>&1; then
    exit 0
  fi
  sleep 5
done
echo "\$(date -Is) [watchdog] /health fail — ${SERVICE} restart kar raha hoon" >> ${DATA_DIR}/logs/watchdog.log
systemctl restart ${SERVICE}
EOF
chmod +x /usr/local/bin/${SERVICE}-watchdog

cat > "/etc/systemd/system/${SERVICE}-watchdog.service" <<EOF
[Unit]
Description=GIL CLINIC health watchdog
[Service]
Type=oneshot
ExecStart=/usr/local/bin/${SERVICE}-watchdog
EOF

cat > "/etc/systemd/system/${SERVICE}-watchdog.timer" <<EOF
[Unit]
Description=GIL CLINIC health watchdog (har 2 minute)
[Timer]
OnBootSec=3min
OnUnitActiveSec=2min
Unit=${SERVICE}-watchdog.service
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now "${SERVICE}-watchdog.timer" >/dev/null 2>&1
ok "watchdog har 2 minute /health check karta hai"

# ── 7. Caddy — free permanent HTTPS ───────────────────────────────────────────
if [ "${USE_CADDY}" = "1" ] && [ -n "${DOMAIN}" ]; then
  log "[7/10] Caddy (free HTTPS) → ${DOMAIN}"
  if ! command -v caddy >/dev/null 2>&1; then
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
      | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
      > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -y -qq && apt-get install -y -qq caddy >/dev/null
  fi
  cat > /etc/caddy/Caddyfile <<EOF
# GIL CLINIC — auto HTTPS (Let's Encrypt). Port 80 + 443 khule hone chahiye.
${DOMAIN} {
    encode gzip
    reverse_proxy 127.0.0.1:${PORT}
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        -Server
    }
    log {
        output file ${DATA_DIR}/logs/caddy.log
        format console
    }
}
EOF
  systemctl enable caddy >/dev/null 2>&1 || true
  systemctl restart caddy
  PUBLIC_URL="https://${DOMAIN}"
  ok "HTTPS ready (certificate pehli request par ban jata hai)"
else
  log "[7/10] Caddy skip (--no-caddy ya --domain nahi diya)"
  IP_ADDR=$(curl -s --max-time 8 ifconfig.me 2>/dev/null || echo "")
  PUBLIC_URL="http://${IP_ADDR:-<VM-IP>}:${PORT}"
fi

# ── 8. off-site backup (optional, ₹0) ─────────────────────────────────────────
log "[8/10] Backup (local + off-site)"
cat > /usr/local/bin/${SERVICE}-backup <<EOF
#!/usr/bin/env bash
# SQLite ko safely copy karo (WAL ke saath) + purane backups saaf karo
set -e
STAMP=\$(date +%Y%m%d-%H%M)
DB="${DATA_DIR}/ghos_prod.db"
OUT="${BACKUP_DIR}/daily-\${STAMP}.db"
if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "\$DB" ".backup '\$OUT'"
else
  cp "\$DB" "\$OUT"
fi
gzip -f "\$OUT" || true
find "${BACKUP_DIR}" -name '*.db*' -mtime +30 -delete 2>/dev/null || true
EOF
chmod +x /usr/local/bin/${SERVICE}-backup
apt-get install -y -qq sqlite3 >/dev/null 2>&1 || true

if [ -n "${BACKUP_REPO}" ]; then
  cat >> /usr/local/bin/${SERVICE}-backup <<EOF

# ── Off-site: private GitHub repo (₹0, permanent) ─────────────────────────────
cd "${DATA_DIR}/offsite" 2>/dev/null || exit 0
EOF
  mkdir -p "${DATA_DIR}/offsite"
  if [ ! -d "${DATA_DIR}/offsite/.git" ]; then
    git clone "${BACKUP_REPO}" "${DATA_DIR}/offsite" 2>/dev/null || {
      git init "${DATA_DIR}/offsite"
      git -C "${DATA_DIR}/offsite" remote add origin "${BACKUP_REPO}"
    }
  fi
  cat >> /usr/local/bin/${SERVICE}-backup <<EOF
cp "${BACKUP_DIR}/daily-\${STAMP}.db.gz" "${DATA_DIR}/offsite/" 2>/dev/null || true
ls -1t "${DATA_DIR}/offsite"/*.db.gz 2>/dev/null | tail -n +31 | xargs -r rm -f
git -C "${DATA_DIR}/offsite" add -A >/dev/null 2>&1 || true
git -C "${DATA_DIR}/offsite" -c user.email=backup@gilclinic -c user.name=backup \
  commit -m "backup \${STAMP}" >/dev/null 2>&1 || true
git -C "${DATA_DIR}/offsite" push -q origin HEAD 2>/dev/null || true
EOF
  ok "off-site backup: ${BACKUP_REPO}"
else
  warn "off-site backup skip (--backup-repo <private-repo-url> se chalu kar sakte hain)"
fi

cat > /etc/cron.d/${SERVICE}-backup <<EOF
# Roz 2 baar backup (13:00 + 21:00) + 30 din se purane backup delete
0 13,21 * * * root /usr/local/bin/${SERVICE}-backup >/dev/null 2>&1
15 3 * * * root find ${BACKUP_DIR} -name '*.db*' -mtime +30 -delete 2>/dev/null || true
# Heartbeat — Oracle "idle VM" na samjhe (roz chhota write)
30 9 * * * root date -Is > ${DATA_DIR}/heartbeat.txt
EOF
chmod 644 /etc/cron.d/${SERVICE}-backup
systemctl enable cron >/dev/null 2>&1 || true
ok "backup cron set"

# ── 9. one-command update ─────────────────────────────────────────────────────
log "[9/10] Update command (naya code deploy karne ke liye)"
cat > /usr/local/bin/${SERVICE}-update <<EOF
#!/usr/bin/env bash
# Naya code GitHub se laao, dependencies update karo, app restart karo.
set -e
echo "==> code update"
git -C ${APP_DIR} fetch --depth=1 origin main
git -C ${APP_DIR} reset --hard origin/main
echo "==> dependencies"
${APP_DIR}/venv/bin/pip install -q -r ${APP_DIR}/requirements.txt
echo "==> restart"
systemctl restart ${SERVICE}
sleep 5
curl -fsS http://127.0.0.1:${PORT}/health && echo "  [OK] app healthy" || echo "  [WARN] health fail — journalctl -u ${SERVICE} -n 50"
EOF
chmod +x /usr/local/bin/${SERVICE}-update
ok "command: ${SERVICE}-update"

# ── 10. APP_BASE_URL + final health check ─────────────────────────────────────
log "[10/10] APP_BASE_URL + health check"
if [ -n "${PUBLIC_URL}" ]; then
  if grep -q '^APP_BASE_URL=' "${APP_DIR}/.env"; then
    sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=${PUBLIC_URL}|" "${APP_DIR}/.env"
  else
    echo "APP_BASE_URL=${PUBLIC_URL}" >> "${APP_DIR}/.env"
  fi
  systemctl restart "${SERVICE}"
  ok "APP_BASE_URL = ${PUBLIC_URL}"
fi

sleep 6
HEALTH="FAIL"
for i in 1 2 3 4 5 6; do
  if curl -fsS --max-time 8 "http://127.0.0.1:${PORT}/health" 2>/dev/null | grep -q '"ok"'; then
    HEALTH="PASS"; break
  fi
  sleep 5
done

echo ""
echo "════════════════════════════════════════════════════════════════"
if [ "${HEALTH}" = "PASS" ]; then
  echo " ✅ APP CHALU HAI — ${PUBLIC_URL}"
else
  echo " ⚠️  HEALTH FAIL — ye chalayein: journalctl -u ${SERVICE} -n 80 --no-pager"
fi
echo "════════════════════════════════════════════════════════════════"
echo "   Doctor login : ${PUBLIC_URL}/opd/login   (PIN: 5554 chief / 1234 junior)"
echo "   Admin        : ${PUBLIC_URL}/clinic-portal"
echo "   Health       : ${PUBLIC_URL}/health"
echo ""
echo "   Logs         : journalctl -u ${SERVICE} -f"
echo "   Restart      : systemctl restart ${SERVICE}"
echo "   Update app   : sudo ${SERVICE}-update"
echo "   Data + backup: ${DATA_DIR}  (backups: ${BACKUP_DIR})"
echo ""
echo "   ⚠️  Oracle console me ye 2 kaam (ek baar):"
echo "       1) Security List / NSG me port 80 + 443 open karein"
echo "       2) Public IP ko RESERVED karein (free) — warna restart par IP badal jayega"
echo "   ⚠️  Domain free rakhein: DuckDNS (gilclinic.duckdns.org) ya sslip.io"
echo "       aur VM par DuckDNS updater cron daal dein (deploy/permanent/README.md)"
echo "════════════════════════════════════════════════════════════════"
