#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# DuckDNS free permanent domain updater (GIL CLINIC) — ₹0, hamesha ke liye
#
# DuckDNS ek free subdomain deta hai (jaise gilclinic.duckdns.org) jo aapke VM ke
# public IP par point karta hai. VM ka IP badle to ye script usko update kar deta hai.
#
# Setup (ek baar):
#   1. https://www.duckdns.org par Google/GitHub se login → ek naam chuno, e.g. gilclinic
#   2. Token copy karein (page par dikhta hai)
#   3. VM par:  sudo bash deploy/permanent/duckdns-update.sh --domain gilclinic --token <TOKEN> --install
#      (— ya —  sudo DUCKDNS_DOMAIN=gilclinic DUCKDNS_TOKEN=xxxx bash ... --install)
#
# Ye script:
#   * abhi turant IP update karta hai
#   * /etc/cron.d me har 5 minute ka cron daal deta hai (cron me token 600 permission ke saath)
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

DOMAIN="${DUCKDNS_DOMAIN:-}"
TOKEN="${DUCKDNS_TOKEN:-}"
INSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --token) TOKEN="${2:-}"; shift 2 ;;
    --install) INSTALL=1; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [ -z "${DOMAIN}" ] || [ -z "${TOKEN}" ]; then
  echo "Usage: sudo bash deploy/permanent/duckdns-update.sh --domain <name> --token <token> [--install]"
  echo "  (DuckDNS par free subdomain lein: https://www.duckdns.org)"
  exit 1
fi

update_now() {
  local out
  out=$(curl -fsS --max-time 15 "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=" 2>/dev/null || true)
  echo "DuckDNS response: ${out:-<koi jawab nahi>}"
  if [ "${out}" = "OK" ]; then
    echo "   [OK] https://${DOMAIN}.duckdns.org → $(curl -s --max-time 8 ifconfig.me || echo '<VM-IP>')"
  else
    echo "   [WARN] update fail — token/domain check karein"
  fi
}

if [ "${INSTALL}" = "1" ]; then
  if [ "$(id -u)" -ne 0 ]; then echo "sudo se chalayein (--install ke liye)"; exit 1; fi
  cat > /usr/local/bin/gilclinic-duckdns <<EOF
#!/usr/bin/env bash
# DuckDNS IP updater (GIL CLINIC) — har 5 minute cron se chalta hai
curl -fsS --max-time 15 "https://www.duckdns.org/update?domains=${DOMAIN}&token=${TOKEN}&ip=" >/dev/null 2>&1 || true
EOF
  chmod 700 /usr/local/bin/gilclinic-duckdns
  cat > /etc/cron.d/gilclinic-duckdns <<'EOF'
# DuckDNS: VM ka public IP badle to domain usko follow kare (har 5 min)
*/5 * * * * root /usr/local/bin/gilclinic-duckdns
EOF
  chmod 644 /etc/cron.d/gilclinic-duckdns
  systemctl enable cron >/dev/null 2>&1 || true
  echo "   [OK] cron install ho gaya (/usr/local/bin/gilclinic-duckdns)"
fi

update_now
echo ""
echo "Agla step: Caddy ko is domain par chalayein:"
echo "   sudo bash deploy/permanent/bootstrap.sh --domain ${DOMAIN}.duckdns.org"
