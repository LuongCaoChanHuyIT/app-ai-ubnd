from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend.db import get_conn

# Single-syllable Vietnamese administrative stopwords & ambiguous morphemes
# that should NOT trigger standalone false-positive matches across domains.
VIETNAMESE_ADMIN_STOPWORDS: set[str] = {
    "của", "và", "các", "cho", "tại", "về", "việc", "theo", "như", "thế", "nào",
    "hỏi", "xin", "cần", "làm", "gì", "xã", "phường", "thị", "trấn", "ubnd", "hđnd",
    "cán", "bộ", "công", "chức", "cấp", "có", "được", "không", "trong", "với",
    "trên", "dưới", "địa", "bàn", "phương", "khi", "này", "đó", "hay", "hoặc",
    "để", "từ", "đến", "ra", "vào", "lên", "xuống", "một", "hai", "ba", "những",
    "người", "dân", "hộ", "hiện", "nay", "quy", "định", "hướng", "dẫn", "thực",
    "giải", "quyết", "xử", "lý", "trường", "hợp", "thủ", "tục", "hồ", "sơ", "văn",
    "bản", "cơ", "quan", "nhà", "nước", "đơn", "vị", "phòng", "ban", "tư", "vấn",
    "giúp", "tôi", "em", "anh", "chị", "ông", "bà", "năm", "tháng", "ngày", "số",
    "luật", "nghị", "thông", "tờ", "trình", "báo", "cáo", "kế", "hoạch", "triển",
    "khai", "tác", "quản", "vừa", "tải", "phiên", "kiểm", "tra", "lại", "luôn",
    "đồng", "thời", "bên", "tự", "ý", "lần", "đầu", "cuối", "quý", "kỳ", "thẩm",
    "mức", "chuẩn", "đối", "tượng", "danh", "sách", "hành", "chính", "phép", "sao",
    "du", "phóng", "tàu", "gia", "đình", "khu", "cư", "tổ", "thôn", "phố", "chủ",
    "tịch", "ủy", "nhân", "soạn", "thảo", "nhanh", "chuyên", "sâu", "mới", "cũ",
}

GENERIC_ADMIN_PHRASES: set[str] = {
    "tại xã", "tại phường", "trên địa", "địa bàn", "địa bàn xã", "trên địa bàn",
    "hộ dân", "hộ gia", "gia đình", "hộ gia đình", "người dân", "công dân",
    "hướng dẫn", "quy định", "quy định về", "thực hiện", "giải quyết", "xử lý",
    "thủ tục", "hồ sơ", "văn bản", "cấp xã", "ubnd xã", "ubnd phường", "ubnd cấp",
    "chủ tịch", "chủ tịch ubnd", "tư vấn", "thẩm định", "soạn thảo", "vừa tải",
    "tải lên", "trong phiên", "hiện tại", "kiểm tra", "triển khai", "công tác",
    "quản lý", "nhà nước", "cơ quan", "đơn vị", "tổ dân", "dân phố", "tổ dân phố",
    "khu dân", "dân cư", "khu dân cư", "lần đầu", "định kỳ", "hằng năm", "hàng năm",
}

# Domain concept expansion: maps colloquial/practical commune phrases to canonical doc numbers & terms
CONCEPT_TRIGGERS: list[tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]] = [
    (
        ("phân loại rác", "rác thải sinh hoạt", "chất thải rắn", "vứt rác", "đổ rác", "bừa bãi", "rác tại nguồn"),
        ("72/2020/QH14", "45/2022/NĐ-CP"),
        ("chất thải rắn sinh hoạt", "phân loại tại nguồn"),
    ),
    (
        ("hòa giải tranh chấp đất", "tranh chấp đất", "tranh chấp ranh giới", "ranh giới đất", "hội đồng hòa giải"),
        ("31/2024/QH15", "HD-03/2026/UBND-NNMT"),
        ("điều 235", "hòa giải tranh chấp đất đai"),
    ),
    (
        ("sổ đỏ", "sổ hồng", "cấp giấy chứng nhận", "nguồn gốc đất", "niêm yết 15 ngày", "đăng ký đất đai"),
        ("31/2024/QH15", "101/2024/NĐ-CP"),
        ("điều 136", "điều 137", "điều 138", "giấy chứng nhận quyền sử dụng đất"),
    ),
    (
        ("lấn chiếm đất", "lấn đất", "chiếm đất", "chuyển mục đích sử dụng đất", "xây trên đất nông nghiệp", "hủy hoại đất"),
        ("123/2024/NĐ-CP",),
        ("lấn đất, chiếm đất", "xử phạt vi phạm hành chính trong lĩnh vực đất đai"),
    ),
    (
        ("trật tự xây dựng", "xây dựng không phép", "xây dựng trái phép", "xây không phép", "sai phép", "ngừng thi công"),
        ("16/2022/NĐ-CP", "QT-04/2026/UBND-NNMT"),
        ("trật tự xây dựng", "ngừng thi công xây dựng"),
    ),
    (
        ("nông thôn mới", "ocop", "19 tiêu chí"),
        ("318/2022/QĐ-TTg",),
        ("nông thôn mới",),
    ),
    (
        ("nghị định 30", "nđ 30", "thể thức văn bản", "công tác văn thư", "ký hiệu văn bản", "nơi nhận"),
        ("30/2020/NĐ-CP", "QT-02/2026/UBND-VP"),
        ("công tác văn thư", "thể thức"),
    ),
    (
        ("thẩm quyền tập thể", "chính quyền địa phương", "thẩm quyền chủ tịch", "tập thể ubnd"),
        ("65/2025/QH15", "QC-01/2026/UBND-VP"),
        ("tổ chức chính quyền địa phương",),
    ),
    (
        ("hộ tịch", "khai sinh", "kết hôn", "khai tử", "tình trạng hôn nhân", "xác nhận độc thân"),
        ("60/2014/QH13",),
        ("luật hộ tịch", "123/2015/nđ-cp"),
    ),
    (
        ("chứng thực", "sao y", "bản sao từ bản chính", "chứng thực chữ ký", "chứng thực hợp đồng"),
        ("23/2015/NĐ-CP",),
        ("chứng thực bản sao",),
    ),
    (
        ("tiếp công dân", "lịch tiếp dân", "tiếp dân định kỳ"),
        ("42/2013/QH13",),
        ("luật tiếp công dân",),
    ),
    (
        ("khiếu nại", "đối thoại khiếu nại", "giải quyết khiếu nại"),
        ("02/2011/QH13",),
        ("khiếu nại lần đầu",),
    ),
    (
        ("tố cáo", "bảo vệ người tố cáo"),
        ("25/2018/QH14",),
        ("luật tố cáo",),
    ),
    (
        ("một cửa", "số hóa hồ sơ", "liên thông điện tử", "hẹn trả kết quả"),
        ("61/2018/NĐ-CP",),
        ("107/2021/nđ-cp", "một cửa"),
    ),
    (
        ("ngân sách xã", "dự toán ngân sách", "quyết toán ngân sách", "kho bạc", "tạm ứng", "thanh toán sửa chữa"),
        ("83/2015/QH13", "HD-02/2026/UBND-KT"),
        ("344/2016/tt-btc", "ngân sách xã"),
    ),
    (
        ("đầu tư công", "giám sát đầu tư của cộng đồng", "chủ đầu tư"),
        ("58/2024/QH15", "ST-03/2026/UBND-KT"),
        ("luật đầu tư công",),
    ),
    (
        ("tài sản công", "nhà văn hóa thôn", "kiểm kê tài sản", "khấu hao", "hao mòn"),
        ("15/2017/QH14",),
        ("tài sản công",),
    ),
    (
        ("hộ kinh doanh", "chợ dân sinh", "chợ hạng 3", "tiểu thương", "tiểu thủ công nghiệp"),
        ("01/2021/NĐ-CP",),
        ("hộ kinh doanh", "chợ dân sinh"),
    ),
    (
        ("tư vấn thuế", "thuế khoán", "thuế sử dụng đất phi nông nghiệp", "chống thất thu thuế"),
        ("38/2019/QH14",),
        ("hội đồng tư vấn thuế",),
    ),
    (
        ("lệ phí hộ tịch", "phí chứng thực", "miễn lệ phí", "biên lai điện tử"),
        ("85/2019/TT-BTC",),
        ("phí và lệ phí",),
    ),
    (
        ("bảo trợ xã hội", "trợ giúp xã hội", "trợ cấp xã hội", "khuyết tật", "mồ côi", "500.000", "mai táng phí"),
        ("20/2021/NĐ-CP", "ST-01/2026/UBND-VHXH"),
        ("76/2024/nđ-cp", "bảo trợ xã hội"),
    ),
    (
        ("người có công", "thương binh", "liệt sĩ", "chất độc hóa học", "thờ cúng liệt sĩ"),
        ("02/2020/UBTVQH14",),
        ("ưu đãi người có công", "131/2021/nđ-cp"),
    ),
    (
        ("lễ hội", "tiền công đức", "di tích"),
        ("110/2018/NĐ-CP",),
        ("tổ chức lễ hội",),
    ),
    (
        ("gia đình văn hóa", "thôn văn hóa", "tổ dân phố văn hóa", "phường tiêu biểu", "xã tiêu biểu"),
        ("86/2023/NĐ-CP",),
        ("gia đình văn hóa",),
    ),
    (
        ("hộ nghèo", "hộ cận nghèo", "nghèo đa chiều", "thoát nghèo"),
        ("07/2021/NĐ-CP",),
        ("chuẩn nghèo đa chiều",),
    ),
    (
        ("trẻ em", "bảo vệ trẻ em", "xâm hại trẻ em", "bạo hành trẻ em", "tổng đài 111", "cách ly trẻ em"),
        ("102/2016/QH13", "QT-02/2026/UBND-VHXH"),
        ("luật trẻ em", "56/2017/nđ-cp"),
    ),
]


def _tokenize_words(text: str) -> list[str]:
    cleaned = re.sub(r"[^\w/\-.]+", " ", (text or "").lower())
    return [tok.strip(".-/") for tok in cleaned.split() if len(tok.strip(".-/")) >= 2]


def _word_in_text(word: str, haystack: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(word) + r"(?!\w)"
    return re.search(pattern, haystack) is not None


def decompose_question_clauses(message: str) -> list[str]:
    """Split multi-part citizen/officer questions into distinct operational sub-clauses."""
    raw = " ".join((message or "").split())
    if not raw:
        return []
    parts = re.split(
        r"(?:[;?\n]+|\bđồng thời\b|\bngoài ra\b|\bbên cạnh đó\b|\bvà hỏi\b|\bvà cho hỏi\b|\bthứ nhất\b|\bthứ hai\b|\bthứ ba\b)",
        raw,
        flags=re.IGNORECASE,
    )
    clauses = [p.strip(" ,.-:;") for p in parts if len(p.strip(" ,.-:;")) >= 8]
    return clauses if clauses else [raw]


def _score_single_query(
    query: str,
    rows: list[dict[str, Any]],
    department_id: str,
    min_score: int = 8,
) -> list[tuple[int, dict[str, Any]]]:
    cleaned_q = " ".join((query or "").lower().split())
    if not cleaned_q:
        return []

    words = _tokenize_words(cleaned_q)
    if not words:
        return []

    meaningful_unigrams = [
        w for w in words
        if w not in VIETNAMESE_ADMIN_STOPWORDS and not w.isdigit()
    ]
    # Keep numeric codes like 235, 136, 76/2024, 30/2020
    code_tokens = [
        tok.lower()
        for tok in re.findall(r"\b(?:[a-zđ]{1,4}-\d+|\d{1,4}/\d{4}(?:/[\w\-đ]+)?|\d{2,4})\b", cleaned_q)
        if tok not in {"2024", "2025", "2026", "2027"}
    ]

    bigrams: list[str] = []
    for i in range(len(words) - 1):
        bg = f"{words[i]} {words[i + 1]}"
        if bg in GENERIC_ADMIN_PHRASES:
            continue
        if words[i] in VIETNAMESE_ADMIN_STOPWORDS and words[i + 1] in VIETNAMESE_ADMIN_STOPWORDS:
            continue
        bigrams.append(bg)

    trigrams: list[str] = []
    for i in range(len(words) - 2):
        tg = f"{words[i]} {words[i + 1]} {words[i + 2]}"
        if tg in GENERIC_ADMIN_PHRASES:
            continue
        stop_cnt = sum(1 for w in words[i : i + 3] if w in VIETNAMESE_ADMIN_STOPWORDS)
        if stop_cnt <= 1:
            trigrams.append(tg)

    boosted_doc_nums: set[str] = set()
    boosted_phrases: list[str] = []
    for triggers, target_docs, extra_phrases in CONCEPT_TRIGGERS:
        if any(trig in cleaned_q for trig in triggers):
            boosted_doc_nums.update(d.lower() for d in target_docs)
            boosted_phrases.extend(extra_phrases)

    is_single_term_lookup = len(words) == 1 and (words[0] not in VIETNAMESE_ADMIN_STOPWORDS)

    scored: list[tuple[int, dict[str, Any]]] = []
    for doc in rows:
        doc_num_l = doc["doc_number"].lower()
        title_l = doc["title"].lower()
        summary_l = doc["summary"].lower()
        content_l = doc["content"].lower()
        full_l = f"{doc_num_l} {title_l} {summary_l} {content_l}"

        topic_score = 0

        # 1. Exact doc_number or code reference
        if cleaned_q == doc_num_l or (len(cleaned_q) >= 5 and doc_num_l in cleaned_q):
            topic_score += 50
        for code_tok in code_tokens:
            if "/" in code_tok or "-" in code_tok:
                if code_tok in doc_num_l:
                    topic_score += 42
                elif code_tok in full_l:
                    topic_score += 24
            elif f"điều {code_tok}" in cleaned_q and f"điều {code_tok}" in full_l:
                topic_score += 26

        # 2. Concept trigger boost (domain-curated legal mapping)
        if doc_num_l in boosted_doc_nums:
            topic_score += 34
        for bp in boosted_phrases:
            if bp in title_l or bp in summary_l:
                topic_score += 14
            elif bp in content_l:
                topic_score += 10

        # 3. Exact query phrase match (for specific lookups)
        if len(cleaned_q) >= 4 and cleaned_q not in GENERIC_ADMIN_PHRASES:
            if cleaned_q in doc_num_l:
                topic_score += 45
            elif cleaned_q in title_l:
                topic_score += 28
            elif cleaned_q in summary_l:
                topic_score += 18
            elif cleaned_q in content_l:
                topic_score += 14

        # 4. Compound Vietnamese 3-gram & 2-gram phrase scoring
        for tg in trigrams:
            if tg in title_l:
                topic_score += 18
            elif tg in summary_l:
                topic_score += 13
            elif tg in content_l:
                topic_score += 9

        for bg in bigrams:
            if bg in title_l:
                topic_score += 11
            elif bg in summary_l:
                topic_score += 8
            elif bg in content_l:
                topic_score += 5

        # 5. Meaningful unigram word-boundary scoring
        for ug in meaningful_unigrams:
            if _word_in_text(ug, doc_num_l):
                topic_score += 16
            elif _word_in_text(ug, title_l):
                topic_score += 9 if is_single_term_lookup else 3
            elif _word_in_text(ug, summary_l):
                topic_score += 8 if is_single_term_lookup else 2
            elif _word_in_text(ug, content_l):
                topic_score += 8 if is_single_term_lookup else 1

        if topic_score >= min_score:
            # Apply department specialty bonus ONLY after passing substantive relevance threshold
            dept_bonus = 5 if doc["department_id"] == department_id else 0
            scored.append((topic_score + dept_bonus, doc))

    scored.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
    return scored


def search_official_docs_smart(
    query: str,
    department_id: str,
    tier: str | None = None,
    include_private: bool = True,
    fallback_on_empty: bool = False,
    min_score: int = 8,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    dept_clean = (department_id or "VP").strip().upper()
    with get_conn(db_path) as conn:
        if include_private:
            sql = """
                SELECT id, doc_number, title, doc_type, tier, department_id,
                       issuer, issued_date, status, summary, content, created_at
                FROM official_documents
                WHERE (tier != 'kho_rieng' OR department_id IN (?, 'ALL'))
            """
            params: list[Any] = [dept_clean]
        else:
            sql = """
                SELECT id, doc_number, title, doc_type, tier, department_id,
                       issuer, issued_date, status, summary, content, created_at
                FROM official_documents
                WHERE tier != 'kho_rieng'
            """
            params = []

        if tier and tier in {"trung_uong", "dia_phuong", "kho_rieng"}:
            sql += " AND tier = ?"
            params.append(tier)
        sql += " ORDER BY CASE WHEN department_id = ? THEN 0 WHEN department_id = 'ALL' THEN 1 ELSE 2 END, id ASC"
        params.append(dept_clean)
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    cleaned_q = (query or "").strip()
    if not cleaned_q:
        return rows

    clauses = decompose_question_clauses(cleaned_q)
    best_by_id: dict[int, tuple[int, dict[str, Any]]] = {}

    # Score full query and each decomposed sub-clause so multi-clause questions retrieve all relevant laws
    queries_to_run = [cleaned_q] + ([c for c in clauses if c != cleaned_q] if len(clauses) > 1 else [])
    for q_part in queries_to_run:
        part_scored = _score_single_query(q_part, rows, dept_clean, min_score=min_score)
        if not part_scored:
            continue
        part_top = part_scored[0][0]
        part_cutoff = max(min_score, int(part_top * 0.32))
        for sc, doc in part_scored:
            if sc < part_cutoff:
                continue
            did = doc["id"]
            if did not in best_by_id or sc > best_by_id[did][0]:
                best_by_id[did] = (sc, doc)

    if best_by_id:
        merged = sorted(best_by_id.values(), key=lambda item: (item[0], -item[1]["id"]), reverse=True)
        overall_top = merged[0][0]
        # For single-clause queries, prune weak tangential matches below 30% of top score
        relative_floor = min_score if len(clauses) > 1 else max(min_score, int(overall_top * 0.30))
        return [doc for sc, doc in merged if sc >= relative_floor]

    if fallback_on_empty:
        dept_public = [r for r in rows if r["tier"] != "kho_rieng" and r["department_id"] in {dept_clean, "ALL"}]
        return (dept_public or [r for r in rows if r["tier"] != "kho_rieng"])[:2]
    return []

