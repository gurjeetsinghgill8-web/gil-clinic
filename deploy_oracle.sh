#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# GIL CLINIC — Oracle Cloud Always Free (or Google e2-micro) deploy script
#
# Usage (VM par, root ya sudo user se):
#   bash deploy_oracle.sh
#
# Kya karta hai:
#   1. System packages (python3, pip, venv, git)
#   2. App ko /opt/gilclinic mein clone (ya /opt/gilclinic se update)
#   3. Data folder /opt/gilclinic/data (permanent disk — kabhi nahi udta)
#   4. Python venv + dependencies
#   5. systemd service — VM reboot par app apne aap start, crash par restart
#   6. Roz 2 baar auto-backup (cron) — data/backups ke andar
#   7. Public IP auto-set (APP_BASE_URL) + health check
#
# Env vars (Railway ki jagah ab ye):
#   GHOS_DB_URL=sqlite:////opt/gilclinic/data/ghos_prod.db
#   SECRET_KEY=<lamba random string>
#   GHOS_AI_KEYS_SECRET=<lamba random string>       (clinic keys ki encryption)
#   SUPER_ADMIN_PASSWORD=<apna>  CEO_PASSWORD=<apna>
#   APP_BASE_URL=http://<VM-PUBLIC-IP>:8000          (ya domain/tunnel URL)
#   SYSTEM_AI_FALLBACK_ENABLED=false                 (hamari keys kabhi use na ho)
# ═══════════════════════════════════════════════════════════════════════════
set -euo pipefail

APP_DIR=/opt/gilclinic
DATA_DIR=${APP_DIR}/data
REPO_URL="https://github.com/gurjeetsinghgill8-web/gil-clinic.git"   # ← apna repo URL
SERVICE_NAME=gilclinic

echo "==> [1/6] System packages (python3 + pip + git)..."
apt-get update -y
apt-get install -y python3 python3-pip python3-venv git curl

echo "==> [2/6] App folder + data volume..."
mkdir -p "${DATA_DIR}" "${DATA_DIR}/backups"
if [ -d "${APP_DIR}/.git" ]; then
  (cd "${APP_DIR}" && git pull || true)
else
  git clone "${REPO_URL}" "${APP_DIR}"
fi

echo "==> [3/6] Environment file..."
if [ ! -f "${APP_DIR}/.env" ]; then
  SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '\n')
  AI_SECRET=$(head -c 48 /dev/urandom | base64 | tr -d '\n')
  cat > "${APP_DIR}/.env" <<EOF
GHOS_DB_URL=sqlite:///${DATA_DIR}/ghos_prod.db
GHOS_DB_URL_ASYNC=sqlite+aiosqlite:///${DATA_DIR}/ghos_prod.db
SECRET_KEY=${SECRET}
GHOS_AI_KEYS_SECRET=${AI_SECRET}
SUPER_ADMIN_PASSWORD=ChangeMe123!
CEO_PASSWORD=ChangeMe123!
APP_BASE_URL=http://localhost:8000
SYSTEM_AI_FALLBACK_ENABLED=true
EOF
  echo "   .env bana diya — SUPER_ADMIN_PASSWORD/CEO_PASSWORD zaroor badlein!"
fi

echo "==> [4/6] Python venv + dependencies..."
python3 -m venv "${APP_DIR}/venv"
"${APP_DIR}/venv/bin/pip" install --upgrade pip
"${APP_DIR}/venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "==> [5/6] systemd service..."
cat > /etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=GIL CLINIC hospital system
After=network.target

[Service]
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStartPre=/bin/sh -c 'mkdir -p ${DATA_DIR} && cp ${DATA_DIR}/ghos_prod.db ${DATA_DIR}/backups/pre-boot-\$(date +%%Y%%m%%d-%%H%%M%%S).db 2>/dev/null || true'
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn main_v2:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ${SERVICE_NAME}

echo "==> [6/6] Roz 2 baar backup (cron)..."
cat > /etc/cron.d/gilclinic-backup <<EOF
# Roz 2 baar GIL CLINIC data backup
0 13 * * * root cp ${DATA_DIR}/ghos_prod.db ${DATA_DIR}/backups/daily-\$(date +\%Y\%m\%d-13h).db
0 21 * * * root cp ${DATA_DIR}/ghos_prod.db ${DATA_DIR}/backups/daily-\$(date +\%Y\%m\%d-21h).db
# Purane backups (30 din se zyada) hatao
5 3 * * * root find ${DATA_DIR}/backups -name '*.db' -mtime +30 -delete
EOF

echo "==> [7/7] Public IP auto-set + health check..."
PUB_IP=$(curl -s --max-time 10 ifconfig.me 2>/dev/null || true)
if [ -n "${PUB_IP}" ]; then
  if grep -q '^APP_BASE_URL=http://localhost:8000' "${APP_DIR}/.env" 2>/dev/null; then
    sed -i "s|^APP_BASE_URL=.*|APP_BASE_URL=http://${PUB_IP}:8000|" "${APP_DIR}/.env"
    systemctl restart ${SERVICE_NAME}
    echo "   APP_BASE_URL set: http://${PUB_IP}:8000"
  fi
fi
sleep 4
if curl -s --max-time 10 "http://localhost:8000/health" | grep -q '"ok"'; then
  echo "   [OK] App HEALTH CHECK PASS"
else
  echo "   [WARN] Health fail — dekhein: journalctl -u ${SERVICE_NAME} -n 50"
fi

echo ""
echo "════════════════════════════════════════════════════════════"
echo " ✅ DEPLOY HO GAYA!"
echo "   Website: http://${PUB_IP:-<VM-PUBLIC-IP>}:8000"
echo "   Status:  systemctl status ${SERVICE_NAME}"
echo "   Logs:    journalctl -u ${SERVICE_NAME} -f"
echo "   Data:    ${DATA_DIR}/ghos_prod.db  (backups: ${DATA_DIR}/backups/)"
echo ""
echo "   [1] Oracle console → Security List mein port 8000 open karein"
echo "   [2] ${APP_DIR}/.env mein SUPER_ADMIN_PASSWORD/CEO_PASSWORD badlein"
echo "       (sudo nano ${APP_DIR}/.env  →  sudo systemctl restart ${SERVICE_NAME})"
echo "   [3] Admin login ke credentials pehli boot par admin_credentials.txt"
echo "       mein bante hain — usse save kar lein"
echo "════════════════════════════════════════════════════════════"
