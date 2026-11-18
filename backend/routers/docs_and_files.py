from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, Query, UploadFile

from backend.db import SESSION_STORE, get_conn, log_audit, utc_now_iso
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
    FileTooLargeError,
    UnsupportedFileError,
    parse_uploaded_bytes,
)

router = APIRouter(prefix="/api", tags=["docs-and-files-m04-m05"])


def _has_private_repo_access(actor_email: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT role, private_repo_access, active FROM users_rbac WHERE email = ?",
            (actor_email,),
        ).fetchone()
        if not row:
            return True
        if not row["active"]:
            return False
        if row["role"] == "owner":
            return True
        return bool(row["private_repo_access"])


@router.get("/m04/documents")
def list_official_documents(
    q: str = Query(default=""),
    tier: str | None = Query(default=None),
    department_id: str = Query(default="VP"),
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    can_view_private = _has_private_repo_access(x_actor_email)
    if q.strip():
        docs = search_official_documents(
            query=q.strip(),
            department_id=department_id,
            tier=tier,
        )
    else:
        with get_conn() as conn:
            sql = """
                SELECT id, doc_number, title, doc_type, tier, department_id,
                       issuer, issued_date, status, summary, content, created_at
                FROM official_documents
                WHERE (tier != 'kho_rieng' OR department_id IN (?, 'ALL'))
            """
            params: list[Any] = [department_id]
            if tier and tier in {"trung_uong", "dia_phuong", "kho_rieng"}:
                sql += " AND tier = ?"
                params.append(tier)
            sql += " ORDER BY id DESC"
            docs = [dict(r) for r in conn.execute(sql, params).fetchall()]

    if not can_view_private:
        docs = [d for d in docs if d["tier"] != "kho_rieng"]

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
                req.department_id.strip().upper(),
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
        department_id=req.department_id,
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
    raw_bytes = await file.read()

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
