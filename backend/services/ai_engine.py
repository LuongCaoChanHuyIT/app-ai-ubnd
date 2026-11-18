from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import httpx

from backend.db import (
    SESSION_STORE,
    can_access_private_docs,
    get_commune_name,
    get_conn,
    utc_now_iso,
)
from backend.services.dossier_diff import (
    STRUCTURED_FIELD_SPECS,
    build_ocr_warning_banner,
    extract_structured_fields,
    run_structured_session_processing,
)
from backend.services.legal_kb import (
    decompose_question_clauses,
    search_official_docs_smart,
)
from backend.services.nd30_engine import (
    audit_nd30_draft,
    build_nd30_draft,
    parse_commune_identity,
)

LEGAL_RESPONSIBILITY_NOTE = (
    "Lưu ý nghiệp vụ: AI là công cụ hỗ trợ; cán bộ, công chức và người có thẩm quyền "
    "trực tiếp kiểm tra, quyết định và chịu trách nhiệm đối với nội dung sử dụng."
)


def _clip(text: str, max_chars: int = 420) -> str:
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
    return search_official_docs_smart(
        query=query,
        department_id=department_id,
        tier=tier,
        include_private=include_private,
        fallback_on_empty=fallback_on_empty,
        db_path=db_path,
    )


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


def _build_authority_guidance(
    message: str,
    matched_docs: list[dict[str, Any]],
    dept: dict[str, Any],
) -> list[str]:
    doc_nums = {d["doc_number"] for d in matched_docs}
    msg_l = message.lower()
    bullets: list[str] = []

    if "31/2024/QH15" in doc_nums or "101/2024/NĐ-CP" in doc_nums:
        bullets.append(
            "- **Về hòa giải & xác nhận đất đai tại cấp xã (Luật Đất đai 31/2024/QH15):** "
            "**Chủ tịch UBND cấp xã** quyết định thành lập Hội đồng hòa giải tranh chấp đất đai và tổ chức hòa giải trong thời hạn **không quá 30 ngày** (Điều 235); "
            "**UBND cấp xã** tổ chức kiểm tra thực địa, xác nhận nguồn gốc, thời điểm sử dụng đất, tình trạng tranh chấp, quy hoạch và **niêm yết công khai 15 ngày** (Điều 137, 138)."
        )
        if any(k in msg_l for k in ("sổ đỏ", "sổ hồng", "giấy chứng nhận", "cấp sổ", "điều 136")):
            bullets.append(
                "- **Giới hạn thẩm quyền cấp Giấy chứng nhận (Điều 136 Luật Đất đai 2024):** "
                "**UBND cấp xã KHÔNG tự ký cấp sổ đỏ (Giấy chứng nhận QSDĐ) lần đầu vượt thẩm quyền** khi chưa có văn bản phân quyền đặc thù; "
                "cấp xã thực hiện thẩm tra, xác nhận nguồn gốc, niêm yết 15 ngày và chuyển liên thông hồ sơ lên cơ quan có thẩm quyền ký cấp GCN."
            )

    if doc_nums & {"123/2024/NĐ-CP", "45/2022/NĐ-CP", "16/2022/NĐ-CP"}:
        bullets.append(
            "- **Về xử phạt vi phạm hành chính tại cơ sở:** Công chức chuyên môn đang thi hành công vụ lập Biên bản vi phạm hành chính ngay tại hiện trường; "
            "cá nhân **Chủ tịch UBND cấp xã** ký Quyết định xử phạt (phạt tiền tối đa đến **5.000.000 đồng** đối với cá nhân) và áp dụng biện pháp buộc khôi phục lại tình trạng ban đầu. "
            "Trường hợp mức phạt hoặc biện pháp khắc phục **vượt thẩm quyền Chủ tịch UBND cấp xã**, phải giữ nguyên hiện trạng và chuyển hồ sơ lên cấp trên (trong **24 giờ** đối với trật tự xây dựng)."
        )

    if "72/2020/QH14" in doc_nums:
        bullets.append(
            "- **Về quản lý chất thải rắn sinh hoạt (Điều 75–77 Luật Bảo vệ môi trường 72/2020/QH14):** "
            "**Tập thể UBND cấp xã** ban hành Kế hoạch triển khai phân loại chất thải rắn sinh hoạt tại nguồn thành **03 nhóm** (tái chế, thực phẩm, khác), "
            "giám sát đơn vị thu gom và phối hợp Ủy ban MTTQ, các đoàn thể vận động hộ gia đình."
        )

    if "20/2021/NĐ-CP" in doc_nums:
        bullets.append(
            "- **Về trợ giúp xã hội (Nghị định 20/2021/NĐ-CP & Nghị định 76/2024/NĐ-CP):** "
            "UBND cấp xã tiếp nhận tờ khai, xác minh điều kiện, niêm yết công khai **02 ngày làm việc** tại trụ sở UBND xã và áp dụng đúng mức chuẩn trợ giúp xã hội **500.000 đồng/tháng** nhân hệ số từng nhóm đối tượng để trình quyết định hưởng trợ cấp."
        )

    if "86/2023/NĐ-CP" in doc_nums:
        bullets.append(
            "- **Về danh hiệu văn hóa (Nghị định 86/2023/NĐ-CP):** Cá nhân **Chủ tịch UBND cấp xã** có thẩm quyền ban hành Quyết định tặng danh hiệu **\"Gia đình văn hóa\"** hằng năm (ký trực tiếp chức danh `CHỦ TỊCH`); đối với danh hiệu \"Thôn, tổ dân phố văn hóa\" thì UBND cấp xã lập tờ trình đề nghị cấp trên quyết định."
        )

    if "102/2016/QH13" in doc_nums:
        bullets.append(
            "- **Về bảo vệ trẻ em (Luật Trẻ em 102/2016/QH13 & Nghị định 56/2017/NĐ-CP):** Cá nhân **Chủ tịch UBND cấp xã** có thẩm quyền ra Quyết định tạm thời cách ly trẻ em khỏi môi trường/người gây tổn hại trong vòng **12 giờ** đối với ca khẩn cấp và phê duyệt Kế hoạch hỗ trợ, can thiệp."
        )

    if "83/2015/QH13" in doc_nums:
        bullets.append(
            "- **Về tài chính - ngân sách xã (Luật NSNN 83/2015/QH13 & Thông tư 344/2016/TT-BTC):** Tập thể **UBND cấp xã** lập dự toán và phương án phân bổ ngân sách trình **HĐND cấp xã** quyết định; **Chủ tịch UBND cấp xã** làm Chủ tài khoản duyệt chi theo dự toán qua Kho bạc Nhà nước."
        )

    if doc_nums & {"02/2011/QH13", "25/2018/QH14", "42/2013/QH13"}:
        bullets.append(
            "- **Về tiếp công dân, giải quyết khiếu nại, tố cáo:** Cá nhân **Chủ tịch UBND cấp xã** trực tiếp tiếp công dân định kỳ hằng tuần (Luật Tiếp công dân), thụ lý trong 10 ngày và ban hành Quyết định giải quyết khiếu nại lần đầu trong **30 ngày** — vụ việc phức tạp hoặc vùng sâu xa tối đa **45 ngày** (bắt buộc đối thoại trước khi ký)."
        )

    if not bullets:
        bullets.append(
            f"- **Phân định theo Luật Tổ chức chính quyền địa phương 65/2025/QH15:** Tập thể **UBND cấp xã** thảo luận, quyết định các kế hoạch, đề án, báo cáo chung (ký `TM. ỦY BAN NHÂN DÂN`); "
            f"cá nhân **Chủ tịch UBND cấp xã** quyết định các việc điều hành cá biệt, xử lý hành chính, giải quyết đơn thư, thành lập tổ công tác (ký `CHỦ TỊCH`). Bộ phận **{dept['name']}** chịu trách nhiệm thẩm tra chuyên môn và trình ký đúng thể thức."
        )
    return bullets


def _infer_draft_type_and_subject(message: str) -> tuple[str, str]:
    msg = " ".join((message or "").split()).strip()
    for candidate in ("Quyết định", "Kế hoạch", "Báo cáo", "Thông báo", "Tờ trình", "Công văn"):
        m = re.search(
            r"(?:soạn(?:\s+thảo)?|dự\s+thảo|lập|viết)?\s*" + re.escape(candidate) + r"\s*(.+)$",
            msg,
            flags=re.IGNORECASE,
        )
        if m and len(m.group(1).strip()) >= 4:
            return candidate, m.group(1).strip(" :.-")
    cleaned = re.sub(
        r"^(?:hãy\s+|vui\s+lòng\s+|nhờ\s+ai\s+)?(?:soạn(?:\s+thảo)?(?:\s+nhanh)?|dự\s+thảo|viết)\s*",
        "",
        msg,
        flags=re.IGNORECASE,
    ).strip()
    return "Công văn", (cleaned or msg)


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
    commune_name = get_commune_name(db_path)
    session_state = SESSION_STORE.get_or_create(
        session_id,
        tenant_slug=tenant_slug,
        actor_email=actor_email,
        department_id=department_id,
    )
    session_files = session_state["files"]

    allow_private = can_access_private_docs(actor_email, department_id, db_path)
    matched_docs = search_official_docs_smart(
        message,
        department_id,
        include_private=allow_private,
        fallback_on_empty=False,
        db_path=db_path,
    )[:4]

    if not matched_docs and mode == "tham_dinh" and session_files:
        files_text_q = " ".join(f["extracted_text"][:300] for f in session_files)
        matched_docs = search_official_docs_smart(
            files_text_q,
            department_id,
            include_private=allow_private,
            fallback_on_empty=False,
            db_path=db_path,
        )[:3]

    citations = (
        [
            {
                "doc_number": d["doc_number"],
                "title": d["title"],
                "tier": d["tier"],
            }
            for d in matched_docs
        ]
        if mode in {"nghiep_vu", "tham_dinh", "soan_thao"}
        else []
    )

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

    files_snippet = "\n".join(
        f"- {f['filename']}: {f['extracted_text'][:400]}" for f in session_files
    )
    docs_snippet = "\n".join(
        f"- {d['doc_number']} ({d['title']}): {d['content'][:400]}" for d in matched_docs
    )

    llm_answer = _try_live_llm(
        system_prompt=(
            f"Bạn là Chuyên viên chính / Chánh Văn phòng hỗ trợ {dept['name']} thuộc {commune_name}. "
            f"Chỉ dẫn phòng: {dept['instruction']}. Chế độ: {mode}. "
            "Tuyệt đối không viện dẫn văn bản lệch chủ đề hoặc vượt thẩm quyền cấp xã."
        ),
        user_prompt=f"Câu hỏi: {message}\nTài liệu phiên:\n{files_snippet}\nVăn bản chính thức:\n{docs_snippet}",
        db_path=db_path,
    )

    if llm_answer:
        reply_content = llm_answer
    elif mode == "soan_thao":
        inferred_type, inferred_subj = _infer_draft_type_and_subject(message)
        extra_pts = "; ".join(
            f"Căn cứ thông tin hồ sơ {f['filename']}: {_clip(f['extracted_text'], 120)}"
            for f in session_files
        )
        draft_bundle = build_nd30_draft(
            department=dept,
            doc_type=inferred_type,
            title=inferred_subj,
            key_points=extra_pts,
            actor_email=actor_email,
            authority_mode="auto",
            db_path=db_path,
        )
        file_ref = (
            f"\n**Tài liệu phiên đã kết nối ({len(session_files)} tệp):** "
            + "; ".join(f"`{f['filename']}`" for f in session_files)
            + "\n"
            if session_files
            else ""
        )
        reply_content = (
            f"### Dự thảo văn bản chuẩn Nghị định 30/2020/NĐ-CP · {dept['name']}\n"
            f"- **Đơn vị ban hành:** {commune_name}\n"
            f"- **Loại văn bản & Ký hiệu:** {inferred_type} (`{draft_bundle['symbol']}`)\n"
            f"{file_ref}\n"
            f"```text\n{draft_bundle['draft_text']}\n```\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        )
    elif mode == "tham_dinh":
        ocr_warn = build_ocr_warning_banner(session_files)
        if session_files:
            file_rows = []
            for f in session_files:
                fields = extract_structured_fields(f["extracted_text"])
                extracted_summary = "; ".join(
                    f"{lbl}: {', '.join(fields[k])}"
                    for k, lbl in STRUCTURED_FIELD_SPECS
                    if fields[k]
                )
                file_rows.append(
                    f"- **{f['filename']}**: {_clip(f['extracted_text'], 220)}"
                    + (f" *(Trích xuất: {extracted_summary})*" if extracted_summary else "")
                )
            file_section = "#### Hồ sơ đính kèm trong phiên đã đối chiếu:\n" + "\n".join(file_rows) + "\n\n"
        else:
            file_section = "*(Chưa có tệp đính kèm trong phiên — thẩm định trực tiếp trên nội dung yêu cầu)*\n\n"

        basis_text = (
            "\n".join(
                f"- **{d['doc_number']}** — *{d['title']}* ({d['issuer']}): {_clip(d['content'], 340)}"
                for d in matched_docs
            )
            if matched_docs
            else "- *(Chưa có văn bản chuyên ngành khớp trực tiếp trong kho hiện tại; đề nghị bổ sung tại **Mô-đun 04** nếu có văn bản mới)*"
        )
        cited_codes = ", ".join(d["doc_number"] for d in matched_docs) if matched_docs else "65/2025/QH15, 30/2020/NĐ-CP"

        reply_content = (
            f"### Báo cáo Thẩm định Chuyên sâu · {dept['name']} ({commune_name})\n"
            f"**Nội dung thẩm định:** {message}\n\n"
            f"{ocr_warn}"
            f"{file_section}"
            f"#### 1. Ma trận rà soát tính hợp pháp, thẩm quyền & thể thức\n"
            f"| Tiêu chí thẩm định | Căn cứ đối chiếu | Kết quả rà soát & Lưu ý kiểm soát |\n"
            f"| --- | --- | --- |\n"
            f"| **1. Tính hợp pháp & Căn cứ** | {cited_codes} | Rà soát hiệu lực văn bản, đối tượng áp dụng và định mức/thời hạn pháp định tại cấp xã. |\n"
            f"| **2. Thẩm quyền ký ban hành** | Luật TCCQĐP `65/2025/QH15` | Phân định rõ việc thuộc tập thể UBND (`TM. ỦY BAN NHÂN DÂN`) hay thẩm quyền riêng Chủ tịch UBND (`CHỦ TỊCH`); không ký vượt thẩm quyền cấp trên. |\n"
            f"| **3. Thể thức & Kỹ thuật trình bày** | Nghị định `30/2020/NĐ-CP` | Kiểm tra ký hiệu Phụ lục I, không lặp `Về việc`, đúng quy tắc `Nơi nhận` và dòng `Lưu: VT, {dept['code']}.`. |\n"
            f"| **4. Đối chiếu số liệu & Hồ sơ** | {len(session_files)} tệp trong phiên | Kiểm tra chéo họ tên, CCCD, diện tích, kinh phí dự toán - nghiệm thu và mốc ngày tháng giữa các biên bản. |\n\n"
            f"#### 2. Chi tiết điều khoản pháp lý đối chiếu\n{basis_text}\n\n"
            f"#### 3. Các điểm cần hoàn thiện trước khi trình Lãnh đạo UBND ký\n"
            f"- Đảm bảo đầy đủ chữ ký xác nhận thực địa / biên bản nghiệm thu / niêm yết công khai (nếu thủ tục bắt buộc).\n"
            f"- Chuyển Văn phòng HĐND & UBND kiểm soát thể thức lần cuối và cấp số văn bản đi theo Nghị định `30/2020/NĐ-CP`.\n\n"
            f"*{LEGAL_RESPONSIBILITY_NOTE}*"
        )
    else:
        # Mode: nghiep_vu
        if not matched_docs:
            reply_content = (
                f"### Tư vấn nghiệp vụ · {dept['name']} ({commune_name})\n"
                f"**Nội dung truy vấn:** {message}\n\n"
                f"> ⚠️ **Thông báo tra cứu kho pháp luật nội bộ:** Hiện tại **chưa tìm thấy văn bản pháp quy hoặc hướng dẫn nội bộ khớp trực tiếp** với chủ đề truy vấn trong kho dữ liệu của {commune_name}.\n\n"
                f"**Khuyến nghị xử lý chuẩn xác cho công chức:**\n"
                f"1. Hệ thống **không tự ý suy diễn hoặc ghép văn bản lệch chuyên ngành** để tránh rủi ro áp dụng sai căn cứ pháp luật.\n"
                f"2. Nếu đây là lĩnh vực mới phát sinh hoặc văn bản chuyên ngành mới ban hành, đề nghị đồng chí gửi **Đề nghị cập nhật văn bản** tại **Mô-đun 04 (Nguồn văn bản chính thức)** để Quản trị viên phê duyệt bổ sung vào kho.\n"
                f"3. Trường hợp cần nghiên cứu các kịch bản tham khảo ngoài kho nội bộ, có thể sử dụng **Mô-đun 02 (Kiến thức mở rộng)**.\n\n"
                f"*{LEGAL_RESPONSIBILITY_NOTE}*"
            )
        else:
            clauses = decompose_question_clauses(message)
            clause_block = ""
            if len(clauses) >= 2:
                clause_lines = "\n".join(f"- **Vấn đề {i}:** {c}" for i, c in enumerate(clauses, start=1))
                clause_block = f"**Bóc tách câu hỏi nhiều vế cần xử lý đồng bộ:**\n{clause_lines}\n\n"

            auth_bullets = "\n".join(_build_authority_guidance(message, matched_docs, dept))
            basis_lines = "\n".join(
                f"- **{d['doc_number']}** — *{d['title']}* ({d['issuer']}): {_clip(d['content'], 520)}"
                for d in matched_docs
            )
            file_note = (
                "\n- **Đối chiếu dữ liệu tệp đính kèm trong phiên:** "
                + "; ".join(f"`{f['filename']}` ({_clip(f['extracted_text'], 150)})" for f in session_files)
                if session_files
                else ""
            )

            reply_content = (
                f"### Tư vấn nghiệp vụ chuyên sâu · {dept['name']} ({commune_name})\n"
                f"**Nội dung yêu cầu:** {message}\n\n"
                f"{clause_block}"
                f"#### 1. Phân định thẩm quyền giải quyết\n"
                f"{auth_bullets}\n\n"
                f"#### 2. Căn cứ pháp lý & điều khoản áp dụng\n"
                f"{basis_lines}\n\n"
                f"#### 3. Thành phần hồ sơ & trình tự thực hiện tại cấp xã\n"
                f"- **Bước 1 — Tiếp nhận & kiểm tra hồ sơ tại Bộ phận Một cửa:** Kiểm tra thành phần hồ sơ, thực hiện số hóa và lập Giấy tiếp nhận hồ sơ và hẹn trả kết quả theo Nghị định `61/2018/NĐ-CP` & `107/2021/NĐ-CP`.\n"
                f"- **Bước 2 — Thẩm tra chuyên môn / Xác minh thực địa / Niêm yết:** Bộ phận **{dept['name']}** đối chiếu hồ sơ gốc, kiểm tra hiện trạng thực địa, lấy ý kiến khu dân cư hoặc niêm yết công khai đúng thời hạn pháp định.\n"
                f"- **Bước 3 — Tổ chức hòa giải, đối thoại hoặc tham mưu trình ký:** Lập biên bản làm việc chặt chẽ; dự thảo văn bản đúng thể thức Nghị định `30/2020/NĐ-CP` trình tập thể UBND hoặc Chủ tịch UBND cấp xã ký đúng thẩm quyền (hoặc chuyển cấp trên nếu vượt thẩm quyền).\n"
                f"- **Bước 4 — Trả kết quả & lưu trữ hồ sơ công việc:** Phát hành văn bản có chữ ký số, cập nhật kết quả điện tử và lưu Văn thư (`Lưu: VT, {dept['code']}`).\n\n"
                f"#### 4. Cảnh báo rủi ro thực tiễn & lưu ý nghiệp vụ\n"
                f"- Kiểm soát chặt **thời hạn pháp định** (không để hồ sơ quá hạn trên Cổng Dịch vụ công hoặc quá thời hạn hòa giải/giải quyết khiếu nại).\n"
                f"- Tuyệt đối không ký ban hành văn bản sai thẩm quyền hoặc viện dẫn văn bản đã hết hiệu lực.{file_note}\n\n"
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


def _classify_m02_theme(topic: str, context: str, department_id: str) -> str:
    blob = f"{topic} {context}".lower()
    if any(k in blob for k in ("rác", "chất thải", "môi trường", "phân loại", "vệ sinh", "nước thải", "xanh sạch")):
        return "moi_truong"
    if any(k in blob for k in ("đất", "tranh chấp", "ranh giới", "lấn chiếm", "sổ đỏ", "xây dựng", "quy hoạch", "trật tự xây dựng")):
        return "dat_dai_xd"
    if any(k in blob for k in ("ngân sách", "dự toán", "tài sản công", "nhà văn hóa", "chợ", "hộ kinh doanh", "tiểu thương", "thuế", "đầu tư công")):
        return "ngan_sach_kinh_te"
    if any(k in blob for k in ("bảo trợ", "trợ cấp", "người có công", "hộ nghèo", "cận nghèo", "gia đình văn hóa", "lễ hội", "trẻ em", "an sinh")):
        return "van_hoa_xa_hoi"
    if any(k in blob for k in ("một cửa", "trực tuyến", "số hóa", "tthc", "thủ tục hành chính", "hộ tịch", "khai sinh", "chứng thực", "tiếp công dân", "khiếu nại")):
        return "cai_cach_tthc"
    return {
        "NNMT": "dat_dai_xd",
        "KT": "ngan_sach_kinh_te",
        "VHXH": "van_hoa_xa_hoi",
        "VP": "cai_cach_tthc",
    }.get(department_id, "quan_tri_chung")


def analyze_extended_options(
    department_id: str,
    topic: str,
    context: str = "",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    commune_name = get_commune_name(db_path)
    _, unit_display, _ = parse_commune_identity(commune_name)
    ctx_note = f" (gắn với đặc thù: {context.strip()})" if context.strip() else ""
    theme = _classify_m02_theme(topic, context, department_id)

    if theme == "moi_truong":
        options = [
            {
                "code": "Phương án A",
                "title": "Mô hình Tổ tự quản phân loại rác 03 nhóm tại từng thôn, tổ dân phố",
                "summary": (
                    f"Triển khai phân loại chất thải rắn sinh hoạt tại nguồn (tái chế, thực phẩm, khác) cho nhiệm vụ '{topic}'{ctx_note} "
                    f"thông qua Tổ tự quản môi trường thôn/tổ dân phố, phối hợp Ủy ban MTTQ, Hội Phụ nữ ('Nhà sạch - Ngõ văn minh') và Đoàn Thanh niên xã. "
                    "Nguồn lực: sử dụng kinh phí sự nghiệp môi trường thường xuyên kết hợp xã hội hóa thùng ủ phân hữu cơ. "
                    "Lưu ý pháp lý: không tự đặt mức thu phí ngoài khung HĐND tỉnh; xử phạt đúng thẩm quyền Chủ tịch UBND xã theo Nghị định 45/2022/NĐ-CP. "
                    "Lộ trình 3 bước: Bước 1: Họp dân ký cam kết tại nhà văn hóa thôn -> Bước 2: Đồng bộ lịch thu gom theo nhóm rác -> Bước 3: Kiểm tra, nhắc nhở và biểu dương hằng tháng."
                ),
                "pros": [
                    "Huy động trực tiếp Ủy ban MTTQ, Hội Phụ nữ, Đoàn Thanh niên đến từng hộ gia đình mà không tốn chi phí đầu tư lớn",
                    "Giảm ngay 40%–55% lượng rác thực phẩm phải vận chuyển đi chôn lấp nhờ ủ phân hữu cơ tại hộ/cụm dân cư",
                ],
                "cons": [
                    "Cần duy trì đôn đốc liên tục trong 60 ngày đầu để hình thành thói quen phân loại ổn định",
                ],
                "feasibility": "Rất khả thi (Triển khai ngay tại thôn/tổ dân phố)",
            },
            {
                "code": "Phương án B",
                "title": "Chuẩn hóa hợp đồng giám sát đơn vị thu gom kết hợp điểm tập kết xanh theo giờ",
                "summary": (
                    f"Thiết lập lịch thu gom phân luồng theo ngày/giờ cố định tại các điểm trung chuyển sạch cho '{topic}'{ctx_note}, "
                    "gắn trách nhiệm đơn vị dịch vụ thu gom từ chối tiếp nhận túi rác chưa phân loại theo Điều 75 Luật BVMT 72/2020/QH14; "
                    "Ban Thanh tra nhân dân và Tổ trưởng dân phố giám sát biên bản khối lượng. "
                    "Lưu ý pháp lý: đảm bảo đúng thẩm quyền giám sát của UBND cấp xã, không làm gián đoạn vệ sinh chung. "
                    "Lộ trình 3 bước: Bước 1: Rà soát lại các điểm tập kết gây ô nhiễm -> Bước 2: Ký phụ lục quy chuẩn thu gom theo giờ -> Bước 3: Gắn camera/kênh phản ánh hiện trường xử lý vi phạm."
                ),
                "pros": [
                    "Xóa bỏ triệt để các điểm tập kết rác tự phát lấn chiếm lòng lề đường tại khu dân cư",
                    "Ràng buộc rõ trách nhiệm pháp lý giữa đơn vị thu gom, Tổ dân phố và hộ phát sinh chất thải",
                ],
                "cons": [
                    "Đòi hỏi đơn vị dịch vụ thu gom bố trí phương tiện/ngăn chứa tách biệt tương ứng",
                ],
                "feasibility": "Khả thi cao (Trung hạn 1–3 tháng)",
            },
            {
                "code": "Phương án C",
                "title": "Thí điểm 02 tổ dân phố kiểu mẫu kết hợp tuần tra xử lý vi phạm hành chính",
                "summary": (
                    f"Chọn 02 thôn/tổ dân phố trung tâm làm điểm sáng phân loại rác và 'Đổi rác tái chế lấy quà an sinh' cùng MTTQ xã cho '{topic}'{ctx_note}, "
                    "kết hợp Tổ kiểm tra quy tắc đô thị/môi trường lập biên bản xử phạt nghiêm các trường hợp đổ trộm rác (khung phạt đến 5.000.000 đồng thẩm quyền Chủ tịch UBND xã). "
                    "Lộ trình 3 bước: Bước 1: Thí điểm 30 ngày tại 02 tổ dân phố trọng điểm -> Bước 2: Sơ kết rút kinh nghiệm cùng MTTQ và các đoàn thể -> Bước 3: Nhân rộng toàn địa bàn xã/phường."
                ),
                "pros": [
                    "Kiểm soát chắc chắn hiệu quả thực tế, tạo mô hình trực quan thuyết phục người dân trước khi nhân rộng đại trà",
                    "Kết hợp hài hòa giữa vận động dân vận khéo và tính răn đe pháp lý đúng thẩm quyền cấp xã",
                ],
                "cons": [
                    "Cần bước sơ kết đánh giá sau 30 ngày trước khi đồng loạt áp dụng cho các thôn còn lại",
                ],
                "feasibility": "Khuyến nghị áp dụng (Bền vững, rủi ro thấp)",
            },
        ]
    elif theme == "dat_dai_xd":
        options = [
            {
                "code": "Phương án A",
                "title": "Tăng cường Tổ hòa giải cơ sở & đối thoại thực địa sớm tại thôn, tổ dân phố",
                "summary": (
                    f"Giải quyết bài toán '{topic}'{ctx_note} ngay từ khi mới phát sinh tại thôn/tổ dân phố thông qua phối hợp giữa Công chức NNMT, "
                    "Ủy ban MTTQ xã, Hội Nông dân, Hội Cựu chiến binh và người cao tuổi am hiểu lịch sử thửa đất trước khi chuyển thành hồ sơ tranh chấp căng thẳng. "
                    "Lưu ý pháp lý: tuân thủ chặt hạn 30 ngày theo Điều 235 Luật Đất đai 2024; UBND xã không ký vượt thẩm quyền cấp sổ đỏ. "
                    "Lộ trình 3 bước: Bước 1: Đo đạc, đối chiếu bản đồ địa chính và sổ mục kê -> Bước 2: Mời MTTQ và hộ liền kề xác minh mốc giới tại thực địa -> Bước 3: Họp Hội đồng hòa giải lập biên bản đúng hạn."
                ),
                "pros": [
                    "Nâng cao tỷ lệ hòa giải thành tại cơ sở, giữ gìn đoàn kết tình làng nghĩa xóm và giảm đơn thư vượt cấp",
                    "Chi phí thấp, tận dụng uy tín của Ban Công tác Mặt trận khu dân cư",
                ],
                "cons": [
                    "Phụ thuộc thiện chí hợp tác của các bên tranh chấp đối với các hồ sơ lịch sử đất đai phức tạp",
                ],
                "feasibility": "Rất khả thi (Áp dụng thường xuyên)",
            },
            {
                "code": "Phương án B",
                "title": "Thiết lập cơ chế tuần tra liên ngành 24/7 kiểm soát đất công & trật tự xây dựng",
                "summary": (
                    f"Thành lập Tổ kiểm tra liên ngành cấp xã (Công chức NNMT - Công an xã - Tổ trưởng dân phố) tuần tra định kỳ xử lý '{topic}'{ctx_note}; "
                    "lập biên bản ngừng thi công ngay khi phát hiện lấn chiếm/xây trái phép theo Nghị định 123/2024/NĐ-CP và 16/2022/NĐ-CP. "
                    "Lưu ý pháp lý: Chủ tịch UBND xã phạt tiền tối đa đến 5.000.000 đồng đối với cá nhân; vượt thẩm quyền bắt buộc chuyển hồ sơ lên cấp trên trong 24 giờ. "
                    "Lộ trình 3 bước: Bước 1: Lập bản đồ điểm nóng đất nông nghiệp/đất công dễ lấn chiếm -> Bước 2: Giao trách nhiệm cảnh báo sớm cho Trưởng thôn/Tổ trưởng -> Bước 3: Lập biên bản đình chỉ trong 04 giờ khi phát sinh."
                ),
                "pros": [
                    "Ngăn chặn vi phạm ngay từ khi mới tập kết vật liệu, tránh phát sinh công trình kiên cố khó cưỡng chế",
                    "Đúng quy trình pháp lý, bảo vệ trách nhiệm công vụ cho cán bộ địa chính và lãnh đạo UBND xã",
                ],
                "cons": [
                    "Đòi hỏi chế độ trực kiểm tra ngoài giờ hành chính tại các khu vực giáp ranh",
                ],
                "feasibility": "Khả thi cao (Hiệu lực quản lý mạnh)",
            },
            {
                "code": "Phương án C",
                "title": "Số hóa sổ mục kê - niêm yết công khai 15 ngày minh bạch tại nhà văn hóa thôn",
                "summary": (
                    f"Kết hợp chuẩn hóa dữ liệu thửa đất với công khai dân chủ kết quả xét nguồn gốc đất 15 ngày tại trụ sở UBND {unit_display} và nhà văn hóa thôn cho '{topic}'{ctx_note}, "
                    "có sự giám sát của Ban Thanh tra nhân dân thuộc Ủy ban MTTQ xã. "
                    "Lộ trình 3 bước: Bước 1: Chuẩn hóa danh mục hồ sơ tồn đọng theo từng tổ dân phố -> Bước 2: Tổ chức lấy ý kiến khu dân cư và niêm yết 15 ngày -> Bước 3: Hoàn thiện xác nhận liên thông trình cấp có thẩm quyền."
                ),
                "pros": [
                    "Minh bạch 100% nguồn gốc sử dụng đất, phòng ngừa khiếu kiện phát sinh sau khi xác nhận",
                    "Rút ngắn thời gian tra cứu hồ sơ địa chính qua các thời kỳ cho công chức NNMT",
                ],
                "cons": [
                    "Cần rà soát, số hóa dần các sổ mục kê giấy cũ bị mờ rách",
                ],
                "feasibility": "Khuyến nghị áp dụng",
            },
        ]
    elif theme == "ngan_sach_kinh_te":
        options = [
            {
                "code": "Phương án A",
                "title": "Sắp xếp hộ kinh doanh tự quản kết hợp công khai thuế & phí minh bạch tại cơ sở",
                "summary": (
                    f"Triển khai '{topic}'{ctx_note} thông qua phối hợp giữa Phòng Kinh tế, Hội đồng tư vấn thuế xã (Luật Quản lý thuế 38/2019/QH14), "
                    "Ban Quản lý chợ, Ủy ban MTTQ xã và Tổ trưởng dân phố để rà soát hộ kinh doanh, tiểu thương ký cam kết niêm yết giá, an toàn PCCC và vệ sinh. "
                    "Lưu ý pháp lý: UBND xã tuyệt đối không đặt thêm khoản thu ngoài danh mục phí, lệ phí do HĐND tỉnh quyết định. "
                    "Lộ trình 3 bước: Bước 1: Thống kê phân loại hộ kinh doanh/tiểu thương theo tuyến phố, khu chợ -> Bước 2: Họp Hội đồng tư vấn thuế và MTTQ niêm yết công khai -> Bước 3: Hậu kiểm định kỳ và hướng dẫn thanh toán không tiền mặt."
                ),
                "pros": [
                    "Tạo sự đồng thuận cao của hộ kinh doanh và tiểu thương nhờ công khai, dân chủ qua MTTQ xã",
                    "Chống thất thu ngân sách xã mà không gây xáo trộn hoạt động mưu sinh tại chợ dân sinh",
                ],
                "cons": [
                    "Tốn thời gian rà soát thực tế các hộ kinh doanh thời vụ hoặc kinh doanh nhỏ lẻ biến động",
                ],
                "feasibility": "Rất khả thi (Ngắn hạn)",
            },
            {
                "code": "Phương án B",
                "title": "Chuẩn hóa quy trình kiểm soát chi ngân sách xã & giám sát đầu tư của cộng đồng",
                "summary": (
                    f"Áp dụng bộ tiêu chí kiểm soát kép chứng từ dự toán - nghiệm thu (Thông tư 344/2016/TT-BTC, Luật Đầu tư công 58/2024/QH15) cho '{topic}'{ctx_note}, "
                    "phát huy vai trò Ban Giám sát đầu tư của cộng đồng do Ủy ban MTTQ xã chủ trì tại các thôn, tổ dân phố. "
                    "Lộ trình 3 bước: Bước 1: Công khai dự toán được HĐND xã giao tại trụ sở và nhà văn hóa thôn -> Bước 2: Đối chiếu 3 bên khối lượng thực tế trước nghiệm thu -> Bước 3: Quyết toán qua Kho bạc Nhà nước đúng mục lục ngân sách."
                ),
                "pros": [
                    "Ngăn ngừa tuyệt đối sai lệch khối lượng dự toán - quyết toán và xuất toán khi kiểm toán/thanh tra",
                    "Tăng niềm tin của nhân dân khi giám sát trực tiếp các công trình dân sinh ngõ xóm",
                ],
                "cons": [
                    "Yêu cầu các bộ phận thụ hưởng hoàn thiện hồ sơ chứng từ chặt chẽ ngay từ đầu kỳ",
                ],
                "feasibility": "Khả thi cao",
            },
            {
                "code": "Phương án C",
                "title": "Mô hình Chợ văn minh thương mại 4.0 & kiểm kê số hóa tài sản công cấp xã",
                "summary": (
                    f"Thí điểm tuyến phố/khu chợ thanh toán QR không dùng tiền mặt phối hợp Đoàn Thanh niên, Hội Phụ nữ và ngân hàng thương mại cho '{topic}'{ctx_note}, "
                    "đồng thời gắn mã theo dõi tài sản công tại trụ sở và nhà văn hóa thôn theo Luật 15/2017/QH14. "
                    "Lộ trình 3 bước: Bước 1: Chọn khu điểm kinh doanh tập trung làm mẫu trong 30 ngày -> Bước 2: Tập huấn biên lai điện tử, mã QR và niêm yết nội quy -> Bước 3: Đánh giá và trình UBND xã nhân rộng."
                ),
                "pros": [
                    "Hiện đại hóa quản lý thương mại cơ sở, minh bạch dòng thu phí chợ và bảo vệ tài sản công",
                    "Huy động hiệu quả nguồn lực xã hội hóa hợp pháp từ ngân hàng/doanh nghiệp viễn thông",
                ],
                "cons": [
                    "Cần hỗ trợ trực tiếp cho nhóm tiểu thương lớn tuổi ít sử dụng điện thoại thông minh",
                ],
                "feasibility": "Khuyến nghị áp dụng",
            },
        ]
    elif theme == "van_hoa_xa_hoi":
        options = [
            {
                "code": "Phương án A",
                "title": "Rà soát an sinh đến từng tổ dân phố phối hợp Mặt trận & các đoàn thể nhận đỡ đầu",
                "summary": (
                    f"Triển khai '{topic}'{ctx_note} bằng mạng lưới cộng tác viên thôn/tổ dân phố phối hợp Ủy ban MTTQ, Hội Phụ nữ, Hội Chữ thập đỏ và Đoàn Thanh niên xã "
                    "rà soát đúng đối tượng bảo trợ xã hội (mức chuẩn 500.000 đồng/tháng theo Nghị định 76/2024/NĐ-CP), người có công và trẻ em có hoàn cảnh đặc biệt. "
                    "Lưu ý pháp lý: niêm yết công khai đủ thời hạn tại trụ sở UBND xã và nhà văn hóa thôn; ký quyết định đúng thẩm quyền Chủ tịch UBND xã/cấp trên. "
                    "Lộ trình 3 bước: Bước 1: Rà soát thực tế tại hộ cùng Trưởng thôn và Ban Công tác Mặt trận -> Bước 2: Họp bình xét dân chủ, niêm yết công khai -> Bước 3: Chi trả qua tài khoản an sinh hoặc hỗ trợ kịp thời."
                ),
                "pros": [
                    "Không bỏ sót đối tượng yếu thế, bảo đảm công bằng, dân chủ và không phát sinh khiếu nại tại khu dân cư",
                    "Kết nối thêm nguồn quỹ Vì người nghèo của MTTQ xã hỗ trợ ngoài định mức ngân sách",
                ],
                "cons": [
                    "Cần đối soát chặt biến động nhân khẩu hằng tháng với bộ phận Tư pháp - Hộ tịch",
                ],
                "feasibility": "Rất khả thi (Triển khai ngay)",
            },
            {
                "code": "Phương án B",
                "title": "Liên thông dữ liệu Hộ tịch - Bảo trợ xã hội & mạng lưới bảo vệ trẻ em phản ứng nhanh",
                "summary": (
                    f"Thiết lập quy trình đối soát định kỳ trước ngày 05 hằng tháng giữa VHXH - Hộ tịch - Công an xã - Trạm Y tế - Trường học cho '{topic}'{ctx_note}, "
                    "đảm bảo chi trả trợ cấp không tiền mặt chính xác và phản ứng trong 02–12 giờ đối với ca bảo vệ trẻ em theo Luật Trẻ em 102/2016/QH13. "
                    "Lộ trình 3 bước: Bước 1: Lập danh sách đối tượng quản lý theo từng thôn/tổ dân phố -> Bước 2: Vận hành kênh thông tin nhanh liên ngành xã -> Bước 3: Kiểm tra định kỳ và báo cáo Chủ tịch UBND xã."
                ),
                "pros": [
                    "Ngăn chặn triệt để rủi ro chi trùng, chi sai trợ cấp khi có biến động khai tử hoặc chuyển nơi cư trú",
                    "Bảo vệ kịp thời an toàn cho trẻ em và người yếu thế ngay tại cơ sở",
                ],
                "cons": [
                    "Yêu cầu duy trì chế độ giao ban trao đổi số liệu đều đặn hằng tháng giữa các bộ phận",
                ],
                "feasibility": "Khả thi cao",
            },
            {
                "code": "Phương án C",
                "title": "Gắn kết bình xét Gia đình văn hóa thực chất với xây dựng nếp sống văn minh lễ hội",
                "summary": (
                    f"Đổi mới cách thức triển khai '{topic}'{ctx_note} thông qua bình xét 'Gia đình văn hóa' theo Nghị định 86/2023/NĐ-CP và quản lý lễ hội theo Nghị định 110/2018/NĐ-CP "
                    "dưới sự chủ trì phối hợp của UBND và Ủy ban MTTQ xã. "
                    "Lưu ý pháp lý: Chủ tịch UBND cấp xã trực tiếp ký Quyết định tặng danh hiệu Gia đình văn hóa trước 25/11 hằng năm. "
                    "Lộ trình 3 bước: Bước 1: Phổ biến tiêu chí cụ thể tới từng hộ đầu năm -> Bước 2: Ban Công tác Mặt trận họp dân bình xét công khai -> Bước 3: Chủ tịch UBND xã quyết định công nhận và biểu dương tại Ngày hội Đại đoàn kết."
                ),
                "pros": [
                    "Khắc phục bệnh hình thức trong bình xét danh hiệu văn hóa, tạo phong trào thi đua thực chất ở khu dân cư",
                    "Lồng ghép hiệu quả với Ngày hội Đại đoàn kết toàn dân tộc ngày 18/11 tại các thôn, tổ dân phố",
                ],
                "cons": [
                    "Cần hướng dẫn thống nhất biểu mẫu biên bản bình xét cho các Trưởng ban công tác Mặt trận",
                ],
                "feasibility": "Khuyến nghị áp dụng",
            },
        ]
    else:
        # cai_cach_tthc / quan_tri_chung
        options = [
            {
                "code": "Phương án A",
                "title": f"Chuẩn hóa quy trình Một cửa kết hợp Tổ công nghệ số cộng đồng tại thôn, tổ dân phố ({dept['code']})",
                "summary": (
                    f"Triển khai '{topic}'{ctx_note} bằng cách niêm yết bộ mẫu hướng dẫn trực quan (QR mẫu tờ khai hộ tịch, chứng thực) tại Bộ phận Một cửa "
                    "và huy động Đoàn Thanh niên, Hội Phụ nữ, Ủy ban MTTQ xã tham gia Tổ công nghệ số cộng đồng hướng dẫn người dân ngay tại nhà văn hóa thôn/tổ dân phố. "
                    "Lưu ý pháp lý: tuân thủ Nghị định 61/2018/NĐ-CP, 107/2021/NĐ-CP; tuyệt đối không yêu cầu nộp thêm giấy tờ ngoài quy định TTHC. "
                    "Lộ trình 3 bước: Bước 1: Chuẩn hóa checklist 10 TTHC phát sinh nhiều nhất -> Bước 2: Tập huấn Tổ công nghệ số cộng đồng tại các tổ dân phố -> Bước 3: Đo lường tỷ lệ hồ sơ đúng hạn hằng tuần."
                ),
                "pros": [
                    "Không phát sinh chi phí đầu tư phần mềm mới, tận dụng lực lượng Đoàn Thanh niên và MTTQ xã tại khu dân cư",
                    "Giảm áp lực chờ đợi giờ cao điểm tại Bộ phận Tiếp nhận và Trả kết quả của UBND xã/phường",
                ],
                "cons": [
                    "Cần phân công lịch trực hỗ trợ công dân lớn tuổi trong 2–3 tuần đầu triển khai",
                ],
                "feasibility": "Rất khả thi (Ngắn hạn 1–2 tuần)",
            },
            {
                "code": "Phương án B",
                "title": "Số hóa hồ sơ ngay tại quầy tiếp nhận & liên thông phối hợp nội bộ tối đa 02 ngày",
                "summary": (
                    f"Áp dụng quy trình số hóa ký số toàn trình và phiếu chuyển điện tử có gắn hạn phản hồi 02 ngày làm việc giữa 04 phòng (VP, KT, VHXH, NNMT) cho '{topic}'{ctx_note}, "
                    "gắn với lịch tiếp công dân định kỳ hằng tuần của Chủ tịch UBND xã (Luật Tiếp công dân 42/2013/QH13). "
                    "Lưu ý pháp lý: phân định rõ văn bản ký TM. ỦY BAN NHÂN DÂN và văn bản ký CHỦ TỊCH theo Nghị định 30/2020/NĐ-CP. "
                    "Lộ trình 3 bước: Bước 1: Ban hành Quy chế phối hợp nội bộ -> Bước 2: Số hóa tái sử dụng dữ liệu hộ tịch, dân cư -> Bước 3: Kiểm điểm tiến độ hồ sơ trễ hạn vào giao ban sáng thứ Hai."
                ),
                "pros": [
                    "Rút ngắn 35%–50% thời gian luân chuyển hồ sơ giấy nội bộ và khắc phục triệt để tình trạng trễ hạn trả kết quả",
                    "Tái sử dụng kho dữ liệu số hóa, giảm phiền hà sao y chứng thực nhiều lần cho người dân",
                ],
                "cons": [
                    "Đòi hỏi 100% công chức chuyên môn tuân thủ nghiêm kỷ luật cập nhật trạng thái hồ sơ điện tử",
                ],
                "feasibility": "Khả thi cao (Trung hạn)",
            },
            {
                "code": "Phương án C",
                "title": "Mô hình 'Ngày thứ Bảy/Buổi chiều hướng dẫn TTHC lưu động' tại cụm dân cư kết hợp đối thoại",
                "summary": (
                    f"Thí điểm tổ công tác lưu động (Văn phòng - Tư pháp - Địa chính - VHXH phối hợp Ủy ban MTTQ xã) xuống trực tiếp nhà văn hóa cụm dân cư đông dân để hướng dẫn '{topic}'{ctx_note} "
                    "và tiếp nhận phản ánh kiến nghị tại chỗ trước khi nhân rộng toàn {unit_display}. "
                    "Lưu ý pháp lý: việc ký chứng thực, hộ tịch vẫn đảm bảo đúng trình tự sổ gốc và thẩm quyền theo Luật Hộ tịch, Nghị định 23/2015/NĐ-CP. "
                    "Lộ trình 3 bước: Bước 1: Chọn 02 cụm dân cư đông công nhân/người cao tuổi làm điểm trong 30 ngày -> Bước 2: Đánh giá sự hài lòng cùng MTTQ xã -> Bước 3: Đưa vào kế hoạch CCHC hằng quý của UBND xã."
                ),
                "pros": [
                    "Nâng cao rõ rệt chỉ số hài lòng của người dân (SIPAS) và giải tỏa sớm các vướng mắc thủ tục ngay tại cơ sở",
                    "Tạo số liệu thực chứng sinh động phục vụ báo cáo HĐND xã và UBND cấp trên",
                ],
                "cons": [
                    "Cần bố trí bù thời gian làm việc hợp lý theo quy định cho cán bộ tham gia tổ lưu động",
                ],
                "feasibility": "Khuyến nghị áp dụng",
            },
        ]

    return {
        "department": dept,
        "topic": topic,
        "context": context,
        "theme": theme,
        "scope_notice": (
            "Chế độ Kiến thức mở rộng: Nội dung gợi mở đa phương án bên ngoài kho văn bản nội bộ "
            "phục vụ nghiên cứu, tham khảo trước khi đưa vào dự thảo chính thức; tuyệt đối tuân thủ giới hạn thẩm quyền cấp xã."
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
    authority_mode: str = "auto",
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    dept = get_department_info(department_id, db_path)
    return build_nd30_draft(
        department=dept,
        doc_type=doc_type,
        title=title,
        key_points=key_points,
        recipient=recipient,
        actor_email=actor_email,
        authority_mode=authority_mode,
        db_path=db_path,
    )


def audit_administrative_draft(
    department_id: str,
    doc_type: str,
    draft_text: str,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    return audit_nd30_draft(
        department_id=department_id,
        doc_type=doc_type,
        draft_text=draft_text,
        db_path=db_path,
    )


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
    return run_structured_session_processing(
        files=state["files"],
        department=dept,
        action=action,
        legal_note=LEGAL_RESPONSIBILITY_NOTE,
    )
