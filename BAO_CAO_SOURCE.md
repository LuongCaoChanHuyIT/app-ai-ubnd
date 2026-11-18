# BÁO CÁO TỔNG HỢP & GIẢI PHẪU MÃ NGUỒN — BỘ TRỢ LÝ AI UBND XÃ, PHƯỜNG (`UBND-AI-Support`)

> **Tài liệu thiết kế gốc:** Hồ sơ giới thiệu Bộ Trợ lý AI UBND xã, phường (TSH) & Hệ thống pháp luật hành chính nhà nước Việt Nam hiện hành (Luật Tổ chức chính quyền địa phương `65/2025/QH15`, Nghị định `30/2020/NĐ-CP`, Luật Đất đai `31/2024/QH15`, Luật Bảo vệ môi trường `72/2020/QH14`, Luật Ngân sách nhà nước `83/2015/QH13`, Nghị định `20/2021/NĐ-CP` & `76/2024/NĐ-CP`).
> **Trạng thái kiểm định:** **`76/76` bài kiểm thử tự động PASS (`100%`)** · `0` lỗi TypeScript · Build Production SSR + Client sạch · Đã kiểm định trực quan trên trình duyệt qua đủ **5 tài khoản** và kịch bản nhân bản độc lập **`Phường Bến Nghé`**.

---

## 1. Tổng Quan Kiến Trúc & Công Nghệ (Tech Stack)

| Tầng hệ thống | Công nghệ sử dụng | Quy mô thực tế | Vai trò kiến trúc |
| :--- | :--- | :--- | :--- |
| **Frontend (SSR + SPA)** | React `19.3` · React Router `v8.5` (Framework Mode) · TypeScript · Vite `8` · Tailwind CSS `v4.2` · `shadcn/ui` (`63` primitives) | **`7.006` LOC** ứng dụng + **`657` LOC** test | Giao diện 7 mô-đun xuyên suốt, đồng bộ Cookie/Header cho SSR & Client, bảng Markdown GFM & khối văn bản `<pre>` chuẩn `1280px`. |
| **Backend API & Domain AI** | Python `3.15` · FastAPI · Pydantic `v2` · `pypdf` · `python-docx` · Uvicorn | **`5.261` LOC** ứng dụng + **`1.702` LOC** test | Cung cấp **30 REST API operations**, xác thực Zero-Trust RBAC, suy luận hành chính cấp xã, kiểm định thể thức NĐ 30/2020 và đối chiếu hồ sơ. |
| **Lưu trữ Bền vững & Tạm thời** | SQLite (`ubnd_ai.db` & `tenants/<slug>.db`) + `EphemeralSessionStore` trên RAM | **`9` bảng SQL** + RAM cô lập 4 chiều | Cô lập cứng dữ liệu giữa đơn vị gốc và từng xã/phường nhân bản; xóa sạch 100% lịch sử chat và tệp phiên trên RAM khi kết thúc phiên. |
| **Kho Tri thức Pháp luật** | Seed tự động khi khởi tạo đơn vị gốc hoặc nhân bản đơn vị mới | **`36` văn bản chuyên sâu** | Phủ kín 4 phòng (`VP`: 10, `KT`: 8, `VHXH`: 8, `NNMT`: 10) gồm 27 văn bản Trung ương, 01 văn bản Địa phương và 08 sổ tay Kho riêng nội bộ. |

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                   FRONTEND — REACT ROUTER FRAMEWORK MODE (:5173)                     │
│  • WorkspaceShell: Hiển thị tên đơn vị vận hành, Công tắc chuyển xã/phường độc lập,  │
│    Khóa cứng combobox phòng đối với Cán bộ (Officer), Ẩn khu vực Quản trị M07        │
│  • Đồng bộ danh tính kép: Cookie (ubnd_actor_email, ubnd_tenant_slug cho SSR loader) │
│    + HTTP Header (X-Actor-Email, X-Tenant-Slug cho Client fetch & Upload multipart)  │
└──────────────────────────────────────────┬───────────────────────────────────────────┘
                                           │ HTTP / JSON / Multipart (Zero-Trust Auth)
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND — FASTAPI ZERO-TRUST (:8000)                          │
│  • backend/auth.py: Chặn 401 truy vấn ẩn danh, chặn 403 truy cập chéo phòng / M07,   │
│    định tuyến động tới đúng tệp SQLite của xã/phường đang vận hành                   │
│  • Routers: workspace.py (M01–M03) · docs_and_files.py (M04–M05) · ops_and_admin.py  │
├──────────────────────────────────────────┬───────────────────────────────────────────┘
│  4 Động Cơ Nghiệp Vụ (backend/services/):│  Lưu Trữ Cô Lập (backend/db.py):
│  • legal_kb.py: Truy hồi pháp lý tiếng   │  • Đơn vị gốc: backend/data/ubnd_ai.db
│    Việt (bigram/trigram, chống lạc đề)   │  • Đơn vị nhân bản: tenants/<slug>.db
│  • ai_engine.py: Suy luận M01 & M02      │  • RAM: EphemeralSessionStore theo khóa
│  • nd30_engine.py: Thể thức NĐ 30/2020   │    (tenant_slug, email, dept_id, sid)
│  • dossier_diff.py & doc_parser.py (M05) │
└──────────────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 2. Cây Thư Mục Mã Nguồn Chính

```text
UBND-AI-Support/
├── BAO_CAO_SOURCE.md                         # Báo cáo tổng hợp & giải phẫu mã nguồn (tệp hiện tại)
├── Profile_gioi_thieu_Bo_Tro_ly_AI_UBND_xa_phuong_TSH.pdf
├── backend/                                  # Phân hệ Backend Python / FastAPI
│   ├── main.py                               # Điểm vào FastAPI, CORS, lifespan init_db
│   ├── auth.py                               # Zero-Trust RBAC (Cookie + Header) & Multi-Tenant resolver
│   ├── db.py                                 # Lược đồ 9 bảng SQLite, Seed 36 văn bản & EphemeralSessionStore
│   ├── schemas.py                            # Lược đồ dữ liệu Pydantic v2 cho toàn bộ 7 mô-đun
│   ├── routers/
│   │   ├── workspace.py                      # Bootstrap, Quản lý phiên RAM, API M01, M02, M03
│   │   ├── docs_and_files.py                 # Kho văn bản & Duyệt cập nhật M04, Upload & Đối chiếu M05
│   │   └── ops_and_admin.py                  # Điều hành công việc M06, Quản trị RBAC/API/Log/Nhân bản M07
│   ├── services/
│   │   ├── legal_kb.py                       # Tách câu hỏi đa vế & tìm kiếm pháp lý tiếng Việt chống lạc đề
│   │   ├── ai_engine.py                      # Điều phối M01 (3 chế độ) & M02 (3 phương án A/B/C theo ngành)
│   │   ├── nd30_engine.py                    # Sinh dự thảo & Chấm điểm 5 tiêu chí chuẩn NĐ 30/2020/NĐ-CP
│   │   ├── dossier_diff.py                   # Bóc tách 8 trường thực thể & lập bảng đối chiếu sai lệch M05
│   │   └── doc_parser.py                     # Đọc an toàn .txt/.md/.csv/.json/.docx/.pdf trên RAM (≤10MB)
│   └── tests/                                # 7 tệp kiểm thử tự động Backend (48 test cases)
├── app/                                      # Phân hệ Frontend React Router Framework Mode
│   ├── app/
│   │   ├── routes.ts                         # Định nghĩa cây định tuyến 7 mô-đun
│   │   ├── components/
│   │   │   ├── layout/workspace-shell.tsx    # Khung làm việc 4 bộ phận, chuyển đổi tài khoản & xã/phường
│   │   │   └── ui/                           # formatted-markdown.tsx + 63 shadcn/ui components
│   │   ├── lib/
│   │   │   ├── api.ts & session.ts           # HTTP client, đồng bộ Cookie/Header, cô lập phiên 4 chiều
│   │   │   ├── markdown-helpers.ts           # Parser bảng GFM, khối <pre>, blockquote, inline code lồng bold
│   │   │   └── m01-m02 / m03-m05 / m06-m07   # Hồ sơ mẫu lệch số liệu 4 phòng, RBAC & liên thông M03/M06
│   │   └── routes/                           # workspace-layout.tsx và 7 tuyến m01..m07 chuyên biệt
│   └── tests/                                # 7 tệp kiểm thử tự động Frontend (28 test cases)
└── docs/
    └── BAO_CAO_TONG_HOP_SOURCE.md            # Bản sao báo cáo lưu trong thư mục tài liệu kỹ thuật
```

---

## 3. Bảng Giải Phẫu Chi Tiết 26 Thành Phần Mã Nguồn & Kiểm Thử

| STT | Phân lớp / Mô-đun | Đường dẫn tệp mã nguồn | Dung lượng | Thành phần / API / Hàm cốt lõi | Chức năng nghiệp vụ & Cơ chế bảo mật | Trạng thái |
| :-: | :--- | :--- | :-: | :--- | :--- | :-: |
| 1 | **Backend Core** | `backend/main.py` | 68 dòng | `app`, `lifespan()`, `health_check()`, `say_hello()` | Khởi tạo FastAPI, cấu hình CORS an toàn, tự động chạy `init_db()` và gắn kết 3 nhóm router API (`30` operations). | PASS |
| 2 | **Database & Seed** | `backend/db.py` | 1.173 dòng | `SCHEMA_SQL` (9 bảng), `init_db()`, `EphemeralSessionStore` | Quản trị SQLite Multi-Tenant, seed **36 văn bản pháp luật & sổ tay kho riêng** (4 phòng), 5 tài khoản RBAC và kho phiên RAM 4 chiều. | PASS |
| 3 | **Zero-Trust Auth** | `backend/auth.py` | 131 dòng | `get_actor()`, `require_owner_actor()`, `enforce_dept_scope()`, `resolve_tenant_from_request()` | Đồng bộ xác thực Header + Cookie (`401` nếu ẩn danh), chặn truy cập chéo phòng (`403`) và định tuyến động tới CSDL của xã/phường đang chọn. | PASS |
| 4 | **API Schemas** | `backend/schemas.py` | 124 dòng | `ChatRequest`, `DraftRequest`, `DocUpdateReviewRequest`, `UserPatchRequest`, `CloneTenantRequest` | Kiểm tra kiểu dữ liệu nghiêm ngặt bằng Pydantic v2 cho toàn bộ dữ liệu đầu vào của 7 mô-đun. | PASS |
| 5 | **Router M01–M03** | `backend/routers/workspace.py` | 271 dòng | `/api/bootstrap`, `/api/sessions/*`, `/api/m01/chat`, `/api/m02/analyze`, `/api/m03/*` | Khởi tạo ngữ cảnh đơn vị & tài khoản, xóa sạch bộ nhớ phiên RAM (`WIPE_SESSION`), điều phối chat M01, phân tích M02, soạn/chấm M03. | PASS |
| 6 | **Router M04–M05** | `backend/routers/docs_and_files.py` | 369 dòng | `/api/m04/documents`, `/api/m04/update-requests`, `/api/m05/sessions/*` | Tra cứu kho 3 tầng (cô lập `kho_rieng` theo phòng & quyền), phê duyệt đề nghị tự động nhập kho chính thức, tải & xử lý tệp phiên M05. | PASS |
| 7 | **Router M06–M07** | `backend/routers/ops_and_admin.py` | 551 dòng | `/api/m06/tasks`, `/api/m07/users`, `/api/m07/api-connectors`, `/api/m07/clone-tenant` | Giao việc & tính 4 KPI khớp bộ lọc, bật/tắt quyền Kho riêng, che khóa API `***`, nhật ký kiểm toán & nhân bản xã/phường chống ghi đè (`409`). | PASS |
| 8 | **AI Orchestrator** | `backend/services/ai_engine.py` | 835 dòng | `run_assistant_turn()`, `analyze_extended_options()`, `_try_live_llm()` | Suy luận M01 (3 chế độ, tách câu hỏi đa vế, phân định thẩm quyền cấp xã) & M02 (3 phương án A/B/C chuyên biệt theo ngành + MTTQ/đoàn thể). | PASS |
| 9 | **Động cơ NĐ 30/2020** | `backend/services/nd30_engine.py` | 839 dòng | `build_nd30_draft()`, `audit_nd30_draft()`, `clean_subject_title()`, `parse_commune_identity()` | Lấy động tên/địa danh xã phường, ký hiệu Phụ lục I, khử lặp `"Về việc"`, ngữ pháp `"Căn cứ ...;"`, ký `TM. UBND` vs `CHỦ TỊCH`, chấm 5 tiêu chí `/100`. | PASS |
| 10 | **Truy hồi Pháp lý** | `backend/services/legal_kb.py` | 398 dòng | `decompose_question_clauses()`, `search_official_docs_smart()` | Lọc hư từ tiếng Việt, chấm điểm cụm `bigram/trigram` + ngưỡng cắt chống trích lạc đề (tách rõ Điều 235 hòa giải vs Điều 136 cấp GCN Luật Đất đai). | PASS |
| 11 | **Đối chiếu Hồ sơ** | `backend/services/dossier_diff.py` | 370 dòng | `extract_structured_fields()`, `run_structured_session_processing()` | Bóc tách 8 trường thực thể (Họ tên, CCCD, Thửa đất, Tờ bản đồ, `m2`, Số tiền, Ngày tháng, Địa chỉ) & lập bảng đối chiếu `[KHỚP]` / `[SAI LỆCH]`. | PASS |
| 12 | **Giải mã Tệp tin** | `backend/services/doc_parser.py` | 129 dòng | `parse_uploaded_bytes()`, `_extract_docx_text()`, `_extract_pdf_text()` | Đọc trên RAM cho `.txt`, `.md`, `.csv`, `.json`, `.docx`, `.pdf`; chặn `.exe` (`400`) & tệp `>10MB` (`413`), cảnh báo PDF scan thiếu OCR. | PASS |
| 13 | **Cấu hình & Tuyến FE** | `app/package.json`, `app/app/routes.ts`, `app/app/routes/workspace-layout.tsx` | 267 dòng | React `19.3`, React Router `v8.5` SSR, Tailwind `v4`, `loader` `/api/bootstrap` | Khởi tạo SSR có xác thực Cookie, tự phục hồi tenant và tự điều hướng khóa cứng `?dept=` cho vai trò Cán bộ. | PASS |
| 14 | **Khung giao diện chung** | `app/app/components/layout/workspace-shell.tsx` | 655 dòng | `WorkspaceShell`, Sidebar 7 mô-đun, Tenant & Actor Switcher | Hiển thị tên UBND xã/phường đang vận hành, khóa chọn phòng đối với Cán bộ, ẩn M07 khi không phải Owner, chuyển đổi Multi-Tenant tức thời. | PASS |
| 15 | **Bộ dựng Markdown** | `app/app/components/ui/formatted-markdown.tsx` & `app/app/lib/markdown-helpers.ts` | 430 dòng | `FormattedMarkdown`, `parseMarkdownBlocks()`, `parseInlineSpans()` | Render bảng GFM `<table>` chuẩn `1280px`, khối dự thảo `<pre>` monospace, callout blockquote, danh sách đa cấp và `` `code` `` lồng trong bold. | PASS |
| 16 | **Client API & Phiên** | `app/app/lib/api.ts`, `app/app/lib/session.ts` | 735 dòng | `apiRequest()`, `extractServerAuthHeaders()`, `getOrInitSessionId()`, `rotateSessionId()` | Đồng bộ song song Cookie + `localStorage` cho `ubnd_actor_email` & `ubnd_tenant_slug`; cô lập và xoay vòng mã phiên theo từng đơn vị/người/phòng. | PASS |
| 17 | **Helpers Liên thông** | `app/app/lib/m01-m02-helpers.ts`, `m03-m05-helpers.ts`, `m06-m07-helpers.ts` | 531 dòng | `buildM03HandoffUrl()`, `buildM06TaskHandoffUrl()`, `DEPARTMENT_SAMPLE_DOSSIERS` | Bộ 04 hồ sơ mẫu có tình huống sai lệch riêng cho từng phòng (`VP`, `KT`, `VHXH`, `NNMT`), kiểm soát quyền RBAC và tạo URL bàn giao sang M03/M06. | PASS |
| 18 | **Giao diện Mô-đun 01** | `app/app/routes/m01-assistant.tsx` | 576 dòng | `Module01AssistantRoute` (`soan_thao`, `nghiep_vu`, `tham_dinh`) | Trợ lý hội thoại theo phòng (lưu chế độ trong `sessionStorage`), tải tệp tạm, trích dẫn link pháp lý sang M04, giao việc sang M06 & xóa phiên RAM. | PASS |
| 19 | **Giao diện Mô-đun 02** | `app/app/routes/m02-extended.tsx` | 260 dòng | `Module02ExtendedRoute` (Phân tích 3 phương án A/B/C) | So sánh Ưu điểm, Lưu ý hạn chế, Tính khả thi cấp xã trên lưới 3 cột chống tràn chữ tại `1280px` và chuyển thẳng sang dự thảo Kế hoạch M03. | PASS |
| 20 | **Giao diện Mô-đun 03** | `app/app/routes/m03-drafting.tsx` | 470 dòng | `Module03DraftingRoute` (6 loại VB & Chấm điểm 5 tiêu chí) | Chọn thẩm quyền ký (`Tự động` / `Tập thể UBND` / `Cá nhân Chủ tịch`), khung soạn thảo monospace chuẩn NĐ 30/2020, tải `.txt` & chuyển giao việc M06. | PASS |
| 21 | **Giao diện Mô-đun 04** | `app/app/routes/m04-official-docs.tsx` | 842 dòng | `Module04OfficialDocsRoute` (Kho văn bản 3 tầng & Đề nghị cập nhật) | Lọc Trung ương/Địa phương/Kho riêng, cảnh báo giới hạn Kho riêng theo quyền, gửi đề nghị và nút Owner *"Phê duyệt & Nhập kho"* / *"Từ chối"*. | PASS |
| 22 | **Giao diện Mô-đun 05** | `app/app/routes/m05-doc-session.tsx` | 461 dòng | `Module05DocSessionRoute` (`tom_tat`, `trich_xuat`, `doi_chieu`, `tong_hop`) | Tải tệp thực tế hoặc bộ hồ sơ mẫu chuyên ngành của phòng, hiển thị bảng đối chiếu sai lệch sắc nét và tạo nhiệm vụ xác minh hồ sơ sang M06. | PASS |
| 23 | **Giao diện Mô-đun 06** | `app/app/routes/m06-tasks.tsx` | 638 dòng | `Module06TasksRoute` (4 thẻ KPI & Bảng điều hành tiến độ) | Mặc định lọc theo phòng đang chọn, 4 thẻ KPI khớp 100% danh sách lọc, nhận dữ liệu bàn giao từ M01/M03/M05, cập nhật `+25%` và gửi `Nhắc việc`. | PASS |
| 24 | **Giao diện Mô-đun 07** | `app/app/routes/m07-admin.tsx` | 1.052 dòng | `Module07AdminRoute` (5 phân khu quản trị độc quyền Owner) | Bật/tắt quyền Kho riêng trực tiếp, Instruction 4 phòng, Cổng API che khóa `***`, Nhật ký hệ thống & Nhân bản + Chuyển đổi vận hành xã/phường độc lập. | PASS |
| 25 | **Bộ Test Backend** | `backend/tests/test_*.py` (7 tệp kiểm thử) | 1.702 dòng | **48 test cases** (`unittest` + FastAPI `TestClient`) | Kiểm thử Zero-Trust `401/403`, cô lập RAM 4 chiều, Multi-Tenant, kho 36 văn bản, thể thức NĐ 30/2020, đối chiếu M05 và luồng E2E 7 mô-đun. | **48/48 PASS** |
| 26 | **Bộ Test Frontend** | `app/tests/*.test.ts` (7 tệp kiểm thử) | 657 dòng | **28 test cases** (`node:test`) + `tsc` + Vite SSR Build | Kiểm thử đồng bộ Cookie/Header, khóa RBAC giao diện, parser bảng GFM & `<pre>`, 4 bộ hồ sơ mẫu lệch số liệu và liên thông M03/M06. | **28/28 PASS** |

---

## 4. Lược Đồ 9 Bảng SQLite, Bảo Mật Zero-Trust & Kho 36 Văn Bản Cấp Xã

### 4.1. Lược đồ 9 bảng dữ liệu (`backend/db.py`)
1. `tenant_meta`: Lưu cấu hình định danh đơn vị hành chính (`commune_name`, mặc định `"UBND xã, phường trung tâm"`).
2. `departments`: Cấu hình 4 bộ phận chuyên môn (`VP`, `KT`, `VHXH`, `NNMT`), tóm tắt chức năng và `instruction` riêng của từng phòng.
3. `official_documents`: Lưu trữ văn bản theo 3 tầng (`trung_uong`, `dia_phuong`, `kho_rieng`) gắn mã phòng quản lý.
4. `doc_update_requests`: Lưu yêu cầu đề nghị cập nhật văn bản từ cán bộ (`cho_duyet` -> `da_duyet` / `tu_choi`).
5. `tasks`: Lưu nhiệm vụ giao việc M06 (`cho_xu_ly`, `dang_thuc_hien`, `sap_den_han`, `hoan_thanh`, tiến độ `%`, số lần nhắc việc `reminder_count`).
6. `users_rbac`: Danh sách phân quyền email theo vai trò (`owner` / `officer`), phòng chuyên môn và cờ `private_repo_access`.
7. `api_connectors`: Cấu hình cổng LLM tương thích chuẩn OpenAI (khóa `api_key` luôn được che `***` khi trả qua API).
8. `audit_logs`: Nhật ký kiểm toán mọi thao tác nghiệp vụ, xóa phiên RAM và thay đổi cấu hình quản trị.
9. `cloned_tenants`: Danh mục các đơn vị xã/phường đã nhân bản độc lập (ẩn đường dẫn tệp vật lý máy chủ, chỉ trả `storage_label` an toàn).

### 4.2. Cơ chế cô lập bảo mật 4 chiều
- **Xác thực bắt buộc (`Zero-Trust`):** Xóa bỏ hoàn toàn cơ chế gán mặc định tài khoản chủ sở hữu khi thiếu Header/Cookie; mọi truy vấn không định danh bị từ chối `HTTP 401`.
- **Cô lập phòng chuyên môn (`Department Lock`):** Tài khoản `officer` chỉ được thao tác trong đúng phòng được phân công; mọi hành vi đọc/ghi `kho_rieng`, nhắc việc M06 hoặc truy cập M07 trái thẩm quyền đều bị chặn `HTTP 403`.
- **Cô lập phiên tạm trên RAM (`EphemeralSessionStore`):** Khóa phân vùng `tenant_slug::actor_email::department_id::session_id` bảo đảm chuyển đổi đơn vị, tài khoản hoặc phòng ban không bao giờ làm rò rỉ lịch sử hội thoại M01 hay tệp hồ sơ M05.

### 4.3. Kho 36 văn bản pháp luật & sổ tay nội bộ cấp xã
- **`VP` (10 văn bản):** Luật TCCQĐP `65/2025/QH15`, Nghị định `30/2020/NĐ-CP`, Luật Hộ tịch `60/2014/QH13` & NĐ `123/2015/NĐ-CP`, Luật Tiếp công dân `42/2013/QH13`, Luật Khiếu nại `02/2011/QH13`, Luật Tố cáo `25/2018/QH14`, Nghị định Một cửa `61/2018/NĐ-CP` & `107/2021/NĐ-CP`, Nghị định Chứng thực `23/2015/NĐ-CP` + 02 quy chế `kho_rieng`.
- **`KT` (8 văn bản):** Luật NSNN `83/2015/QH13` & TT `344/2016/TT-BTC` (ngân sách xã), Luật Đầu tư công `58/2024/QH15`, Luật Tài sản công `15/2017/QH14`, Nghị định Hộ kinh doanh `01/2021/NĐ-CP`, Luật Quản lý thuế `38/2019/QH14`, TT `85/2019/TT-BTC` + 02 hướng dẫn kiểm soát thanh toán `kho_rieng`.
- **`VHXH` (8 văn bản):** Nghị định Bảo trợ xã hội `20/2021/NĐ-CP` & `76/2024/NĐ-CP`, Pháp lệnh Người có công `02/2020/UBTVQH14`, Nghị định Lễ hội `110/2018/NĐ-CP`, Nghị định Gia đình văn hóa `86/2023/NĐ-CP`, Nghị định Chuẩn nghèo `07/2021/NĐ-CP`, Luật Trẻ em `102/2016/QH13` + 02 sổ tay `kho_rieng`.
- **`NNMT` (10 văn bản):** Luật Đất đai `31/2024/QH15` (Điều 235 hòa giải 30 ngày, Điều 137–138 niêm yết 15 ngày, Điều 136 thẩm quyền cấp GCN), Nghị định `101/2024/NĐ-CP`, Nghị định xử phạt đất đai `123/2024/NĐ-CP`, Luật BVMT `72/2020/QH14` (Điều 75–77 phân loại rác 3 nhóm), Nghị định `45/2022/NĐ-CP`, Nghị định xây dựng `16/2022/NĐ-CP`, Quyết định NTM `318/2022/QĐ-TTg`, Quyết định địa phương `24/2026/QĐ-UBND` + 02 sổ tay thực địa `kho_rieng`.

---

## 5. Danh Mục 30 REST API Endpoints

| Nhóm | Phương thức & Đường dẫn | Quyền truy cập | Mô tả chức năng |
| :--- | :--- | :--- | :--- |
| **Hệ thống** | `GET /api/health`, `GET /api/hello`, `GET /api/bootstrap` | Công khai / Tenant | Kiểm tra sức khỏe máy chủ và tải cấu hình đơn vị, danh sách phòng, tài khoản mẫu. |
| **Không gian & Phiên** | `GET /api/departments`, `GET /api/sessions/{id}`, `DELETE /api/sessions/{id}` | Đã xác thực (Theo phòng) | Lấy danh sách bộ phận, trạng thái phiên tạm và xóa sạch 100% bộ nhớ RAM của phiên. |
| **Mô-đun 01–03** | `POST /api/m01/chat`, `POST /api/m02/analyze`, `POST /api/m03/draft`, `POST /api/m03/audit` | Đã xác thực (Theo phòng) | Hội thoại 3 chế độ, phân tích 3 phương án mở rộng, sinh dự thảo và chấm điểm 5 tiêu chí NĐ 30/2020. |
| **Mô-đun 04** | `GET /api/m04/documents`, `POST /api/m04/documents`, `GET /api/m04/update-requests`, `POST /api/m04/update-requests`, `PATCH /api/m04/update-requests/{id}/review` | Đã xác thực (`review` chỉ `owner`) | Tra cứu/thêm văn bản, gửi đề nghị cập nhật và phê duyệt tự động nhập vào kho chính thức. |
| **Mô-đun 05** | `POST /api/m05/sessions/{id}/upload`, `POST /api/m05/sessions/{id}/process` | Đã xác thực (Theo phòng) | Tải tệp lên bộ nhớ phiên RAM và chạy 4 chế độ tóm tắt, trích xuất, đối chiếu mâu thuẫn, tổng hợp. |
| **Mô-đun 06** | `GET /api/m06/tasks`, `POST /api/m06/tasks`, `PATCH /api/m06/tasks/{id}` | Đã xác thực (Theo phòng) | Lọc danh sách nhiệm vụ kèm 4 chỉ số KPI đồng bộ, giao nhiệm vụ mới, cập nhật tiến độ & nhắc việc. |
| **Mô-đun 07** | `GET/POST /api/m07/users`, `PATCH/DELETE /api/m07/users/{id}`, `PUT /api/m07/departments/{id}/instruction`, `GET/PUT /api/m07/api-connectors`, `GET /api/m07/audit-logs`, `GET /api/m07/tenants`, `POST /api/m07/clone-tenant` | Độc quyền `owner` (`403` với `officer`) | Quản trị phân quyền email, bật/tắt Kho riêng, sửa Instruction phòng, cấu hình khóa API, xem nhật ký và nhân bản xã/phường. |

---

## 6. Kết Quả Kiểm Thử & Hướng Dẫn Chạy Hệ Thống

### 6.1. Tổng hợp kết quả kiểm định
- **Backend Automated Tests (`unittest`):** **`48/48 PASS`** (`0.72s`, `0` cảnh báo tài nguyên).
- **Frontend Automated Tests (`node:test` + `tsc` + Vite Build):** **`28/28 PASS`** (`~167ms`), `0` lỗi kiểu TypeScript, build thành công cả Client bundle và SSR Server bundle.
- **Browser Adversarial QA (`1280x850` & `1440x900`):** **`100% PASS`** trên toàn bộ 7 mô-đun, 5 tài khoản (`tsh.co@tshorg.vn`, `canbo.vp@ubnd.vn`, `canbo.kt@ubnd.vn`, `canbo.vhxh@ubnd.vn`, `canbo.nnmt@ubnd.vn`) và luồng nhân bản + chuyển sang vận hành trực tiếp **`Phường Bến Nghé`** (`0 console.error`, `0 HTTP 4xx/500`).

### 6.2. Lệnh kiểm thử & khởi chạy nhanh
```bash
# Chạy toàn bộ 48 bài test Backend
cd /home/fedora/Documents/UBND-AI-Support
.venv/bin/python -m unittest discover -s backend/tests -v

# Chạy toàn bộ 28 bài test Frontend + Kiểm tra TypeScript + Build Production
cd /home/fedora/Documents/UBND-AI-Support/app
npm test && npm run typecheck && npm run build

# Khởi chạy máy chủ phát triển (Backend :8000 & Frontend :5173)
cd /home/fedora/Documents/UBND-AI-Support && .venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
cd /home/fedora/Documents/UBND-AI-Support/app && npm run dev -- --host 127.0.0.1 --port 5173
```
