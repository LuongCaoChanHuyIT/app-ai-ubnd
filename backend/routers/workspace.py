from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Header

from backend.db import SESSION_STORE, get_conn, log_audit
from backend.schemas import (
    AuditRequest,
    ChatRequest,
    DraftRequest,
    ExtendedAnalyzeRequest,
)
from backend.services.ai_engine import (
    analyze_extended_options,
    audit_administrative_draft,
    generate_administrative_draft,
    run_assistant_turn,
)

router = APIRouter(prefix="/api", tags=["workspace-m01-m03"])


@router.get("/departments")
def list_departments() -> dict[str, list[dict[str, Any]]]:
    with get_conn() as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, code, name, scope_summary, instruction, updated_at
                FROM departments
                ORDER BY CASE id
                    WHEN 'VP' THEN 1
                    WHEN 'KT' THEN 2
                    WHEN 'VHXH' THEN 3
                    WHEN 'NNMT' THEN 4
                    ELSE 5
                END
                """
            ).fetchall()
        ]
    return {"departments": rows}


@router.get("/sessions/{session_id}")
def get_session_state(session_id: str) -> dict[str, Any]:
    return SESSION_STORE.get_or_create(session_id)


@router.delete("/sessions/{session_id}")
def wipe_session_state(
    session_id: str,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
    department_id: str = "VP",
    module_code: str = "M01",
) -> dict[str, Any]:
    existed = SESSION_STORE.wipe(session_id)
    safe_mod = module_code if module_code in {"M01", "M05"} else "M01"
    log_audit(
        actor_email=x_actor_email,
        department_id=department_id,
        module_code=safe_mod,
        action="WIPE_SESSION",
        detail=f"Kết thúc phiên và xóa bộ nhớ tạm ({session_id})",
    )
    return {"wiped": True, "existed": existed, "session_id": session_id}


@router.post("/m01/chat")
def m01_chat(
    req: ChatRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    result = run_assistant_turn(
        session_id=req.session_id,
        department_id=req.department_id,
        mode=req.mode,
        message=req.message,
        actor_email=x_actor_email,
    )
    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M01",
        action=f"CHAT_{req.mode.upper()}",
        detail=f"Trao đổi chế độ {req.mode}: {req.message[:80]}",
    )
    return result


@router.post("/m02/analyze")
def m02_analyze(
    req: ExtendedAnalyzeRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    result = analyze_extended_options(
        department_id=req.department_id,
        topic=req.topic,
        context=req.context,
    )
    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M02",
        action="EXTENDED_ANALYZE",
        detail=f"Phân tích đa phương án: {req.topic[:80]}",
    )
    return result


@router.post("/m03/draft")
def m03_draft(
    req: DraftRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    result = generate_administrative_draft(
        department_id=req.department_id,
        doc_type=req.doc_type,
        title=req.title,
        key_points=req.key_points,
        recipient=req.recipient,
        actor_email=x_actor_email,
    )
    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M03",
        action="GENERATE_DRAFT",
        detail=f"Soạn dự thảo {req.doc_type}: {req.title[:80]}",
    )
    return result


@router.post("/m03/audit")
def m03_audit(
    req: AuditRequest,
    x_actor_email: str = Header(default="tsh.co@tshorg.vn"),
) -> dict[str, Any]:
    result = audit_administrative_draft(
        department_id=req.department_id,
        doc_type=req.doc_type,
        draft_text=req.draft_text,
    )
    log_audit(
        actor_email=x_actor_email,
        department_id=req.department_id,
        module_code="M03",
        action="AUDIT_DRAFT",
        detail=f"Kiểm tra dự thảo {req.doc_type} — điểm {result['score']}/100",
    )
    return result

