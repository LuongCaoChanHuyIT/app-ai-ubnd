# VPS Production Hardening & Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `UBND-AI-Support` for production Internet exposure and package idempotent `systemd`, `Nginx`, SQLite backup, and SSH/rsync deployment automation targeting VPS `157.66.219.248`.

**Architecture:** Same-origin reverse proxy on Nginx (`:80/:443`) routes `/api/*` to a single-worker FastAPI Uvicorn service (`127.0.0.1:8000`) and `/*` to React Router SSR (`127.0.0.1:3000`). Persistent SQLite databases (`ubnd_ai.db` and `tenants/<slug>.db`) live outside the code tree in `/var/lib/ubnd-ai` so code deployments never overwrite commune data, while optional Cloudflare Access header enforcement (`UBND_TRUST_CF_ACCESS=1`) prevents header/cookie spoofing on the public Internet.

**Tech Stack:** Python `3.12+` / FastAPI / Uvicorn / SQLite3 / `pypdf` / `python-docx`, Node.js `22+` / React Router `v8.5` SSR (`@react-router/serve`), `systemd`, `Nginx`, `rsync` + `OpenSSH`.

**Spec:** `BAO_CAO_SOURCE.md`

## Global Constraints
- Backend Uvicorn MUST run with `--workers 1` so `EphemeralSessionStore` in process RAM and SQLite write locks remain consistent across requests.
- Persistent database path MUST use `UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db`.
- Frontend SSR MUST run with `NODE_ENV=production`, `PORT=3000`, and `API_BASE_URL=http://127.0.0.1:8000`.
- Nginx MUST set `client_max_body_size 15M;`.
- `backend/requirements.txt` MUST include `pypdf>=5.0.0` and `python-docx>=1.1.0` with Ubuntu/Debian Python 3.12+ compatible version bounds.
- Target VPS host defaults to `VPS_HOST=root@157.66.219.248` and code directory `/opt/ubnd-ai`.

## Review Focus
- `UBND_TRUST_CF_ACCESS=1` with spoofed `X-Actor-Email: tsh.co@tshorg.vn` but no `Cf-Access-Authenticated-User-Email` header must return `HTTP 401`.
- `UBND_ENV=production` must disable `/docs`, `/redoc`, and `/openapi.json` (`HTTP 404`) while keeping `/api/health` (`HTTP 200`).
- `ubnd-ai-backend.service` must pin `--workers 1` and `UBND_ENV=production`.
- `ubnd-ai.conf` must pin `client_max_body_size 15M;`.
- `deploy-vps.sh` must exclude `backend/data` and store DBs in `/var/lib/ubnd-ai`, inspect ports/bootstrap SSH key cleanly, and `backup-sqlite.sh` must back up both root and `tenants/*.db` online.

---

### Task 1: Backend Production Hardening & Cloudflare Access Identity Lock

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/main.py`
- Modify: `backend/auth.py`
- Create: `backend/tests/test_production_config.py`

- [ ] **Step 1: Write failing tests in `backend/tests/test_production_config.py`**
  Test:
  1. `backend/requirements.txt` lists `pypdf` and `python-docx` with compatible version bounds.
  2. `create_app()` with `UBND_ENV=production` returns `404` on `/docs`, `/redoc`, `/openapi.json` and `200` on `/api/health`.
  3. `create_app()` respects `UBND_ALLOWED_ORIGINS` for CORS preflight.
  4. When `UBND_TRUST_CF_ACCESS=1`, spoofed `X-Actor-Email: tsh.co@tshorg.vn` or `Cookie: ubnd_actor_email=...` without `Cf-Access-Authenticated-User-Email` returns `401`, while valid `Cf-Access-Authenticated-User-Email: tsh.co@tshorg.vn` returns `200`.
- [ ] **Step 2: Run test to verify RED**
  Run: `.venv/bin/python -m unittest backend/tests/test_production_config.py -v`
  Expected: FAIL (`ImportError: cannot import name 'create_app'`).
- [ ] **Step 3: Implement `backend/requirements.txt`, `create_app()` in `backend/main.py`, and `UBND_TRUST_CF_ACCESS` in `backend/auth.py`**
- [ ] **Step 4: Run test suite to verify GREEN & Commit**
  Run: `.venv/bin/python -m unittest discover -s backend/tests -v`
  Expected: PASS.

---

### Task 2: Systemd Services, Nginx Reverse Proxy & Online SQLite Backup

**Files:**
- Create: `deploy/systemd/ubnd-ai-backend.service`
- Create: `deploy/systemd/ubnd-ai-frontend.service`
- Create: `deploy/nginx/ubnd-ai.conf`
- Create: `deploy/scripts/backup-sqlite.sh`
- Create: `backend/tests/test_deploy_artifacts.py`

- [ ] **Step 1: Write failing tests in `backend/tests/test_deploy_artifacts.py`**
  Test:
  1. `ubnd-ai-backend.service` pins `--workers 1`, `UBND_ENV=production`, `UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db`.
  2. `ubnd-ai-frontend.service` pins `NODE_ENV=production`, `PORT=3000`, `API_BASE_URL=http://127.0.0.1:8000`.
  3. `ubnd-ai.conf` pins `client_max_body_size 15M;` and routes `/api/` -> `127.0.0.1:8000` and `/` -> `127.0.0.1:3000`.
  4. `backup-sqlite.sh` executes a live online SQLite backup of both `ubnd_ai.db` and `tenants/ubnd-phuong-da-kao.db` into date-stamped output directory.
- [ ] **Step 2: Run test to verify RED**
  Run: `.venv/bin/python -m unittest backend/tests/test_deploy_artifacts.py -v`
  Expected: FAIL (`FileNotFoundError`).
- [ ] **Step 3: Create `deploy/systemd/*`, `deploy/nginx/ubnd-ai.conf`, and `deploy/scripts/backup-sqlite.sh`**
- [ ] **Step 4: Run test suite to verify GREEN & Commit**
  Run: `.venv/bin/python -m unittest discover -s backend/tests -v`
  Expected: PASS.

---

### Task 3: Idempotent VPS `157.66.219.248` Provisioning & One-Command Deploy Script

**Files:**
- Create: `deploy/scripts/deploy-vps.sh`
- Modify: `backend/tests/test_deploy_artifacts.py`

- [ ] **Step 1: Add failing dry-run & validation tests for `deploy-vps.sh` in `backend/tests/test_deploy_artifacts.py`**
  Test:
  1. `bash -n deploy/scripts/deploy-vps.sh` syntax check passes.
  2. Invalid `DOMAIN` (e.g. `DOMAIN="bad/domain"`) exits non-zero.
  3. Default `DOMAIN` (`157.66.219.248`) and custom `DOMAIN=ai.ubnd.vn` with `--dry-run` print complete rsync exclusions (`backend/data`, `.venv`, `app/node_modules`, `.git`), `/var/lib/ubnd-ai` DB preservation, systemd + Nginx setup, and health smoke check.
- [ ] **Step 2: Run test to verify RED**
  Run: `.venv/bin/python -m unittest backend/tests/test_deploy_artifacts.py -v`
  Expected: FAIL (`deploy-vps.sh` missing).
- [ ] **Step 3: Implement `deploy/scripts/deploy-vps.sh` (including automatic SSH key bootstrap if missing, port `:80` collision guard with `PUBLIC_PORT` fallback, Ubuntu/Debian/RHEL package auto-installer, systemd/Nginx activation, daily backup cron, and `/api/health` + SSR `/` smoke verification)**
- [ ] **Step 4: Run full Backend + Frontend test & build suites to verify GREEN & Commit**
  Run: `.venv/bin/python -m unittest discover -s backend/tests -v && (cd app && npm test && npm run typecheck && npm run build)`
  Expected: 100% PASS.

