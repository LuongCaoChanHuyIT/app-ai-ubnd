from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from backend.db import (
    SESSION_STORE,
    can_access_private_docs,
    get_conn,
    log_audit,
    utc_now_iso,
)
from backend.schemas import (
    CreateDocRequest,
    DocUpdateRequestCreate,
    ProcessSessionRequest,
)
from backend.services.ai_engine import (
    process_session_files,
    search_official_documents,
)
from backend.services.doc_parser import (
    MAX_UPLOAD_BYTES,
    FileTooLargeError,
    UnsupportedFileError,
    parse_uploaded_bytes,
)

router = APIRouter(prefix="/api", tags=["docs-and-files-m04-m05"])


def _is_active_owner(actor_email: str) -> bool:
    email = (actor_email or "").strip().lower()
    if not email:
        return False
    with get_conn() as conn:
        row = conn.execute(
            "SELECT role, active FROM users_rbac WHERE lower(email) = ?",
            (email,),
        ).fetchone()
        return bool(row and row["active"] and row["role"] == "owner")


@router.get("/m04/documents")
def list_official_documents(
    q: str = Query(default=""),
    tier: str | None = Query(default=None),
    department_id: str = Query(default="VP"),
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    can_view_private = can_access_private_docs(x_actor_email, department_id)
    docs = search_official_documents(
        query=q.strip(),
        department_id=department_id,
        tier=tier,
        include_private=can_view_private,
        fallback_on_empty=False,
    )
    return {
        "documents": docs,
        "count": len(docs),
        "department_id": department_id,
    }


@router.post("/m04/documents")
def create_official_document(
    req: CreateDocRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    target_dept = "ALL" if req.tier in {"trung_uong", "dia_phuong"} else req.department_id

    if req.tier in {"trung_uong", "dia_phuong"} or target_dept == "ALL":
        if not _is_active_owner(x_actor_email):
            raise HTTPException(
                status_code=403,
                detail="Chỉ Chủ sở hữu mới được bổ sung trực tiếp văn bản Trung ương/Địa phương/Toàn UBND; cán bộ chuyên môn vui lòng gửi Đề nghị cập nhật văn bản.",
            )
    else:
        if not can_access_private_docs(x_actor_email, target_dept):
            raise HTTPException(
                status_code=403,
                detail=f"Tài khoản không có quyền thêm văn bản vào kho dữ liệu riêng của phòng {target_dept}.",
            )

    now = utc_now_iso()
    summary = req.summary.strip() or req.content.strip()[:220]
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO official_documents(
                doc_number, title, doc_type, tier, department_id,
                issuer, issued_date, status, summary, content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                req.doc_number.strip(),
                req.title.strip(),
                req.doc_type.strip(),
                req.tier,
                target_dept,
                req.issuer.strip(),
                req.issued_date.strip(),
                req.status.strip(),
                summary,
                req.content.strip(),
                now,
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        row = dict(
            conn.execute(
                "SELECT * FROM official_documents WHERE id = ?",
                (new_id,),
            ).fetchone()
        )

    log_audit(
        actor_email=x_actor_email,
        department_id=target_dept,
        module_code="M04",
        action="ADD_DOCUMENT",
        detail=f"Bổ sung văn bản {req.doc_number} ({req.tier})",
    )
    return row


@router.get("/m04/update-requests")
def list_doc_update_requests(
    department_id: str | None = Query(default=None),
) -> dict[str, Any]:
    with get_conn() as conn:
        if department_id and department_id in {"VP", "KT", "VHXH", "NNMT"}:
            rows = conn.execute(
                "SELECT * FROM doc_update_requests WHERE department_id = ? ORDER BY id DESC",
                (department_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM doc_update_requests ORDER BY id DESC"
            ).fetchall()
    return {"requests": [dict(r) for r in rows]}


@router.post("/m04/update-requests")
def create_doc_update_request(
    req: DocUpdateRequestCreate,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    now = utc_now_iso()
    requester = req.requested_by.strip() or x_actor_email
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO doc_update_requests(
                doc_number, title, tier, department_id, reason, requested_by, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'cho_duyet', ?)
            """,
            (
                req.doc_number.strip(),
                req.title.strip(),
                req.tier,
                req.department_id,
                req.reason.strip(),
                requester,
                now,
            ),
        )
        new_id = cur.lastrowid
        conn.commit()
        row = dict(
            conn.execute(
                "SELECT * FROM doc_update_requests WHERE id = ?",
                (new_id,),
            ).fetchone()
        )

    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M04",
        action="REQUEST_DOC_UPDATE",
        detail=f"Đề nghị cập nhật văn bản {req.doc_number}: {req.title[:80]}",
    )
    return row


@router.post("/m05/sessions/{session_id}/upload")
async def upload_session_document(
    session_id: str,
    file: UploadFile = File(...),
    department_id: str = Query(default="VP"),
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    filename = Path(file.filename or "tai_lieu.txt").name
    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)

    try:
        extracted_text, parse_note = parse_uploaded_bytes(filename, raw_bytes)
    except FileTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    record = {
        "file_id": uuid.uuid4().hex[:12],
        "filename": filename,
        "size_bytes": len(raw_bytes),
        "ext": Path(filename).suffix.lower(),
        "extracted_text": extracted_text,
        "parse_note": parse_note,
        "uploaded_at": utc_now_iso(),
    }
    state = SESSION_STORE.add_file(session_id, record)
    log_audit(
        actor_email=x_actor_email,
        department_id=department_id,
        module_code="M05",
        action="SESSION_UPLOAD",
        detail=f"Tải tệp tạm trong phiên: {filename} ({len(raw_bytes)} bytes)",
    )
    return state


@router.post("/m05/sessions/{session_id}/process")
def process_session_documents(
    session_id: str,
    req: ProcessSessionRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    result = process_session_files(
        session_id=session_id,
        department_id=req.department_id,
        action=req.action,
    )
    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M05",
        action=f"PROCESS_{req.action.upper()}",
        detail=f"Xử lý {result['file_count']} tệp phiên với tác vụ {req.action}",
    )
    return result
