#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VPS_HOST="${VPS_HOST:-root@157.66.219.248}"
VPS_IP="${VPS_HOST#*@}"
DOMAIN="${DOMAIN:-${VPS_IP}}"
PUBLIC_PORT="${PUBLIC_PORT:-80}"
APP_DIR="${APP_DIR:-/opt/ubnd-ai}"
DATA_DIR="${DATA_DIR:-/var/lib/ubnd-ai}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/ubnd-ai}"
DRY_RUN=0

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN=1
      ;;
    *)
      echo "[deploy-vps] Tham số không hợp lệ: ${arg}" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${DOMAIN}" ]] || [[ ! "${DOMAIN}" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "[deploy-vps] DOMAIN không hợp lệ: '${DOMAIN}'" >&2
  exit 2
fi

if [[ ! "${PUBLIC_PORT}" =~ ^[0-9]+$ ]]; then
  echo "[deploy-vps] PUBLIC_PORT không hợp lệ: '${PUBLIC_PORT}'" >&2
  exit 2
fi

RSYNC_EXCLUDES=(
  "--exclude=.git"
  "--exclude=.venv"
  "--exclude=app/node_modules"
  "--exclude=backend/data"
  "--exclude=.superpowers"
  "--exclude=.codegraph"
  "--exclude=.ua"
  "--exclude=__pycache__"
  "--exclude=*.pyc"
)

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "=== [DRY-RUN] KẾ HOẠCH DEPLOY BỘ TRỢ LÝ AI UBND XÃ, PHƯỜNG ==="
  echo "Target VPS   : ${VPS_HOST}"
  echo "Server Name  : ${DOMAIN} (port ${PUBLIC_PORT})"
  echo "Code Dir     : ${APP_DIR}"
  echo "Database Dir : ${DATA_DIR} (tách rời cây code, bảo toàn ubnd_ai.db & tenants/*.db)"
  echo "Backup Dir   : ${BACKUP_DIR}"
  echo "Rsync Command: rsync -az --delete ${RSYNC_EXCLUDES[*]} ${REPO_ROOT}/ ${VPS_HOST}:${APP_DIR}/"
  echo "Services     : ubnd-ai-backend.service (--workers 1 :8000), ubnd-ai-frontend.service (:3000), nginx (:${PUBLIC_PORT})"
  exit 0
fi

echo "=== [1/5] Kiểm tra SSH Key tới ${VPS_HOST} ==="
if ! ssh -o BatchMode=yes -o ConnectTimeout=6 "${VPS_HOST}" "true" 2>/dev/null; then
  if [[ ! -f "${HOME}/.ssh/id_ed25519.pub" ]]; then
    echo "-> Chưa có SSH key cục bộ, đang khởi tạo ~/.ssh/id_ed25519..."
    mkdir -p "${HOME}/.ssh"
    chmod 700 "${HOME}/.ssh"
    ssh-keygen -t ed25519 -N "" -f "${HOME}/.ssh/id_ed25519"
  fi
  echo "-> Vui lòng nhập mật khẩu của ${VPS_HOST} 1 lần để gắn SSH key tự động:"
  ssh-copy-id -i "${HOME}/.ssh/id_ed25519.pub" "${VPS_HOST}"
fi

echo "=== [2/5] Build bản Production SSR + Client ngay trên máy cục bộ ==="
(cd "${REPO_ROOT}/app" && npm run build)

echo "=== [3/5] Đồng bộ mã nguồn & bản build lên ${VPS_HOST}:${APP_DIR} ==="
ssh "${VPS_HOST}" "mkdir -p '${APP_DIR}' '${DATA_DIR}/tenants' '${BACKUP_DIR}'"
rsync -avz --delete "${RSYNC_EXCLUDES[@]}" "${REPO_ROOT}/" "${VPS_HOST}:${APP_DIR}/"

echo "=== [4/5] Cài đặt môi trường, systemd services & Nginx trên VPS ==="
ssh "${VPS_HOST}" "APP_DIR='${APP_DIR}' DATA_DIR='${DATA_DIR}' BACKUP_DIR='${BACKUP_DIR}' DOMAIN='${DOMAIN}' PUBLIC_PORT='${PUBLIC_PORT}' bash -s" <<'REMOTE_EOF'
set -euo pipefail

# 1. Install OS packages (Ubuntu/Debian apt or RHEL/Fedora dnf)
if command -v apt-get >/dev/null 2>&1; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y python3 python3-venv python3-pip nginx curl ca-certificates gnupg
  if ! command -v node >/dev/null 2>&1 || [[ "$(node -v | cut -d. -f1 | tr -d 'v')" -lt 20 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
    apt-get install -y nodejs
  fi
elif command -v dnf >/dev/null 2>&1; then
  dnf install -y python3 python3-pip nginx curl ca-certificates nodejs npm
fi

mkdir -p "${DATA_DIR}/tenants" "${BACKUP_DIR}"

# 2. Setup Python virtualenv & Backend dependencies
cd "${APP_DIR}"
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

# 3. Install Frontend production runtime dependencies
cd "${APP_DIR}/app"
npm ci --omit=dev

# 4. Write environment defaults (preserving existing file if already customized)
if [[ ! -f /etc/default/ubnd-ai ]]; then
  cat > /etc/default/ubnd-ai <<ENV_EOF
UBND_ENV=production
UBND_DB_PATH=${DATA_DIR}/ubnd_ai.db
UBND_ALLOWED_ORIGINS=http://${DOMAIN},http://${DOMAIN}:${PUBLIC_PORT},https://${DOMAIN}
ENV_EOF
  chmod 600 /etc/default/ubnd-ai
fi

# 5. Install and restart systemd units
cp "${APP_DIR}/deploy/systemd/ubnd-ai-backend.service" /etc/systemd/system/ubnd-ai-backend.service
cp "${APP_DIR}/deploy/systemd/ubnd-ai-frontend.service" /etc/systemd/system/ubnd-ai-frontend.service
systemctl daemon-reload
systemctl enable ubnd-ai-backend.service ubnd-ai-frontend.service
systemctl restart ubnd-ai-backend.service
systemctl restart ubnd-ai-frontend.service

# 6. Render and enable Nginx configuration safely
NGINX_RENDERED="/tmp/ubnd-ai.nginx.conf"
sed \
  -e "s/__PUBLIC_PORT__/${PUBLIC_PORT}/g" \
  -e "s/__SERVER_NAME__/${DOMAIN}/g" \
  "${APP_DIR}/deploy/nginx/ubnd-ai.conf" > "${NGINX_RENDERED}"

if [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]]; then
  cp "${NGINX_RENDERED}" /etc/nginx/sites-available/ubnd-ai.conf
  ln -sf /etc/nginx/sites-available/ubnd-ai.conf /etc/nginx/sites-enabled/ubnd-ai.conf
  if [[ "${PUBLIC_PORT}" == "80" && "${DOMAIN}" =~ ^[0-9.]+$ && -L /etc/nginx/sites-enabled/default ]]; then
    rm -f /etc/nginx/sites-enabled/default
  fi
else
  cp "${NGINX_RENDERED}" /etc/nginx/conf.d/ubnd-ai.conf
fi

nginx -t
systemctl enable nginx
systemctl restart nginx

# Open firewall port if ufw or firewalld is active
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow "${PUBLIC_PORT}/tcp" >/dev/null || true
elif command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
  firewall-cmd --permanent --add-port="${PUBLIC_PORT}/tcp" >/dev/null || true
  firewall-cmd --reload >/dev/null || true
fi

# 7. Install daily 02:00 UTC online SQLite backup cronjob
chmod +x "${APP_DIR}/deploy/scripts/backup-sqlite.sh"
cat > /etc/cron.d/ubnd-ai-backup <<CRON_EOF
0 2 * * * root UBND_DATA_DIR=${DATA_DIR} UBND_BACKUP_DIR=${BACKUP_DIR} ${APP_DIR}/deploy/scripts/backup-sqlite.sh >> /var/log/ubnd-ai-backup.log 2>&1
CRON_EOF
chmod 644 /etc/cron.d/ubnd-ai-backup
REMOTE_EOF

echo "=== [5/5] Kiểm tra sức khỏe dịch vụ (Smoke Check) trên VPS ==="
ssh "${VPS_HOST}" "PUBLIC_PORT='${PUBLIC_PORT}' DOMAIN='${DOMAIN}' bash -s" <<'SMOKE_EOF'
set -euo pipefail
for i in {1..15}; do
  if curl -fsS http://127.0.0.1:8000/api/health >/dev/null 2>&1 && curl -fsS http://127.0.0.1:3000/ >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo -n "-> Backend (:8000/api/health): "
curl -fsS http://127.0.0.1:8000/api/health
echo ""
echo -n "-> Nginx Proxy (:${PUBLIC_PORT}/api/health): "
curl -fsS -H "Host: ${DOMAIN}" "http://127.0.0.1:${PUBLIC_PORT}/api/health"
echo ""
SMOKE_EOF

if [[ "${PUBLIC_PORT}" == "80" ]]; then
  echo "🎉 DEPLOY THÀNH CÔNG! Truy cập ngay: http://${DOMAIN}"
else
  echo "🎉 DEPLOY THÀNH CÔNG! Truy cập ngay: http://${DOMAIN}:${PUBLIC_PORT}"
fi
