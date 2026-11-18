from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.db import can_access_private_docs, get_commune_name
from backend.services.legal_kb import search_official_docs_smart

APPENDIX_I_SYMBOLS: dict[str, tuple[str, str]] = {
    "quyết định": ("Quyết định", "QĐ-UBND"),
    "kế hoạch": ("Kế hoạch", "KH-UBND"),
    "báo cáo": ("Báo cáo", "BC-UBND"),
    "thông báo": ("Thông báo", "TB-UBND"),
    "tờ trình": ("Tờ trình", "TTr-UBND"),
    "chỉ thị": ("Chỉ thị", "CT-UBND"),
    "chương trình": ("Chương trình", "CTr-UBND"),
    "phương án": ("Phương án", "PA-UBND"),
    "quy chế": ("Quy chế", "QC-UBND"),
    "giấy mời": ("Giấy mời", "GM-UBND"),
    "biên bản": ("Biên bản", "BB-UBND"),
}

NO_VE_VIEC_TYPES: set[str] = {"Kế hoạch", "Báo cáo", "Chương trình", "Phương án", "Quy chế"}

CANONICAL_LEGAL_CITATIONS: dict[str, str] = {
    "65/2025/QH15": "Căn cứ Luật Tổ chức chính quyền địa phương số 65/2025/QH15 ngày 19 tháng 6 năm 2025;",
    "30/2020/NĐ-CP": "Căn cứ Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư;",
    "60/2014/QH13": "Căn cứ Luật Hộ tịch số 60/2014/QH13 ngày 20 tháng 11 năm 2014;",
    "42/2013/QH13": "Căn cứ Luật Tiếp công dân số 42/2013/QH13 ngày 25 tháng 11 năm 2013;",
    "02/2011/QH13": "Căn cứ Luật Khiếu nại số 02/2011/QH13 ngày 11 tháng 11 năm 2011;",
    "25/2018/QH14": "Căn cứ Luật Tố cáo số 25/2018/QH14 ngày 12 tháng 6 năm 2018;",
    "61/2018/NĐ-CP": "Căn cứ Nghị định số 61/2018/NĐ-CP ngày 23 tháng 4 năm 2018 của Chính phủ về thực hiện cơ chế một cửa, một cửa liên thông trong giải quyết thủ tục hành chính (được sửa đổi, bổ sung tại Nghị định số 107/2021/NĐ-CP);",
    "23/2015/NĐ-CP": "Căn cứ Nghị định số 23/2015/NĐ-CP ngày 16 tháng 02 năm 2015 của Chính phủ về cấp bản sao từ sổ gốc, chứng thực bản sao từ bản chính, chứng thực chữ ký và chứng thực hợp đồng, giao dịch;",
    "83/2015/QH13": "Căn cứ Luật Ngân sách nhà nước số 83/2015/QH13 ngày 25 tháng 6 năm 2015;",
    "58/2024/QH15": "Căn cứ Luật Đầu tư công số 58/2024/QH15 ngày 29 tháng 11 năm 2024;",
    "15/2017/QH14": "Căn cứ Luật Quản lý, sử dụng tài sản công số 15/2017/QH14 ngày 21 tháng 6 năm 2017;",
    "01/2021/NĐ-CP": "Căn cứ Nghị định số 01/2021/NĐ-CP ngày 04 tháng 01 năm 2021 của Chính phủ về đăng ký doanh nghiệp và hộ kinh doanh;",
    "38/2019/QH14": "Căn cứ Luật Quản lý thuế số 38/2019/QH14 ngày 13 tháng 6 năm 2019;",
    "85/2019/TT-BTC": "Căn cứ Thông tư số 85/2019/TT-BTC ngày 29 tháng 11 năm 2019 của Bộ trưởng Bộ Tài chính hướng dẫn về phí và lệ phí thuộc thẩm quyền quyết định của Hội đồng nhân dân tỉnh, thành phố trực thuộc Trung ương;",
    "20/2021/NĐ-CP": "Căn cứ Nghị định số 20/2021/NĐ-CP ngày 15 tháng 3 năm 2021 của Chính phủ quy định chính sách trợ giúp xã hội đối với đối tượng bảo trợ xã hội (được sửa đổi, bổ sung tại Nghị định số 76/2024/NĐ-CP);",
    "02/2020/UBTVQH14": "Căn cứ Pháp lệnh Ưu đãi người có công với cách mạng số 02/2020/UBTVQH14 ngày 09 tháng 12 năm 2020;",
    "110/2018/NĐ-CP": "Căn cứ Nghị định số 110/2018/NĐ-CP ngày 29 tháng 8 năm 2018 của Chính phủ quy định về quản lý và tổ chức lễ hội;",
    "86/2023/NĐ-CP": "Căn cứ Nghị định số 86/2023/NĐ-CP ngày 07 tháng 12 năm 2023 của Chính phủ quy định về khung tiêu chuẩn và trình tự, thủ tục, hồ sơ xét tặng danh hiệu Gia đình văn hóa, Thôn, tổ dân phố văn hóa, Xã, phường, thị trấn tiêu biểu;",
    "07/2021/NĐ-CP": "Căn cứ Nghị định số 07/2021/NĐ-CP ngày 27 tháng 01 năm 2021 của Chính phủ quy định chuẩn nghèo đa chiều giai đoạn 2021 - 2025;",
    "102/2016/QH13": "Căn cứ Luật Trẻ em số 102/2016/QH13 ngày 05 tháng 4 năm 2016;",
    "31/2024/QH15": "Căn cứ Luật Đất đai số 31/2024/QH15 ngày 18 tháng 01 năm 2024;",
    "101/2024/NĐ-CP": "Căn cứ Nghị định số 101/2024/NĐ-CP ngày 29 tháng 7 năm 2024 của Chính phủ quy định về điều tra cơ bản đất đai; đăng ký, cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất và Hệ thống thông tin đất đai;",
    "123/2024/NĐ-CP": "Căn cứ Nghị định số 123/2024/NĐ-CP ngày 04 tháng 10 năm 2024 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực đất đai;",
    "72/2020/QH14": "Căn cứ Luật Bảo vệ môi trường số 72/2020/QH14 ngày 17 tháng 11 năm 2020;",
    "45/2022/NĐ-CP": "Căn cứ Nghị định số 45/2022/NĐ-CP ngày 07 tháng 7 năm 2022 của Chính phủ quy định về xử phạt vi phạm hành chính trong lĩnh vực bảo vệ môi trường;",
    "16/2022/NĐ-CP": "Căn cứ Nghị định số 16/2022/NĐ-CP ngày 28 tháng 01 năm 2022 của Chính phủ quy định xử phạt vi phạm hành chính về xây dựng;",
    "318/2022/QĐ-TTg": "Căn cứ Quyết định số 318/2022/QĐ-TTg ngày 08 tháng 3 năm 2022 của Thủ tướng Chính phủ ban hành Bộ tiêu chí quốc gia về xã nông thôn mới và Bộ tiêu chí quốc gia về xã nông thôn mới nâng cao;",
    "24/2026/QĐ-UBND": "Căn cứ Quyết định số 24/2026/QĐ-UBND ngày 15 tháng 8 năm 2026 của Ủy ban nhân dân Thành phố ban hành Quy chế phối hợp quản lý đất đai, trật tự xây dựng và bảo vệ môi trường cấp xã, phường;",
}

EXPIRED_LAWS_REGISTRY: list[tuple[str, str, str]] = [
    ("45/2013/QH13", "Luật Đất đai năm 2013 (45/2013/QH13)", "Luật Đất đai số 31/2024/QH15"),
    ("luật đất đai năm 2013", "Luật Đất đai năm 2013", "Luật Đất đai số 31/2024/QH15"),
    ("luật đất đai 2013", "Luật Đất đai 2013", "Luật Đất đai số 31/2024/QH15"),
    ("55/2014/QH13", "Luật Bảo vệ môi trường năm 2014 (55/2014/QH13)", "Luật Bảo vệ môi trường số 72/2020/QH14"),
    ("91/2019/NĐ-CP", "Nghị định 91/2019/NĐ-CP về xử phạt đất đai", "Nghị định số 123/2024/NĐ-CP"),
    ("136/2013/NĐ-CP", "Nghị định 136/2013/NĐ-CP về bảo trợ xã hội", "Nghị định số 20/2021/NĐ-CP và Nghị định số 76/2024/NĐ-CP"),
    ("110/2004/NĐ-CP", "Nghị định 110/2004/NĐ-CP về công tác văn thư", "Nghị định số 30/2020/NĐ-CP"),
    ("01/2011/TT-BNV", "Thông tư 01/2011/TT-BNV về thể thức văn bản", "Nghị định số 30/2020/NĐ-CP"),
    ("77/2015/QH13", "Luật Tổ chức chính quyền địa phương 2015 (77/2015/QH13)", "Luật Tổ chức chính quyền địa phương số 65/2025/QH15"),
]

CHU_TICH_PERSONAL_TRIGGERS: tuple[str, ...] = (
    "xử phạt",
    "vi phạm hành chính",
    "vphc",
    "khắc phục hậu quả",
    "cưỡng chế",
    "ngừng thi công",
    "đình chỉ thi công",
    "khiếu nại",
    "tố cáo",
    "đối thoại",
    "gia đình văn hóa",
    "khen thưởng",
    "giấy khen",
    "thành lập tổ",
    "tổ kiểm tra",
    "tổ công tác",
    "tổ rà soát",
    "hội đồng hòa giải",
    "hội đồng tư vấn",
    "ban chỉ đạo",
    "ban tổ chức",
    "hộ nghèo",
    "hộ cận nghèo",
    "thoát nghèo",
    "trợ cấp xã hội",
    "bảo trợ xã hội",
    "cách ly trẻ em",
    "can thiệp khẩn cấp",
)

COLLOQUIAL_WORDS_REGEX = re.compile(
    r"(?<!\w)(ko|dc|đc|ok|okay|thanks|thank|nhé|nha|lun|bik|ntn|j)(?!\w)",
    flags=re.IGNORECASE,
)
COLLOQUIAL_PHRASES: tuple[str, ...] = (
    "vì vậy nên là",
    "tụi mình",
    "anh em",
    "hên xui",
    "nói chung là",
)


def parse_commune_identity(commune_name: str) -> tuple[str, str, str]:
    """Return (unit_upper_line, unit_display, place_name) per Nghị định 30/2020/NĐ-CP."""
    raw = " ".join((commune_name or "UBND Phường Trung Tâm").split()).strip()
    stripped = re.sub(
        r"^(?:ủy\s+ban\s+nhân\s+dân|ubnd)\s+",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()
    if not stripped:
        stripped = "Xã, phường trung tâm"

    unit_upper = stripped.upper()

    # Extract dateline place_name per Phụ lục I NĐ 30/2020/NĐ-CP:
    # "Phường Bến Nghé" -> "Bến Nghé"; "Phường 1" or "Phường X" keeps "Phường 1" / "Phường X"
    place_candidate = stripped
    m = re.match(r"^(?:phường|xã|thị\s+trấn)\s+(.+)$", stripped, flags=re.IGNORECASE)
    if m:
        tail = m.group(1).strip()
        if not tail.isdigit() and len(tail) > 1:
            place_candidate = tail
    elif "xã, phường" in stripped.lower():
        place_candidate = re.sub(
            r"^xã\s*,\s*phường\s+",
            "",
            stripped,
            flags=re.IGNORECASE,
        ).strip().title() or "Trung Tâm"

    return unit_upper, stripped, place_candidate


def resolve_doc_symbol_and_kind(doc_type: str, dept_code: str) -> tuple[str, str]:
    key = " ".join((doc_type or "Công văn").strip().lower().split())
    if key in APPENDIX_I_SYMBOLS:
        return APPENDIX_I_SYMBOLS[key]
    if key == "công văn":
        return ("Công văn", f"UBND-{dept_code}")
    return (doc_type.strip().title(), f"UBND-{dept_code}")


def _lower_first_unless_acronym(text: str) -> str:
    if not text:
        return text
    first_word = text.split()[0]
    if len(first_word) >= 2 and first_word.isupper():
        return text
    for proper_prefix in ("UBND", "HĐND", "MTTQ", "TTHC", "VPHC", "NĐ-CP", "Bộ phận"):
        if text.startswith(proper_prefix):
            return text
    return text[0].lower() + text[1:]


def clean_subject_title(raw_title: str, canonical_doc_type: str) -> str:
    """Strip duplicate 'Về việc' / 'V/v' prefixes and format subject per Phụ lục I NĐ 30/2020/NĐ-CP."""
    cleaned = " ".join((raw_title or "").split()).strip()
    prefix_re = re.compile(r"^\s*(?:về\s+việc|v\s*/\s*v)\s*[:\-–]?\s*", flags=re.IGNORECASE)
    while prefix_re.match(cleaned):
        cleaned = prefix_re.sub("", cleaned, count=1).strip()

    # Strip redundant leading doc_type name (e.g., "Kế hoạch triển khai..." inside a Kế hoạch)
    dtype_prefix_re = re.compile(
        r"^\s*" + re.escape(canonical_doc_type) + r"\s+",
        flags=re.IGNORECASE,
    )
    if dtype_prefix_re.match(cleaned):
        cleaned = dtype_prefix_re.sub("", cleaned, count=1).strip()
        while prefix_re.match(cleaned):
            cleaned = prefix_re.sub("", cleaned, count=1).strip()

    if not cleaned:
        cleaned = "thực hiện nhiệm vụ chuyên môn tại địa phương"

    if canonical_doc_type in NO_VE_VIEC_TYPES:
        return cleaned[0].upper() + cleaned[1:]
    if canonical_doc_type == "Công văn":
        return f"V/v {_lower_first_unless_acronym(cleaned)}"
    return f"Về việc {_lower_first_unless_acronym(cleaned)}"


def _format_vn_date(iso_date: str) -> str:
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", (iso_date or "").strip())
    if not m:
        return ""
    year, month_s, day_s = m.group(1), m.group(2), m.group(3)
    day_i = int(day_s)
    month_i = int(month_s)
    day_fmt = f"{day_i:02d}" if day_i < 10 else str(day_i)
    month_fmt = f"{month_i:02d}" if month_i in {1, 2} else str(month_i)
    return f"ngày {day_fmt} tháng {month_fmt} năm {year}"


def format_legal_basis_line(doc: dict[str, Any]) -> str:
    """Render 100% grammatical Vietnamese clerical 'Căn cứ ...;' clause."""
    doc_num = (doc.get("doc_number") or "").strip()
    if doc_num in CANONICAL_LEGAL_CITATIONS:
        return CANONICAL_LEGAL_CITATIONS[doc_num]

    doc_type = (doc.get("doc_type") or "Văn bản").strip()
    raw_title = re.sub(r"\s*\([^)]*\)\s*", " ", doc.get("title") or "").strip()
    raw_title = " ".join(raw_title.split())
    issuer = (doc.get("issuer") or "").strip()
    date_phrase = _format_vn_date(doc.get("issued_date") or "")
    date_part = f" {date_phrase}" if date_phrase else ""

    if doc_type.lower() in {"luật", "bộ luật", "pháp lệnh"} or raw_title.lower().startswith(("luật ", "pháp lệnh ")):
        law_name = raw_title if raw_title.lower().startswith(("luật ", "bộ luật ", "pháp lệnh ")) else f"{doc_type} {raw_title}"
        return f"Căn cứ {law_name} số {doc_num}{date_part};"

    # Strip duplicate leading doc_type in title (e.g., "Nghị định quy định về...")
    topic = re.sub(r"^\s*" + re.escape(doc_type) + r"\s+", "", raw_title, flags=re.IGNORECASE).strip()
    if not topic.lower().startswith(("về ", "quy định ", "ban hành ", "hướng dẫn ", "sửa đổi ")):
        topic = f"về {topic[0].lower() + topic[1:]}" if topic else ""
    else:
        topic = topic[0].lower() + topic[1:]
    issuer_part = f" của {issuer}" if issuer else ""
    topic_part = f" {topic}" if topic else ""
    return f"Căn cứ {doc_type} số {doc_num}{date_part}{issuer_part}{topic_part};"


def resolve_issuing_authority(
    authority_mode: str,
    canonical_doc_type: str,
    title: str,
    key_points: str,
) -> str:
    mode = (authority_mode or "auto").strip().lower()
    if mode in {"ubnd", "chu_tich"}:
        return mode

    # Auto classification based on Law on Organization of Local Government 65/2025/QH15
    if canonical_doc_type in {"Kế hoạch", "Báo cáo", "Tờ trình", "Chương trình", "Quy chế"}:
        return "ubnd"

    combined = f"{title} {key_points}".lower()
    if any(trig in combined for trig in CHU_TICH_PERSONAL_TRIGGERS):
        return "chu_tich"
    if canonical_doc_type == "Thông báo" and "lịch tiếp công dân" in combined and "chủ tịch" in combined:
        return "chu_tich"
    return "ubnd"


def build_nd30_draft(
    department: dict[str, Any],
    doc_type: str,
    title: str,
    key_points: str,
    recipient: str = "Các bộ phận chuyên môn trực thuộc UBND",
    actor_email: str = "tsh.co@tshorg.vn",
    authority_mode: str = "auto",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept_id = department["id"]
    dept_code = department["code"]
    commune_raw = get_commune_name(db_path)
    unit_upper, unit_display, place_name = parse_commune_identity(commune_raw)
    canonical_type, symbol_code = resolve_doc_symbol_and_kind(doc_type, dept_code)
    subject_line = clean_subject_title(title, canonical_type)
    resolved_auth = resolve_issuing_authority(authority_mode, canonical_type, title, key_points)

    allow_private = can_access_private_docs(actor_email, dept_id, db_path)
    matched_docs = search_official_docs_smart(
        f"{title} {key_points}",
        dept_id,
        include_private=allow_private,
        fallback_on_empty=False,
        db_path=db_path,
    )
    public_matched = [d for d in matched_docs if d["tier"] in {"trung_uong", "dia_phuong"}][:2]

    legal_bases = [
        CANONICAL_LEGAL_CITATIONS["65/2025/QH15"],
    ]
    for d in public_matched:
        if d["doc_number"] != "65/2025/QH15":
            clause = format_legal_basis_line(d)
            if clause not in legal_bases:
                legal_bases.append(clause)
    if len(legal_bases) == 1:
        legal_bases.append(CANONICAL_LEGAL_CITATIONS["30/2020/NĐ-CP"])

    raw_points = [
        p.strip(" -•\t")
        for p in re.split(r"[;\n]+", key_points or "")
        if p.strip(" -•\t")
    ]
    if not raw_points:
        raw_points = [
            f"Giao bộ phận {department['name']} chủ trì rà soát hồ sơ, tham mưu tổ chức thực hiện đúng quy định pháp luật và tiến độ đề ra.",
            "Các bộ phận chuyên môn, Trưởng thôn/Tổ trưởng tổ dân phố phối hợp cung cấp thông tin, tuyên truyền và giám sát thực hiện tại cơ sở.",
            f"Định kỳ tổng hợp kết quả, báo cáo lãnh đạo UBND {unit_display} xem xét, chỉ đạo kịp thời.",
        ]

    if resolved_auth == "chu_tich":
        signer_block = "CHỦ TỊCH"
    else:
        signer_block = "TM. ỦY BAN NHÂN DÂN\n                                       CHỦ TỊCH"

    # Build Nơi nhận without self-listing CHỦ TỊCH when CHỦ TỊCH signs directly
    if canonical_type == "Quyết định":
        last_art_num = len(raw_points) + 1
        first_recipient = f"- Như Điều {last_art_num};"
    elif canonical_type in {"Công văn", "Tờ trình"}:
        first_recipient = "- Như trên;"
    else:
        first_recipient = f"- {recipient};"

    noi_nhan_lines = [
        f"Nơi nhận:                              {signer_block}",
        first_recipient,
        f"- Thường trực Đảng ủy, HĐND {unit_display} (để b/c);",
        f"- Các Phó Chủ tịch UBND {unit_display};",
        f"- Lưu: VT, {dept_code}.",
        "                                       (Chữ ký số, đóng dấu)",
    ]

    header_block = (
        f"ỦY BAN NHÂN DÂN                       CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
        f"{unit_upper:<38}Độc lập - Tự do - Hạnh phúc\n"
    )

    if canonical_type == "Công văn":
        numbered_body = "\n".join(f"{idx}. {pt}" for idx, pt in enumerate(raw_points, start=1))
        basis_intro = legal_bases[-1].rstrip(";")
        draft_text = (
            f"{header_block}"
            f"Số: .../{symbol_code:<30}{place_name}, ngày 18 tháng 11 năm 2026\n"
            f"{subject_line}\n\n"
            f"Kính gửi: {recipient},\n\n"
            f"{basis_intro}; thực hiện nhiệm vụ quản lý nhà nước tại địa phương, "
            f"Ủy ban nhân dân {unit_display} đề nghị triển khai các nội dung sau:\n"
            f"{numbered_body}\n\n"
            f"Đề nghị {recipient} nghiêm túc tổ chức thực hiện; nếu có vướng mắc kịp thời phản ánh qua "
            f"bộ phận {department['name']} để tổng hợp, báo cáo./.\n\n"
            + "\n".join(noi_nhan_lines)
        )
    elif canonical_type == "Quyết định":
        promulgator = (
            f"CHỦ TỊCH ỦY BAN NHÂN DÂN {unit_upper}"
            if resolved_auth == "chu_tich"
            else f"ỦY BAN NHÂN DÂN {unit_upper}"
        )
        articles = "\n".join(f"Điều {idx}. {pt}" for idx, pt in enumerate(raw_points, start=1))
        next_art = len(raw_points) + 1
        draft_text = (
            f"{header_block}"
            f"Số: .../{symbol_code:<30}{place_name}, ngày 18 tháng 11 năm 2026\n\n"
            f"QUYẾT ĐỊNH\n"
            f"{subject_line}\n\n"
            f"{promulgator}\n\n"
            + "\n".join(legal_bases)
            + f"\nTheo đề nghị của Công chức phụ trách bộ phận {department['name']},\n\n"
            f"QUYẾT ĐỊNH:\n\n"
            f"{articles}\n"
            f"Điều {next_art}. Quyết định này có hiệu lực thi hành kể từ ngày ký. "
            f"Văn phòng HĐND và UBND, Công chức phụ trách bộ phận {department['name']} "
            f"và {recipient} chịu trách nhiệm thi hành Quyết định này./.\n\n"
            + "\n".join(noi_nhan_lines)
        )
    elif canonical_type == "Tờ trình":
        numbered_body = "\n".join(f"{idx}. {pt}" for idx, pt in enumerate(raw_points, start=1))
        draft_text = (
            f"{header_block}"
            f"Số: .../{symbol_code:<30}{place_name}, ngày 18 tháng 11 năm 2026\n\n"
            f"TỜ TRÌNH\n"
            f"{subject_line}\n\n"
            f"Kính gửi: {recipient},\n\n"
            + "\n".join(legal_bases)
            + f"\n\nỦy ban nhân dân {unit_display} kính trình {recipient} xem xét, phê duyệt các nội dung trọng tâm sau:\n"
            f"{numbered_body}\n\n"
            f"Ủy ban nhân dân {unit_display} kính trình {recipient} xem xét, quyết định./.\n\n"
            + "\n".join(noi_nhan_lines)
        )
    else:
        # Kế hoạch, Báo cáo, Thông báo, Chương trình...
        numbered_body = "\n".join(f"{idx}. {pt}" for idx, pt in enumerate(raw_points, start=1))
        section_one = "I. KẾT QUẢ VÀ NỘI DUNG ĐÁNH GIÁ" if canonical_type == "Báo cáo" else "I. NỘI DUNG TRIỂN KHAI TRỌNG TÂM"
        section_two = "II. ĐỀ XUẤT, KIẾN NGHỊ" if canonical_type == "Báo cáo" else "II. TỔ CHỨC THỰC HIỆN"
        draft_text = (
            f"{header_block}"
            f"Số: .../{symbol_code:<30}{place_name}, ngày 18 tháng 11 năm 2026\n\n"
            f"{canonical_type.upper()}\n"
            f"{subject_line}\n\n"
            + "\n".join(legal_bases)
            + f"\n\n{section_one}\n{numbered_body}\n\n"
            f"{section_two}\n"
            f"Giao bộ phận {department['name']} chủ trì theo dõi, đôn đốc thực hiện {canonical_type.lower()} này, "
            f"tổng hợp kết quả báo cáo theo quy định./.\n\n"
            + "\n".join(noi_nhan_lines)
        )

    return {
        "department_id": dept_id,
        "doc_type": doc_type,
        "title": title,
        "authority_mode": resolved_auth,
        "symbol": f".../{symbol_code}",
        "draft_text": draft_text,
    }


def audit_nd30_draft(
    department_id: str,
    doc_type: str,
    draft_text: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    text = draft_text or ""
    text_upper = text.upper()
    text_lower = text.lower()
    canonical_type, expected_symbol = resolve_doc_symbol_and_kind(doc_type, department_id)

    score = 100
    issues: list[dict[str, str]] = []

    def add_issue(
        code: str,
        criterion_id: str,
        penalty: int,
        severity: str,
        message: str,
        suggestion: str,
    ) -> None:
        nonlocal score
        score -= penalty
        issues.append(
            {
                "code": code,
                "criterion_id": criterion_id,
                "severity": severity,
                "message": message,
                "suggestion": suggestion,
            }
        )

    # =========================================================================
    # 1. BỐ CỤC & THỂ THỨC (NGHỊ ĐỊNH 30/2020/NĐ-CP)
    # =========================================================================
    bo_cuc_notes: list[str] = []
    bo_cuc_fail = False
    bo_cuc_warn = False

    if "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" not in text_upper or "ĐỘC LẬP - TỰ DO - HẠNH PHÚC" not in text_upper:
        bo_cuc_fail = True
        bo_cuc_notes.append("Thiếu Quốc hiệu hoặc Tiêu ngữ chuẩn.")
        add_issue(
            "MISSING_NATIONAL_HEADER",
            "bo_cuc",
            18,
            "error",
            "Thiếu Quốc hiệu 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM' hoặc Tiêu ngữ 'Độc lập - Tự do - Hạnh phúc'.",
            "Bổ sung đầy đủ Quốc hiệu (in hoa, cỡ chữ 12–13, đứng đậm) và Tiêu ngữ ở góc trên bên phải theo Phụ lục I Nghị định 30/2020/NĐ-CP.",
        )

    if not re.search(r"ngày\s+(?:\d{1,2}|\.{2,})\s+tháng\s+(?:\d{1,2}|\.{2,})\s+năm\s+\d{4}", text_lower):
        bo_cuc_warn = True
        bo_cuc_notes.append("Thiếu địa danh và mốc ngày tháng năm ban hành.")
        add_issue(
            "MISSING_DATELINE",
            "bo_cuc",
            10,
            "warning",
            "Chưa ghi nhận dòng địa danh và ngày, tháng, năm ban hành văn bản đúng quy chuẩn.",
            "Bổ sung dòng '[Địa danh], ngày ... tháng ... năm 2026' (ngày < 10 và tháng 01, 02 có số 0 phía trước).",
        )

    if "NƠI NHẬN" not in text_upper:
        bo_cuc_fail = True
        bo_cuc_notes.append("Thiếu mục 'Nơi nhận:'.")
        add_issue(
            "MISSING_NOI_NHAN",
            "bo_cuc",
            14,
            "error",
            "Thiếu khối 'Nơi nhận:' ở cuối văn bản.",
            "Bổ sung mục 'Nơi nhận:' ngang hàng với quyền hạn, chức vụ của người ký.",
        )
    elif not re.search(r"lưu\s*:\s*vt", text_lower):
        bo_cuc_fail = True
        bo_cuc_notes.append("Mục Nơi nhận thiếu dòng 'Lưu: VT, ...'.")
        add_issue(
            "MISSING_LUU_VT",
            "bo_cuc",
            12,
            "error",
            "Khối Nơi nhận thiếu dòng lưu trữ bắt buộc 'Lưu: VT, [Chữ viết tắt đơn vị soạn thảo].'.",
            f"Thêm dòng '- Lưu: VT, {department_id}.' ở dòng cuối cùng của mục Nơi nhận theo khoản 9 Điều 8 Nghị định 30/2020/NĐ-CP.",
        )

    # Check (a): Duplicate "Về việc Về việc" / "V/v V/v"
    if re.search(r"\b(?:về\s+việc|v/v)\s+(?:về\s+việc|v/v)\b", text_lower):
        bo_cuc_fail = True
        bo_cuc_notes.append("Trích yếu bị lặp tiền tố 'Về việc' / 'V/v'.")
        add_issue(
            "DUPLICATE_VE_VIEC",
            "bo_cuc",
            15,
            "error",
            "Phát hiện lỗi lặp tiền tố 'Về việc Về việc' hoặc 'V/v Về việc' trong trích yếu nội dung.",
            "Lược bỏ tiền tố thừa; chỉ giữ duy nhất một tiền tố ('Về việc' cho Quyết định/Thông báo/Tờ trình, 'V/v' cho Công văn).",
        )

    # Check (a2): Wrong "Về việc" on Báo cáo / Kế hoạch
    if canonical_type in {"Kế hoạch", "Báo cáo"}:
        non_empty_lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for idx, ln in enumerate(non_empty_lines[:-1]):
            if ln.upper() == canonical_type.upper():
                subj = non_empty_lines[idx + 1]
                if re.match(r"^(?:về\s+việc|v/v)\b", subj, flags=re.IGNORECASE):
                    bo_cuc_fail = True
                    bo_cuc_notes.append(f"{canonical_type} không dùng tiền tố 'Về việc' ở dòng trích yếu.")
                    add_issue(
                        "WRONG_PREFIX_ON_REPORT_OR_PLAN",
                        "bo_cuc",
                        12,
                        "error",
                        f"Văn bản loại '{canonical_type}' đang gắn cụm từ 'Về việc'/'V/v' đầu trích yếu sai mẫu Phụ lục I Nghị định 30/2020/NĐ-CP.",
                        f"Xóa chữ 'Về việc' dưới dòng {canonical_type.upper()}, viết trực tiếp nội dung trích yếu (ví dụ: 'Kết quả công tác...').",
                    )
                break

    # Check (c): Symbol mismatch against doc_type
    if canonical_type == "Công văn":
        has_valid_cv_sym = bool(re.search(r"/ubnd-[a-z0-9]+", text_lower)) and "/cv-ubnd" not in text_lower
        if not has_valid_cv_sym:
            bo_cuc_fail = True
            bo_cuc_notes.append(f"Ký hiệu Công văn chưa đúng chuẩn '.../UBND-{department_id}'.")
            add_issue(
                "SYMBOL_MISMATCH",
                "bo_cuc",
                14,
                "error",
                f"Ký hiệu văn bản chưa khớp thể thức Công văn (Công văn không viết tắt CV-UBND mà ghi .../UBND-{department_id}).",
                f"Sửa dòng số và ký hiệu thành 'Số: .../UBND-{department_id}'.",
            )
    else:
        if f"/{expected_symbol.lower()}" not in text_lower:
            bo_cuc_fail = True
            bo_cuc_notes.append(f"Ký hiệu văn bản lệch loại '{canonical_type}' (cần '{expected_symbol}').")
            add_issue(
                "SYMBOL_MISMATCH",
                "bo_cuc",
                16,
                "error",
                f"Số và ký hiệu văn bản không khớp với loại văn bản '{canonical_type}' (thiếu '/{expected_symbol}').",
                f"Đổi ký hiệu văn bản thành 'Số: .../{expected_symbol}' theo Phụ lục I Nghị định 30/2020/NĐ-CP.",
            )

    bo_cuc_status = "khong_dat" if bo_cuc_fail else ("can_ra_soat" if bo_cuc_warn else "dat")
    bo_cuc_detail = (
        " ".join(bo_cuc_notes)
        if bo_cuc_notes
        else f"Đầy đủ Quốc hiệu, Tiêu ngữ, ký hiệu '{expected_symbol}', trích yếu, địa danh và khối Nơi nhận/Lưu: VT đúng Nghị định 30/2020/NĐ-CP."
    )

    # =========================================================================
    # 2. CĂN CỨ PHÁP LÝ
    # =========================================================================
    can_cu_notes: list[str] = []
    can_cu_fail = False
    can_cu_warn = False

    has_can_cu = ("CĂN CỨ" in text_upper) or (canonical_type == "Công văn" and "THỰC HIỆN" in text_upper)
    if not has_can_cu:
        can_cu_warn = True
        can_cu_notes.append("Chưa viện dẫn căn cứ pháp lý hoặc văn bản chỉ đạo đầu văn bản.")
        add_issue(
            "MISSING_LEGAL_BASIS",
            "can_cu",
            18,
            "warning",
            "Dự thảo chưa nêu căn cứ pháp lý trực tiếp (Luật Tổ chức chính quyền địa phương và văn bản chuyên ngành).",
            "Bổ sung các dòng 'Căn cứ ...;' đối với văn bản pháp quy đang còn hiệu lực thi hành.",
        )

    # Check (d1): Expired laws
    for expired_token, expired_label, replacement_law in EXPIRED_LAWS_REGISTRY:
        if expired_token.lower() in text_lower:
            can_cu_fail = True
            can_cu_notes.append(f"Viện dẫn văn bản đã hết hiệu lực: {expired_label}.")
            add_issue(
                "EXPIRED_LEGAL_BASIS",
                "can_cu",
                25,
                "error",
                f"Dự thảo đang viện dẫn '{expired_label}' đã hết hiệu lực pháp luật!",
                f"Thay thế ngay bằng '{replacement_law}' đang có hiệu lực hiện hành.",
            )

    # Check (d2): Clumsy grammar ("Căn cứ Luật số ... về Luật ...", "về Nghị định ...")
    if re.search(r"căn\s+cứ\s+(?:luật|nghị\s+định|thông\s+tư|quyết\s+định)[^\n;]{0,60}\bvề\s+(?:luật|nghị\s+định|thông\s+tư|quyết\s+định)\b", text_lower):
        can_cu_fail = True
        can_cu_notes.append("Câu 'Căn cứ' diễn đạt lủng củng lặp danh từ loại văn bản ('... về Luật/Nghị định ...').")
        add_issue(
            "AWKWARD_CAN_CU_GRAMMAR",
            "can_cu",
            12,
            "error",
            "Cấu trúc câu 'Căn cứ ... về Luật/Nghị định ...' sai ngữ pháp văn bản hành chính nhà nước.",
            "Viết chuẩn tên gọi văn bản: ví dụ 'Căn cứ Luật Đất đai số 31/2024/QH15 ngày 18 tháng 01 năm 2024;'.",
        )

    can_cu_status = "khong_dat" if can_cu_fail else ("can_ra_soat" if can_cu_warn else "dat")
    can_cu_detail = (
        " ".join(can_cu_notes)
        if can_cu_notes
        else "Các căn cứ pháp lý được trình bày đúng ngữ pháp hành chính và đang còn hiệu lực thi hành."
    )

    # =========================================================================
    # 3. THẨM QUYỀN BAN HÀNH & CHỮ KÝ
    # =========================================================================
    tq_notes: list[str] = []
    tq_fail = False
    tq_warn = False

    has_tm_ubnd = "TM. ỦY BAN NHÂN DÂN" in text_upper
    has_kt_ct = "KT. CHỦ TỊCH" in text_upper
    has_chu_tich_sig = "CHỦ TỊCH" in text_upper

    if not (has_tm_ubnd or has_chu_tich_sig):
        tq_warn = True
        tq_notes.append("Thiếu thể thức quyền hạn, chức vụ người ký.")
        add_issue(
            "MISSING_SIGNER_AUTHORITY",
            "tham_quyen",
            18,
            "error",
            "Chưa ghi rõ chức vụ và thẩm quyền người ký ban hành văn bản.",
            "Ghi 'TM. ỦY BAN NHÂN DÂN / CHỦ TỊCH' (thẩm quyền tập thể UBND) hoặc 'CHỦ TỊCH' (thẩm quyền riêng Chủ tịch UBND).",
        )

    if canonical_type == "Quyết định":
        if "ĐIỀU 1" not in text_upper:
            tq_fail = True
            tq_notes.append("Quyết định thiếu kết cấu 'Điều 1...'.")
            add_issue(
                "MISSING_DIEU_1",
                "tham_quyen",
                15,
                "error",
                "Văn bản loại 'Quyết định' không có kết cấu điều khoản ('Điều 1. ...').",
                "Trình bày nội dung Quyết định theo Điều 1, Điều 2... và điều khoản hiệu lực, trách nhiệm thi hành.",
            )
        if "CHỊU TRÁCH NHIỆM THI HÀNH" not in text_upper and "HIỆU LỰC" not in text_upper:
            tq_warn = True
            tq_notes.append("Quyết định thiếu điều khoản hiệu lực và trách nhiệm thi hành.")
            add_issue(
                "MISSING_EXECUTION_ARTICLE",
                "tham_quyen",
                10,
                "warning",
                "Quyết định chưa nêu rõ hiệu lực thi hành và các bộ phận/cá nhân chịu trách nhiệm thi hành.",
                "Bổ sung điều khoản cuối: 'Quyết định này có hiệu lực kể từ ngày ký. Văn phòng HĐND và UBND... chịu trách nhiệm thi hành.'.",
            )

        # Check (e): Contradiction between promulgation line and signature block
        body_before_qd = text_upper.split("QUYẾT ĐỊNH:")[0] if "QUYẾT ĐỊNH:" in text_upper else text_upper
        promulgates_as_chairman = bool(re.search(r"CHỦ\s+TỊCH\s+ỦY\s+BAN\s+NHÂN\s+DÂN", body_before_qd))
        promulgates_as_ubnd_collective = (
            not promulgates_as_chairman
            and len(re.findall(r"ỦY\s+BAN\s+NHÂN\s+DÂN", body_before_qd)) >= 2
        )

        if promulgates_as_chairman and has_tm_ubnd:
            tq_fail = True
            tq_notes.append("Mâu thuẫn thẩm quyền: phần mở đầu ghi 'CHỦ TỊCH ỦY BAN NHÂN DÂN ... QUYẾT ĐỊNH:' nhưng cuối văn bản lại ký 'TM. ỦY BAN NHÂN DÂN'.")
            add_issue(
                "AUTHORITY_SIGNATURE_CONTRADICTION",
                "tham_quyen",
                22,
                "error",
                "Mâu thuẫn nghiêm trọng thẩm quyền ban hành: dòng thẩm quyền ghi cá nhân 'CHỦ TỊCH ỦY BAN NHÂN DÂN' nhưng phần chữ ký lại ghi thay mặt tập thể 'TM. ỦY BAN NHÂN DÂN'.",
                "Nếu thuộc thẩm quyền riêng Chủ tịch UBND (xử phạt VPHC, khiếu nại, Gia đình văn hóa...), xóa dòng 'TM. ỦY BAN NHÂN DÂN' và chỉ ký 'CHỦ TỊCH'.",
            )
        elif promulgates_as_ubnd_collective and has_chu_tich_sig and not has_tm_ubnd:
            tq_fail = True
            tq_notes.append("Mâu thuẫn thẩm quyền: Quyết định của tập thể UBND nhưng phần chữ ký thiếu 'TM. ỦY BAN NHÂN DÂN'.")
            add_issue(
                "MISSING_TM_ON_COLLECTIVE_DECISION",
                "tham_quyen",
                20,
                "error",
                "Quyết định ban hành nhân danh tập thể 'ỦY BAN NHÂN DÂN' nhưng chữ ký cuối trang không ghi 'TM. ỦY BAN NHÂN DÂN'.",
                "Thêm dòng 'TM. ỦY BAN NHÂN DÂN' phía trên chức vụ 'CHỦ TỊCH' theo khoản 7 Điều 8 Nghị định 30/2020/NĐ-CP.",
            )

    # Check self-listing signer in Nơi nhận
    if has_chu_tich_sig and not has_kt_ct and re.search(r"-\s*chủ\s+tịch\s*(?:,|ubnd)", text_lower):
        tq_warn = True
        tq_notes.append("Mục Nơi nhận tự liệt kê lại chính Chủ tịch (người trực tiếp ký).")
        add_issue(
            "SELF_LISTED_IN_NOI_NHAN",
            "tham_quyen",
            8,
            "warning",
            "Chủ tịch UBND trực tiếp ký nhưng mục Nơi nhận vẫn ghi '- Chủ tịch, các PCT UBND...'.",
            "Đổi thành '- Thường trực Đảng ủy, HĐND (để b/c);' và '- Các Phó Chủ tịch UBND;'.",
        )

    tq_status = "khong_dat" if tq_fail else ("can_ra_soat" if tq_warn else "dat")
    tq_detail = (
        " ".join(tq_notes)
        if tq_notes
        else "Thẩm quyền ban hành, kết cấu văn bản và chữ ký thống nhất, đúng phạm vi UBND / Chủ tịch UBND cấp xã."
    )

    # =========================================================================
    # 4. TÍNH LOGIC & KHẢ THI NGHIỆP VỤ
    # =========================================================================
    logic_notes: list[str] = []
    logic_fail = False
    logic_warn = False

    has_ellipsis = "..." in text or "…" in text
    bracket_placeholders = re.findall(r"\[(?:điền|nhập|số|tên|ngày)[^\]]*\]", text, flags=re.IGNORECASE)

    if bracket_placeholders:
        logic_fail = True
        logic_notes.append(f"Còn trường trống chưa điền thông tin: {', '.join(bracket_placeholders[:3])}.")
        add_issue(
            "UNFILLED_BRACKET_PLACEHOLDERS",
            "logic",
            14,
            "error",
            f"Dự thảo còn ô giữ chỗ chưa hoàn thiện dữ liệu thực tế: {', '.join(bracket_placeholders[:3])}.",
            "Điền đầy đủ tên đơn vị, số tiền, mốc thời gian cụ thể trước khi trình Lãnh đạo ký ban hành.",
        )
    if has_ellipsis:
        logic_warn = True
        logic_notes.append("Còn dấu ba chấm '...' tại mục Số văn bản hoặc nội dung chờ hoàn thiện.")
        add_issue(
            "UNFILLED_ELLIPSIS",
            "logic",
            8,
            "warning",
            "Còn ký hiệu chờ '...' trong dự thảo (ví dụ tại mục Số văn bản).",
            "Rà soát nội dung số liệu và cấp số văn bản đi tại bộ phận Văn thư ngay sau khi Lãnh đạo ký duyệt.",
        )

    logic_status = "khong_dat" if logic_fail else ("can_ra_soat" if logic_warn else "dat")
    logic_detail = (
        " ".join(logic_notes)
        if logic_notes
        else "Bố cục điều khoản và số liệu thống nhất, không còn trường bỏ trống trước khi phát hành."
    )

    # =========================================================================
    # 5. CHÍNH TẢ & VĂN PHONG HÀNH CHÍNH
    # =========================================================================
    found_slang: list[str] = []
    for m in COLLOQUIAL_WORDS_REGEX.finditer(text):
        tok = m.group(1).lower()
        if tok not in found_slang:
            found_slang.append(tok)
    for phr in COLLOQUIAL_PHRASES:
        if phr in text_lower and phr not in found_slang:
            found_slang.append(phr)

    if found_slang:
        add_issue(
            "COLLOQUIAL_SLANG",
            "van_phong",
            16,
            "error",
            f"Phát hiện từ viết tắt tuỳ tiện / khẩu ngữ sai chuẩn văn phong hành chính: {', '.join(found_slang)}.",
            "Thay toàn bộ từ viết tắt/khẩu ngữ bằng thuật ngữ hành chính trang trọng, tường minh ('không', 'được', 'do đó', 'các bộ phận chuyên môn').",
        )
        van_phong_status = "khong_dat"
        van_phong_detail = f"Phát hiện từ ngữ khẩu ngữ / viết tắt không phù hợp văn phong hành chính: {', '.join(found_slang)}."
    else:
        van_phong_status = "dat"
        van_phong_detail = "Ngôn ngữ khách quan, lịch sự, chuẩn mực văn phong hành chính công vụ."

    criteria = [
        {
            "id": "bo_cuc",
            "name": "Bố cục & Thể thức NĐ 30/2020",
            "status": bo_cuc_status,
            "detail": bo_cuc_detail,
        },
        {
            "id": "can_cu",
            "name": "Căn cứ pháp lý",
            "status": can_cu_status,
            "detail": can_cu_detail,
        },
        {
            "id": "tham_quyen",
            "name": "Thẩm quyền ban hành & Chữ ký",
            "status": tq_status,
            "detail": tq_detail,
        },
        {
            "id": "logic",
            "name": "Tính logic & Khả thi nghiệp vụ",
            "status": logic_status,
            "detail": logic_detail,
        },
        {
            "id": "van_phong",
            "name": "Chính tả & Văn phong hành chính",
            "status": van_phong_status,
            "detail": van_phong_detail,
        },
    ]

    final_score = max(0, min(100, score))
    issue_count = len(issues)
    return {
        "score": final_score,
        "doc_type": doc_type,
        "department_id": department_id,
        "criteria": criteria,
        "issues": issues,
        "summary": (
            f"Dự thảo đạt {final_score}/100 điểm chuẩn hóa Nghị định 30/2020/NĐ-CP "
            f"(phát hiện {issue_count} điểm lưu ý/cần chỉnh sửa). "
            "Cán bộ tham mưu rà soát kỹ trước khi trình Lãnh đạo UBND ký ban hành."
        ),
    }

