# Bộ Trợ Lý AI UBND Xã, Phường — 7-Module Fullstack Web App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete, unified fullstack web platform for **Bộ Trợ lý AI UBND xã, phường (TSH)** implementing all 7 operational modules and 4 specialized department workspaces with React Router v8 (`shadcn/ui`) and FastAPI + SQLite.

**Architecture:** A single FastAPI backend (`backend/`) persists official documents, tasks, department instructions, RBAC accounts, API connectors, audit logs, and cloned commune tenant metadata in SQLite while isolating active session chat & uploaded files in an ephemeral RAM `EphemeralSessionStore` (wiped instantly on *"Kết thúc phiên - Xóa bộ nhớ"*). A React Router v8 Framework Mode frontend (`app/`) renders the dark-sidebar TSH workspace shell (`#0F172A`) and 7 nested routes sharing `?dept=` workspace state, session storage ID, and `/api` proxy calls.

**Tech Stack:** Frontend: React `19.3`, React Router `8.5` (Framework Mode SSR + Vite `8` proxy), Tailwind CSS `4.2`, `shadcn/ui` (63 installed components), `lucide-react`, Node `node:test`. Backend: Python `3.15` (`.venv`), FastAPI `0.163`, Pydantic `2.14`, stdlib `sqlite3` / `zipfile` / `xml.etree` / `unittest`, `httpx`.

**Spec:** `docs/superpowers/specs/2026-11-18-ubnd-ai-7-modules-webapp-design.md` (derived from `Profile_gioi_thieu_Bo_Tro_ly_AI_UBND_xa_phuong_TSH.pdf`)

## Global Constraints

- Display the verbatim accountability notice across the workspace shell: `"AI là công cụ hỗ trợ nghiệp vụ; cán bộ, công chức và người có thẩm quyền vẫn trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."`
- Support all 4 commune/ward departments everywhere: `VP` (*Văn phòng HĐND & UBND*), `KT` (*Kinh tế*), `VHXH` (*Văn hóa - Xã hội*), `NNMT` (*Nông nghiệp và Môi trường*).
- Session-uploaded files (`Mô-đun 01` & `Mô-đun 05`) MUST live only in `SESSION_STORE` RAM and be purged completely by `DELETE /api/sessions/{session_id}`.
- Preserve backward compatibility with `/api/health`, `/api/hello`, `backend/tests/test_hello.py`, and `app/tests/api-hello.test.ts`.
- Database path MUST honor `os.environ.get("UBND_DB_PATH")` so every backend test runs against an isolated temporary SQLite file without touching `backend/data/ubnd_ai.db`.
- All 7 modules MUST function end-to-end out-of-the-box via the deterministic Vietnamese administrative engine when no external LLM API key is configured, and automatically use the live OpenAI-compatible HTTP connector when enabled in `Mô-đun 07`.

## Review Focus

1. **Session memory leak after *"Kết thúc phiên - Xóa bộ nhớ"*:** Calling `DELETE /api/sessions/{session_id}` must remove both conversation messages and extracted file buffers from `SESSION_STORE` so a subsequent `GET /api/sessions/{session_id}` or `POST /api/m01/chat` sees 0 prior messages and 0 files. *(Pinned in Task 1)*
2. **Unsupported, oversized (>10 MB), or empty/unreadable binary uploads in Module 05:** Uploading a disallowed extension (`.exe`), a >10 MB payload, or a corrupt/image-only `.pdf`/`.docx` must return HTTP `400`/`413` or a clean Vietnamese `parse_note` fallback rather than an unhandled `500` exception. *(Pinned in Task 2 & Task 3)*
3. **Cross-department leak on private commune repository (`kho_rieng`):** Querying Module 04 (`GET /api/m04/documents`) or Module 01 RAG from department `KT` must never expose `kho_rieng` documents assigned exclusively to `VP`, while keeping `trung_uong` and `dia_phuong` documents shared. *(Pinned in Task 3)*
4. **Plaintext API key leak or non-owner privilege escalation in Module 07:** `GET /api/m07/api-connectors` must mask secret keys (`***`), and calls to owner-only endpoints (`POST/DELETE /api/m07/users`, `PUT /api/m07/departments/{id}/instruction`, `PUT /api/m07/api-connectors/{id}`, `POST /api/m07/clone-tenant`) with a non-owner `X-Actor-Email` must return HTTP `403`. *(Pinned in Task 3)*
5. **Unsafe or duplicate commune slug during *"Nhân bản AI"* (`POST /api/m07/clone-tenant`):** Vietnamese commune names or path-like characters (`"../UBND Phường Bến Nghé"`) must normalize strictly to `[a-z0-9-]+` (`"ubnd-phuong-ben-nghe"`), and re-cloning an existing slug must return HTTP `409` without overwriting its SQLite database. *(Pinned in Task 3)*

---

## File Structure

### Backend (`backend/`)
- `backend/schemas.py` — Shared Pydantic request/response models and `Literal` enums for all 7 modules.
- `backend/db.py` — SQLite schema initialization, realistic commune/ward seed data (4 departments, Central/Local/Private legal docs, tasks, RBAC users, API connector), `log_audit()`, and RAM-only `EphemeralSessionStore`.
- `backend/services/doc_parser.py` — Safe parser for `.txt`, `.md`, `.csv`, `.json`, `.docx` (WordprocessingML XML), and `.pdf` (text extraction + scanned-PDF fallback) with 10 MB & extension guards.
- `backend/services/ai_engine.py` — Department-scoped legal document search, 3-mode assistant responder (`soan_thao`, `nghiep_vu`, `tham_dinh`), 3-option extended analyzer (`M02`), Decree 30/2020/NĐ-CP draft generator & 5-criteria auditor (`M03`), 4-action session file processor (`M05`), plus optional live HTTP LLM connector.
- `backend/routers/workspace.py` — FastAPI router for `/api/departments`, `/api/sessions/{session_id}`, `/api/m01/chat`, `/api/m02/analyze`, `/api/m03/draft`, `/api/m03/audit`.
- `backend/routers/docs_and_files.py` — FastAPI router for `/api/m04/documents`, `/api/m04/update-requests`, `/api/m05/sessions/{session_id}/upload`, `/api/m05/sessions/{session_id}/process`.
- `backend/routers/ops_and_admin.py` — FastAPI router for `/api/m06/tasks`, `/api/m07/users`, `/api/m07/departments/{dept_id}/instruction`, `/api/m07/api-connectors`, `/api/m07/audit-logs`, `/api/m07/tenants`, `/api/m07/clone-tenant`.
- `backend/main.py` — Lifespan DB init, CORS, `/api/health`, `/api/hello`, and router registration.
- `backend/tests/test_db_and_sessions.py` — Unit tests for Task 1.
- `backend/tests/test_ai_and_authoring.py` — Unit/API tests for Task 2.
- `backend/tests/test_docs_ops_admin.py` — API & security tests for Task 3.
- `backend/tests/test_e2e_workflow.py` — Cross-module end-to-end integration test for Task 8.

### Frontend (`app/`)
- `app/app/lib/api.ts` — Typed API client & domain types for all 7 modules (preserving `fetchBackendHello`).
- `app/app/lib/session.ts` — Browser session ID helper (`ubnd_ai_session_id` + active actor email state) with instant rotation on session wipe.
- `app/app/components/layout/workspace-shell.tsx` — Dark navy `#0F172A` TSH sidebar (12 nav links, 4-department switcher, owner/officer switcher) + top bar + legal accountability banner.
- `app/app/routes.ts` — Nested Framework Mode route configuration wrapping the 7 module routes inside `routes/workspace-layout.tsx` (plus `/hello-check` -> `routes/home.tsx`).
- `app/app/routes/workspace-layout.tsx` — Shared layout loader fetching `/api/departments` & `/api/m07/users` and rendering `<WorkspaceShell>`.
- `app/app/routes/m01-assistant.tsx` — Module 01: 3-mode AI workspace, quick pills, inline session upload, *"Kết thúc phiên - Xóa bộ nhớ"*, chat composer.
- `app/app/routes/m02-extended.tsx` — Module 02: Extended knowledge multi-option analyzer (`Phương án A/B/C`) with handoff to Module 03.
- `app/app/routes/m03-drafting.tsx` — Module 03: Split Decree 30/2020/NĐ-CP administrative draft editor + 5-criteria audit scorecard.
- `app/app/routes/m04-official-docs.tsx` — Module 04: Official legal repository (`trung_uong`, `dia_phuong`, `kho_rieng`) + *Đề nghị cập nhật văn bản* tab.
- `app/app/routes/m05-doc-session.tsx` — Module 05: Session file uploader + 4-mode processor (*Tóm tắt*, *Trích xuất*, *Đối chiếu*, *Tổng hợp*).
- `app/app/routes/m06-tasks.tsx` — Module 06: 4 KPI cards, 4-department filter, task assignment dialog, progress & reminder actions.
- `app/app/routes/m07-admin.tsx` — Module 07: 5-tab admin console (*Phân quyền email*, *Instruction của phòng*, *Cổng API đấu nối*, *Nhật ký hệ thống*, *Nhân bản AI*).
- `app/tests/api-client.test.ts` — Unit tests for typed frontend API client & session helper.

---

### Task 1: Backend Core Database, Seeded Domain Data & Ephemeral Session Store

**Files:**
- Create: `backend/schemas.py`
- Create: `backend/db.py`
- Test: `backend/tests/test_db_and_sessions.py`

**Interfaces:**
- Consumes: Spec Sections 2 & 3 (`docs/superpowers/specs/2026-11-18-ubnd-ai-7-modules-webapp-design.md`)
- Produces:
  - `backend/schemas.py`: `DepartmentId`, `AssistantMode`, `DocTier`, `SessionProcessAction`, `TaskStatus`, and Pydantic request models (`ChatRequest`, `ExtendedAnalyzeRequest`, `DraftRequest`, `AuditRequest`, `CreateDocRequest`, `DocUpdateRequestCreate`, `ProcessSessionRequest`, `TaskCreateRequest`, `TaskPatchRequest`, `UserCreateRequest`, `InstructionUpdateRequest`, `ConnectorUpdateRequest`, `CloneTenantRequest`).
  - `backend/db.py`:
    - `get_db_path() -> Path`
    - `init_db(db_path: Path | str | None = None, commune_name: str = "UBND Xã/Phường Trung Tâm", owner_email: str = "tsh.co@tshorg.vn") -> None`
    - `get_conn(db_path: Path | str | None = None) -> sqlite3.Connection`
    - `log_audit(actor_email: str, department_id: str, module_code: str, action: str, detail: str, db_path: Path | str | None = None) -> None`
    - `SESSION_STORE: EphemeralSessionStore` with `.get_or_create(session_id: str)`, `.add_file(session_id: str, record: dict)`, `.append_message(session_id: str, msg: dict)`, `.wipe(session_id: str) -> bool`

- [ ] **Step 1: Write the failing test in `backend/tests/test_db_and_sessions.py` (pinning Review Focus #1)**

```python
import os
import tempfile
import unittest
from pathlib import Path

from backend.db import SESSION_STORE, get_conn, init_db, log_audit


class DbAndSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test_ubnd.db"
        os.environ["UBND_DB_PATH"] = str(self.db_path)
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_db_seeds_four_departments_docs_tasks_and_owner(self) -> None:
        with get_conn(self.db_path) as conn:
            depts = [r["id"] for r in conn.execute("SELECT id FROM departments ORDER BY id").fetchall()]
            self.assertEqual(sorted(depts), ["KT", "NNMT", "VHXH", "VP"])
            owner = conn.execute("SELECT role FROM users_rbac WHERE email = ?", ("tsh.co@tshorg.vn",)).fetchone()
            self.assertEqual(owner["role"], "owner")
            doc_count = conn.execute("SELECT COUNT(*) AS c FROM official_documents").fetchone()["c"]
            self.assertGreaterEqual(doc_count, 6)

    def test_wipe_session_purges_messages_and_files(self) -> None:
        sid = "sess-review-focus-1"
        SESSION_STORE.add_file(sid, {
            "file_id": "f1",
            "filename": "ho_so.txt",
            "size_bytes": 12,
            "ext": ".txt",
            "extracted_text": "Nội dung mật trong phiên",
            "parse_note": "ok",
            "uploaded_at": "2026-11-18T00:00:00Z",
        })
        SESSION_STORE.append_message(sid, {
            "role": "user",
            "mode": "nghiep_vu",
            "content": "Tóm tắt hồ sơ",
            "citations": [],
            "created_at": "2026-11-18T00:00:00Z",
        })
        self.assertTrue(SESSION_STORE.wipe(sid))
        fresh = SESSION_STORE.get_or_create(sid)
        self.assertEqual(fresh["files"], [])
        self.assertEqual(fresh["messages"], [])

    def test_log_audit_persists_entry(self) -> None:
        log_audit("tsh.co@tshorg.vn", "VP", "M01", "WIPE_SESSION", "Đã xóa bộ nhớ phiên", self.db_path)
        with get_conn(self.db_path) as conn:
            row = conn.execute("SELECT action, module_code FROM audit_logs ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual(row["action"], "WIPE_SESSION")
            self.assertEqual(row["module_code"], "M01")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest backend/tests/test_db_and_sessions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.db'`.

- [ ] **Step 3: Implement `backend/schemas.py` and `backend/db.py`**

Create the 8 SQLite tables from Spec Section 3.1 (`CREATE TABLE IF NOT EXISTS ...`), idempotent seed inserts (4 departments `VP`, `KT`, `VHXH`, `NNMT` with tailored Vietnamese `instruction` prompts; ≥6 realistic official documents across `trung_uong`, `dia_phuong`, and department-specific `kho_rieng` including `Nghị định 30/2020/NĐ-CP`, `Nghị định 399/2026/NĐ-CP`, `Luật Tổ chức chính quyền địa phương`, `Quy chế làm việc VP`, `Hướng dẫn thẩm tra ngân sách KT`; 5 sample tasks across all 4 departments; `tsh.co@tshorg.vn` owner + 4 department officers; 1 default inactive OpenAI-compatible connector), `log_audit`, and thread-safe `EphemeralSessionStore`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest discover -s backend/tests -v`
Expected: PASS (all tests in `test_hello.py` and `test_db_and_sessions.py`).

- [ ] **Step 5: Commit (initializing root repo or committing cleanly)**

Ensure root `.gitignore` excludes `.venv/`, `backend/data/*.db`, `backend/data/tenants/`, `app/node_modules/`, `app/build/`, `app/.react-router/`, `__pycache__/`, then commit Task 1 files.

---

### Task 2: Backend Document Parser, Legal Search & AI Modules 01–03

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/doc_parser.py`
- Create: `backend/services/ai_engine.py`
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/workspace.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_ai_and_authoring.py`

**Interfaces:**
- Consumes: `get_conn`, `init_db`, `log_audit`, `SESSION_STORE` from `backend/db.py`; request models from `backend/schemas.py`
- Produces:
  - `doc_parser.py`: `parse_uploaded_bytes(filename: str, content: bytes) -> tuple[str, str]`
  - `ai_engine.py`:
    - `search_official_documents(query: str, department_id: str, tier: str | None = None, db_path: Path | str | None = None) -> list[dict[str, Any]]`
    - `run_assistant_turn(session_id: str, department_id: str, mode: str, message: str, actor_email: str = "tsh.co@tshorg.vn") -> dict[str, Any]`
    - `analyze_extended_options(department_id: str, topic: str, context: str = "") -> dict[str, Any]`
    - `generate_administrative_draft(department_id: str, doc_type: str, title: str, key_points: str) -> dict[str, Any]`
    - `audit_administrative_draft(department_id: str, doc_type: str, draft_text: str) -> dict[str, Any]`
    - `process_session_files(session_id: str, department_id: str, action: str) -> dict[str, Any]`
  - `workspace.py` routes: `GET /api/departments`, `GET /api/sessions/{session_id}`, `DELETE /api/sessions/{session_id}`, `POST /api/m01/chat`, `POST /api/m02/analyze`, `POST /api/m03/draft`, `POST /api/m03/audit`

- [ ] **Step 1: Write the failing test in `backend/tests/test_ai_and_authoring.py` (pinning Review Focus #2 parser edge cases)**

```python
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app
from backend.services.doc_parser import parse_uploaded_bytes


def make_docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>',
        )
    return buf.getvalue()


class AiAndAuthoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["UBND_DB_PATH"] = str(Path(self.tmp.name) / "test.db")
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_doc_parser_extracts_docx_and_handles_corrupt_pdf_gracefully(self) -> None:
        text, note = parse_uploaded_bytes("to_trinh.docx", make_docx_bytes("Đề nghị xác nhận hộ tịch"))
        self.assertIn("Đề nghị xác nhận hộ tịch", text)
        self.assertEqual(note, "Đã trích xuất văn bản DOCX")

        pdf_text, pdf_note = parse_uploaded_bytes("scan.pdf", b"%PDF-1.4 binary scan without text")
        self.assertTrue(len(pdf_note) > 0)
        self.assertIsInstance(pdf_text, str)

        with self.assertRaises(ValueError):
            parse_uploaded_bytes("malware.exe", b"MZ")

    def test_m01_chat_modes_and_session_wipe(self) -> None:
        res = self.client.post("/api/m01/chat", json={
            "session_id": "s-m01",
            "department_id": "VP",
            "mode": "nghiep_vu",
            "message": "Quy định thể thức văn bản hành chính theo Nghị định 30",
        })
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertGreaterEqual(len(body["reply"]["citations"]), 1)

        del_res = self.client.delete("/api/sessions/s-m01")
        self.assertEqual(del_res.status_code, 200)
        state = self.client.get("/api/sessions/s-m01").json()
        self.assertEqual(state["messages"], [])

    def test_m02_extended_returns_three_options(self) -> None:
        res = self.client.post("/api/m02/analyze", json={
            "department_id": "VP",
            "topic": "Nâng cao tỷ lệ hồ sơ trực tuyến tại Bộ phận Một cửa",
            "context": "Phường đông dân cư",
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["options"]), 3)

    def test_m03_draft_and_five_criteria_audit(self) -> None:
        draft_res = self.client.post("/api/m03/draft", json={
            "department_id": "VP",
            "doc_type": "Kế hoạch",
            "title": "Triển khai chuyển đổi số quý IV/2026",
            "key_points": "Rà soát TTHC; Tập huấn cán bộ; Tuyên truyền khu dân cư",
        })
        self.assertEqual(draft_res.status_code, 200)
        draft_text = draft_res.json()["draft_text"]
        self.assertIn("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", draft_text)

        audit_res = self.client.post("/api/m03/audit", json={
            "department_id": "VP",
            "doc_type": "Quyết định",
            "draft_text": draft_text,
        })
        self.assertEqual(audit_res.status_code, 200)
        self.assertEqual(len(audit_res.json()["criteria"]), 5)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest backend/tests/test_ai_and_authoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.services'`.

- [ ] **Step 3: Implement `doc_parser.py`, `ai_engine.py`, `workspace.py`, and mount in `backend/main.py`**

- `doc_parser.py`: Enforce `ALLOWED_EXTENSIONS` and `MAX_UPLOAD_BYTES = 10 * 1024 * 1024`; decode UTF-8 for text formats; parse `word/document.xml` `<w:t>` runs for `.docx`; extract readable text streams or return structured metadata fallback note for scanned/binary `.pdf` without crashing.
- `ai_engine.py`: Query `official_documents` respecting department isolation; build grounded responses for `soan_thao` / `nghiep_vu` / `tham_dinh`; generate 3 structured options (`Phương án A`, `B`, `C`) for `M02`; generate Decree 30/2020/NĐ-CP compliant drafts and evaluate all 5 audit criteria (flagging missing Quốc hiệu, missing `Căn cứ`, authority mismatch, date/number inconsistencies, and colloquial phrases) for `M03`; implement 4 session file processors (`tom_tat`, `trich_xuat`, `doi_chieu`, `tong_hop`) for `M05`. If an active `api_connectors` row has a non-empty `api_key`, invoke `httpx` to its `/chat/completions` endpoint with graceful fallback on network error.
- Mount `workspace.router` in `backend/main.py` and call `init_db()` on startup.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest discover -s backend/tests -v`
Expected: PASS across all backend tests.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): add document parser, AI synthesis engine, and M01-M03 endpoints"
```

---

### Task 3: Backend Official Docs (M04), Session Files (M05), Task Ops (M06) & Admin/Clone APIs (M07)

**Files:**
- Create: `backend/routers/docs_and_files.py`
- Create: `backend/routers/ops_and_admin.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_docs_ops_admin.py`

**Interfaces:**
- Consumes: `backend/db.py`, `backend/schemas.py`, `backend/services/doc_parser.py`, `backend/services/ai_engine.py`
- Produces:
  - `docs_and_files.py`: `GET/POST /api/m04/documents`, `GET/POST /api/m04/update-requests`, `POST /api/m05/sessions/{session_id}/upload`, `POST /api/m05/sessions/{session_id}/process`
  - `ops_and_admin.py`: `GET/POST /api/m06/tasks`, `PATCH /api/m06/tasks/{task_id}`, `GET/POST /api/m07/users`, `DELETE /api/m07/users/{user_id}`, `PUT /api/m07/departments/{dept_id}/instruction`, `GET /api/m07/api-connectors`, `PUT /api/m07/api-connectors/{connector_id}`, `GET /api/m07/audit-logs`, `GET /api/m07/tenants`, `POST /api/m07/clone-tenant`

- [ ] **Step 1: Write the failing test in `backend/tests/test_docs_ops_admin.py` (pinning Review Focus #2, #3, #4, #5)**

```python
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class DocsOpsAdminTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.tmp.name)
        os.environ["UBND_DB_PATH"] = str(self.base_dir / "main.db")
        init_db()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_private_documents_enforce_department_isolation(self) -> None:
        self.client.post("/api/m04/documents", json={
            "doc_number": "NB-VP-01/2026",
            "title": "Sổ tay nội bộ Văn phòng",
            "doc_type": "Quy chế",
            "tier": "kho_rieng",
            "department_id": "VP",
            "issuer": "Văn phòng UBND",
            "issued_date": "2026-10-01",
            "summary": "Tài liệu riêng VP",
            "content": "Chỉ cán bộ VP được xem",
        })
        kt_docs = self.client.get("/api/m04/documents", params={"department_id": "KT"}).json()["documents"]
        vp_docs = self.client.get("/api/m04/documents", params={"department_id": "VP"}).json()["documents"]
        self.assertFalse(any(d["doc_number"] == "NB-VP-01/2026" for d in kt_docs))
        self.assertTrue(any(d["doc_number"] == "NB-VP-01/2026" for d in vp_docs))

    def test_upload_rejects_unsupported_extension_and_processes_discrepancies(self) -> None:
        bad = self.client.post(
            "/api/m05/sessions/s-up/upload",
            files={"file": ("virus.exe", b"MZ123", "application/octet-stream")},
        )
        self.assertEqual(bad.status_code, 400)

        self.client.post(
            "/api/m05/sessions/s-up/upload",
            files={"file": ("don_de_nghi.txt", "Chủ hộ: Nguyễn Văn A. Diện tích: 120 m2. Ngày: 10/10/2026".encode(), "text/plain")},
        )
        self.client.post(
            "/api/m05/sessions/s-up/upload",
            files={"file": ("bien_ban.txt", "Chủ hộ: Nguyễn Văn A. Diện tích: 145 m2. Ngày: 15/10/2026".encode(), "text/plain")},
        )
        proc = self.client.post("/api/m05/sessions/s-up/process", json={"action": "doi_chieu", "department_id": "NNMT"})
        self.assertEqual(proc.status_code, 200)
        self.assertIn("120", proc.json()["result_markdown"] + str(proc.json()["highlights"]))

    def test_m06_task_lifecycle_and_reminder(self) -> None:
        created = self.client.post("/api/m06/tasks", json={
            "title": "Báo cáo thu chi ngân sách tháng 11",
            "description": "Tổng hợp biểu mẫu trình Chủ tịch UBND",
            "department_id": "KT",
            "assignee": "Trần Thị B",
            "due_date": "2026-11-25",
            "priority": "cao",
            "ref_doc_number": "CV-112/UBND",
        })
        self.assertEqual(created.status_code, 200)
        tid = created.json()["id"]
        patched = self.client.patch(f"/api/m06/tasks/{tid}", json={"progress": 65, "status": "dang_thuc_hien", "remind": True})
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json()["reminder_count"], 1)

    def test_admin_masks_api_keys_and_blocks_non_owner_mutations(self) -> None:
        owner_headers = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        connectors = self.client.get("/api/m07/api-connectors", headers=owner_headers).json()["connectors"]
        cid = connectors[0]["id"]
        self.client.put(
            f"/api/m07/api-connectors/{cid}",
            headers=owner_headers,
            json={"name": "OpenAI Gateway", "provider": "openai", "base_url": "https://api.openai.com/v1", "model_name": "gpt-4o-mini", "api_key": "sk-super-secret-1234", "active": False},
        )
        masked = self.client.get("/api/m07/api-connectors", headers=owner_headers).json()["connectors"][0]["api_key_masked"]
        self.assertNotIn("super-secret", masked)
        self.assertTrue(masked.endswith("1234"))

        forbidden = self.client.post(
            "/api/m07/users",
            headers={"X-Actor-Email": "canbo.kt@ubnd.vn"},
            json={"email": "new@ubnd.vn", "full_name": "Lê C", "position": "Công chức", "role": "officer", "department_id": "KT", "private_repo_access": True},
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_clone_tenant_sanitizes_slug_and_prevents_overwrite(self) -> None:
        owner_headers = {"X-Actor-Email": "tsh.co@tshorg.vn"}
        res1 = self.client.post("/api/m07/clone-tenant", headers=owner_headers, json={
            "commune_name": "../UBND Phường Bến Nghé",
            "admin_email": "admin.bennghe@tphcm.gov.vn",
        })
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["slug"], "ubnd-phuong-ben-nghe")
        self.assertTrue(Path(res1.json()["db_path"]).exists())

        dup = self.client.post("/api/m07/clone-tenant", headers=owner_headers, json={
            "commune_name": "UBND Phường Bến Nghé",
            "admin_email": "admin2@tphcm.gov.vn",
        })
        self.assertEqual(dup.status_code, 409)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest backend/tests/test_docs_ops_admin.py -v`
Expected: FAIL (`404 Not Found` on `/api/m04/...`).

- [ ] **Step 3: Implement `docs_and_files.py`, `ops_and_admin.py`, and wire into `backend/main.py`**

- Implement department-isolated SQL queries in `docs_and_files.py` (`WHERE (tier != 'kho_rieng' OR department_id IN (?, 'ALL'))`), update-request creation/listing, multipart upload (`HTTPException(400)` / `HTTPException(413)` on `ValueError`), and 4-action session file processing (including numerical/date cross-file discrepancy detection in `doi_chieu`).
- Implement `ops_and_admin.py` with KPI aggregation, task CRUD + reminder increment, `require_owner(x_actor_email)` dependency returning `HTTPException(403)`, `mask_secret()`, Unicode diacritic stripping (`unicodedata.normalize("NFKD", ...)` + `đ -> d`) into `[a-z0-9-]+` slug for `clone-tenant` placing cloned DBs in `get_db_path().parent / "tenants" / f"{slug}.db"`, and HTTP `409` on conflict.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest discover -s backend/tests -v`
Expected: PASS across all backend test files.

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat(backend): add M04-M07 endpoints with RBAC isolation and multi-tenant cloning"
```

---

### Task 4: Frontend Typed API Client, Session Helper & Shared TSH Workspace Layout

**Files:**
- Modify: `app/app/lib/api.ts`
- Create: `app/app/lib/session.ts`
- Create: `app/app/components/layout/workspace-shell.tsx`
- Create: `app/app/routes/workspace-layout.tsx`
- Modify: `app/app/routes.ts`
- Test: `app/tests/api-client.test.ts`

**Interfaces:**
- Consumes: Backend `/api/departments`, `/api/m07/users`, and all module contracts from Tasks 1–3
- Produces:
  - `app/app/lib/api.ts`: Preserves `fetchBackendHello`, adds `resolveServerApiBase(): string`, `apiRequest<T>(path: string, opts?: { method?: string; body?: unknown; baseUrl?: string; actorEmail?: string }): Promise<T>`, `uploadSessionFile(sessionId: string, file: File, actorEmail?: string): Promise<SessionState>`, plus TypeScript interfaces `Department`, `AssistantMode`, `SessionState`, `OfficialDoc`, `DocUpdateRequest`, `TaskItem`, `TasksOverview`, `RbacUser`, `ApiConnector`, `AuditLogEntry`, `ClonedTenant`.
  - `app/app/lib/session.ts`: `getOrInitSessionId(): string`, `rotateSessionId(): string`, `getActiveActorEmail(): string`, `setActiveActorEmail(email: string): void`.
  - `app/app/components/layout/workspace-shell.tsx`: `<WorkspaceShell departments={...} users={...} currentDeptId={...} />` rendering the `#0F172A` `268px` sidebar with 12 TSH navigation links, 4-department selector (`?dept=`), top bar (`UBND CẤP XÃ · HỆ THỐNG NỘI BỘ`, `↑ Tải tài liệu tham khảo`, `+ Kiểm tra văn bản`), accountability banner, and `<Outlet />`.

- [ ] **Step 1: Write the failing test in `app/tests/api-client.test.ts`**

```ts
import test from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import { apiRequest } from "../app/lib/api.ts";
import { createMemorySessionManager } from "../app/lib/session.ts";

test("apiRequest sends JSON body and X-Actor-Email header and parses response", async () => {
  let receivedActor = "";
  const server = http.createServer((req, res) => {
    receivedActor = String(req.headers["x-actor-email"] ?? "");
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true }));
  });
  await new Promise<void>((r) => server.listen(0, "127.0.0.1", r));
  const port = (server.address() as { port: number }).port;

  try {
    const res = await apiRequest<{ ok: boolean }>("/api/departments", {
      baseUrl: `http://127.0.0.1:${port}`,
      actorEmail: "tsh.co@tshorg.vn",
    });
    assert.equal(res.ok, true);
    assert.equal(receivedActor, "tsh.co@tshorg.vn");
  } finally {
    server.close();
  }
});

test("session manager rotates session ID cleanly on wipe", () => {
  const mgr = createMemorySessionManager();
  const first = mgr.getOrInitSessionId();
  const second = mgr.rotateSessionId();
  assert.notEqual(first, second);
  assert.equal(mgr.getOrInitSessionId(), second);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/fedora/Documents/UBND-AI-Support/app && npm test`
Expected: FAIL (`apiRequest` and `session.ts` not yet defined).

- [ ] **Step 3: Implement `api.ts`, `session.ts`, `workspace-shell.tsx`, `workspace-layout.tsx`, and placeholder module routes in `routes.ts`**

Configure `app/app/routes.ts` with `layout("routes/workspace-layout.tsx", [...7 module routes...])` plus `route("hello-check", "routes/home.tsx")`. Create minimal typed stub files for the 7 route modules (`m01-assistant.tsx` .. `m07-admin.tsx`) so `npm run typecheck` succeeds immediately at the end of Task 4 before Tasks 5–7 fill in each module's full UI.

- [ ] **Step 4: Run tests and typecheck to verify they pass**

Run: `cd /home/fedora/Documents/UBND-AI-Support/app && npm test && npm run typecheck`
Expected: PASS (0 test failures, 0 TypeScript errors).

- [ ] **Step 5: Commit**

```bash
git add app/
git commit -m "feat(frontend): add typed API client, session manager, and TSH workspace shell"
```

---

### Task 5: Frontend Modules 01 & 02 — Trợ lý AI theo nghiệp vụ & AI kiến thức mở rộng

**Files:**
- Modify: `app/app/routes/m01-assistant.tsx`
- Modify: `app/app/routes/m02-extended.tsx`

**Interfaces:**
- Consumes: `apiRequest`, `uploadSessionFile`, `AssistantMode`, `SessionState` from `~/lib/api`; `getOrInitSessionId`, `rotateSessionId`, `getActiveActorEmail` from `~/lib/session`; `?dept=` search param from URL
- Produces:
  - Interactive Module 01 route (`/`) matching Page 1 & 2 of the TSH Profile PDF
  - Interactive Module 02 route (`/kien-thuc-mo-rong`) with 3-option comparison & handoff link `/soan-thao-kiem-tra?dept=...&title=...&points=...`

- [ ] **Step 1: Implement `app/app/routes/m01-assistant.tsx`**

Build the exact TSH workspace card:
- Header: `TRỢ LÝ NGHIỆP VỤ · {dept.name.toUpperCase()}`, title `Anh/chị cần xử lý công việc gì?`, file upload button `↑ Tải thêm tài liệu ({files.length} tệp)` calling `uploadSessionFile`, and red button `Kết thúc phiên - Xóa bộ nhớ` calling `DELETE /api/sessions/{sessionId}` + `rotateSessionId()` + clearing chat state.
- 3 selectable mode cards (`soan_thao` / `SOẠN THẢO`, `nghiep_vu` / `NGHIỆP VỤ`, `tham_dinh` / `THẨM ĐỊNH`).
- Empty state (`Ta nên bắt đầu việc gì?`, quick starter pills `Xử lý hồ sơ`, `Soạn văn bản`, `Kiểm tra thẩm quyền`) switching cleanly to message history list with clickable cited official document badges when messages exist.
- Composer textarea (`Enter` to send, `Shift + Enter` for newline) + footer caption `Enter để gửi · Shift + Enter để xuống dòng · Tài liệu chỉ được dùng trong phiên hiện tại`.

- [ ] **Step 2: Implement `app/app/routes/m02-extended.tsx`**

Build the external-knowledge scope notice banner, topic & local context form calling `POST /api/m02/analyze`, and 3 side-by-side `Card` columns (`Phương án A`, `Phương án B`, `Phương án C`) displaying Pros, Cons, Commune Feasibility badge, and a `Chuyển sang dự thảo Kế hoạch` button navigating to `/soan-thao-kiem-tra` with prefilled query params.

- [ ] **Step 3: Run typecheck and build to verify**

Run: `cd /home/fedora/Documents/UBND-AI-Support/app && npm test && npm run typecheck && npm run build`
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add app/app/routes/m01-assistant.tsx app/app/routes/m02-extended.tsx
git commit -m "feat(frontend): implement Module 01 AI assistant and Module 02 extended analysis"
```

---

### Task 6: Frontend Modules 03, 04 & 05 — Soạn thảo & Kiểm tra, Nguồn văn bản & Xử lý tài liệu

**Files:**
- Modify: `app/app/routes/m03-drafting.tsx`
- Modify: `app/app/routes/m04-official-docs.tsx`
- Modify: `app/app/routes/m05-doc-session.tsx`

**Interfaces:**
- Consumes: `/api/m03/draft`, `/api/m03/audit`, `/api/m04/documents`, `/api/m04/update-requests`, `/api/m05/sessions/{session_id}/upload`, `/api/m05/sessions/{session_id}/process`, `/api/sessions/{session_id}`
- Produces:
  - Interactive Module 03 (`/soan-thao-kiem-tra`), Module 04 (`/nguon-van-ban`), and Module 05 (`/xu-ly-tai-lieu`) views

- [ ] **Step 1: Implement `app/app/routes/m03-drafting.tsx`**

2-column layout:
- Left: Document type selector (`Kế hoạch`, `Báo cáo`, `Quyết định`, `Thông báo`, `Công văn`), title & key points inputs (auto-populated when navigated from Module 02), `Soạn dự thảo chuẩn NĐ 30` button (`POST /api/m03/draft`), editable monospace/document `<Textarea>`, Copy & Download `.txt` buttons, and `Kiểm tra văn bản` button (`POST /api/m03/audit`).
- Right: Score `/100` `Progress` bar + 5 criteria cards (*Bố cục & Thể thức*, *Căn cứ pháp lý*, *Thẩm quyền ban hành*, *Tính logic & Thống nhất*, *Chính tả & Văn phong hành chính*) with `Đạt chuẩn` / `Cần rà soát` / `Không đạt` badges and actionable suggestions.

- [ ] **Step 2: Implement `app/app/routes/m04-official-docs.tsx`**

`loader` fetches `/api/m04/documents` (filtered by `?dept=`, `?tier=`, `?q=`) and `/api/m04/update-requests`. Render search input, tabs (`Tất cả`, `Trung ương`, `Địa phương`, `Kho riêng đơn vị`, and `Đề nghị cập nhật` synced with `?tab=de-nghi`), document detail preview `Dialog`, `+ Thêm văn bản kho riêng` dialog, and `+ Gửi đề nghị cập nhật văn bản` form.

- [ ] **Step 3: Implement `app/app/routes/m05-doc-session.tsx`**

Share the same `sessionId` as Module 01 (`getOrInitSessionId()`). Render ephemeral privacy banner + `Kết thúc phiên - Xóa bộ nhớ` button, multi-file upload zone (`.txt`, `.md`, `.docx`, `.pdf`), active session file list with extracted character count & `parse_note`, and 4 action buttons/tabs (`tom_tat`, `trich_xuat`, `doi_chieu`, `tong_hop`) rendering structured results and discrepancy highlights.

- [ ] **Step 4: Run typecheck and build to verify**

Run: `cd /home/fedora/Documents/UBND-AI-Support/app && npm test && npm run typecheck && npm run build`
Expected: PASS with 0 errors.

- [ ] **Step 5: Commit**

```bash
git add app/app/routes/m03-drafting.tsx app/app/routes/m04-official-docs.tsx app/app/routes/m05-doc-session.tsx
git commit -m "feat(frontend): implement Module 03 drafting/audit, Module 04 legal docs, and Module 05 session files"
```

---

### Task 7: Frontend Modules 06 & 07 — Điều hành công việc & Phân quyền / Quản trị / Nhân bản AI

**Files:**
- Modify: `app/app/routes/m06-tasks.tsx`
- Modify: `app/app/routes/m07-admin.tsx`

**Interfaces:**
- Consumes: `/api/m06/tasks`, `/api/m07/users`, `/api/m07/departments/{id}/instruction`, `/api/m07/api-connectors`, `/api/m07/audit-logs`, `/api/m07/tenants`, `/api/m07/clone-tenant`
- Produces:
  - Interactive Module 06 (`/dieu-hanh-cong-viec`) and Module 07 (`/quan-tri-he-thong` supporting `?tab=phan-quyen | instruction | api | nhat-ky | nhan-ban`)

- [ ] **Step 1: Implement `app/app/routes/m06-tasks.tsx`**

`loader` fetches `/api/m06/tasks`. Render 4 KPI `Card`s (*Tổng nhiệm vụ*, *Đang thực hiện*, *Sắp đến hạn*, *Hoàn thành*), department filter pills (`Tất cả`, `VP`, `KT`, `VHXH`, `NNMT`), `+ Giao nhiệm vụ mới` `Dialog`, and task `Table` with inline progress/status controls and `Nhắc việc` button (`PATCH /api/m06/tasks/{id}`).

- [ ] **Step 2: Implement `app/app/routes/m07-admin.tsx`**

`loader` fetches users, departments, masked API connectors, audit logs, and cloned tenants. Sync active tab with `?tab=` so all 5 admin sidebar items open their exact section:
1. `phan-quyen`: RBAC table across the 4 departments + add/delete user actions (displaying clear `403` permission notice if switched to a non-owner officer account).
2. `instruction`: Per-department `Textarea` editor saving `PUT /api/m07/departments/{deptId}/instruction`.
3. `api`: Connector form (`base_url`, `model_name`, `api_key` write-only input with masked display, `active` `Switch`).
4. `nhat-ky`: Chronological audit log table with module & department badges.
5. `nhan-ban`: **Nhân bản hệ thống AI độc lập** form (`commune_name`, `admin_email`) calling `POST /api/m07/clone-tenant` and listing provisioned commune instances with their isolated SQLite paths and slugs.

- [ ] **Step 3: Run typecheck and build to verify**

Run: `cd /home/fedora/Documents/UBND-AI-Support/app && npm test && npm run typecheck && npm run build`
Expected: PASS with 0 errors.

- [ ] **Step 4: Commit**

```bash
git add app/app/routes/m06-tasks.tsx app/app/routes/m07-admin.tsx
git commit -m "feat(frontend): implement Module 06 task ops and Module 07 RBAC/multi-tenant admin"
```

---

### Task 8: Cross-Module End-to-End Verification & Live Server Readiness

**Files:**
- Create: `backend/tests/test_e2e_workflow.py`

**Interfaces:**
- Consumes: Complete `backend` FastAPI app + `app` React Router production build
- Produces: End-to-end automated proof across all 7 modules + verified running dev servers

- [ ] **Step 1: Write `backend/tests/test_e2e_workflow.py` exercising all 7 modules in one continuous commune workflow**

```python
import os
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.db import init_db
from backend.main import app


class FullSevenModuleWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["UBND_DB_PATH"] = str(Path(self.tmp.name) / "e2e.db")
        init_db()
        self.client = TestClient(app)
        self.owner = {"X-Actor-Email": "tsh.co@tshorg.vn"}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_end_to_end_seven_module_workflow(self) -> None:
        sid = "e2e-session-01"
        # M05: Upload temporary dossier
        up = self.client.post(
            f"/api/m05/sessions/{sid}/upload",
            files={"file": ("ho_so_tthc.txt", "Hồ sơ đăng ký khai sinh quá hạn của công dân Lê Văn D".encode(), "text/plain")},
        )
        self.assertEqual(up.status_code, 200)
        self.assertEqual(len(up.json()["files"]), 1)

        # M01: Consult business regulations using uploaded dossier
        chat = self.client.post("/api/m01/chat", json={
            "session_id": sid,
            "department_id": "VP",
            "mode": "tham_dinh",
            "message": "Thẩm định hồ sơ hộ tịch vừa tải lên",
        })
        self.assertEqual(chat.status_code, 200)
        self.assertIn("Lê Văn D", chat.json()["reply"]["content"])

        # M02: Analyze extended options
        ext = self.client.post("/api/m02/analyze", json={
            "department_id": "VP",
            "topic": "Rút ngắn thời gian trả kết quả hộ tịch",
            "context": "",
        })
        self.assertEqual(ext.status_code, 200)
        self.assertEqual(len(ext.json()["options"]), 3)

        # M03: Generate & audit draft
        draft = self.client.post("/api/m03/draft", json={
            "department_id": "VP",
            "doc_type": "Công văn",
            "title": "Xác minh tình trạng hộ tịch",
            "key_points": "Phối hợp xác minh nơi cư trú trước đây",
        }).json()["draft_text"]
        audit = self.client.post("/api/m03/audit", json={
            "department_id": "VP",
            "doc_type": "Công văn",
            "draft_text": draft,
        })
        self.assertEqual(audit.status_code, 200)
        self.assertEqual(len(audit.json()["criteria"]), 5)

        # M04: Submit official document update request
        req = self.client.post("/api/m04/update-requests", json={
            "doc_number": "TT-04/2026/TT-BTP",
            "title": "Thông tư hướng dẫn hộ tịch điện tử",
            "tier": "trung_uong",
            "department_id": "VP",
            "reason": "Bổ sung biểu mẫu mới",
            "requested_by": "tsh.co@tshorg.vn",
        })
        self.assertEqual(req.status_code, 200)

        # M06: Create task
        task = self.client.post("/api/m06/tasks", json={
            "title": "Trả kết quả hộ tịch hồ sơ Lê Văn D",
            "description": "Hoàn tất trước 16h00",
            "department_id": "VP",
            "assignee": "Nguyễn Thị Hộ Tịch",
            "due_date": "2026-11-20",
            "priority": "cao",
            "ref_doc_number": "HS-2026-88",
        })
        self.assertEqual(task.status_code, 200)

        # M07: Update room instruction, clone new ward tenant, check audit logs
        inst = self.client.put(
            "/api/m07/departments/VP/instruction",
            headers=self.owner,
            json={"instruction": "Ưu tiên viện dẫn Luật Hộ tịch và Nghị định 30/2020/NĐ-CP."},
        )
        self.assertEqual(inst.status_code, 200)
        clone = self.client.post(
            "/api/m07/clone-tenant",
            headers=self.owner,
            json={"commune_name": "UBND Phường Hòa Cường", "admin_email": "admin@hoacuong.gov.vn"},
        )
        self.assertEqual(clone.status_code, 200)

        # M01/M05: Wipe ephemeral session memory
        self.client.delete(f"/api/sessions/{sid}")
        after = self.client.get(f"/api/sessions/{sid}").json()
        self.assertEqual(after["files"], [])
        self.assertEqual(after["messages"], [])

        logs = self.client.get("/api/m07/audit-logs", headers=self.owner).json()["logs"]
        self.assertGreaterEqual(len(logs), 5)
```

- [ ] **Step 2: Run the complete verification suite across Backend and Frontend**

Run:
```bash
cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/python -m unittest discover -s backend/tests -v
cd /home/fedora/Documents/UBND-AI-Support/app && npm test && npm run typecheck && npm run build
```
Expected: 100% PASS across all Python tests, Node tests, TypeScript checks, and production SSR/client builds.

- [ ] **Step 3: Commit final verification suite**

```bash
git add backend/tests/test_e2e_workflow.py
git commit -m "test(e2e): verify complete 7-module commune AI workflow"
```

