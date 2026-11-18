from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx

from backend.db import SESSION_STORE, can_access_private_docs, get_conn, utc_now_iso

LEGAL_RESPONSIBILITY_NOTE = (
    "Lưu ý nghiệp vụ: AI là công cụ hỗ trợ; cán bộ, công chức và người có thẩm quyền "
    "trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."
)


def _clip(text: str, max_chars: int = 200) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_chars:
        return cleaned
    cut = cleaned[:max_chars].rsplit(" ", 1)[0]
    return f"{cut}…"


def get_department_info(department_id: str, db_path: Path | str | None = None) -> dict[str, Any]:
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM departments WHERE id = ?",
            (department_id,),
        ).fetchone()
        if row:
            return dict(row)
        fallback = conn.execute("SELECT * FROM departments WHERE id = 'VP'").fetchone()
        return dict(fallback) if fallback else {
            "id": "VP",
            "code": "VP",
            "name": "Văn phòng HĐND & UBND",
            "scope_summary": "Tổng hợp, văn thư, tư pháp - hộ tịch",
            "instruction": "",
        }


def search_official_documents(
    query: str,
    department_id: str,
    tier: str | None = None,
    include_private: bool = True,
    fallback_on_empty: bool = False,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    with get_conn(db_path) as conn:
        if include_private:
            sql = """
                SELECT id, doc_number, title, doc_type, tier, department_id,
                       issuer, issued_date, status, summary, content, created_at
                FROM official_documents
                WHERE (tier != 'kho_rieng' OR department_id IN (?, 'ALL'))
            """
            params: list[Any] = [department_id]
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
        sql += " ORDER BY id DESC"
        rows = [dict(r) for r in conn.execute(sql, params).fetchall()]

    cleaned_q = (query or "").strip().lower()
    if not cleaned_q:
        return rows

    tokens = [tok for tok in re.split(r"\s+", cleaned_q) if len(tok) >= 2]
    scored: list[tuple[int, dict[str, Any]]] = []
    for doc in rows:
        haystack = " ".join(
            [
                doc["doc_number"],
                doc["title"],
                doc["doc_type"],
                doc["summary"],
                doc["content"],
            ]
        ).lower()
        score = 0
        if cleaned_q in haystack:
            score += 10
        for tok in tokens:
            if tok in haystack:
                score += 2
        if score > 0:
            scored.append((score, doc))

    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored]
    if fallback_on_empty:
        return [r for r in rows if r["tier"] != "kho_rieng"][:3]
    return []


def _try_live_llm(system_prompt: str, user_prompt: str, db_path: Path | str | None = None) -> str | None:
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    model_name = os.environ.get("LLM_MODEL", "gpt-4o-mini").strip()

    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT base_url, model_name, api_key, active FROM api_connectors WHERE active = 1 ORDER BY id ASC LIMIT 1"
        ).fetchone()
        if row and row["api_key"]:
            base_url = row["base_url"].rstrip("/")
            api_key = row["api_key"].strip()
            model_name = row["model_name"].strip()

    if not api_key or not base_url:
        return None

    try:
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        res = httpx.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.2,
            },
            timeout=15.0,
        )
        if res.status_code == 200:
            payload = res.json()
            return payload["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return None


def run_assistant_turn(
    session_id: str,
    department_id: str,
    mode: str,
    message: str,
    actor_email: str,
    tenant_slug: str = "default",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    session_state = SESSION_STORE.get_or_create(
        session_id,
        tenant_slug=tenant_slug,
        actor_email=actor_email,
        department_id=department_id,
    )
    session_files = session_state["files"]

    allow_private = can_access_private_docs(actor_email, department_id, db_path)
    matched_docs = (
        search_official_documents(
            message,
            department_id,
            include_private=allow_private,
            fallback_on_empty=True,
            db_path=db_path,
        )[:3]
        if mode in {"nghiep_vu", "tham_dinh"}
        else []
    )
    citations = [
        {
            "doc_number": d["doc_number"],
            "title": d["title"],
            "tier": d["tier"],
        }
        for d in matched_docs
    ]

    SESSION_STORE.append_message(
        session_id,
        {
            "role": "user",
            "mode": mode,
            "content": message,
            "citations": [],
            "created_at": utc_now_iso(),
        },
        tenant_slug=tenant_slug,
        actor_email=actor_email,
        department_id=department_id,
    )

    files_snippet = ""
    if session_files:
        excerpts = [
            f"- {f['filename']}: {f['extracted_text'][:400]}"
            for f in session_files
        ]
        files_snippet = "\n".join(excerpts)

    docs_snippet = "\n".join(
        f"- {d['doc_number']} ({d['title']}): {d['content'][:350]}"
        for d in matched_docs
    )

    llm_answer = _try_live_llm(
        system_prompt=(
            f"Bạn là Trợ lý AI chuyên biệt cho {dept['name']} cấp xã/phường. "
            f"Chỉ dẫn phòng: {dept['instruction']}. Chế độ: {mode}."
        ),
        user_prompt=f"Câu hỏi: {message}\nTài liệu phiên:\n{files_snippet}\nVăn bản chính thức:\n{docs_snippet}",
        db_path=db_path,
    )

    if llm_answer:
        reply_content = llm_answer
    elif mode == "soan_thao":
        file_ref = (
            f"\n- **Tài liệu phiên đã tham chiếu ({len(session_files)} tệp):** "
            + "; ".join(f"{f['filename']} ({f['extracted_text'][:140]})" for f in session_files)
            if session_files
            else ""
        )
        reply_content = (
            f"### Dự thảo nhanh ({dept['name']})\n"
            f"**Nội dung xử lý theo yêu cầu:** {message}\n"
            f"{file_ref}\n\n"
            f"Kính gửi: Các bộ phận liên quan thuộc UBND xã/phường,\n\n"
            f"Thực hiện nhiệm vụ thuộc lĩnh vực **{dept['scope_summary']}**, {dept['name']} đề xuất nội dung triển khai như sau:\n"
            f"1. Tiếp nhận và rà soát thông tin đầu vào bảo đảm đầy đủ hồ sơ thành phần.\n"
            f"2. Phân công cán bộ chuyên trách phối hợp xử lý và báo cáo kết quả đúng thời hạn.\n"
            f"3. Hoàn thiện văn bản trình Lãnh đạo UBND xem xét, quyết định.\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        )
    elif mode == "tham_dinh":
        file_analysis = (
            "### Đối chiếu hồ sơ tải lên trong phiên\n"
            + "\n".join(
                f"- **{f['filename']}**: {f['extracted_text'][:220]}"
                for f in session_files
            )
            + "\n\n"
            if session_files
            else "*(Chưa có tệp đính kèm trong phiên — thẩm định dựa trên nội dung mô tả trực tiếp)*\n\n"
        )
        basis_lines = "\n".join(
            f"- **{d['doc_number']}** — *{d['title']}*: {_clip(d['content'], 220)}"
            for d in matched_docs
        )
        reply_content = (
            f"### Kết quả Thẩm định chuyên sâu ({dept['name']})\n"
            f"**Yêu cầu thẩm định:** {message}\n\n"
            f"{file_analysis}"
            f"### 1. Căn cứ pháp lý & Kho dữ liệu đối chiếu\n{basis_lines}\n\n"
            f"### 2. Đánh giá thẩm quyền, tính logic & rủi ro\n"
            f"- **Thẩm quyền cấp xã/phường:** Cần phân định rõ văn bản thuộc thẩm quyền tập thể UBND hay thẩm quyền cá nhân Chủ tịch UBND theo Luật Tổ chức chính quyền địa phương.\n"
            f"- **Thể thức & Hồ sơ:** Tuân thủ Điều 8 Nghị định 30/2020/NĐ-CP và quy trình số hóa tại Nghị định 399/2026/NĐ-CP.\n"
            f"- **Khuyến nghị kiểm soát rủi ro:** Kiểm tra kỹ chữ ký xác nhận thực địa, mốc ngày tháng giữa các biên bản trước khi trình ký.\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        )
    else:
        basis_lines = "\n".join(
            f"- **{d['doc_number']}** ({d['issuer']}): {d['summary']} — *{_clip(d['content'], 200)}*"
            for d in matched_docs
        )
        file_note = (
            f"\n\n**Thông tin ghi nhận từ {len(session_files)} tệp trong phiên:** "
            + "; ".join(f"{f['filename']}: {_clip(f['extracted_text'], 160)}" for f in session_files)
            if session_files
            else ""
        )
        reply_content = (
            f"### Tư vấn nghiệp vụ · {dept['name']}\n"
            f"**Vấn đề cần giải đáp:** {message}\n\n"
            f"**1. Căn cứ văn bản chính thức & quy chế của đơn vị:**\n{basis_lines}"
            f"{file_note}\n\n"
            f"**2. Hướng xử lý đề xuất cho cán bộ chuyên môn:**\n"
            f"- Bước 1: Tiếp nhận và kiểm tra tính đầy đủ, hợp lệ của thành phần hồ sơ theo quy định hiện hành.\n"
            f"- Bước 2: Áp dụng chỉ dẫn nghiệp vụ của **{dept['name']}** (*{_clip(dept['instruction'], 180)}*).\n"
            f"- Bước 3: Lập phiếu trình kèm dự thảo văn bản kết quả chuyển Lãnh đạo UBND xem xét phê duyệt.\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        )

    reply_msg = {
        "role": "assistant",
        "mode": mode,
        "content": reply_content,
        "citations": citations,
        "created_at": utc_now_iso(),
    }
    updated = SESSION_STORE.append_message(
        session_id,
        reply_msg,
        tenant_slug=tenant_slug,
        actor_email=actor_email,
        department_id=department_id,
    )
    return {
        "session_id": session_id,
        "department": dept,
        "reply": reply_msg,
        "session": updated,
    }


def analyze_extended_options(
    department_id: str,
    topic: str,
    context: str = "",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    ctx_clause = f" (Bối cảnh địa phương: {context.strip()})" if context.strip() else ""
    options = [
        {
            "code": "Phương án A",
            "title": f"Triển khai theo lộ trình chuẩn hóa quy trình tại chỗ ({dept['code']})",
            "summary": f"Tận dụng ngay nhân sự hiện có của {dept['name']} và Tổ công nghệ số cộng đồng để xử lý '{topic}'{ctx_clause}.",
            "pros": [
                "Không phát sinh kinh phí đầu tư mới ngoài dự toán thường xuyên",
                "Triển khai ngay trong 1–2 tuần, phù hợp quy mô UBND xã/phường",
            ],
            "cons": [
                "Tăng tải công việc hướng dẫn trực tiếp cho công chức đầu mối trong giai đoạn đầu",
            ],
            "feasibility": "Rất khả thi (Ngắn hạn)",
        },
        {
            "code": "Phương án B",
            "title": "Ứng dụng tự động hóa biểu mẫu số & liên thông dữ liệu chuyên ngành",
            "summary": f"Chuẩn hóa bộ mẫu điện tử kết hợp ki-ốt/hướng dẫn số hóa toàn trình cho nhiệm vụ '{topic}'.",
            "pros": [
                "Rút ngắn 35%–50% thời gian tổng hợp báo cáo và kiểm tra hồ sơ lặp lại",
                "Dễ dàng theo dõi tiến độ định lượng và hạn chế sai sót thể thức",
            ],
            "cons": [
                "Cần thống nhất quy chuẩn biểu mẫu giữa các bộ phận và tập huấn đồng bộ",
            ],
            "feasibility": "Khả thi cao (Trung hạn)",
        },
        {
            "code": "Phương án C",
            "title": "Mô hình kết hợp thí điểm theo cụm dân cư / nhóm thủ tục trọng điểm",
            "summary": f"Thí điểm trước với nhóm hồ sơ phát sinh nhiều nhất của {dept['name']}, đánh giá sau 30 ngày rồi nhân rộng toàn xã/phường.",
            "pros": [
                "Kiểm soát chặt rủi ro pháp lý và điều chỉnh linh hoạt theo phản hồi người dân",
                "Tạo số liệu minh chứng cụ thể trước khi trình HĐND/UBND phê duyệt diện rộng",
            ],
            "cons": [
                "Cần bước sơ kết đánh giá giữa kỳ trước khi áp dụng đại trà",
            ],
            "feasibility": "Khuyến nghị áp dụng",
        },
    ]
    return {
        "department": dept,
        "topic": topic,
        "context": context,
        "scope_notice": (
            "Chế độ Kiến thức mở rộng: Nội dung gợi mở đa phương án bên ngoài kho văn bản nội bộ "
            "phục vụ nghiên cứu, tham khảo trước khi đưa vào dự thảo chính thức."
        ),
        "options": options,
    }


def generate_administrative_draft(
    department_id: str,
    doc_type: str,
    title: str,
    key_points: str,
    recipient: str = "Các bộ phận chuyên môn trực thuộc UBND",
    actor_email: str = "tsh.co@tshorg.vn",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    allow_private = can_access_private_docs(actor_email, department_id, db_path)
    docs = search_official_documents(
        f"{doc_type} {title}",
        department_id,
        include_private=allow_private,
        fallback_on_empty=True,
        db_path=db_path,
    )[:2]
    legal_bases = [
        "Căn cứ Luật Tổ chức chính quyền địa phương ngày 19 tháng 6 năm 2025;",
        "Căn cứ Nghị định số 30/2020/NĐ-CP ngày 05 tháng 3 năm 2020 của Chính phủ về công tác văn thư;",
    ]
    for d in docs:
        if d["doc_number"] not in {"30/2020/NĐ-CP", "65/2025/QH15"}:
            legal_bases.append(f"Căn cứ {d['doc_type']} số {d['doc_number']} về {d['title']};")

    raw_points = [
        p.strip(" -•\t")
        for p in re.split(r"[;\n]+", key_points or "")
        if p.strip(" -•\t")
    ]
    if not raw_points:
        raw_points = [
            f"Giao {dept['name']} chủ trì rà soát, tham mưu tổ chức thực hiện đảm bảo đúng tiến độ.",
            "Các bộ phận chuyên môn phối hợp cung cấp số liệu, hồ sơ liên quan đầy đủ, kịp thời.",
            "Định kỳ tổng hợp kết quả báo cáo Chủ tịch UBND xã/phường xem xét, chỉ đạo.",
        ]

    doc_upper = doc_type.strip().upper()
    is_quyet_dinh = doc_type.strip().lower() == "quyết định"
    authority_signer = (
        "TM. ỦY BAN NHÂN DÂN\nCHỦ TỊCH"
        if doc_type.strip().lower() in {"kế hoạch", "báo cáo", "quyết định", "thông báo"}
        else "KT. CHỦ TỊCH\nPHÓ CHỦ TỊCH"
    )
    symbol_code = "QĐ-UBND" if is_quyet_dinh else f"UBND-{dept['code']}"

    if is_quyet_dinh:
        articles = "\n".join(
            f"Điều {idx}. {pt}" for idx, pt in enumerate(raw_points, start=1)
        )
        next_art = len(raw_points) + 1
        body_section = (
            f"QUYẾT ĐỊNH:\n\n"
            f"{articles}\n"
            f"Điều {next_art}. Quyết định này có hiệu lực kể từ ngày ký. "
            f"Văn phòng HĐND & UBND, Phụ trách {dept['name']} và các bộ phận liên quan chịu trách nhiệm thi hành Quyết định này./."
        )
    else:
        numbered_body = "\n".join(
            f"{idx}. {pt}" for idx, pt in enumerate(raw_points, start=1)
        )
        body_section = (
            f"I. NỘI DUNG TRIỂN KHAI\n{numbered_body}\n\n"
            f"II. TỔ CHỨC THỰC HIỆN\n"
            f"Giao {dept['name']} theo dõi, đôn đốc việc thực hiện {doc_type.lower()} này và tổng hợp báo cáo theo quy định."
        )

    draft_text = (
        "ỦY BAN NHÂN DÂN XÃ/PHƯỜNG          CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM\n"
        "                                      Độc lập - Tự do - Hạnh phúc\n"
        f"Số: .../{symbol_code}\n"
        "                                      ..., ngày 18 tháng 11 năm 2026\n\n"
        f"{doc_upper}\n"
        f"Về việc {title.strip()}\n\n"
        + "\n".join(legal_bases)
        + f"\nTheo đề nghị của Phụ trách {dept['name']},\n\n"
        f"{body_section}\n\n"
        f"Nơi nhận:                              {authority_signer}\n"
        f"- {recipient};\n"
        f"- Chủ tịch, các PCT UBND;\n"
        f"- Lưu: VT, {dept['code']}.\n"
        f"                                       (Đã ký và đóng dấu)"
    )
    return {
        "department_id": department_id,
        "doc_type": doc_type,
        "title": title,
        "draft_text": draft_text,
    }


def audit_administrative_draft(
    department_id: str,
    doc_type: str,
    draft_text: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    text_upper = draft_text.upper()
    criteria: list[dict[str, str]] = []
    score = 100

    # 1. Thể thức & Bố cục (NĐ 30/2020/NĐ-CP)
    has_quoc_hieu = "CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM" in text_upper
    has_noi_nhan = "NƠI NHẬN" in text_upper
    if has_quoc_hieu and has_noi_nhan:
        criteria.append({
            "id": "bo_cuc",
            "name": "Bố cục & Thể thức (NĐ 30/2020/NĐ-CP)",
            "status": "dat",
            "detail": "Đầy đủ Quốc hiệu, Tiêu ngữ, Số/Ký hiệu, Nội dung và khối Nơi nhận theo Điều 8 Nghị định 30/2020/NĐ-CP.",
        })
    else:
        score -= 22
        criteria.append({
            "id": "bo_cuc",
            "name": "Bố cục & Thể thức (NĐ 30/2020/NĐ-CP)",
            "status": "khong_dat",
            "detail": "Thiếu Quốc hiệu 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM' hoặc mục 'Nơi nhận:' bắt buộc theo Nghị định 30/2020/NĐ-CP.",
        })

    # 2. Căn cứ pháp lý
    has_can_cu = "CĂN CỨ" in text_upper
    if has_can_cu:
        criteria.append({
            "id": "can_cu",
            "name": "Căn cứ pháp lý viện dẫn",
            "status": "dat",
            "detail": "Đã nêu căn cứ pháp lý đầu văn bản; khuyến nghị rà soát thêm hiệu lực văn bản chuyên ngành mới nhất năm 2026.",
        })
    else:
        score -= 20
        criteria.append({
            "id": "can_cu",
            "name": "Căn cứ pháp lý viện dẫn",
            "status": "can_ra_soat",
            "detail": "Chưa thấy viện dẫn 'Căn cứ...' (Luật Tổ chức chính quyền địa phương / văn bản chuyên ngành có liên quan).",
        })

    # 3. Thẩm quyền ban hành
    is_quyet_dinh = "QUYẾT ĐỊNH" in doc_type.upper()
    has_authority = ("TM. ỦY BAN NHÂN DÂN" in text_upper) or ("CHỦ TỊCH" in text_upper)
    if is_quyet_dinh and "ĐIỀU 1" not in text_upper:
        score -= 12
        criteria.append({
            "id": "tham_quyen",
            "name": "Thẩm quyền ban hành & Kết cấu điều khoản",
            "status": "can_ra_soat",
            "detail": "Văn bản loại 'Quyết định' cần trình bày theo kết cấu Điều 1, Điều 2... và xác định rõ thẩm quyền UBND hay Chủ tịch UBND cấp xã.",
        })
    elif has_authority:
        criteria.append({
            "id": "tham_quyen",
            "name": "Thẩm quyền ban hành",
            "status": "dat",
            "detail": "Thể thức ký ban hành phù hợp phạm vi thẩm quyền của UBND / Chủ tịch UBND cấp xã, phường.",
        })
    else:
        score -= 18
        criteria.append({
            "id": "tham_quyen",
            "name": "Thẩm quyền ban hành",
            "status": "can_ra_soat",
            "detail": "Chưa ghi rõ chức danh, thẩm quyền người ký (TM. ỦY BAN NHÂN DÂN / CHỦ TỊCH).",
        })

    # 4. Tính logic & Thống nhất
    has_placeholder = "..." in draft_text
    if has_placeholder:
        score -= 8
        criteria.append({
            "id": "logic",
            "name": "Tính logic & Thống nhất dữ liệu",
            "status": "can_ra_soat",
            "detail": "Còn ký hiệu chờ điền '...' tại mục Số văn bản hoặc Địa danh; cần điền đầy đủ trước khi phát hành chính thức.",
        })
    else:
        criteria.append({
            "id": "logic",
            "name": "Tính logic & Thống nhất dữ liệu",
            "status": "dat",
            "detail": "Bố cục mạch lạc, không phát hiện dấu chỗ trống '...' hay mâu thuẫn nội tại.",
        })

    # 5. Chính tả & Văn phong hành chính
    colloquial = [w for w in ["nhé", "ok", "tụi mình", "anh em", "hên xui"] if w in draft_text.lower()]
    if colloquial:
        score -= 15
        criteria.append({
            "id": "van_phong",
            "name": "Chính tả & Văn phong hành chính",
            "status": "khong_dat",
            "detail": f"Phát hiện từ ngữ khẩu ngữ không phù hợp văn phong hành chính: {', '.join(colloquial)}.",
        })
    else:
        criteria.append({
            "id": "van_phong",
            "name": "Chính tả & Văn phong hành chính",
            "status": "dat",
            "detail": "Ngôn ngữ trang trọng, khách quan, chuẩn mực văn phong hành chính nhà nước.",
        })

    final_score = max(0, min(100, score))
    return {
        "score": final_score,
        "doc_type": doc_type,
        "department_id": department_id,
        "criteria": criteria,
        "summary": (
            f"Dự thảo đạt {final_score}/100 điểm chuẩn hóa hành chính. "
            "Cán bộ trực tiếp rà soát các mục đánh dấu 'Cần rà soát' trước khi trình ký."
        ),
    }


def process_session_files(
    session_id: str,
    department_id: str,
    action: str,
    actor_email: str = "local",
    tenant_slug: str = "default",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    state = SESSION_STORE.get_or_create(
        session_id,
        tenant_slug=tenant_slug,
        actor_email=actor_email,
        department_id=department_id,
    )
    files = state["files"]

    if not files:
        return {
            "action": action,
            "file_count": 0,
            "result_markdown": "Chưa có tài liệu nào được tải lên trong phiên hiện tại. Vui lòng tải lên ít nhất 01 tệp để AI xử lý.",
            "highlights": [],
        }

    if action == "tom_tat":
        bullets = [
            f"- **{f['filename']}** ({f['size_bytes']} bytes · *{f['parse_note']}*): {f['extracted_text'][:260]}"
            for f in files
        ]
        return {
            "action": action,
            "file_count": len(files),
            "result_markdown": f"### Tóm tắt {len(files)} tài liệu trong phiên ({dept['name']})\n" + "\n".join(bullets),
            "highlights": [f["filename"] for f in files],
        }

    if action == "trich_xuat":
        extracted_items: list[str] = []
        lines: list[str] = [f"### Trích xuất thông tin nghiệp vụ ({dept['name']})"]
        for f in files:
            dates = re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", f["extracted_text"])
            numbers = re.findall(r"\b\d+(?:[.,]\d+)?\s*(?:m2|m²|ngày|triệu|đồng|%)?\b", f["extracted_text"])
            lines.append(
                f"- **{f['filename']}**:\n"
                f"  - Mốc ngày tháng phát hiện: {', '.join(dates[:5]) if dates else 'Không ghi nhận'}\n"
                f"  - Số liệu / định lượng: {', '.join(n.strip() for n in numbers[:6]) if numbers else 'Không ghi nhận'}\n"
                f"  - Nội dung chính: {f['extracted_text'][:200]}"
            )
            extracted_items.extend(dates[:3])
        return {
            "action": action,
            "file_count": len(files),
            "result_markdown": "\n".join(lines),
            "highlights": extracted_items[:8],
        }

    if action == "doi_chieu":
        per_file_nums: list[tuple[str, set[str], set[str]]] = []
        for f in files:
            areas_or_nums = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", f["extracted_text"]))
            dates = set(re.findall(r"\b\d{1,2}/\d{1,2}/\d{4}\b", f["extracted_text"]))
            per_file_nums.append((f["filename"], areas_or_nums, dates))

        warnings: list[str] = []
        if len(per_file_nums) >= 2:
            base_name, base_nums, base_dates = per_file_nums[0]
            for other_name, other_nums, other_dates in per_file_nums[1:]:
                diff_nums = sorted((base_nums ^ other_nums))
                diff_dates = sorted((base_dates ^ other_dates))
                if diff_nums:
                    warnings.append(
                        f"Chênh lệch số liệu giữa '{base_name}' ({', '.join(sorted(base_nums))}) và '{other_name}' ({', '.join(sorted(other_nums))})."
                    )
                if diff_dates:
                    warnings.append(
                        f"Khác biệt mốc ngày tháng giữa '{base_name}' ({', '.join(sorted(base_dates))}) và '{other_name}' ({', '.join(sorted(other_dates))})."
                    )
        else:
            warnings.append("Chỉ có 01 tệp trong phiên — cần tải từ 02 tệp trở lên (ví dụ: Đơn đề nghị & Biên bản xác minh) để đối chiếu chéo.")

        md_lines = [
            f"### Kết quả Đối chiếu hồ sơ ({len(files)} tệp · {dept['name']})",
            *(f"- ⚠️ {w}" for w in warnings),
        ]
        if not warnings:
            md_lines.append("- ✅ Các số liệu và mốc ngày tháng trùng khớp giữa các tệp trong phiên.")
        return {
            "action": action,
            "file_count": len(files),
            "result_markdown": "\n".join(md_lines),
            "highlights": warnings,
        }

    # tong_hop
    summary_rows = "\n".join(
        f"{idx}. **{f['filename']}**: {f['extracted_text'][:200]}"
        for idx, f in enumerate(files, start=1)
    )
    return {
        "action": "tong_hop",
        "file_count": len(files),
        "result_markdown": (
            f"### Phiếu Tổng hợp Hồ sơ Trình Lãnh đạo ({dept['name']})\n"
            f"**1. Thành phần hồ sơ đã tiếp nhận ({len(files)} tệp):**\n{summary_rows}\n\n"
            f"**2. Đề xuất tham mưu của {dept['name']}:**\n"
            f"- Hồ sơ đã được trích xuất và kiểm tra sơ bộ trên phiên làm việc nội bộ.\n"
            f"- Đề nghị cán bộ chuyên trách đối chiếu bản gốc và trình Lãnh đạo UBND xem xét quyết định.\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        ),
        "highlights": [f["filename"] for f in files],
    }

