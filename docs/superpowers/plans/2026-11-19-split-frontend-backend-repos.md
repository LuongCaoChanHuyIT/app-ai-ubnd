# Split Frontend & Backend Standalone Repositories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare and split `UBND-AI-Support` into two standalone, independently deployable private GitHub repositories (`LuongCaoChanHuyIT/ubnd-ai-frontend` and `LuongCaoChanHuyIT/ubnd-ai-backend` on branch `main`) while keeping `LuongCaoChanHuyIT/app-ai-ubnd` untouched.

**Architecture:** Frontend (`app/`) gains `VITE_API_BASE_URL` cross-origin API resolution alongside `API_BASE_URL` SSR resolution and Docker build-arg support so it works both on separate domains and behind a same-origin Nginx reverse proxy, then exports its contents directly to the root of `ubnd-ai-frontend`. Backend (`backend/`) retains its internal `backend.*` package layout and adds standalone root packaging (`main.py` shim, synced `requirements.txt`, single-worker `Dockerfile`, `.env.example`, and `deploy/` scripts) exported to `ubnd-ai-backend` via an idempotent export-and-push script (`deploy/scripts/split-and-push-repos.sh`).

**Tech Stack:** TypeScript / Node.js `22+` / React Router `v8.5` SSR / Docker, Python `3.12+` / FastAPI / Uvicorn / SQLite3, Bash / Git / GitHub CLI (`gh`).

**Spec:** `docs/superpowers/specs/2026-11-19-split-frontend-backend-repos-design.md`

## Global Constraints

- Target GitHub repositories MUST be `LuongCaoChanHuyIT/ubnd-ai-frontend` and `LuongCaoChanHuyIT/ubnd-ai-backend`, created as `--private` with default branch `main`.
- Existing remote `LuongCaoChanHuyIT/app-ai-ubnd` (`origin`) MUST NOT be pushed to, overwritten, or deleted.
- Backend Uvicorn MUST run with `--workers 1` in both `Dockerfile` and `systemd` so `EphemeralSessionStore` RAM and SQLite write locks stay consistent.
- Backend `Dockerfile` MUST set `UBND_ENV=production`, `UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db`, and bind `--host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers`.
- Frontend `resolveClientApiBase()` MUST safely guard `import.meta.env` in plain Node.js (`node --test` and SSR), fall back to `process.env.VITE_API_BASE_URL ?? ""`, and strip whitespace and trailing slashes.
- Frontend `resolveServerApiBase()` MUST prioritize `process.env.API_BASE_URL`, then `process.env.VITE_API_BASE_URL`, then `"http://127.0.0.1:8000"`.
- Exported standalone trees MUST exclude `.git`, `.venv`, `node_modules`, `build`, `.react-router`, `backend/data`, `__pycache__`, `.superpowers`, `.codegraph`, and `.ua`.

## Review Focus

- `VITE_API_BASE_URL` or `API_BASE_URL` configured with trailing slashes and spaces (e.g. `" https://api.ubnd.vn/// "`) must produce `"https://api.ubnd.vn/api/..."` without double slashes in both `apiRequest` and `uploadSessionFile`.
- Running `resolveClientApiBase()` under plain Node.js (`node --test`) where `import.meta.env` is `undefined` must not throw `TypeError` and must read `process.env.VITE_API_BASE_URL` or return `""`.
- Starting the exported `ubnd-ai-backend` repository with `uvicorn main:app` from its root directory must import `app` and `create_app` cleanly without `ModuleNotFoundError`.
- Exporting `ubnd-ai-backend` from a workspace containing local `backend/data/ubnd_ai.db` must never copy `.db` files into the exported Git working tree.
- Re-running `deploy/scripts/split-and-push-repos.sh` when target directories or GitHub repositories already exist must succeed idempotently without touching `LuongCaoChanHuyIT/app-ai-ubnd`.

---

### Task 1: Cross-Origin API Base URL Resolution & Docker Build Support in Frontend

**Files:**
- Modify: `app/app/lib/api.ts:266-412`
- Modify: `app/Dockerfile:1-22`
- Modify: `app/README.md`
- Create: `app/.env.example`
- Test: `app/tests/api-client.test.ts`

**Interfaces:**
- Consumes: `process.env.API_BASE_URL`, `process.env.VITE_API_BASE_URL`, `import.meta.env.VITE_API_BASE_URL`
- Produces:
  - `resolveClientApiBase(): string` in `app/app/lib/api.ts`
  - `resolveServerApiBase(): string` in `app/app/lib/api.ts`
  - Updated `apiRequest<T>(path, options)` and `uploadSessionFile(sessionId, file, departmentId?, actorEmail?, tenantSlug?, baseUrl?: string)` defaulting omitted `baseUrl` to `resolveClientApiBase()`
  - `ARG VITE_API_BASE_URL=""` + `ENV NODE_ENV=production` + `ENV PORT=3000` + `EXPOSE 3000` in `app/Dockerfile`

- [ ] **Step 1: Write failing tests in `app/tests/api-client.test.ts`**

Add tests importing `resolveClientApiBase` and `resolveServerApiBase` from `../app/lib/api.ts`:

```typescript
test("resolveClientApiBase & resolveServerApiBase handle env precedence, Node runtime safety, and trailing slashes", () => {
  const prevApi = process.env.API_BASE_URL;
  const prevVite = process.env.VITE_API_BASE_URL;
  try {
    delete process.env.API_BASE_URL;
    delete process.env.VITE_API_BASE_URL;
    assert.equal(resolveClientApiBase(), "");
    assert.equal(resolveServerApiBase(), "http://127.0.0.1:8000");

    process.env.VITE_API_BASE_URL = " https://api.ubnd.vn/// ";
    assert.equal(resolveClientApiBase(), "https://api.ubnd.vn");
    assert.equal(resolveServerApiBase(), "https://api.ubnd.vn");

    process.env.API_BASE_URL = "http://127.0.0.1:18000/";
    assert.equal(resolveServerApiBase(), "http://127.0.0.1:18000");
  } finally {
    if (prevApi === undefined) delete process.env.API_BASE_URL;
    else process.env.API_BASE_URL = prevApi;
    if (prevVite === undefined) delete process.env.VITE_API_BASE_URL;
    else process.env.VITE_API_BASE_URL = prevVite;
  }
});

test("apiRequest and uploadSessionFile default to VITE_API_BASE_URL when baseUrl is omitted", async () => {
  const receivedPaths: string[] = [];
  const server = http.createServer((req, res) => {
    receivedPaths.push(String(req.url ?? ""));
    req.resume();
    req.on("end", () => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ session_id: "s1", created_at: "", files: [], messages: [] }));
    });
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as { port: number }).port;
  const prevVite = process.env.VITE_API_BASE_URL;
  process.env.VITE_API_BASE_URL = `http://127.0.0.1:${port}///`;

  try {
    await apiRequest("/api/health");
    const blob = new File([Buffer.from("noi dung")], "hoso.txt", { type: "text/plain" });
    await uploadSessionFile("s1", blob, "VP", "tsh.co@tshorg.vn", "default");
    assert.deepEqual(receivedPaths, [
      "/api/health",
      "/api/m05/sessions/s1/upload?department_id=VP",
    ]);
  } finally {
    if (prevVite === undefined) delete process.env.VITE_API_BASE_URL;
    else process.env.VITE_API_BASE_URL = prevVite;
    server.close();
  }
});
```

- [ ] **Step 2: Run Frontend test suite to verify failure**

Run: `cd app && npm test`
Expected: FAIL (`SyntaxError: The requested module '../app/lib/api.ts' does not provide an export named 'resolveClientApiBase'`).

- [ ] **Step 3: Implement `resolveClientApiBase()`, update `resolveServerApiBase()`, `apiRequest()`, `uploadSessionFile()`, `app/Dockerfile`, `app/.env.example`, and `app/README.md`**

In `app/app/lib/api.ts`:
- Export `resolveClientApiBase(): string` reading `(import.meta as { env?: Record<string, string | undefined> })?.env?.VITE_API_BASE_URL ?? (typeof process !== "undefined" ? process.env?.VITE_API_BASE_URL : undefined) ?? ""` with `.trim().replace(/\/+$/, "")`.
- Update `resolveServerApiBase(): string` to check `process.env?.API_BASE_URL` then `process.env?.VITE_API_BASE_URL` (trimmed and trailing-slash stripped) before `"http://127.0.0.1:8000"`.
- In `apiRequest`, set `const baseUrl = (options?.baseUrl ?? resolveClientApiBase()).trim().replace(/\/+$/, "");`.
- Change `uploadSessionFile` 6th parameter from `baseUrl = ""` to `baseUrl?: string`, resolving `const resolvedBase = (baseUrl ?? resolveClientApiBase()).trim().replace(/\/+$/, "");`.

In `app/Dockerfile`:
- Add `ARG VITE_API_BASE_URL=""` and `ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}` before `RUN npm run build` in `build-env`.
- Add `ENV NODE_ENV=production`, `ENV PORT=3000`, and `EXPOSE 3000` in the runtime stage.

Create `app/.env.example` documenting `API_BASE_URL` and `VITE_API_BASE_URL`, and update `app/README.md` with standalone build/Docker/env instructions.

- [ ] **Step 4: Run Frontend tests, typecheck, and production build**

Run: `cd app && npm test && npm run typecheck && npm run build`
Expected: 100% PASS and clean SSR + client production build.

- [ ] **Step 5: Commit Frontend standalone readiness**

```bash
git add app/app/lib/api.ts app/tests/api-client.test.ts app/Dockerfile app/.env.example app/README.md
git commit -m "feat(frontend): support cross-origin VITE_API_BASE_URL and standalone Docker build"
```

---

### Task 2: Standalone Backend Root Packaging & Idempotent Split/Export Script

**Files:**
- Create: `deploy/standalone-backend/main.py`
- Create: `deploy/standalone-backend/Dockerfile`
- Create: `deploy/standalone-backend/.dockerignore`
- Create: `deploy/standalone-backend/.gitignore`
- Create: `deploy/standalone-backend/.env.example`
- Create: `deploy/standalone-backend/README.md`
- Create: `deploy/scripts/split-and-push-repos.sh`
- Create: `backend/tests/test_split_repos.py`

**Interfaces:**
- Consumes: `backend/main.py` (`app`, `create_app`), `backend/requirements.txt`, `app/` tree (from Task 1)
- Produces:
  - `deploy/standalone-backend/main.py` re-exporting `app` and `create_app` from `backend.main`
  - `deploy/scripts/split-and-push-repos.sh` supporting `--dry-run` and `--export-only <target_dir>`, plus default GitHub repo creation & push to `GITHUB_OWNER` (default `LuongCaoChanHuyIT`), `FRONTEND_REPO` (default `ubnd-ai-frontend`), `BACKEND_REPO` (default `ubnd-ai-backend`), `VISIBILITY` (default `--private`), branch `main`

- [ ] **Step 1: Write failing tests in `backend/tests/test_split_repos.py`**

Test:
1. `bash -n deploy/scripts/split-and-push-repos.sh` passes syntax validation.
2. `--dry-run` prints `LuongCaoChanHuyIT/ubnd-ai-frontend`, `LuongCaoChanHuyIT/ubnd-ai-backend`, `--private`, branch `main`, and confirms `app-ai-ubnd` is untouched.
3. `--export-only <tmpdir>` (even when dummy `backend/data/leak_check.db` exists during test) produces:
   - `<tmpdir>/ubnd-ai-backend` containing `main.py`, `requirements.txt` (matching `backend/requirements.txt`), `Dockerfile` (containing `--workers 1`, `UBND_ENV=production`, `UBND_DB_PATH=/var/lib/ubnd-ai/ubnd_ai.db`, `${PORT:-8000}`), `.env.example`, `backend/main.py`, `deploy/scripts/backup-sqlite.sh`, zero `.db` files, and zero `app/` directory.
   - Running `.venv/bin/python -c "import main; assert main.app.title"` with `cwd=<tmpdir>/ubnd-ai-backend` exits `0` (`uvicorn main:app` compatibility).
   - `<tmpdir>/ubnd-ai-frontend` containing `package.json`, `Dockerfile` (containing `ARG VITE_API_BASE_URL`), `.env.example`, `app/lib/api.ts`, zero `node_modules` or `build` directories, and zero `backend/` directory.
   - Re-running `--export-only <tmpdir>` a second time succeeds idempotently (`returncode == 0`).

- [ ] **Step 2: Run Backend test to verify failure**

Run: `.venv/bin/python -m unittest backend/tests/test_split_repos.py -v`
Expected: FAIL (`AssertionError` / missing `deploy/scripts/split-and-push-repos.sh`).

- [ ] **Step 3: Create `deploy/standalone-backend/*` templates and `deploy/scripts/split-and-push-repos.sh`**

- `deploy/standalone-backend/main.py`: `from backend.main import app, create_app` (`__all__ = ["app", "create_app"]`).
- `deploy/standalone-backend/Dockerfile`: `python:3.12-slim`, installs `requirements.txt`, copies `main.py`, `backend/`, `deploy/`, creates `/var/lib/ubnd-ai/tenants`, runs `uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers`.
- `deploy/standalone-backend/.env.example`, `.gitignore`, `.dockerignore`, `README.md`.
- `deploy/scripts/split-and-push-repos.sh`:
  - Validates `GITHUB_OWNER`, `FRONTEND_REPO`, `BACKEND_REPO`.
  - Stages clean `ubnd-ai-backend` and `ubnd-ai-frontend` directories using `rsync` with strict exclusions (`backend/data`, `.venv`, `node_modules`, `build`, `.react-router`, `__pycache__`, `*.pyc`, `*.db`, `.git`, `.superpowers`, `.codegraph`, `.ua`), copying `backend/requirements.txt` -> `<backend>/requirements.txt` and `deploy/standalone-backend/*` -> `<backend>/`.
  - When `--export-only <dir>` is passed, writes both clean trees into `<dir>` and exits `0`.
  - Otherwise initializes fresh Git `main` branches in both staged directories, creates `LuongCaoChanHuyIT/ubnd-ai-backend` and `LuongCaoChanHuyIT/ubnd-ai-frontend` via `gh repo create --private` if not yet present, and pushes `HEAD:refs/heads/main` using `gh auth setup-git` credentials without touching `origin` (`app-ai-ubnd`).

- [ ] **Step 4: Run full Backend & Frontend test suites to verify GREEN**

Run: `.venv/bin/python -m unittest discover -s backend/tests -v && (cd app && npm test)`
Expected: 100% PASS.

- [ ] **Step 5: Commit standalone backend templates, split script, and tests**

```bash
git add deploy/standalone-backend deploy/scripts/split-and-push-repos.sh backend/tests/test_split_repos.py docs/superpowers/specs/2026-11-19-split-frontend-backend-repos-design.md docs/superpowers/plans/2026-11-19-split-frontend-backend-repos.md
git commit -m "feat(deploy): add standalone backend packaging and idempotent repo split script"
```

---

### Task 3: Create & Push Standalone GitHub Repositories and Verify Remote State

**Files:**
- Execute: `deploy/scripts/split-and-push-repos.sh`

**Interfaces:**
- Consumes: `deploy/scripts/split-and-push-repos.sh` (from Task 2) and authenticated `gh` session (`LuongCaoChanHuyIT`)
- Produces:
  - Live private repository `https://github.com/LuongCaoChanHuyIT/ubnd-ai-frontend` (`main` branch populated)
  - Live private repository `https://github.com/LuongCaoChanHuyIT/ubnd-ai-backend` (`main` branch populated)
  - Verified unchanged `https://github.com/LuongCaoChanHuyIT/app-ai-ubnd` (`HEAD` still at `158cc0db6003a32031db9dec93f6621667e2a208`)

- [ ] **Step 1: Record `app-ai-ubnd` remote SHA before push and run `--dry-run`**

Run: `git ls-remote https://github.com/LuongCaoChanHuyIT/app-ai-ubnd.git && bash deploy/scripts/split-and-push-repos.sh --dry-run`
Expected: `158cc0db6003a32031db9dec93f6621667e2a208` on `app-ai-ubnd` and clean dry-run summary.

- [ ] **Step 2: Execute `split-and-push-repos.sh` to create & push both GitHub repositories**

Run: `bash deploy/scripts/split-and-push-repos.sh`
Expected: Creates `LuongCaoChanHuyIT/ubnd-ai-backend` and `LuongCaoChanHuyIT/ubnd-ai-frontend` (private) and pushes `main` to both.

- [ ] **Step 3: Verify remote branches, root files, privacy flags, and untouched `app-ai-ubnd` backup**

Run:
```bash
gh repo view LuongCaoChanHuyIT/ubnd-ai-frontend --json name,url,isPrivate,defaultBranchRef
gh repo view LuongCaoChanHuyIT/ubnd-ai-backend --json name,url,isPrivate,defaultBranchRef
gh api repos/LuongCaoChanHuyIT/ubnd-ai-frontend/contents --jq '.[].name'
gh api repos/LuongCaoChanHuyIT/ubnd-ai-backend/contents --jq '.[].name'
git ls-remote https://github.com/LuongCaoChanHuyIT/app-ai-ubnd.git
```
Expected:
- Both new repos report `"isPrivate": true` and `"defaultBranchRef": {"name": "main"}`.
- `ubnd-ai-frontend` root contains `package.json`, `Dockerfile`, `.env.example`, `app`, `public`.
- `ubnd-ai-backend` root contains `main.py`, `requirements.txt`, `Dockerfile`, `.env.example`, `backend`, `deploy`.
- `app-ai-ubnd` still points to `158cc0db6003a32031db9dec93f6621667e2a208`.

