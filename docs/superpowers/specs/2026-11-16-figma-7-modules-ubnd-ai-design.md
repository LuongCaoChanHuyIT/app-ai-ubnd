# Thiết Kế Giao Diện Figma 7 Mô-đun — Bộ Trợ Lý AI UBND Xã, Phường (TSH)

**Nguồn tham chiếu gốc:** `Profile_gioi_thieu_Bo_Tro_ly_AI_UBND_xa_phuong_TSH.pdf` (Công ty Cổ phần Đào tạo và Giải pháp – TSH, Hà Nội, 2026) và văn bản mẫu `Nghị định 399_2026_nd-cp_02112026_6-signed.signed.pdf`.

---

## 1. Mục tiêu & Phạm vi (Goals, Non-Goals, Anti-Goals)

- **Mục tiêu (Goal):** Xây dựng trọn bộ thiết kế giao diện **7 mô-đun xử lý công việc** kèm **1 bảng Design System & Components** (tổng cộng 8 màn hình Desktop `1440×960` px có Auto Layout, Variables, Components, Text tiếng Việt chỉnh sửa được 100%) trên **Figma Design**, đồng thời xuất **Sơ đồ luồng liên thông 7 mô-đun** trên **FigJam**.
- **Phi mục tiêu (Non-Goals):** Không xây dựng backend AI/RAG hay cơ sở dữ liệu thật trong phạm vi bản vẽ Figma này.
- **Chống mục tiêu (Anti-Goals):**
  - Không dùng ảnh chụp màn hình phẳng (flattened raster screenshot) dán lên Figma thay cho layer chỉnh sửa được.
  - Không bỏ sót bất kỳ mô-đun nào trong 7 mô-đun hoặc 4 nhóm nghiệp vụ chuyên biệt của UBND cấp xã, phường.
  - Không ẩn nguyên tắc pháp lý cốt lõi: *"AI là công cụ hỗ trợ nghiệp vụ; cán bộ, công chức và người có thẩm quyền vẫn trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."*

---

## 2. Ràng buộc Môi trường Figma MCP & Phương án Kỹ thuật

### Khảo sát thực tế tài khoản Figma MCP (`whoami`)
- **Tài khoản:** `Chấn Huy Lương Cao` (`lcch0901047493@gmail.com`)
- **Plan Key:** `team::1703004690588386734` (`tier: "starter"`, `seat: "View"`, `role: "admin"`, `code_layers_enabled: true`)
- **Công cụ MCP khả dụng:** Máy chủ `figma_figma` hiện tại **không mở tool `use_figma` hay `html_to_figma`** từ xa (do giới hạn seat Starter/View), nhưng **có mở đầy đủ**:
  1. `create_generative_plugin` / `get_generative_plugin` / `update_generative_plugin` (triển khai Figma Design Plugin trực tiếp vào thư viện tài khoản, chạy Figma Plugin API sinh native Auto-Layout Frames, Variables, Components, Vectors).
  2. `generate_diagram` (sinh sơ đồ quy trình trực tiếp trên FigJam).
  3. `create_new_file` + `send_code_to_figma` (chỉ tạo Code Layer, *không tạo được native Design shapes*).

### Lựa chọn kiến trúc (Selected Approach)
Kết hợp **Figma Design Plugin tự động hóa (`code.ts` + `ui.html`)** + **FigJam Workflow Diagram (`generate_diagram`)**:
1. Phát triển bộ mã nguồn TypeScript module hóa tại `src/figma-plugin/`, kiểm thử tự động bằng `node --test` trên Node.js `v22.23.4` với Mock Figma Scenegraph (bắt lỗi font, màu `0..1`, thứ tự `appendChild` trước `FILL`, SVG icon).
2. Đóng gói thành `dist/code.ts` (single-file TypeScript không còn `import`/`export`) và `dist/ui.html` (giao diện PropsKit cho phép chọn vẽ cả 8 frames hoặc từng mô-đun theo từng phòng chuyên môn), đẩy lên Figma qua `create_generative_plugin` + `update_generative_plugin`.
3. Tạo thêm sơ đồ quy trình tổng thể 7 mô-đun trên FigJam qua `generate_diagram` để phục vụ thuyết trình kiến trúc nghiệp vụ.

---

## 3. Hệ thống Token Thiết kế (Design Tokens trích xuất từ Profile TSH)

### 3.1. Bảng màu (Colors)
| Token Name | Hex | RGB chuẩn hóa (`0..1`) | Vai trò sử dụng |
|---|---|---|---|
| `color/sidebar-bg` | `#0F172A` | `{ r: 0.059, g: 0.090, b: 0.165 }` | Nền thanh điều hướng trái (`268px`) |
| `color/sidebar-surface` | `#1E293B` | `{ r: 0.118, g: 0.161, b: 0.231 }` | Khối chọn Không gian làm việc & thẻ phụ sidebar |
| `color/sidebar-active` | `#1E3A8A` | `{ r: 0.118, g: 0.227, b: 0.541 }` | Nền mục menu đang chọn |
| `color/primary` | `#2563EB` | `{ r: 0.145, g: 0.388, b: 0.922 }` | Nút chính (`+ Kiểm tra văn bản`), icon `AI`, điểm nhấn |
| `color/primary-soft` | `#EFF6FF` | `{ r: 0.937, g: 0.965, b: 1.000 }` | Nền pill/tag trạng thái xanh dương |
| `color/app-bg` | `#F1F5F9` | `{ r: 0.945, g: 0.961, b: 0.976 }` | Nền vùng làm việc chính bên phải |
| `color/surface` | `#FFFFFF` | `{ r: 1.000, g: 1.000, b: 1.000 }` | Nền thẻ (card), bảng dữ liệu, header |
| `color/border` | `#E2E8F0` | `{ r: 0.886, g: 0.910, b: 0.941 }` | Viền thẻ, đường chia khu vực |
| `color/text-primary` | `#0F172A` | `{ r: 0.059, g: 0.090, b: 0.165 }` | Tiêu đề chính & nội dung văn bản |
| `color/text-secondary` | `#475569` | `{ r: 0.278, g: 0.333, b: 0.412 }` | Mô tả phụ, nhãn bảng |
| `color/text-muted` | `#94A3B8` | `{ r: 0.580, g: 0.639, b: 0.722 }` | Placeholder, chú thích cuối trang |
| `color/sidebar-text` | `#F8FAFC` | `{ r: 0.973, g: 0.980, b: 0.988 }` | Chữ sáng trên nền sidebar tối |
| `color/success` | `#10B981` | `{ r: 0.063, g: 0.725, b: 0.506 }` | Đạt chuẩn thể thức / Còn hiệu lực / Đúng hạn |
| `color/warning` | `#F59E0B` | `{ r: 0.961, g: 0.620, b: 0.043 }` | Cần rà soát căn cứ / Sắp đến hạn |
| `color/danger` | `#EF4444` | `{ r: 0.937, g: 0.267, b: 0.267 }` | Cảnh báo thẩm quyền / `Kết thúc phiên - Xóa bộ nhớ` |
| `color/indigo` | `#6366F1` | `{ r: 0.388, g: 0.400, b: 0.945 }` | Nhãn chế độ Nghiệp vụ / Kiến thức mở rộng |

### 3.2. Typography & Kích thước Bố cục (Layout Grid)
- **Font chữ:** `Inter` (`Regular`, `Medium`, `Semi Bold`, `Bold`) — hỗ trợ đầy đủ dấu tiếng Việt; cơ chế fallback tự động sang `Bold` / `Regular` nếu môi trường thiếu `Semi Bold`.
- **Thang chữ:**
  - `Heading XL`: `22px` Bold (`lineHeight: 30px`)
  - `Heading LG`: `18px` Semi Bold (`lineHeight: 26px`)
  - `Heading MD`: `15px` Semi Bold (`lineHeight: 22px`)
  - `Body`: `13px` Regular / Medium (`lineHeight: 20px`)
  - `Caption / Badge`: `11px` Semi Bold (`lineHeight: 16px`)
- **Khung màn hình chuẩn:** `1440 × 960` px (`HORIZONTAL` Auto Layout):
  - **Sidebar trái:** rộng cố định `268px`, cao `960px`, padding `16px`, khoảng cách mục `6px`.
  - **Khung chính phải:** rộng `1172px`, cao `960px` (`VERTICAL` Auto Layout):
    - **Top Header:** cao `68px`, padding ngang `28px`, nền `#FFFFFF`, viền dưới `#E2E8F0`.
    - **Workspace Body:** cao `892px`, padding `24px 28px`, `itemSpacing: 20px`, nền `#F1F5F9`.
- **Khoảng cách giữa các màn hình trên Canvas:** `160px` theo trục ngang `X`.

---

## 4. Bốn Không gian Nghiệp vụ Chuyên biệt (4 Department Workspaces)

1. **`VP` — Văn phòng HĐND & UBND:** *Tổng hợp, văn thư, tư pháp - hộ tịch, tiếp công dân và kiểm soát TTHC* (mặc định theo ảnh chụp Profile).
2. **`KT` — Kinh tế:** *Tài chính - ngân sách xã, kế hoạch đầu tư công, thương mại - dịch vụ và hộ kinh doanh*.
3. **`VHXH` — Văn hóa - Xã hội:** *Chính sách người có công, bảo trợ xã hội, giáo dục, y tế cơ sở và thông tin tuyên truyền*.
4. **`NNMT` — Nông nghiệp và Môi trường:** *Quản lý đất đai, trật tự xây dựng, tài nguyên môi trường và nông thôn mới*.

---

## 5. Đặc tả Chi tiết 8 Màn hình Figma (`00` → `07`)

### Màn hình `00 · Design System & Components` (`1440×960`)
- Bảng màu chuẩn (`16` color swatches gắn Figma Variables).
- Bảng Typography tiếng Việt (`Heading XL` → `Caption`).
- Bộ Figma `COMPONENT` gốc để tái sử dụng (`createInstance()`) trên cả 7 màn hình:
  - `Comp/SidebarItem` (trạng thái Default & Active)
  - `Comp/ActionButton` (Primary `#2563EB`, Secondary `#FFFFFF`, Danger Text)
  - `Comp/StatusBadge` (`SOẠN THẢO`, `NGHIỆP VỤ`, `THẨM ĐỊNH`, `CÒN HIỆU LỰC`, `CẦN RÀ SOÁT`)
  - `Comp/KpiCard` (Tiêu đề chỉ số, Giá trị lớn, Xu hướng/chú thích)

### Màn hình `01 · Mô-đun 01: Trợ lý AI theo nghiệp vụ` (`1440×960`)
- **Menu active:** `+ Tư vấn công việc`
- **Bám sát 100% bố cục ảnh chụp trang 1 & 2 của Profile TSH:**
  - Header thẻ chính: `TRỢ LÝ NGHIỆP VỤ · VĂN PHÒNG HĐND & UBND` | Tiêu đề `Anh/chị cần xử lý công việc gì?` | Nút phải: `↑ Tải thêm tài liệu (0 tệp)` và `Kết thúc phiên - Xóa bộ nhớ` (đỏ).
  - **Hàng 3 thẻ chế độ (`HORIZONTAL`, `gap: 16px`):**
    1. `Soạn thảo nhanh` (badge `SOẠN THẢO`): *"Soạn mới, chỉnh sửa văn bản và xử lý công việc thông thường không cần viện dẫn pháp lý."*
    2. `Tư vấn nghiệp vụ` (badge `NGHIỆP VỤ`): *"Kiểm tra nguồn pháp lý hiện hành và đề xuất hướng xử lý công việc."*
    3. `Thẩm định chuyên sâu` (badge `THẨM ĐỊNH`): *"Đối chiếu căn cứ, thẩm quyền, logic và rủi ro của hồ sơ, dự thảo."*
  - **Vùng gợi ý trung tâm:** Icon `AI` xanh `#2563EB`, tiêu đề `Ta nên bắt đầu việc gì?`, mô tả `Đặt câu hỏi, yêu cầu soạn thảo hoặc tải tài liệu lên để AI tham khảo trong phiên làm việc.`, 3 pill hành động nhanh: `Xử lý hồ sơ` · `Soạn văn bản` · `Kiểm tra thẩm quyền`.
  - **Khung nhập liệu dưới cùng:** Placeholder `Làm với bất kỳ nội dung nghiệp vụ nào...`, thanh công cụ trong ô nhập `+ Tải tài liệu lên` · `Soạn thảo nhanh` · nút gửi `↑`, dòng nhắc: `Enter để gửi · Shift + Enter để xuống dòng · Tài liệu chỉ được dùng trong phiên hiện tại`.

### Màn hình `02 · Mô-đun 02: AI kiến thức mở rộng` (`1440×960`)
- **Menu active:** `AI hỗ trợ kiến thức mở rộng`
- **Banner phân tách nguồn tri thức:** Cảnh báo rõ chế độ đang tham khảo kiến thức mở rộng bên ngoài kho nội bộ để gợi mở nghiên cứu, phân tích đa chiều.
- **Câu hỏi nghiên cứu mẫu:** *"Phân tích các phương án nâng cao tỷ lệ hồ sơ trực tuyến toàn trình tại Bộ phận Một cửa UBND phường năm 2026"*.
- ** Lưới so sánh 3 phương án (`Phương án A: Tổ công nghệ số cộng đồng`, `Phương án B: Quầy hướng dẫn tự phục vụ thông minh`, `Phương án C: Mô hình kết hợp theo nhóm thủ tục`):** Mỗi thẻ hiển thị Ưu điểm, Hạn chế/Nguồn lực, Mức độ khả thi cấp xã, cùng nút `Chuyển thành đề cương Kế hoạch`.

### Màn hình `03 · Mô-đun 03: Soạn thảo và kiểm tra` (`1440×960`)
- **Menu active:** `Soạn thảo & kiểm tra`
- **Bố cục chia đôi 2 cột (`HORIZONTAL`, `gap: 20px`):**
  - **Cột trái (`690px`) — Trình soạn thảo văn bản hành chính chuẩn Nghị định 30/2020/NĐ-CP:** Thanh chọn loại văn bản (`Kế hoạch`, `Báo cáo`, `Quyết định`, `Thông báo`, `Công văn`), quốc hiệu tiêu ngữ, tên cơ quan `ỦY BAN NHÂN DÂN PHƯỜNG...`, trích yếu dự thảo, phần *Căn cứ* và *Nội dung thực hiện*, nút `Xuất tệp .docx` & `Chuyển kiểm tra thể thức`.
  - **Cột phải (`406px`) — Bảng Rà soát & Kiểm tra 5 tiêu chí:** Điểm chuẩn hóa `88/100`, danh sách 5 hạng mục kiểm tra:
    1. `Bố cục & Thể thức (NĐ 30/2020/NĐ-CP)` — `ĐẠT CHUẨN`
    2. `Căn cứ pháp lý viện dẫn` — `CẦN RÀ SOÁT` *(Gợi ý cập nhật Nghị định 399/2026/NĐ-CP ngày 02/11/2026)*
    3. `Thẩm quyền ban hành (UBND vs Chủ tịch UBND cấp xã)` — `ĐẠT CHUẨN`
    4. `Tính logic & Thống nhất số liệu` — `CẦN RÀ SOÁT` *(Mốc thời gian mục II.2 lệch 5 ngày so với Phụ lục)*
    5. `Chính tả & Văn phong hành chính` — `ĐẠT CHUẨN`

### Màn hình `04 · Mô-đun 04: Nguồn văn bản chính thức` (`1440×960`)
- **Menu active:** `Nguồn văn bản chính thức`
- **Thanh tìm kiếm & bộ lọc:** Ô tìm kiếm theo số hiệu/trích yếu, 3 tab kho dữ liệu (`Văn bản Trung ương (1.240)`, `Văn bản Địa phương - Tỉnh/Thành (385)`, `Kho dữ liệu riêng Xã/Phường (162)`), nút `+ Đề nghị cập nhật văn bản`.
- **Bảng danh mục văn bản chính thức (5 dòng mẫu sát thực tế):**
  - `Nghị định 399/2026/NĐ-CP` (02/11/2026) — Chính phủ — `MỚI CẬP NHẬT`
  - `Nghị định 30/2020/NĐ-CP` (05/03/2020) — Chính phủ (Công tác văn thư) — `CÒN HIỆU LỰC`
  - `Luật Tổ chức chính quyền địa phương` — Quốc hội — `CÒN HIỆU LỰC`
  - `Quyết định 24/2026/QĐ-UBND` — UBND Thành phố (Quy chế phối hợp TTHC) — `CÒN HIỆU LỰC`
  - `Quy chế làm việc của UBND Phường nhiệm kỳ 2026-2031` — Kho nội bộ (`VP`) — `NỘI BỘ PHÂN QUYỀN`

### Màn hình `05 · Mô-đun 05: Tải và xử lý tài liệu` (`1440×960`)
- **Menu active:** `Tải & xử lý tài liệu phiên`
- **Thanh cam kết bảo mật phiên:** `Tài liệu tải lên chỉ phục vụ phiên làm việc hiện tại · Nhấn "Kết thúc phiên - Xóa bộ nhớ" để hủy toàn bộ dữ liệu tạm`.
- **Bố cục 2 cột:**
  - **Cột trái (`380px`) — Danh sách tệp trong phiên (`3 tệp`):** Khu vực kéo-thả PDF/DOCX/XLSX + 3 thẻ tệp đã tải (`Don_de_nghi_xac_nhan_nguon_goc_dat.pdf`, `Bien_ban_xac_minh_thuc_dia.docx`, `Nghi_dinh_399_2026_ND-CP.pdf`).
  - **Cột phải (`716px`) — Kết quả Đọc, Tóm tắt, Trích xuất & Đối chiếu hồ sơ:** 4 tab nghiệp vụ (`Tóm tắt hồ sơ`, `Trích xuất trường dữ liệu`, `Đối chiếu mâu thuẫn`, `Tổng hợp phiếu trình`), bảng trích xuất thực thể (Người nộp, Thửa đất/Tờ bản đồ, Căn cứ áp dụng) và hộp cảnh báo `Phát hiện 02 điểm chưa thống nhất giữa Đơn đề nghị và Biên bản xác minh`.

### Màn hình `06 · Mô-đun 06: Điều hành công việc` (`1440×960`)
- **Menu active:** `Điều hành công việc`
- **Hàng 4 thẻ KPI (`Comp/KpiCard`):** `Tổng nhiệm vụ tháng (48)` · `Đang xử lý (19)` · `Sắp đến hạn / Nhắc việc (06)` · `Tỷ lệ đúng hạn (93,7%)`.
- **Thanh lọc theo 4 nhóm nghiệp vụ:** `Tất cả bộ phận` · `Văn phòng HĐND & UBND` · `Kinh tế` · `Văn hóa - Xã hội` · `Nông nghiệp & Môi trường` + nút `+ Giao nhiệm vụ mới` & `Gửi nhắc việc`.
- **Bảng theo dõi tiến độ nhiệm vụ (5 nhiệm vụ mẫu đại diện đủ 4 phòng):** Cột Nhiệm vụ & Văn bản giao, Bộ phận chủ trì, Cán bộ phụ trách, Hạn hoàn thành, Tiến độ (`%`), Trạng thái (`Đúng tiến độ`, `Sắp đến hạn`, `Hoàn thành`).

### Màn hình `07 · Mô-đun 07: Phân quyền & Nhân bản hệ thống` (`1440×960`)
- **Menu active:** `Phân quyền email` *(hiển thị liên thông nhóm quản trị: `Instruction của phòng`, `Cổng API đấu nối`, `Nhật ký hệ thống`, `Nhân bản AI`)*
- **Hàng 4 thẻ Phân nhóm Nghiệp vụ & Phạm vi Kho dữ liệu:** `Văn phòng HĐND & UBND (08 TK)` · `Kinh tế (05 TK)` · `Văn hóa - Xã hội (06 TK)` · `Nông nghiệp & Môi trường (05 TK)`.
- **Khu vực chính chia 2 khối:**
  - **Bảng Quản trị tài khoản & Phân quyền theo vị trí (`680px`):** Email cán bộ, Chức danh/Vị trí, Nhóm nghiệp vụ, Quyền truy cập kho dữ liệu riêng, Trạng thái kích hoạt.
  - **Cột Quản trị Chủ sở hữu & Nhân bản Multi-tenant (`416px`):**
    - Thẻ **Nhân bản hệ thống AI độc lập (`Nhân bản AI`)**: Cho phép Chủ sở hữu đóng gói cấu hình chuẩn và khởi tạo một hệ thống độc lập mới cho xã/phường khác (`UBND Phường... / UBND Xã...`) với kho dữ liệu tách biệt hoàn toàn.
    - Thẻ tóm tắt **Instruction của phòng & Cổng API đấu nối** + **Nhật ký hệ thống** gần nhất.

