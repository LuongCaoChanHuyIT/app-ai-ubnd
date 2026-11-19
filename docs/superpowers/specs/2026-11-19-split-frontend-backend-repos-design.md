# Split Frontend & Backend Standalone Repositories — Design Spec

## 1. Intent & Why
Split the `UBND-AI-Support` full-stack monorepo into two standalone, independently deployable GitHub repositories under `https://github.com/LuongCaoChanHuyIT` while preserving `LuongCaoChanHuyIT/app-ai-ubnd` untouched as a backup archive:
- **`LuongCaoChanHuyIT/ubnd-ai-frontend`** (default branch `main`, private): Standalone React Router v8.5 SSR application ready for Docker, PaaS (Coolify, Render, Railway, Dokploy), or Node.js VPS deployment.
- **`LuongCaoChanHuyIT/ubnd-ai-backend`** (default branch `main`, private): Standalone FastAPI + SQLite application ready for Docker, PaaS with persistent volume, or Linux VPS deployment.

## 2. Goals, Non-Goals & Anti-Goals
- **Goals:**
  - Support both **cross-origin deployment** (Frontend and Backend on separate domains/ports via `VITE_API_BASE_URL` + `UBND_ALLOWED_ORIGINS`) and **same-origin reverse-proxy deployment** (empty `VITE_API_BASE_URL` behind Nginx).
  - Package `ubnd-ai-backend` so both `uvicorn main:app` and `uvicorn backend.main:app` work from the repository root, alongside a production `Dockerfile` and root `requirements.txt`.
  - Package `ubnd-ai-frontend` with `package.json` and `Dockerfile` (accepting `ARG VITE_API_BASE_URL`) at the repository root.
  - Automate clean, repeatable export and push via `deploy/scripts/split-and-push-repos.sh`.
- **Non-Goals:**
  - Rewriting internal `from backend.*` imports across Backend modules and tests.
  - Migrating SQLite or `EphemeralSessionStore` to external databases.
- **Anti-Goals:**
  -Modifying or deleting `LuongCaoChanHuyIT/app-ai-ubnd`.
  - Leaking local SQLite `.db` files, `.venv`, `node_modules`, or build artifacts into either GitHub repository.

## 3. Constraints
- Backend Uvicorn MUST run with `--workers 1` so `EphemeralSessionStore` in RAM and SQLite write locks remain consistent.
- Backend `Dockerfile` MUST default `UBND_ENV=production`, `UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db`, and bind `--host 0.0.0.0 --port ${PORT:-8000}`.
- Frontend `resolveClientApiBase()` MUST safely handle non-Vite runtimes (`node --test` and SSR) where `import.meta.env` is undefined, strip trailing slashes/whitespace, and default to `""`.
- Frontend `resolveServerApiBase()` MUST resolve `process.env.API_BASE_URL`, falling back to `process.env.VITE_API_BASE_URL`, then `"http://127.0.0.1:8000"`.

## 4. Approaches Considered
1. **Selected — Clean Root Export to Two Dedicated Repos (`ubnd-ai-frontend` & `ubnd-ai-backend`):**
   - Frontend repo root contains the contents of `app/`.
   - Backend repo root contains `backend/` package + root `main.py` shim + synced root `requirements.txt` + `Dockerfile` + `deploy/`.
   - Keeps `app-ai-ubnd` untouched, requires zero `Root Directory` overrides on deployment platforms, and preserves 100% of existing Python imports and tests.
2. **Rejected — Reuse `app-ai-ubnd` + `UBND-AI-Support`:** Overwrites the monorepo backup and leaves ambiguous repository naming during deployment setup.
3. **Rejected — Flatten `backend/*` into Backend Repo Root:** Breaks all `from backend.*` imports across routers, services, and the 76+ backend test suite without adding deployment benefit over a root `main.py` shim.

