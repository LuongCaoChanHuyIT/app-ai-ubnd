from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from backend.auth import (
    ActorContext,
    enforce_dept_scope,
    get_actor,
    require_owner_actor,
)
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
    DocUpdateReviewRequest,
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


@router.get("/m04/documents")
def list_official_documents(
    q: str = Query(default=""),
    tier: str | None = Query(default=None),
    department_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    effective_dept = (department_id or actor.department_id).strip().upper()
    enforce_dept_scope(actor, effective_dept)

    can_view_private = can_access_private_docs(
        actor.email, effective_dept, actor.db_path
    )
    docs = search_official_documents(
        query=q.strip(),
        department_id=effective_dept,
        tier=tier,
        include_private=can_view_private,
        fallback_on_empty=False,
        db_path=actor.db_path,
    )
    return {
        "documents": docs,
        "count": len(docs),
        "department_id": effective_dept,
    }


@router.post("/m04/documents")
def create_official_document(
    req: CreateDocRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    target_dept = (
        "ALL" if req.tier in {"trung_uong", "dia_phuong"} else req.department_id
    )

    if req.tier in {"trung_uong", "dia_phuong"} or target_dept == "ALL":
        if actor.role != "owner":
            raise HTTPException(
                status_code=403,
                detail="Chỉ Chủ sở hữu mới được bổ sung trực tiếp văn bản Trung ương/Địa phương/Toàn UBND; cán bộ chuyên môn vui lòng gửi Đề nghị cập nhật văn bản.",
            )
    else:
        enforce_dept_scope(actor, target_dept)
        if not can_access_private_docs(actor.email, target_dept, actor.db_path):
            raise HTTPException(
                status_code=403,
                detail=f"Tài khoản không có quyền thêm văn bản vào kho dữ liệu riêng của phòng {target_dept}.",
            )

    now = utc_now_iso()
    summary = req.summary.strip() or req.content.strip()[:220]
    with get_conn(actor.db_path) as conn:
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
        actor_email=actor.email,
        department_id=target_dept,
        module_code="M04",
        action="ADD_DOCUMENT",
        detail=f"Bổ sung văn bản {req.doc_number} ({req.tier})",
        db_path=actor.db_path,
    )
    return row


@router.get("/m04/update-requests")
def list_doc_update_requests(
    department_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    if actor.role != "owner":
        if department_id and department_id.upper() != actor.department_id:
            raise HTTPException(
                status_code=403,
                detail=f"Cán bộ phòng {actor.department_id} chỉ được xem đề nghị cập nhật của phòng mình.",
            )
        effective_dept: str | None = actor.department_id
    else:
        effective_dept = (
            department_id.upper()
            if department_id and department_id.upper() in {"VP", "KT", "VHXH", "NNMT"}
            else None
        )

    with get_conn(actor.db_path) as conn:
        if effective_dept:
            rows = conn.execute(
                "SELECT * FROM doc_update_requests WHERE department_id = ? ORDER BY id DESC",
                (effective_dept,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM doc_update_requests ORDER BY id DESC"
            ).fetchall()
    return {"requests": [dict(r) for r in rows]}


@router.post("/m04/update-requests")
def create_doc_update_request(
    req: DocUpdateRequestCreate,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    now = utc_now_iso()
    requester = actor.email
    with get_conn(actor.db_path) as conn:
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
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M04",
        action="REQUEST_DOC_UPDATE",
        detail=f"Đề nghị cập nhật văn bản {req.doc_number}: {req.title[:80]}",
        db_path=actor.db_path,
    )
    return row


@router.patch("/m04/update-requests/{request_id}/review")
def review_doc_update_request(
    request_id: int,
    req: DocUpdateReviewRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    now = utc_now_iso()
    inserted_doc: dict[str, Any] | None = None
    with get_conn(actor.db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM doc_update_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy đề nghị cập nhật.")
        if existing["status"] != "cho_duyet":
            raise HTTPException(
                status_code=409,
                detail="Đề nghị cập nhật này đã được xử lý trước đó.",
            )

        conn.execute(
            "UPDATE doc_update_requests SET status = ? WHERE id = ?",
            (req.status, request_id),
        )

        if req.status == "da_duyet":
            target_dept = (
                existing["department_id"]
                if existing["tier"] == "kho_rieng"
                else "ALL"
            )
            doc_content = (
                req.content.strip()
                or f"Văn bản cập nhật theo đề nghị của bộ phận {existing['department_id']}: {existing['reason']}"
            )
            doc_summary = req.summary.strip() or existing["reason"][:220]
            cur = conn.execute(
                """
                INSERT INTO official_documents(
                    doc_number, title, doc_type, tier, department_id,
                    issuer, issued_date, status, summary, content, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'moi_cap_nhat', ?, ?, ?)
                """,
                (
                    existing["doc_number"],
                    existing["title"],
                    req.doc_type.strip(),
                    existing["tier"],
                    target_dept,
                    req.issuer.strip(),
                    req.issued_date.strip(),
                    doc_summary,
                    doc_content,
                    now,
                ),
            )
            inserted_doc = dict(
                conn.execute(
                    "SELECT * FROM official_documents WHERE id = ?",
                    (cur.lastrowid,),
                ).fetchone()
            )

        conn.commit()
        updated_req = dict(
            conn.execute(
                "SELECT * FROM doc_update_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        )

    log_audit(
        actor_email=actor.email,
        department_id=updated_req["department_id"],
        module_code="M04",
        action="APPROVE_DOC_REQUEST" if req.status == "da_duyet" else "REJECT_DOC_REQUEST",
        detail=f"{'Phê duyệt' if req.status == 'da_duyet' else 'Từ chối'} đề nghị {updated_req['doc_number']}",
        db_path=actor.db_path,
    )
    return {"request": updated_req, "inserted_document": inserted_doc}


@router.post("/m05/sessions/{session_id}/upload")
async def upload_session_document(
    session_id: str,
    file: UploadFile = File(...),
    department_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    effective_dept = (department_id or actor.department_id).strip().upper()
    enforce_dept_scope(actor, effective_dept)

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
    state = SESSION_STORE.add_file(
        session_id,
        record,
        tenant_slug=actor.tenant_slug,
        actor_email=actor.email,
        department_id=effective_dept,
    )
    log_audit(
        actor_email=actor.email,
        department_id=effective_dept,
        module_code="M05",
        action="SESSION_UPLOAD",
        detail=f"Tải tệp tạm trong phiên: {filename} ({len(raw_bytes)} bytes)",
        db_path=actor.db_path,
    )
    return state


@router.post("/m05/sessions/{session_id}/process")
def process_session_documents(
    session_id: str,
    req: ProcessSessionRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    result = process_session_files(
        session_id=session_id,
        department_id=req.department_id,
        action=req.action,
        actor_email=actor.email,
        tenant_slug=actor.tenant_slug,
        db_path=actor.db_path,
    )
    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M05",
        action=f"PROCESS_{req.action.upper()}",
        detail=f"Xử lý {result['file_count']} tệp phiên với tác vụ {req.action}",
        db_path=actor.db_path,
    )
    return result
