from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".docx", ".pdf"}


class FileTooLargeError(ValueError):
    """Raised when uploaded payload exceeds MAX_UPLOAD_BYTES."""


class UnsupportedFileError(ValueError):
    """Raised when file extension is not permitted."""


def _extract_docx_text(content: bytes) -> tuple[str, str]:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "word/document.xml" not in zf.namelist():
                return (
                    "",
                    "Tệp DOCX không có cấu trúc word/document.xml chuẩn; đã ghi nhận siêu dữ liệu tệp.",
                )
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        paragraphs: list[str] = []
        for para in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
            runs = [
                node.text
                for node in para.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
                if node.text
            ]
            if runs:
                paragraphs.append("".join(runs).strip())
        extracted = "\n".join(p for p in paragraphs if p)
        if not extracted.strip():
            return ("", "Tệp DOCX rỗng hoặc chỉ chứa hình ảnh/biểu mẫu quét.")
        return (extracted, "Đã trích xuất văn bản DOCX")
    except Exception:
        return (
            "",
            "Không thể giải mã nội dung DOCX (tệp lỗi hoặc định dạng nhị phân cũ); đã lưu thông tin tệp trong phiên.",
        )


def _extract_pdf_text(filename: str, content: bytes) -> tuple[str, str]:
    try:
        import pypdf  # type: ignore

        reader = pypdf.PdfReader(io.BytesIO(content))
        pages = [(p.extract_text() or "").strip() for p in reader.pages]
        joined = "\n\n".join(p for p in pages if p)
        if joined.strip():
            return (joined, f"Đã trích xuất văn bản PDF ({len(reader.pages)} trang)")
    except Exception:
        pass

    # Lightweight PDF stream inspection fallback (handles uncompressed & FlateDecode text blocks)
    chunks: list[str] = []
    for stream_match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", content, re.DOTALL):
        raw = stream_match.group(1)
        decoded_bytes = raw
        try:
            decoded_bytes = zlib.decompress(raw)
        except Exception:
            pass
        for literal in re.findall(rb"\(([^()]{2,400})\)\s*Tj", decoded_bytes):
            try:
                txt = literal.decode("utf-8", errors="ignore").strip()
                if txt and any(ch.isalpha() for ch in txt):
                    chunks.append(txt)
            except Exception:
                continue

    joined_fallback = " ".join(chunks).strip()
    if len(joined_fallback) >= 12:
        return (joined_fallback, "Đã trích xuất lớp văn bản từ PDF")

    return (
        f"[Tệp PDF quét ảnh / chữ ký số: {filename} — chưa có lớp văn bản OCR trực tiếp]",
        "Tệp PDF dạng bản quét hình ảnh hoặc chưa có lớp text OCR; hệ thống đã ghi nhận siêu dữ liệu tệp để cán bộ đối chiếu.",
    )


def parse_uploaded_bytes(filename: str, content: bytes) -> tuple[str, str]:
    clean_name = Path(filename or "tai_lieu").name
    ext = Path(clean_name).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileError(
            f"Định dạng '{ext or 'không xác định'}' không được hỗ trợ. Chỉ chấp nhận: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    if len(content) > MAX_UPLOAD_BYTES:
        raise FileTooLargeError(
            f"Dung lượng tệp vượt quá giới hạn 10 MB ({len(content)} bytes)."
        )

    if ext in {".txt", ".md", ".csv"}:
        text = content.decode("utf-8", errors="replace").strip()
        return (
            text or f"[Tệp {clean_name} không có nội dung văn bản]",
            f"Đã đọc tệp văn bản ({ext})",
        )

    if ext == ".json":
        raw_text = content.decode("utf-8", errors="replace").strip()
        try:
            parsed = json.loads(raw_text)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            return (pretty, "Đã chuẩn hóa cấu trúc JSON")
        except Exception:
            return (raw_text, "Tệp JSON không đúng cú pháp chuẩn; đã đọc dưới dạng văn bản thô")

    if ext == ".docx":
        text, note = _extract_docx_text(content)
        if not text:
            text = f"[Tệp DOCX: {clean_name} — không có đoạn văn bản trích xuất được]"
        return (text, note)

    return _extract_pdf_text(clean_name, content)

