from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, Header, Query, Request

from backend.auth import (
    ActorContext,
    enforce_dept_scope,
    get_actor,
    resolve_tenant_from_request,
)
from backend.db import SESSION_STORE, get_commune_name, get_conn, get_db_path, log_audit
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


@router.get("/bootstrap")
def get_workspace_bootstrap(
    request: Request,
    x_tenant_slug: str = Header(default=""),
) -> dict[str, Any]:
    tenant_slug, db_path, commune_name = resolve_tenant_from_request(
        request, x_tenant_slug
    )
    root_db = get_db_path()
    available_tenants = [
        {"slug": "default", "commune_name": get_commune_name(root_db)}
    ]
    with get_conn(root_db) as rconn:
        for row in rconn.execute(
            "SELECT slug, commune_name FROM cloned_tenants ORDER BY id ASC"
        ).fetchall():
            available_tenants.append(
                {"slug": row["slug"], "commune_name": row["commune_name"]}
            )

    with get_conn(db_path) as conn:
        departments = [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, code, name, scope_summary, updated_at
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
        demo_accounts = [
            {
                "email": r["email"],
                "full_name": r["full_name"],
                "position": r["position"],
                "role": r["role"],
                "department_id": r["department_id"],
                "private_repo_access": bool(r["private_repo_access"]),
            }
            for r in conn.execute(
                """
                SELECT email, full_name, position, role, department_id, private_repo_access
                FROM users_rbac
                WHERE active = 1
                ORDER BY CASE WHEN role = 'owner' THEN 0 ELSE 1 END, id ASC
                """
            ).fetchall()
        ]

    return {
        "commune_name": commune_name,
        "active_tenant_slug": tenant_slug,
        "available_tenants": available_tenants,
        "departments": departments,
        "demo_accounts": demo_accounts,
    }


@router.get("/departments")
def list_departments(
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
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
    if actor.role != "owner":
        for r in rows:
            if r["id"] != actor.department_id:
                r["instruction"] = ""
    return {
        "commune_name": actor.commune_name,
        "active_tenant_slug": actor.tenant_slug,
        "departments": rows,
    }


@router.get("/sessions/{session_id}")
def get_session_state(
    session_id: str,
    department_id: str = Query(default="VP"),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    target_dept = (
        actor.department_id if actor.role != "owner" and department_id == "VP" and actor.department_id != "VP"
        else department_id
    )
    enforce_dept_scope(actor, target_dept)
    return SESSION_STORE.get_or_create(
        session_id,
        tenant_slug=actor.tenant_slug,
        actor_email=actor.email,
        department_id=target_dept,
    )


@router.delete("/sessions/{session_id}")
def wipe_session_state(
    session_id: str,
    department_id: str = Query(default="VP"),
    module_code: str = Query(default="M01"),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    target_dept = (
        actor.department_id if actor.role != "owner" and department_id == "VP" and actor.department_id != "VP"
        else department_id
    )
    enforce_dept_scope(actor, target_dept)
    existed = SESSION_STORE.wipe(
        session_id,
        tenant_slug=actor.tenant_slug,
        actor_email=actor.email,
        department_id=target_dept,
    )
    safe_mod = module_code if module_code in {"M01", "M05"} else "M01"
    log_audit(
        actor_email=actor.email,
        department_id=target_dept,
        module_code=safe_mod,
        action="WIPE_SESSION",
        detail=f"Kết thúc phiên và xóa bộ nhớ tạm ({session_id})",
        db_path=actor.db_path,
    )
    return {"wiped": True, "existed": existed, "session_id": session_id}


@router.post("/m01/chat")
def m01_chat(
    req: ChatRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    result = run_assistant_turn(
        session_id=req.session_id,
        department_id=req.department_id,
        mode=req.mode,
        message=req.message,
        actor_email=actor.email,
        tenant_slug=actor.tenant_slug,
        db_path=actor.db_path,
    )
    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M01",
        action=f"CHAT_{req.mode.upper()}",
        detail=f"Trao đổi chế độ {req.mode}: {req.message[:80]}",
        db_path=actor.db_path,
    )
    return result


@router.post("/m02/analyze")
def m02_analyze(
    req: ExtendedAnalyzeRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    result = analyze_extended_options(
        department_id=req.department_id,
        topic=req.topic,
        context=req.context,
        db_path=actor.db_path,
    )
    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M02",
        action="EXTENDED_ANALYZE",
        detail=f"Phân tích đa phương án: {req.topic[:80]}",
        db_path=actor.db_path,
    )
    return result


@router.post("/m03/draft")
def m03_draft(
    req: DraftRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    result = generate_administrative_draft(
        department_id=req.department_id,
        doc_type=req.doc_type,
        title=req.title,
        key_points=req.key_points,
        recipient=req.recipient,
        actor_email=actor.email,
        authority_mode=req.authority_mode,
        db_path=actor.db_path,
    )
    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M03",
        action="GENERATE_DRAFT",
        detail=f"Soạn dự thảo {req.doc_type}: {req.title[:80]}",
        db_path=actor.db_path,
    )
    return result


@router.post("/m03/audit")
def m03_audit(
    req: AuditRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    result = audit_administrative_draft(
        department_id=req.department_id,
        doc_type=req.doc_type,
        draft_text=req.draft_text,
        db_path=actor.db_path,
    )
    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M03",
        action="AUDIT_DRAFT",
        detail=f"Kiểm tra dự thảo {req.doc_type} — điểm {result['score']}/100",
        db_path=actor.db_path,
    )
    return result
