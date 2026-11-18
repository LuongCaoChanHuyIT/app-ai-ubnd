# Đặc Tả Kiến Trúc & Nghiệp Vụ Web App 7 Mô-đun — Bộ Trợ Lý AI UBND Xã, Phường

**Tài liệu nguồn:** `Profile_gioi_thieu_Bo_Tro_ly_AI_UBND_xa_phuong_TSH.pdf` (Công ty Cổ phần Đào tạo và Giải pháp – TSH, 2026).

---

## 1. Mục tiêu, Phạm vi & Nguyên tắc Pháp lý

- **Mục tiêu:** Xây dựng nền tảng web nội bộ thống nhất **Bộ Trợ lý AI UBND xã, phường** trên stack **React Router v8 (`shadcn/ui`) + FastAPI (Python 3.15 + SQLite)** vận hành đầy đủ **7 mô-đun xử lý công việc xuyên suốt** và **4 không gian nghiệp vụ chuyên biệt**.
- **Nguyên tắc bắt buộc (hiển thị xuyên suốt hệ thống):**
  > *"AI là công cụ hỗ trợ nghiệp vụ; cán bộ, công chức và người có thẩm quyền vẫn trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."*
- **Cam kết bảo mật phiên làm việc:** Tài liệu người dùng tải lên trong phiên (`Mô-đun 01` & `Mô-đun 05`) chỉ lưu trong bộ nhớ tạm của phiên (`in-memory SessionStore`) và bị hủy hoàn toàn ngay khi bấm **"Kết thúc phiên - Xóa bộ nhớ"**.

---

## 2. Bốn Không gian Làm việc Chuyên biệt (`department_id`)

| Mã (`id`) | Tên hiển thị | Phạm vi chuyên môn mặc định |
|---|---|---|
| `VP` | Văn phòng HĐND & UBND | Tổng hợp, văn thư, tư pháp - hộ tịch, tiếp công dân và kiểm soát TTHC |
| `KT` | Kinh tế | Tài chính - ngân sách xã, kế hoạch đầu tư công, thương mại - dịch vụ, hộ kinh doanh |
| `VHXH` | Văn hóa - Xã hội | Chính sách người có công, bảo trợ xã hội, giáo dục, y tế cơ sở, văn hóa - thông tin |
| `NNMT` | Nông nghiệp và Môi trường | Địa chính - đất đai, trật tự xây dựng, tài nguyên môi trường, nông thôn mới |

- Văn bản thuộc `trung_uong` và `dia_phuong` được tra cứu chung cho cả 4 nhóm.
- Văn bản thuộc `kho_rieng` gắn với `department_id` cụ thể (hoặc `"ALL"` nếu dùng chung toàn UBND xã/phường) và chỉ hiển thị/viện dẫn cho đúng nhóm được phân quyền.

---

## 3. Kiến trúc Dữ liệu & Tầng Dịch vụ Backend (`backend/`)

### 3.1. Cơ sở dữ liệu bền vững (`SQLite` — `backend/data/ubnd_ai.db`)
1. `departments(id, code, name, scope_summary, instruction, updated_at)`
2. `official_documents(id, doc_number, title, doc_type, tier, department_id, issuer, issued_date, status, summary, content, created_at)`
   - `tier`: `"trung_uong"` | `"dia_phuong"` | `"kho_rieng"`
3. `doc_update_requests(id, doc_number, title, tier, department_id, reason, requested_by, status, created_at)`
4. `tasks(id, title, description, department_id, assignee, due_date, priority, status, progress, ref_doc_number, reminder_count, created_at, updated_at)`
   - `status`: `"cho_xu_ly"` | `"dang_thuc_hien"` | `"sap_den_han"` | `"hoan_thanh"`
5. `users_rbac(id, email, full_name, position, role, department_id, private_repo_access, active, created_at)`
   - `role`: `"owner"` (*Chủ sở hữu*, mặc định `tsh.co@tshorg.vn`) | `"officer"` (*Cán bộ chuyên môn*)
6. `api_connectors(id, name, provider, base_url, model_name, api_key, active, updated_at)`
7. `audit_logs(id, actor_email, department_id, module_code, action, detail, created_at)`
8. `cloned_tenants(id, slug, commune_name, admin_email, db_path, created_at)`

### 3.2. Bộ nhớ Phiên Tạm thời (`SessionStore` trong RAM)
- Lưu theo `session_id`: danh sách `messages` (lịch sử hội thoại trong phiên) và `files` (tên tệp, kích thước, loại tệp, nội dung văn bản trích xuất).
- Gọi `DELETE /api/sessions/{session_id}` xóa trắng cả `messages` lẫn `files` khỏi RAM và ghi nhận sự kiện xóa phiên vào `audit_logs` (không lưu nội dung tài liệu vào log).

### 3.3. AI Synthesis Engine (`backend/services/ai_engine.py`)
- **Chế độ kết nối LLM thật:** Nếu `api_connectors` có cấu hình đang bật (`active = 1` và có `api_key`) hoặc biến môi trường `LLM_API_KEY`, hệ thống gọi HTTP tới OpenAI-compatible Chat Completions endpoint kèm ngữ cảnh RAG (`official_documents` + `session.files` + `department.instruction`).
- **Chế độ nội bộ chuẩn hóa (Deterministic Administrative Engine):** Khi chưa cấu hình khóa API ngoài, engine tự động tổng hợp câu trả lời tiếng Việt chuẩn hành chính dựa trực tiếp trên các điều khoản tìm được trong `official_documents`, dữ liệu trích xuất từ `session.files`, `department.instruction` và bộ quy tắc kiểm tra thể thức Nghị định `30/2020/NĐ-CP`. Nhờ đó toàn bộ 7 mô-đun chạy thực tế 100% ngay lập tức.

---

## 4. Đặc tả Chi tiết 7 Mô-đun & Giao diện (`app/`)

### Bố cục Khung Thống nhất (`WorkspaceShell` — bám sát ảnh chụp Profile TSH)
- **Sidebar trái (`268px`, nền `#0F172A`, chữ sáng):**
  - Thương hiệu: Huy hiệu `AI` xanh `#2563EB` + **TRỢ LÝ CÁN BỘ** / *Tư vấn công việc xã/phường*.
  - Khối **KHÔNG GIAN LÀM VIỆC**: Dropdown chọn 1 trong 4 phòng (`VP`, `KT`, `VHXH`, `NNMT`) đồng bộ với query `?dept=...` + mô tả phạm vi phòng.
  - Nhóm điều hướng nghiệp vụ & quản trị ánh xạ đủ 12 mục trên ảnh chụp TSH vào 7 route mô-đun:
    1. `+ Tư vấn công việc` → `/` (Mô-đun 01)
    2. `AI hỗ trợ kiến thức mở rộng` → `/kien-thuc-mo-rong` (Mô-đun 02)
    3. `Soạn thảo & kiểm tra` → `/soan-thao-kiem-tra` (Mô-đun 03)
    4. `Nguồn văn bản chính thức` → `/nguon-van-ban` (Mô-đun 04)
    5. `Tải & xử lý tài liệu` → `/xu-ly-tai-lieu` (Mô-đun 05)
    6. `Điều hành công việc` → `/dieu-hanh-cong-viec` (Mô-đun 06)
    7. `Đề nghị cập nhật văn bản` → `/nguon-van-ban?tab=de-nghi` (Mô-đun 04)
    8. `Instruction của phòng` → `/quan-tri-he-thong?tab=instruction` (Mô-đun 07)
    9. `Cổng API đấu nối` → `/quan-tri-he-thong?tab=api` (Mô-đun 07)
    10. `Phân quyền email` → `/quan-tri-he-thong?tab=phan-quyen` (Mô-đun 07)
    11. `Nhật ký hệ thống` → `/quan-tri-he-thong?tab=nhat-ky` (Mô-đun 07)
    12. `Nhân bản AI` → `/quan-tri-he-thong?tab=nhan-ban` (Mô-đun 07)
  - Chân sidebar: Thông tin tài khoản đang chọn (`tsh.co@tshorg.vn` · *Chủ sở hữu*, hỗ trợ chuyển đổi thử vai trò Cán bộ phòng để kiểm chứng RBAC).
- **Thanh tiêu đề trên (`68px`, nền trắng):** Nhãn `UBND CẤP XÃ · HỆ THỐNG NỘI BỘ`, tên phòng hiện tại, nút `↑ Tải tài liệu tham khảo` và nút xanh `+ Kiểm tra văn bản`.

### Mô-đun 01 — Trợ lý AI theo nghiệp vụ (`/`)
- 3 thẻ chế độ chọn trực tiếp:
  - `soan_thao` (**Soạn thảo nhanh**): Soạn mới, chỉnh sửa nhanh văn bản thông thường không bắt buộc viện dẫn pháp lý.
  - `nghiep_vu` (**Tư vấn nghiệp vụ**): Đối chiếu kho văn bản chính thức & kho riêng của phòng, trả về căn cứ pháp lý kèm hướng xử lý.
  - `tham_dinh` (**Thẩm định chuyên sâu**): Kiểm tra căn cứ, thẩm quyền cấp xã/phường, tính logic và rủi ro của hồ sơ/dự thảo.
- Thanh trạng thái tệp tạm trong phiên (`↑ Tải thêm tài liệu (N tệp)`), nút đỏ **`Kết thúc phiên - Xóa bộ nhớ`**, các gợi ý nhanh (*Xử lý hồ sơ*, *Soạn văn bản*, *Kiểm tra thẩm quyền*) và ô nhập chat hỗ trợ `Enter` gửi / `Shift + Enter` xuống dòng.

### Mô-đun 02 — AI kiến thức mở rộng (`/kien-thuc-mo-rong`)
- Cảnh báo rõ phạm vi tham khảo kiến thức mở rộng ngoài kho văn bản nội bộ.
- Nhập chủ đề/vấn đề cần tham mưu → Sinh phân tích đa chiều gồm **3 phương án (`Phương án A`, `Phương án B`, `Phương án C`)** với Ưu điểm, Hạn chế, Điều kiện áp dụng tại xã/phường, và nút chuyển thẳng phương án chọn sang trình soạn thảo ở Mô-đun 03.

### Mô-đun 03 — Soạn thảo & kiểm tra (`/soan-thao-kiem-tra`)
- Khung chia 2 cột:
  - **Trái (Soạn thảo):** Chọn loại văn bản hành chính (`Công văn`, `Báo cáo`, `Kế hoạch`, `Quyết định`, `Thông báo`), nhập yêu cầu để sinh dự thảo chuẩn thể thức Nghị định `30/2020/NĐ-CP` (Quốc hiệu, Tiêu ngữ, Tên cơ quan ban hành, Số/Ký hiệu, Trích yếu, Căn cứ, Nội dung, Nơi nhận, Chữ ký thẩm quyền), cho phép sửa trực tiếp và tải tệp về máy.
  - **Phải (Kiểm tra 5 tiêu chí):** Chấm điểm chuẩn hóa `/100` và đánh giá chi tiết 5 nhóm: *Bố cục & Thể thức*, *Căn cứ pháp lý*, *Thẩm quyền ban hành*, *Tính logic & Thống nhất*, *Chính tả & Văn phong hành chính* (`dat` | `can_ra_soat` | `khong_dat`) kèm gợi ý chỉnh sửa.

### Mô-đun 04 — Nguồn văn bản chính thức (`/nguon-van-ban`)
- Tìm kiếm từ khóa theo số hiệu, trích yếu, nội dung; lọc theo 3 tầng kho (`trung_uong`, `dia_phuong`, `kho_rieng` có kiểm soát quyền theo phòng).
- Xem chi tiết trích yếu & nội dung văn bản, thêm văn bản vào kho riêng, và gửi/theo dõi **Đề nghị cập nhật văn bản** (`?tab=de-nghi`).

### Mô-đun 05 — Tải & xử lý tài liệu (`/xu-ly-tai-lieu`)
- Tải nhiều tệp (`.txt`, `.md`, `.docx`, `.pdf`, tối đa `10 MB`/tệp) vào bộ nhớ phiên hiện tại (dùng chung `session_id` với Mô-đun 01).
- Thực thi 4 tác vụ xử lý chuyên biệt trên các tệp trong phiên:
  1. `tom_tat`: Tóm tắt nội dung cốt lõi từng tệp.
  2. `trich_xuat`: Trích xuất các trường thông tin hành chính (Chủ thể, Ngày tháng, Số hiệu, Nội dung đề nghị).
  3. `doi_chieu`: Đối chiếu chéo giữa các tài liệu trong hồ sơ để phát hiện điểm mâu thuẫn, thiếu sót hoặc chưa thống nhất.
  4. `tong_hop`: Tổng hợp thành phiếu trình / báo cáo tóm tắt xử lý hồ sơ.

### Mô-đun 06 — Điều hành công việc (`/dieu-hanh-cong-viec`)
- 4 thẻ chỉ số KPI (*Tổng nhiệm vụ*, *Đang thực hiện*, *Sắp đến hạn*, *Hoàn thành*).
- Lọc nhiệm vụ theo 4 phòng chuyên môn & trạng thái; tạo nhiệm vụ mới (*Giao việc*); cập nhật phần trăm tiến độ/trạng thái; bấm *Nhắc việc* tăng bộ đếm nhắc và ghi vào nhật ký điều hành.

### Mô-đun 07 — Phân quyền & Quản trị hệ thống (`/quan-tri-he-thong`)
- 5 phân mục quản trị tương ứng 5 mục cuối trên thanh điều hướng TSH:
  1. **Phân quyền email (`phan-quyen`):** Quản lý danh sách cán bộ theo email, chức danh, phòng chuyên môn (`VP`, `KT`, `VHXH`, `NNMT`), quyền truy cập kho dữ liệu riêng; chỉ `owner` được thêm/sửa/xóa.
  2. **Instruction của phòng (`instruction`):** Cấu hình chỉ dẫn nghiệp vụ riêng cho từng phòng chuyên môn.
  3. **Cổng API đấu nối (`api`):** Cấu hình kết nối LLM API (ẩn khóa bí mật khi trả về giao diện).
  4. **Nhật ký hệ thống (`nhat-ky`):** Bảng tra cứu lịch sử thao tác theo thời gian thực.
  5. **Nhân bản AI (`nhan-ban`):** Khởi tạo một bản hệ thống độc lập mới cho xã/phường khác (`backend/data/tenants/<slug>.db`) với cấu trúc CSDL, 4 phòng chuyên môn và tài khoản quản trị riêng biệt.

