# Báo Cáo Tổng Hợp & Giải Phẫu Mã Nguồn — Bộ Trợ Lý AI UBND Xã, Phường

> **Đơn vị thiết kế nghiệp vụ gốc:** Tài liệu giới thiệu Bộ Trợ lý AI UBND xã, phường (TSH) & Pháp luật hành chính nhà nước Việt Nam hiện hành (Luật Tổ chức chính quyền địa phương `65/2025/QH15`, Nghị định `30/2020/NĐ-CP`, Luật Đất đai `31/2024/QH15`, Luật Bảo vệ môi trường `72/2020/QH14`, Luật Ngân sách nhà nước `83/2015/QH13`, Nghị định `20/2021/NĐ-CP` & `76/2024/NĐ-CP`).
> **Trạng thái kiểm định:** Thương mại hóa hoàn chỉnh — **`76/76` bài kiểm thử tự động PASS (`48` Backend + `28` Frontend)**, **`0` lỗi TypeScript**, build Production SSR + Client sạch, đã kiểm định thực tế trên Chrome qua đủ **5 tài khoản** và kịch bản **Multi-Tenant độc lập (`Phường Bến Nghé`)**.

---

## 1. Tổng Quan Quy Mô & Chỉ Số Kỹ Thuật

| Hạng mục | Công nghệ / Cấu trúc | Quy mô thực tế đã kiểm chứng |
| :--- | :--- | :--- |
| **Backend API & Domain Engine** | Python `3.15` · FastAPI · Pydantic v2 · SQLite · `pypdf` · `python-docx` | **`5.261` dòng code** ứng dụng + **`1.702` dòng test** (`30` REST API operations) |
| **Frontend Webapp (SSR + SPA)** | React `19` · React Router `v7/v8` Framework Mode · TypeScript · Tailwind `v4` · `shadcn/ui` (`63` primitives) | **`7.006` dòng code** tuyến/logic chính + **`657` dòng test** (`7` tuyến nghiệp vụ chuyên sâu) |
| **Cơ sở dữ liệu & Phiên RAM** | SQLite cô lập theo từng xã/phường (`tenants/<slug>.db`) + `EphemeralSessionStore` trên RAM | **`9` bảng SQL** + Bộ nhớ RAM cô lập 4 chiều `(tenant_slug, actor_email, department_id, session_id)` |
| **Kho Pháp luật & Sổ tay cấp xã** | Seed tự động khi khởi tạo đơn vị gốc hoặc nhân bản xã/phường mới | **`36` văn bản chi tiết** (`27` Trung ương, `01` Địa phương, `08` Kho riêng nội bộ chia đều 4 phòng) |
| **Chỉ mục đồ thị mã nguồn** | CodeGraph AST + Call Graph cục bộ (`.codegraph/codegraph.db`) | **`776` nút biểu tượng (symbols)** được đồng bộ hóa toàn kho |
| **Kiểm thử tự động & Thực tế** | `unittest` (Backend) + `node:test` (Frontend) + Kiểm thử đối kháng Chrome (`1280px` & `1440px`) | **`76/76` bài test PASS (`100%`)** · `0 console.error` · `0 HTTP 500` |

---

## 2. Kiến Trúc Tổng Thể & Cơ Chế Zero-Trust Multi-Tenant

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                   FRONTEND — REACT ROUTER FRAMEWORK MODE (:5173)                     │
│  • WorkspaceShell: Hiển thị tên đơn vị đang vận hành, Công tắc chuyển xã/phường,     │
│    Khóa cứng phòng chuyên môn với vai trò Cán bộ (Officer), Ẩn menu Quản trị M07     │
│  • Đồng bộ danh tính kép: Cookie (ubnd_actor_email, ubnd_tenant_slug cho SSR loader) │
│    + HTTP Header (X-Actor-Email, X-Tenant-Slug cho Client fetch & Upload multipart)  │
│  • FormattedMarkdown: Bảng GFM <table>, Fenced <pre>, Callout, Danh sách đa cấp      │
└──────────────────────────────────────────┬───────────────────────────────────────────┘
                                           │ HTTP / JSON / Multipart (Zero-Trust Auth)
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                        BACKEND — FASTAPI ZERO-TRUST (:8000)                          │
│  • backend/auth.py: Xác thực bắt buộc (401 nếu thiếu danh tính, 403 nếu trái phòng   │
│    hoặc không phải Owner), định tuyến động tới đúng CSDL SQLite của Tenant đang chọn │
│  • Routers: workspace.py (Bootstrap, Phiên, M01–M03) · docs_and_files.py (M04–M05)   │
│             ops_and_admin.py (M06 Điều hành công việc · M07 Quản trị & Nhân bản AI)  │
├──────────────────────────────────────────┬───────────────────────────────────────────┘
│  Domain Engines (backend/services/):     │  Tầng Lưu Trữ Cô Lập (backend/db.py):
│  • legal_kb.py: Tìm kiếm pháp lý tiếng   │  • SQLite gốc: backend/data/ubnd_ai.db
│    Việt (lọc hư từ, bigram/trigram,      │  • SQLite nhân bản: tenants/<slug>.db
│    ngưỡng điểm chống trích dẫn lạc đề)   │  • EphemeralSessionStore (RAM thuần túy):
│  • ai_engine.py: Suy luận M01 (3 chế độ, │    Xóa sạch 100% lịch sử chat & buffer
│    tách câu hỏi đa vế) & M02 (3 phương   │    tệp ngay khi bấm "Kết thúc phiên"
│    án A/B/C chuyên biệt theo ngành)      │
│  • nd30_engine.py: Soạn thảo & Chấm điểm │
│    5 tiêu chí chuẩn NĐ 30/2020/NĐ-CP     │
│  • dossier_diff.py & doc_parser.py:      │
│    Bóc tách .pdf/.docx/.txt & đối chiếu  │
│    8 trường thực thể hành chính (M05)    │
└──────────────────────────────────────────┴───────────────────────────────────────────┘
```

---

## 3. Giải Phẫu Chi Tiết Từng Phân Hệ Mã Nguồn

### 3.1. Phân hệ Backend (`backend/`)

| Tệp mã nguồn | Số dòng | Vai trò & Thiết kế cốt lõi |
| :--- | :---: | :--- |
| `backend/main.py` | 68 | Khởi tạo ứng dụng FastAPI, cấu hình CORS an toàn, nạp `lifespan` tự động khởi tạo CSDL và gắn kết 3 cụm router cùng `/api/health`, `/api/hello`. |
| `backend/auth.py` | 131 | **Trái tim bảo mật Zero-Trust & Multi-Tenant:** Giải mã đồng thời Header (`X-Actor-Email`, `X-Tenant-Slug`) và Cookie (`ubnd_actor_email`, `ubnd_tenant_slug`); bác bỏ `401` mọi truy vấn ẩn danh; cưỡng chế `enforce_dept_scope` (`403`) khóa chặt cán bộ vào đúng phòng được giao và `require_owner_actor` bảo vệ đặc quyền quản trị M07. |
| `backend/db.py` | 1.173 | Quản lý kết nối SQLite đóng mở tường minh (`@contextmanager`), khởi tạo **9 bảng dữ liệu**, seed **36 văn bản pháp luật & sổ tay kho riêng cấp xã**, 5 tài khoản mẫu (`1 owner` + `4 officer`, trong đó `canbo.nnmt@ubnd.vn` mặc định giới hạn kho riêng để kiểm chứng RBAC), và `EphemeralSessionStore` cô lập RAM 4 chiều. |
| `backend/schemas.py` | 124 | Hệ thống lược đồ kiểm dữ liệu đầu vào Pydantic v2 chặt chẽ cho toàn bộ 7 mô-đun (`ChatRequest`, `DraftRequest` có `authority_mode`, `DocUpdateReviewRequest`, `UserPatchRequest`, `CloneTenantRequest`...). |
| `backend/services/legal_kb.py` | 398 | Bộ máy tìm kiếm pháp lý tiếng Việt thông minh: loại bỏ hư từ hành chính, chấm điểm cụm từ ghép `bigram/trigram` + khớp mã hiệu + trọng số tiêu đề/chuyên ngành và **ngưỡng cắt (threshold)** ngăn chặn triệt để hiện tượng ghép nhầm văn bản lệch chủ đề. |
| `backend/services/ai_engine.py` | 835 | Điều phối suy luận nghiệp vụ **M01** (bóc tách câu hỏi nhiều vế; phân định thẩm quyền Tập thể UBND vs Cá nhân Chủ tịch UBND vs Cơ quan cấp trên; viện dẫn điều khoản, thời hạn, trình tự Một cửa và cảnh báo rủi ro) và **M02** (phân tích 3 phương án A/B/C bám sát chủ đề Môi trường, Đất đai, Ngân sách, An sinh xã hội, Cải cách TTHC có gắn kết vai trò MTTQ & đoàn thể cơ sở). |
| `backend/services/nd30_engine.py` | 839 | Bộ máy soạn thảo & kiểm định văn bản chuẩn **Nghị định `30/2020/NĐ-CP`** (M03): tự động lấy tên xã/phường đang vận hành, ánh xạ ký hiệu Phụ lục I (`QĐ-UBND`, `KH-UBND`, `BC-UBND`, `TB-UBND`, `TTr-UBND`, `UBND-{PHÒNG}`), khử lặp `"Về việc"`, lược bỏ `"Về việc"` trên Kế hoạch/Báo cáo, sinh câu `"Căn cứ ...;"` chuẩn ngữ pháp văn thư, tách thẩm quyền `TM. ỦY BAN NHÂN DÂN` vs `CHỦ TỊCH`, chuẩn hóa `Nơi nhận` và chấm điểm khắt khe 5 tiêu chí (bắt lỗi đạo luật hết hiệu lực như Luật Đất đai 2013, lỗi mâu thuẫn người ký, dấu `...`, khẩu ngữ). |
| `backend/services/doc_parser.py` | 129 | Đọc tệp an toàn hoàn toàn trên RAM (`io.BytesIO`) cho `.txt`, `.md`, `.csv`, `.json`, `.docx`, `.pdf`; chặn tệp thực thi độc hại (`400`) và tệp `>10MB` (`413`); phát hiện thông minh PDF bản quét ảnh (scan) chưa có lớp văn bản OCR mà không bao giờ gây lỗi `500`. |
| `backend/services/dossier_diff.py` | 370 | Bộ bóc tách có cấu trúc **8 trường thực thể hành chính** (`Họ tên/Chủ hộ`, `Số CCCD`, `Thửa đất số`, `Tờ bản đồ`, `Diện tích m2`, `Số tiền/Kinh phí`, `Ngày tháng`, `Địa chỉ`) và lập bảng đối chiếu chéo gắn nhãn `[KHỚP]` vs `[SAI LỆCH - CẦN XÁC MINH]` cho **M05**. |
| `backend/routers/workspace.py` | 271 | Phục vụ `/api/bootstrap`, `/api/departments`, quản lý vòng đời phiên tạm `/api/sessions/{id}` và các API trí tuệ nhân tạo M01, M02, M03. |
| `backend/routers/docs_and_files.py` | 369 | Phục vụ kho văn bản chính thức & kho riêng M04, quy trình gửi và **Phê duyệt / Từ chối đề nghị cập nhật văn bản** (`PATCH /api/m04/update-requests/{id}/review` tự động nhập kho chính thức), cùng tải và xử lý hồ sơ phiên M05. |
| `backend/routers/ops_and_admin.py` | 551 | Phục vụ điều hành công việc M06 (lọc theo bộ phận, tính 4 chỉ số KPI khớp chính xác danh sách hiển thị, đếm số lần nhắc việc) và toàn bộ quản trị hệ thống M07 (cấp/xóa/bật-tắt quyền Kho riêng email, Instruction phòng, che khóa API `***`, nhật ký kiểm toán và nhân bản xã/phường chống ghi đè `409` + ẩn đường dẫn ổ cứng OS). |

---

### 3.2. Phân hệ Frontend (`app/app/`)

| Tệp mã nguồn | Số dòng | Vai trò & Trải nghiệm người dùng |
| :--- | :---: | :--- |
| `lib/session.ts` & `lib/api.ts` | 735 | Đồng bộ danh tính qua cả `document.cookie` lẫn `localStorage` để SSR `loader` và Client `fetch` luôn nhất quán quyền hạn; cô lập `session_id` theo `(tenantSlug, actorEmail, deptId)`; lưu chế độ M01 trong `sessionStorage`; biên dịch thông báo lỗi tiếng Việt tường minh cho mọi mã HTTP `400/401/403/404/409/413`. |
| `lib/markdown-helpers.ts` & `components/ui/formatted-markdown.tsx` | 430 | Bộ phân tích và kết xuất Markdown chuyên dụng cho hành chính công: bảng GFM `<table>` tự co giãn chuẩn ở màn hình `1280px`, khối dự thảo `<pre>` monospace giữ nguyên hàng cột Quốc hiệu, hộp cảnh báo blockquote, danh sách đa cấp và mã inline `` `...` `` lồng trong chữ in đậm. |
| `routes/workspace-layout.tsx` & `components/layout/workspace-shell.tsx` | 858 | Khung làm việc trung tâm 4 bộ phận (`VP`, `KT`, `VHXH`, `NNMT`): hiển thị tên UBND xã/phường đang vận hành, combobox chuyển đổi nhanh giữa Đơn vị gốc và các Xã/Phường nhân bản, tự khóa chọn phòng + ẩn khu vực M07 khi đăng nhập bằng tài khoản Cán bộ, và ghim cố định thanh khuyến cáo trách nhiệm pháp lý ở chân trang. |
| `routes/m01-assistant.tsx` | 576 | **Mô-đun 01 — Trợ lý AI theo nghiệp vụ:** 3 chế độ (`Soạn thảo nhanh`, `Tư vấn nghiệp vụ`, `Thẩm định chuyên sâu`), đính kèm tài liệu tạm ngay trong khung chat, thẻ trích dẫn nguồn văn bản bấm mở sang M04, nút *"Giao việc từ tư vấn này (M06)"* và nút *"Kết thúc phiên - Xóa bộ nhớ"*. |
| `routes/m02-extended.tsx` | 260 | **Mô-đun 02 — AI kiến thức mở rộng:** Phân tích đối sánh 3 phương án tham khảo A/B/C trên lưới 3 cột chuẩn responsive `1280px` và chuyển tiếp 1 chạm sang dự thảo Kế hoạch ở M03. |
| `routes/m03-drafting.tsx` & `lib/m03-m05-helpers.ts` | 751 | **Mô-đun 03 — Soạn thảo & Kiểm tra:** Hỗ trợ đủ 6 loại văn bản (`Công văn`, `Kế hoạch`, `Báo cáo`, `Quyết định`, `Thông báo`, `Tờ trình`), chọn thẩm quyền ký (`Tự động`, `Tập thể UBND`, `Cá nhân Chủ tịch UBND`), bảng chấm điểm 5 tiêu chí trực quan, xuất tệp `.txt` và nút chuyển giao việc sang M06. |
| `routes/m04-official-docs.tsx` | 842 | **Mô-đun 04 — Nguồn văn bản chính thức:** Tra cứu theo 3 tầng (`Trung ương`, `Địa phương`, `Kho dữ liệu riêng` cô lập theo phòng & quyền cán bộ), xem chi tiết toàn văn điều khoản, gửi đề nghị cập nhật và nút **Phê duyệt & Nhập kho / Từ chối** dành cho Chủ sở hữu. |
| `routes/m05-doc-session.tsx` | 461 | **Mô-đun 05 — Tải & xử lý tài liệu:** Tải đa tệp trong phiên, tích hợp **04 bộ hồ sơ mẫu có tình huống sai lệch thực tế riêng cho từng phòng (`VP`, `KT`, `VHXH`, `NNMT`)**, 4 chế độ xử lý (`Tóm tắt`, `Trích xuất`, `Đối chiếu mâu thuẫn`, `Tổng hợp phiếu trình`) và nút tạo nhiệm vụ xác minh hồ sơ sang M06. |
| `routes/m06-tasks.tsx` & `lib/m06-m07-helpers.ts` | 755 | **Mô-đun 06 — Điều hành công việc:** Mặc định lọc theo phòng đang làm việc (`Owner` xem được toàn bộ 4 phòng), **4 thẻ KPI khớp tuyệt đối 100% với danh sách đang lọc**, nhận dữ liệu bàn giao tự động từ M01/M03/M05 mở sẵn biểu mẫu giao việc, cập nhật tiến độ `+25%` và gửi nhắc việc. |
| `routes/m07-admin.tsx` | 1.052 | **Mô-đun 07 — Phân quyền & Quản trị hệ thống:** Hiển thị màn hình từ chối truy cập lịch sự nếu Cán bộ truy cập trực tiếp; cung cấp trọn vẹn 5 phân khu cho Owner: Phân quyền email (kèm nút bật/tắt trực tiếp quyền Kho riêng), Instruction của 4 phòng, Cổng API đấu nối che khóa `***`, Nhật ký hệ thống và **Nhân bản AI + Chuyển sang vận hành trực tiếp đơn vị xã/phường mới nhân bản**. |

---

## 4. Danh Mục 36 Văn Bản Pháp Luật & Kho Riêng Cấp Xã Đã Chuẩn Hóa

- **Văn phòng HĐND & UBND (`VP` — 10 văn bản):** Luật Tổ chức chính quyền địa phương `65/2025/QH15`, Nghị định `30/2020/NĐ-CP` (công tác văn thư & Phụ lục I), Luật Hộ tịch `60/2014/QH13` & NĐ `123/2015/NĐ-CP`, Luật Tiếp công dân `42/2013/QH13`, Luật Khiếu nại `02/2011/QH13`, Luật Tố cáo `25/2018/QH14`, Nghị định `61/2018/NĐ-CP` & `107/2021/NĐ-CP` (Một cửa & số hóa), Nghị định `23/2015/NĐ-CP` (chứng thực), cùng 02 văn bản `kho_rieng` (`QC-01/2026/UBND-VP`, `QT-02/2026/UBND-VP`).
- **Phòng Kinh tế (`KT` — 8 văn bản):** Luật Ngân sách nhà nước `83/2015/QH13` & Thông tư `344/2016/TT-BTC` (ngân sách xã), Luật Đầu tư công `58/2024/QH15`, Luật Quản lý tài sản công `15/2017/QH14` & NĐ `151/2017/NĐ-CP`, Nghị định `01/2021/NĐ-CP` (hộ kinh doanh), Luật Quản lý thuế `38/2019/QH14`, Thông tư `85/2019/TT-BTC`, cùng 02 sổ tay `kho_rieng` (`HD-02/2026/UBND-KT`, `ST-03/2026/UBND-KT`).
- **Phòng Văn hóa - Xã hội (`VHXH` — 8 văn bản):** Nghị định `20/2021/NĐ-CP` & `76/2024/NĐ-CP` (trợ giúp xã hội mức chuẩn 500.000đ), Pháp lệnh Ưu đãi người có công `02/2020/UBTVQH14` & NĐ `131/2021/NĐ-CP`, Nghị định `110/2018/NĐ-CP` (lễ hội), Nghị định `86/2023/NĐ-CP` (Gia đình văn hóa), Nghị định `07/2021/NĐ-CP` (chuẩn nghèo đa chiều), Luật Trẻ em `102/2016/QH13`, cùng 02 sổ tay `kho_rieng` (`ST-01/2026/UBND-VHXH`, `QT-02/2026/UBND-VHXH`).
- **Phòng Nông nghiệp và Môi trường (`NNMT` — 10 văn bản):** Luật Đất đai `31/2024/QH15` (tách bạch rõ Điều 235 hòa giải 30 ngày, Điều 137–138 xác nhận nguồn gốc & niêm yết 15 ngày, Điều 136 thẩm quyền cấp GCN lần đầu), Nghị định `101/2024/NĐ-CP`, Nghị định `123/2024/NĐ-CP` (xử phạt đất đai), Luật Bảo vệ môi trường `72/2020/QH14` (Điều 75–77 phân loại rác 3 nhóm tại nguồn), Nghị định `45/2022/NĐ-CP`, Nghị định `16/2022/NĐ-CP` (trật tự xây dựng), Quyết định `318/2022/QĐ-TTg` (Nông thôn mới), Quyết định địa phương `24/2026/QĐ-UBND`, cùng 02 sổ tay `kho_rieng` (`HD-03/2026/UBND-NNMT`, `QT-04/2026/UBND-NNMT`).

---

## 5. Hướng Dẫn Kiểm Thử & Vận Hành Hệ Thống

### Chạy toàn bộ 76 bài kiểm thử tự động & Build Production
```bash
# 1. Kiểm thử Backend (48 tests: RBAC Zero-Trust, Multi-Tenant, Kho 36 VB, NĐ 30/2020, Đối chiếu M05, E2E)
cd /home/fedora/Documents/UBND-AI-Support
.venv/bin/python -m unittest discover -s backend/tests -v

# 2. Kiểm thử Frontend (28 tests) + Kiểm tra kiểu TypeScript + Build SSR/Client
cd /home/fedora/Documents/UBND-AI-Support/app
npm test && npm run typecheck && npm run build
```

### Khởi chạy môi trường làm việc trực tiếp
```bash
# Terminal 1 — Backend FastAPI (:8000)
cd /home/fedora/Documents/UBND-AI-Support
.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Frontend React Router (:5173)
cd /home/fedora/Documents/UBND-AI-Support/app
npm run dev -- --host 127.0.0.1 --port 5173
```

### Danh sách 5 tài khoản kiểm định phân quyền có sẵn trên giao diện
1. `tsh.co@tshorg.vn` — **Chủ sở hữu hệ thống (`owner`)**: Toàn quyền chuyển đổi 4 phòng, phê duyệt văn bản M04, quản trị M07 và nhân bản/chuyển đổi đơn vị xã, phường.
2. `canbo.vp@ubnd.vn` — **Công chức Văn phòng - Thống kê (`officer` · Khóa phòng `VP` · Có quyền Kho riêng `VP`)**.
3. `canbo.kt@ubnd.vn` — **Công chức Tài chính - Kế toán (`officer` · Khóa phòng `KT` · Có quyền Kho riêng `KT`)**.
4. `canbo.vhxh@ubnd.vn` — **Công chức Văn hóa - Xã hội (`officer` · Khóa phòng `VHXH` · Có quyền Kho riêng `VHXH`)**.
5. `canbo.nnmt@ubnd.vn` — **Công chức Địa chính - Môi trường (`officer` · Khóa phòng `NNMT` · Mặc định giới hạn Kho riêng `private_repo_access = False`)**.
