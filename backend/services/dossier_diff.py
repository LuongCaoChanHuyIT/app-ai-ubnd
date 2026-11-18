from __future__ import annotations

import re
from typing import Any

STRUCTURED_FIELD_SPECS: list[tuple[str, str]] = [
    ("ho_ten", "Họ tên / Chủ hộ"),
    ("cccd", "Số CCCD / CMND"),
    ("thua_dat", "Thửa đất số"),
    ("to_ban_do", "Tờ bản đồ số"),
    ("dien_tich", "Diện tích (m2)"),
    ("so_tien", "Số tiền / Kinh phí (đồng)"),
    ("ngay_thang", "Ngày tháng lập / ghi nhận"),
    ("dia_chi", "Địa chỉ / Thôn - Tổ dân phố"),
]


def is_non_ocr_scan_file(file_rec: dict[str, Any]) -> bool:
    combined = f"{file_rec.get('parse_note', '')} {file_rec.get('extracted_text', '')}".lower()
    return ("ocr" in combined) and (
        "chưa có" in combined or "bản quét" in combined or "quét ảnh" in combined
    )


def build_ocr_warning_banner(files: list[dict[str, Any]]) -> str:
    scan_names = [f["filename"] for f in files if is_non_ocr_scan_file(f)]
    if not scan_names:
        return ""
    joined = ", ".join(f"**{n}**" for n in scan_names)
    return (
        f"> ⚠️ **Cảnh báo tệp PDF bản quét chưa có lớp văn bản OCR:** Tệp {joined} "
        "ở dạng hình ảnh quét/chữ ký số chưa trích xuất được toàn văn OCR tự động. "
        "Cán bộ thụ lý bắt buộc mở kiểm tra trực tiếp bản quét gốc trước khi trình ký!\n\n"
    )


def _dedup_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        clean = " ".join(it.split()).strip(" ,.;:-")
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    return out


def extract_structured_fields(text: str) -> dict[str, list[str]]:
    raw = text or ""
    result: dict[str, list[str]] = {k: [] for k, _ in STRUCTURED_FIELD_SPECS}

    # 1. Họ tên / Chủ hộ
    names: list[str] = []
    for m in re.finditer(
        r"(?:chủ\s+hộ|họ\s+và\s+tên|họ\s+tên|người\s+đề\s+nghị|chủ\s+sử\s+dụng(?:\s+đất)?|ông/bà)\s*[:\-]\s*([^\n.,;0-9]{3,45})",
        raw,
        flags=re.IGNORECASE,
    ):
        cand = re.split(r"\b(?:ngày|sinh|số|cccd|cmnd|địa\s+chỉ|diện\s+tích)\b", m.group(1), flags=re.IGNORECASE)[0]
        names.append(cand)
    for m in re.finditer(
        r"(?:công\s+dân|ông|bà)\s+([A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐ][a-zà-ỹđ]+(?:\s+[A-ZÀÁẠẢÃÂẦẤẬẨẪĂẰẮẶẲẴÈÉẸẺẼÊỀẾỆỂỄÌÍỊỈĨÒÓỌỎÕÔỒỐỘỔỖƠỜỚỢỞỠÙÚỤỦŨƯỪỨỰỬỮỲÝỴỶỸĐA-Z][a-zà-ỹđ]*){1,4})",
        raw,
    ):
        names.append(m.group(1))
    result["ho_ten"] = _dedup_keep_order(names)

    # 2. Số CCCD / CMND
    cccds: list[str] = []
    for m in re.finditer(
        r"(?:cccd|cmnd|căn\s+cước|định\s+danh)\s*(?:số)?\s*[:\-]?\s*(\d{9}|\d{12})\b",
        raw,
        flags=re.IGNORECASE,
    ):
        cccds.append(m.group(1))
    for m in re.finditer(r"\b(0\d{11})\b", raw):
        cccds.append(m.group(1))
    result["cccd"] = _dedup_keep_order(cccds)

    # 3. Thửa đất số
    thuas = [
        m.group(1)
        for m in re.finditer(
            r"thửa\s*(?:đất)?\s*(?:số)?\s*[:\-]?\s*(\d+[A-Za-z0-9/\-]*)",
            raw,
            flags=re.IGNORECASE,
        )
    ]
    result["thua_dat"] = _dedup_keep_order(thuas)

    # 4. Tờ bản đồ số
    tbds = [
        m.group(1)
        for m in re.finditer(
            r"(?:tờ\s+bản\s+đồ|tbđ)\s*(?:số)?\s*[:\-]?\s*(\d+[A-Za-z0-9/\-]*)",
            raw,
            flags=re.IGNORECASE,
        )
    ]
    result["to_ban_do"] = _dedup_keep_order(tbds)

    # 5. Diện tích (m2)
    areas = [
        f"{m.group(1)} m2"
        for m in re.finditer(
            r"(\d+(?:[.,]\d+)?)\s*(?:m2|m²|mét\s+vuông)\b",
            raw,
            flags=re.IGNORECASE,
        )
    ]
    result["dien_tich"] = _dedup_keep_order(areas)

    # 6. Số tiền / Kinh phí (đồng)
    moneys = [
        m.group(0)
        for m in re.finditer(
            r"\b(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:[.,]\d+)?\s*(?:triệu|tỷ|nghìn|ngàn))\s*(?:đồng|vnđ|đ)\b",
            raw,
            flags=re.IGNORECASE,
        )
    ]
    result["so_tien"] = _dedup_keep_order(moneys)

    # 7. Ngày tháng lập / ghi nhận
    dates: list[str] = []
    for m in re.finditer(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})\b", raw):
        dates.append(f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}")
    for m in re.finditer(
        r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
        raw,
        flags=re.IGNORECASE,
    ):
        dates.append(f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}")
    result["ngay_thang"] = _dedup_keep_order(dates)

    # 8. Địa chỉ / Thôn - Tổ dân phố
    addrs: list[str] = []
    for m in re.finditer(
        r"(?:địa\s+chỉ|nơi\s+thường\s+trú|thường\s+trú\s+tại)\s*[:\-]\s*([^\n.;]{3,80})",
        raw,
        flags=re.IGNORECASE,
    ):
        addrs.append(m.group(1))
    if not addrs:
        for m in re.finditer(
            r"\b((?:thôn|tổ\s+dân\s+phố|khu\s+phố|ấp)\s+[A-Za-z0-9À-ỹ\-]{1,25})",
            raw,
            flags=re.IGNORECASE,
        ):
            addrs.append(m.group(1))
    result["dia_chi"] = _dedup_keep_order(addrs)

    return result


def _normalize_field_value(field_key: str, val: str) -> str:
    v = " ".join(val.lower().split()).strip()
    if field_key in {"thua_dat", "to_ban_do"}:
        return v.lstrip("0") or "0"
    if field_key == "dien_tich":
        num_s = re.sub(r"[^\d.,]", "", v).replace(",", ".")
        try:
            return f"{float(num_s):.2f}"
        except ValueError:
            return v
    if field_key == "so_tien":
        m_unit = re.search(r"(\d+(?:[.,]\d+)?)\s*(triệu|tỷ|nghìn|ngàn)", v)
        if m_unit:
            base = float(m_unit.group(1).replace(",", "."))
            mult = {"nghìn": 1_000, "ngàn": 1_000, "triệu": 1_000_000, "tỷ": 1_000_000_000}[m_unit.group(2)]
            return str(int(round(base * mult)))
        digits = re.sub(r"\D", "", v)
        return digits or v
    return v


def run_structured_session_processing(
    files: list[dict[str, Any]],
    department: dict[str, Any],
    action: str,
    legal_note: str,
) -> dict[str, Any]:
    if not files:
        return {
            "action": action,
            "file_count": 0,
            "result_markdown": "Chưa có tài liệu nào được tải lên trong phiên hiện tại. Vui lòng tải lên ít nhất 01 tệp để AI xử lý.",
            "highlights": [],
        }

    ocr_banner = build_ocr_warning_banner(files)
    per_file_extracted = [(f, extract_structured_fields(f["extracted_text"])) for f in files]

    if action == "tom_tat":
        rows = []
        for idx, (f, fields) in enumerate(per_file_extracted, start=1):
            detected_summary = ", ".join(
                f"{label}: {'; '.join(fields[key])}"
                for key, label in STRUCTURED_FIELD_SPECS
                if fields[key]
            )
            meta_line = f"  - *Thực thể nhận diện:* {detected_summary}" if detected_summary else ""
            rows.append(
                f"{idx}. **{f['filename']}** ({f['size_bytes']} bytes · *{f['parse_note']}*)\n"
                f"  - *Nội dung tóm lược:* {f['extracted_text'][:280]}"
                + (f"\n{meta_line}" if meta_line else "")
            )
        return {
            "action": "tom_tat",
            "file_count": len(files),
            "result_markdown": (
                f"### Tóm tắt hồ sơ trong phiên ({len(files)} tệp · {department['name']})\n\n"
                f"{ocr_banner}"
                + "\n".join(rows)
                + f"\n\n*{legal_note}*"
            ),
            "highlights": [f["filename"] for f in files],
        }

    if action == "trich_xuat":
        highlights: list[str] = []
        md_blocks: list[str] = [
            f"### Bảng Trích xuất Thực thể Hành chính ({department['name']})\n",
        ]
        if ocr_banner:
            md_blocks.append(ocr_banner.rstrip() + "\n")

        header_cols = ["Trường thông tin"] + [f"`{f['filename']}`" for f in files]
        md_blocks.append("| " + " | ".join(header_cols) + " |")
        md_blocks.append("| " + " | ".join(["---"] * len(header_cols)) + " |")

        for field_key, field_label in STRUCTURED_FIELD_SPECS:
            vals_per_file = [
                "; ".join(fields[field_key]) if fields[field_key] else "*(Không ghi nhận)*"
                for _, fields in per_file_extracted
            ]
            for _, fields in per_file_extracted:
                highlights.extend(fields[field_key][:2])
            md_blocks.append(f"| **{field_label}** | " + " | ".join(vals_per_file) + " |")

        md_blocks.append(f"\n*{legal_note}*")
        return {
            "action": "trich_xuat",
            "file_count": len(files),
            "result_markdown": "\n".join(md_blocks),
            "highlights": _dedup_keep_order(highlights)[:10],
        }

    if action == "doi_chieu":
        warnings: list[str] = []
        matched_count = 0
        mismatch_count = 0

        md_lines: list[str] = [
            f"### Kết quả Đối chiếu Chéo Hồ sơ ({len(files)} tệp · {department['name']})\n",
        ]
        if ocr_banner:
            md_lines.append(ocr_banner.rstrip() + "\n")

        if len(files) < 2:
            msg = "Chỉ có 01 tệp trong phiên — đề nghị tải lên từ 02 tệp trở lên (ví dụ: Đơn đề nghị & Biên bản kiểm tra thực địa / Dự toán & Biên bản nghiệm thu) để đối chiếu chéo."
            warnings.append(msg)
            md_lines.append(f"- ℹ️ {msg}")
        else:
            header_cols = ["Trường đối chiếu"] + [f"Tệp {i} (`{f['filename']}`)" for i, f in enumerate(files, start=1)] + ["Trạng thái"]
            md_lines.append("| " + " | ".join(header_cols) + " |")
            md_lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")

            any_structured_compared = False
            for field_key, field_label in STRUCTURED_FIELD_SPECS:
                raw_cells: list[str] = []
                norm_sets: list[tuple[str, set[str], str]] = []
                for f, fields in per_file_extracted:
                    vals = fields[field_key]
                    cell = "; ".join(vals) if vals else "—"
                    raw_cells.append(cell)
                    if vals:
                        norm_sets.append(
                            (f["filename"], {_normalize_field_value(field_key, v) for v in vals}, cell)
                        )

                if not norm_sets:
                    continue

                any_structured_compared = True
                if len(norm_sets) == 1:
                    status_tag = f"*(Chỉ có ở `{norm_sets[0][0]}` — cần bổ sung đối chứng)*"
                else:
                    first_norms = norm_sets[0][1]
                    all_equal = all(ns == first_norms for _, ns, _ in norm_sets[1:])
                    if all_equal:
                        status_tag = "**[KHỚP]**"
                        matched_count += 1
                    else:
                        status_tag = "**[SAI LỆCH - CẦN XÁC MINH]**"
                        mismatch_count += 1
                        detail_pairs = " vs ".join(f"'{fname}': {disp}" for fname, _, disp in norm_sets)
                        warnings.append(f"[SAI LỆCH - CẦN XÁC MINH] {field_label}: {detail_pairs}.")

                md_lines.append(f"| **{field_label}** | " + " | ".join(raw_cells) + f" | {status_tag} |")

            # Fallback generic number comparison if files contain unstructured raw numbers without standard labels
            if not any_structured_compared:
                base_nums = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", files[0]["extracted_text"]))
                other_nums = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", files[1]["extracted_text"]))
                if base_nums != other_nums:
                    mismatch_count += 1
                    warnings.append(
                        f"[SAI LỆCH - CẦN XÁC MINH] Chênh lệch số liệu giữa '{files[0]['filename']}' ({', '.join(sorted(base_nums))}) và '{files[1]['filename']}' ({', '.join(sorted(other_nums))})."
                    )

            md_lines.append("\n#### Kết luận kiểm tra hồ sơ:")
            if mismatch_count > 0:
                md_lines.append(
                    f"- ⚠️ Phát hiện **{mismatch_count} trường thông tin `[SAI LỆCH - CẦN XÁC MINH]`** "
                    f"(bên cạnh {matched_count} trường `[KHỚP]`). **Chưa đủ điều kiện trình ký ngay!**"
                )
                for w in warnings:
                    md_lines.append(f"- 🔍 {w}")
                md_lines.append(
                    "- 👉 **Hướng xử lý:** Công chức thụ lý lập Phiếu yêu cầu bổ sung/làm rõ hoặc kiểm tra lại bản gốc/thực địa đối với các chỉ tiêu sai lệch trước khi dự thảo văn bản trình Lãnh đạo UBND."
                )
            else:
                md_lines.append(
                    f"- ✅ Toàn bộ **{matched_count} trường thông tin định danh và định lượng đều `[KHỚP]`** giữa các tệp trong phiên."
                )

        md_lines.append(f"\n*{legal_note}*")
        return {
            "action": "doi_chieu",
            "file_count": len(files),
            "result_markdown": "\n".join(md_lines),
            "highlights": warnings,
        }

    # tong_hop
    summary_rows: list[str] = []
    for idx, (f, fields) in enumerate(per_file_extracted, start=1):
        key_tags = [
            f"{label}: {'; '.join(fields[k])}"
            for k, label in STRUCTURED_FIELD_SPECS
            if fields[k]
        ]
        tag_str = f" — *({'; '.join(key_tags[:4])})*" if key_tags else ""
        summary_rows.append(f"{idx}. **{f['filename']}**: {f['extracted_text'][:220]}{tag_str}")

    return {
        "action": "tong_hop",
        "file_count": len(files),
        "result_markdown": (
            f"### Phiếu Tổng hợp Hồ sơ Trình Lãnh đạo ({department['name']})\n\n"
            f"{ocr_banner}"
            f"**1. Danh mục thành phần hồ sơ đã tiếp nhận ({len(files)} tệp):**\n"
            + "\n".join(summary_rows)
            + f"\n\n**2. Ý kiến tham mưu của bộ phận {department['name']}:**\n"
            "- Đã trích xuất thực thể hành chính và rà soát tính đầy đủ sơ bộ trên phiên làm việc tạm thời.\n"
            "- Đề nghị cán bộ chuyên môn kiểm tra đối chiếu bản chính, ký nháy thể thức trước khi trình Lãnh đạo UBND xem xét, quyết định.\n\n"
            f"*{legal_note}*"
        ),
        "highlights": [f["filename"] for f in files],
    }

