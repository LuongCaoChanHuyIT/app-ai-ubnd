#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VPS_HOST="${VPS_HOST:-root@157.66.219.248}"
VPS_IP="${VPS_HOST#*@}"
DOMAIN="${DOMAIN:-${VPS_IP}}"
# Default to isolated ports (8088 public when using IP, 18000 backend, 13000 frontend)
# so deploying alongside an existing project on the same VPS never collides with :80, :8000, or :3000!
if [[ "${DOMAIN}" =~ ^[0-9.]+$ ]]; then
  PUBLIC_PORT="${PUBLIC_PORT:-8088}"
else
  PUBLIC_PORT="${PUBLIC_PORT:-80}"
fi
BACKEND_PORT="${BACKEND_PORT:-18000}"
FRONTEND_PORT="${FRONTEND_PORT:-13000}"
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

for port_val in "${PUBLIC_PORT}" "${BACKEND_PORT}" "${FRONTEND_PORT}"; do
  if [[ ! "${port_val}" =~ ^[0-9]+$ ]]; then
    echo "[deploy-vps] Cổng không hợp lệ: '${port_val}'" >&2
    exit 2
  fi
done

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
  echo "=== [DRY-RUN] KẾ HOẠCH DEPLOY SONG SONG AN TOÀN (MULTI-PROJECT SAFE) ==="
  echo "Target VPS    : ${VPS_HOST}"
  echo "Server Name   : ${DOMAIN} (public port :${PUBLIC_PORT})"
  echo "Internal Ports: Backend 127.0.0.1:${BACKEND_PORT} | Frontend SSR 127.0.0.1:${FRONTEND_PORT}"
  echo "Code Dir      : ${APP_DIR} (độc lập hoàn toàn với source cũ)"
  echo "Database Dir  : ${DATA_DIR} (tách rời cây code, bảo toàn ubnd_ai.db & tenants/*.db)"
  echo "Backup Dir    : ${BACKUP_DIR}"
  echo "Rsync Command : rsync -az --delete ${RSYNC_EXCLUDES[*]} ${REPO_ROOT}/ ${VPS_HOST}:${APP_DIR}/"
  echo "Safety Guard  : Giữ nguyên 100% Nginx vhost & port của source cũ trên VPS"
  exit 0
fi

echo "=== [1/6] Kiểm tra SSH Key tới ${VPS_HOST} ==="
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

echo "=== [2/6] Kiểm tra tài nguyên & xung đột cổng với source đang chạy trên VPS ==="
ssh "${VPS_HOST}" "PUBLIC_PORT='${PUBLIC_PORT}' BACKEND_PORT='${BACKEND_PORT}' FRONTEND_PORT='${FRONTEND_PORT}' DOMAIN='${DOMAIN}' bash -s" <<'CHECK_EOF'
set -euo pipefail
echo "-> Tài nguyên hiện tại của VPS:"
free -h | head -n 2
df -h / | tail -n 1

check_internal_port() {
  local p="$1"
  local svc_name="$2"
  if ss -tlnp | grep -E ":${p}\b" >/dev/null 2>&1; then
    if ! systemctl is-active --quiet "${svc_name}" 2>/dev/null; then
      echo "[CẢNH BÁO AN TOÀN] Cổng nội bộ :${p} đang được dùng bởi tiến trình khác trên VPS:" >&2
      ss -tlnp | grep -E ":${p}\b" >&2
      echo "Hãy đổi cổng bằng biến BACKEND_PORT / FRONTEND_PORT trước khi chạy lại!" >&2
      exit 10
    fi
  fi
}

check_internal_port "${BACKEND_PORT}" "ubnd-ai-backend.service"
check_internal_port "${FRONTEND_PORT}" "ubnd-ai-frontend.service"

if [[ "${DOMAIN}" =~ ^[0-9.]+$ ]] && ss -tlnp | grep -E ":${PUBLIC_PORT}\b" | grep -v "nginx" >/dev/null 2>&1; then
  echo "[CẢNH BÁO AN TOÀN] Cổng public :${PUBLIC_PORT} đang được giữ bởi ứng dụng không phải Nginx:" >&2
  ss -tlnp | grep -E ":${PUBLIC_PORT}\b" >&2
  echo "Hãy chọn cổng khác, ví dụ: PUBLIC_PORT=8089 bash deploy/scripts/deploy-vps.sh" >&2
  exit 11
fi
echo "-> Kiểm tra an toàn: Không xung đột cổng với source hiện hữu!"
CHECK_EOF

echo "=== [3/6] Build bản Production SSR + Client ngay trên máy cục bộ ==="
(cd "${REPO_ROOT}/app" && npm run build)

echo "=== [4/6] Đồng bộ mã nguồn & bản build lên ${VPS_HOST}:${APP_DIR} ==="
ssh "${VPS_HOST}" "mkdir -p '${APP_DIR}' '${DATA_DIR}/tenants' '${BACKUP_DIR}'"
rsync -avz --delete "${RSYNC_EXCLUDES[@]}" "${REPO_ROOT}/" "${VPS_HOST}:${APP_DIR}/"

echo "=== [5/6] Cài đặt môi trường cô lập, systemd services & Nginx vhost riêng ==="
ssh "${VPS_HOST}" "APP_DIR='${APP_DIR}' DATA_DIR='${DATA_DIR}' BACKUP_DIR='${BACKUP_DIR}' DOMAIN='${DOMAIN}' PUBLIC_PORT='${PUBLIC_PORT}' BACKEND_PORT='${BACKEND_PORT}' FRONTEND_PORT='${FRONTEND_PORT}' bash -s" <<'REMOTE_EOF'
set -euo pipefail

# 1. Install missing OS packages only (never remove/downgrade existing packages!)
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

# 2. Isolated Python virtualenv in /opt/ubnd-ai/.venv (zero impact on existing Python apps)
cd "${APP_DIR}"
if [[ ! -x "${APP_DIR}/.venv/bin/python" ]]; then
  python3 -m venv "${APP_DIR}/.venv"
fi
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/backend/requirements.txt"

# 3. Isolated Node modules in /opt/ubnd-ai/app/node_modules
cd "${APP_DIR}/app"
npm ci --omit=dev

# 4. Write environment defaults
if [[ ! -f /etc/default/ubnd-ai ]]; then
  cat > /etc/default/ubnd-ai <<ENV_EOF
UBND_ENV=production
UBND_DB_PATH=${DATA_DIR}/ubnd_ai.db
UBND_ALLOWED_ORIGINS=http://${DOMAIN},http://${DOMAIN}:${PUBLIC_PORT},https://${DOMAIN}
ENV_EOF
  chmod 600 /etc/default/ubnd-ai
fi

# 5. Render systemd units bound to isolated BACKEND_PORT & FRONTEND_PORT
sed "s/--port 8000/--port ${BACKEND_PORT}/g" \
  "${APP_DIR}/deploy/systemd/ubnd-ai-backend.service" > /etc/systemd/system/ubnd-ai-backend.service

sed \
  -e "s/PORT=3000/PORT=${FRONTEND_PORT}/g" \
  -e "s|http://127.0.0.1:8000|http://127.0.0.1:${BACKEND_PORT}|g" \
  "${APP_DIR}/deploy/systemd/ubnd-ai-frontend.service" > /etc/systemd/system/ubnd-ai-frontend.service

systemctl daemon-reload
systemctl enable ubnd-ai-backend.service ubnd-ai-frontend.service
systemctl restart ubnd-ai-backend.service
systemctl restart ubnd-ai-frontend.service

# 6. Add standalone Nginx vhost WITHOUT touching any existing Nginx site files!
NGINX_RENDERED="/tmp/ubnd-ai.nginx.conf"
sed \
  -e "s/__PUBLIC_PORT__/${PUBLIC_PORT}/g" \
  -e "s/__SERVER_NAME__/${DOMAIN}/g" \
  -e "s|http://127.0.0.1:8000|http://127.0.0.1:${BACKEND_PORT}|g" \
  -e "s|http://127.0.0.1:3000|http://127.0.0.1:${FRONTEND_PORT}|g" \
  "${APP_DIR}/deploy/nginx/ubnd-ai.conf" > "${NGINX_RENDERED}"

if [[ -d /etc/nginx/sites-available && -d /etc/nginx/sites-enabled ]]; then
  cp "${NGINX_RENDERED}" /etc/nginx/sites-available/ubnd-ai.conf
  ln -sf /etc/nginx/sites-available/ubnd-ai.conf /etc/nginx/sites-enabled/ubnd-ai.conf
else
  cp "${NGINX_RENDERED}" /etc/nginx/conf.d/ubnd-ai.conf
fi

nginx -t
systemctl enable nginx
systemctl reload nginx || systemctl restart nginx

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

echo "=== [6/6] Kiểm tra sức khỏe dịch vụ (Smoke Check) trên VPS ==="
ssh "${VPS_HOST}" "PUBLIC_PORT='${PUBLIC_PORT}' BACKEND_PORT='${BACKEND_PORT}' FRONTEND_PORT='${FRONTEND_PORT}' DOMAIN='${DOMAIN}' bash -s" <<'SMOKE_EOF'
set -euo pipefail
for i in {1..15}; do
  if curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null 2>&1 && curl -fsS "http://127.0.0.1:${FRONTEND_PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo -n "-> Backend (:${BACKEND_PORT}/api/health): "
curl -fsS "http://127.0.0.1:${BACKEND_PORT}/api/health"
echo ""
echo -n "-> Nginx Proxy (:${PUBLIC_PORT}/api/health): "
curl -fsS -H "Host: ${DOMAIN}" "http://127.0.0.1:${PUBLIC_PORT}/api/health"
echo ""
SMOKE_EOF

if [[ "${PUBLIC_PORT}" == "80" ]]; then
  echo "🎉 DEPLOY SONG SONG THÀNH CÔNG! Truy cập ngay: http://${DOMAIN}"
else
  echo "🎉 DEPLOY SONG SONG THÀNH CÔNG! Truy cập ngay: http://${DOMAIN}:${PUBLIC_PORT}"
fi
