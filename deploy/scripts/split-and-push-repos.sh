#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

GITHUB_OWNER="${GITHUB_OWNER:-LuongCaoChanHuyIT}"
FRONTEND_REPO="${FRONTEND_REPO:-ubnd-ai-frontend}"
BACKEND_REPO="${BACKEND_REPO:-ubnd-ai-backend}"
TARGET_BRANCH="${TARGET_BRANCH:-main}"
VISIBILITY="${VISIBILITY:---private}"

DRY_RUN=0
EXPORT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --export-only)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        echo "[split-repos] Thiếu đường dẫn sau --export-only" >&2
        exit 2
      fi
      EXPORT_DIR="$2"
      shift 2
      ;;
    *)
      echo "[split-repos] Tham số không hợp lệ: $1" >&2
      exit 2
      ;;
  esac
done

for ident in "${GITHUB_OWNER}" "${FRONTEND_REPO}" "${BACKEND_REPO}" "${TARGET_BRANCH}"; do
  if [[ -z "${ident}" ]] || [[ ! "${ident}" =~ ^[A-Za-z0-9._-]+$ ]]; then
    echo "[split-repos] Định danh GitHub/nhánh không hợp lệ: '${ident}'" >&2
    exit 2
  fi
done

if [[ "${VISIBILITY}" != "--private" && "${VISIBILITY}" != "--public" ]]; then
  echo "[split-repos] VISIBILITY phải là --private hoặc --public (nhận: '${VISIBILITY}')" >&2
  exit 2
fi

FE_REMOTE="https://github.com/${GITHUB_OWNER}/${FRONTEND_REPO}.git"
BE_REMOTE="https://github.com/${GITHUB_OWNER}/${BACKEND_REPO}.git"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "=== [DRY-RUN] KẾ HOẠCH TÁCH 2 REPO ĐỘC LẬP TRÊN GITHUB ==="
  echo "Frontend Repo : ${GITHUB_OWNER}/${FRONTEND_REPO} (${FE_REMOTE})"
  echo "Backend Repo  : ${GITHUB_OWNER}/${BACKEND_REPO} (${BE_REMOTE})"
  echo "Visibility    : ${VISIBILITY}"
  echo "Target Branch : ${TARGET_BRANCH}"
  echo "Backup Guard  : Giữ nguyên 100% repo dự phòng ${GITHUB_OWNER}/app-ai-ubnd (không đụng chạm)"
  exit 0
fi

stage_repositories() {
  local base_dir="$1"
  local be_out="${base_dir}/${BACKEND_REPO}"
  local fe_out="${base_dir}/${FRONTEND_REPO}"

  mkdir -p "${be_out}" "${fe_out}"

  # 1. Stage standalone Backend tree
  rsync -a --delete \
    --exclude=".git" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude="*.pyo" \
    --exclude=".pytest_cache" \
    --exclude="data" \
    --exclude="*.db" \
    --exclude="*.db-*" \
    --exclude="tests/test_split_repos.py" \
    "${REPO_ROOT}/backend/" "${be_out}/backend/"

  rsync -a --delete \
    --exclude="standalone-backend" \
    --exclude="scripts/split-and-push-repos.sh" \
    "${REPO_ROOT}/deploy/" "${be_out}/deploy/"

  cp "${REPO_ROOT}/backend/requirements.txt" "${be_out}/requirements.txt"
  cp "${REPO_ROOT}/deploy/standalone-backend/main.py" "${be_out}/main.py"
  cp "${REPO_ROOT}/deploy/standalone-backend/Dockerfile" "${be_out}/Dockerfile"
  cp "${REPO_ROOT}/deploy/standalone-backend/.dockerignore" "${be_out}/.dockerignore"
  cp "${REPO_ROOT}/deploy/standalone-backend/.gitignore" "${be_out}/.gitignore"
  cp "${REPO_ROOT}/deploy/standalone-backend/.env.example" "${be_out}/.env.example"
  cp "${REPO_ROOT}/deploy/standalone-backend/README.md" "${be_out}/README.md"

  # 2. Stage standalone Frontend tree (app/* directly at repo root)
  rsync -a --delete \
    --exclude=".git" \
    --exclude="node_modules" \
    --exclude="build" \
    --exclude=".react-router" \
    --exclude=".agents" \
    --exclude=".env" \
    --exclude="*.db" \
    "${REPO_ROOT}/app/" "${fe_out}/"
}

if [[ -n "${EXPORT_DIR}" ]]; then
  stage_repositories "${EXPORT_DIR}"
  echo "[split-repos] Đã xuất sạch 2 repo độc lập vào: ${EXPORT_DIR}"
  exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "[split-repos] Không tìm thấy GitHub CLI (gh)." >&2
  exit 1
fi

gh auth setup-git

TMP_WORK="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_WORK}"
}
trap cleanup EXIT

stage_repositories "${TMP_WORK}"

GIT_USER_NAME="$(git -C "${REPO_ROOT}" config user.name || echo "UBND AI Builder")"
GIT_USER_EMAIL="$(git -C "${REPO_ROOT}" config user.email || echo "tsh.co@tshorg.vn")"

publish_standalone_repo() {
  local work_dir="$1"
  local repo_name="$2"
  local repo_desc="$3"
  local commit_msg="$4"
  local full_slug="${GITHUB_OWNER}/${repo_name}"
  local remote_url="https://github.com/${full_slug}.git"

  echo "=== Đồng bộ ${full_slug} (${VISIBILITY}, nhánh ${TARGET_BRANCH}) ==="
  if ! gh repo view "${full_slug}" >/dev/null 2>&1; then
    echo "-> Đang tạo repository mới ${full_slug}..."
    gh repo create "${full_slug}" "${VISIBILITY}" --description "${repo_desc}"
  fi

  (
    cd "${work_dir}"
    git init -q -b "${TARGET_BRANCH}"
    git config user.name "${GIT_USER_NAME}"
    git config user.email "${GIT_USER_EMAIL}"
    git remote add target "${remote_url}"

    if git ls-remote --exit-code --heads target "${TARGET_BRANCH}" >/dev/null 2>&1; then
      git fetch -q --depth=1 target "${TARGET_BRANCH}"
      git reset -q --mixed FETCH_HEAD
    fi

    git add -A
    if git diff --cached --quiet; then
      echo "-> ${full_slug}:${TARGET_BRANCH} đã ở trạng thái mới nhất (không có thay đổi)."
    else
      git commit -q -m "${commit_msg}"
      git push -u target "HEAD:refs/heads/${TARGET_BRANCH}"
    fi
  )
}

publish_standalone_repo \
  "${TMP_WORK}/${BACKEND_REPO}" \
  "${BACKEND_REPO}" \
  "Bộ Trợ lý AI UBND Xã, Phường — Backend FastAPI API" \
  "feat(backend): standalone FastAPI + SQLite production package"

publish_standalone_repo \
  "${TMP_WORK}/${FRONTEND_REPO}" \
  "${FRONTEND_REPO}" \
  "Bộ Trợ lý AI UBND Xã, Phường — Frontend React Router SSR" \
  "feat(frontend): standalone React Router v8 SSR production package"

echo "🎉 Hoàn tất tách & đẩy 2 repo độc lập:"
echo "  - Backend : https://github.com/${GITHUB_OWNER}/${BACKEND_REPO}"
echo "  - Frontend: https://github.com/${GITHUB_OWNER}/${FRONTEND_REPO}"
