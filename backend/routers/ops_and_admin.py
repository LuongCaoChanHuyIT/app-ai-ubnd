from __future__ import annotations

import re
import unicodedata
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.auth import (
    ActorContext,
    enforce_dept_scope,
    get_actor,
    require_owner_actor,
)
from backend.db import get_conn, get_db_path, init_db, log_audit, utc_now_iso
from backend.schemas import (
    CloneTenantRequest,
    ConnectorUpdateRequest,
    InstructionUpdateRequest,
    TaskCreateRequest,
    TaskPatchRequest,
    UserCreateRequest,
    UserPatchRequest,
)

router = APIRouter(prefix="/api", tags=["ops-and-admin-m06-m07"])


def mask_secret(secret: str) -> str:
    cleaned = (secret or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= 10:
        return "***"
    return f"{cleaned[:3]}***{cleaned[-4:]}"


def slugify_commune(name: str) -> str:
    cleaned = name.replace("..", " ").replace("/", " ").replace("\\", " ")
    cleaned = cleaned.replace("đ", "d").replace("Đ", "D")
    normalized = unicodedata.normalize("NFKD", cleaned)
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    slug = slug[:80].rstrip("-")
    if not slug:
        raise HTTPException(
            status_code=400, detail="Tên xã/phường không hợp lệ để tạo mã định danh."
        )
    return slug


def _sanitize_tenant_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.pop("db_path", None)
    out["storage_label"] = f"isolated-tenant://{out['slug']}"
    return out


@router.get("/m06/tasks")
def list_tasks(
    department_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    if actor.role != "owner":
        if department_id and department_id.upper() not in {"ALL", actor.department_id}:
            raise HTTPException(
                status_code=403,
                detail=f"Tài khoản cán bộ phòng {actor.department_id} chỉ được xem nhiệm vụ thuộc phòng {actor.department_id}.",
            )
        effective_dept: str | None = actor.department_id
    else:
        effective_dept = (
            department_id.upper()
            if department_id and department_id.upper() in {"VP", "KT", "VHXH", "NNMT"}
            else None
        )

    with get_conn(actor.db_path) as conn:
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: list[Any] = []
        if effective_dept:
            sql += " AND department_id = ?"
            params.append(effective_dept)
        if status and status in {
            "cho_xu_ly",
            "dang_thuc_hien",
            "sap_den_han",
            "hoan_thanh",
        }:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY id DESC"
        filtered = [dict(r) for r in conn.execute(sql, params).fetchall()]

    # KPIs match the exact filtered dataset displayed on screen
    kpis = {
        "total": len(filtered),
        "in_progress": sum(
            1 for t in filtered if t["status"] in {"cho_xu_ly", "dang_thuc_hien"}
        ),
        "due_soon": sum(1 for t in filtered if t["status"] == "sap_den_han"),
        "completed": sum(1 for t in filtered if t["status"] == "hoan_thanh"),
    }
    return {
        "kpis": kpis,
        "tasks": filtered,
        "effective_department": effective_dept or "ALL",
    }


@router.post("/m06/tasks")
def create_task(
    req: TaskCreateRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    enforce_dept_scope(actor, req.department_id)
    now = utc_now_iso()
    with get_conn(actor.db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO tasks(
                title, description, department_id, assignee, due_date,
                priority, status, progress, ref_doc_number, reminder_count, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'dang_thuc_hien', 0, ?, 0, ?, ?)
            """,
            (
                req.title.strip(),
                req.description.strip(),
                req.department_id,
                req.assignee.strip(),
                req.due_date.strip(),
                req.priority,
                req.ref_doc_number.strip(),
                now,
                now,
            ),
        )
        tid = cur.lastrowid
        conn.commit()
        row = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (tid,)).fetchone())

    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M06",
        action="CREATE_TASK",
        detail=f"Giao nhiệm vụ '{req.title[:70]}' cho {req.assignee}",
        db_path=actor.db_path,
    )
    return row


@router.patch("/m06/tasks/{task_id}")
def patch_task(
    task_id: int,
    req: TaskPatchRequest,
    actor: ActorContext = Depends(get_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy nhiệm vụ.")

        enforce_dept_scope(actor, existing["department_id"])

        progress = req.progress if req.progress is not None else existing["progress"]
        status = req.status if req.status is not None else existing["status"]
        if progress == 100 and req.status is None:
            status = "hoan_thanh"
        reminder_count = existing["reminder_count"] + (1 if req.remind else 0)

        conn.execute(
            """
            UPDATE tasks
            SET progress = ?, status = ?, reminder_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (progress, status, reminder_count, utc_now_iso(), task_id),
        )
        conn.commit()
        updated = dict(
            conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        )

    action_code = "REMIND_TASK" if req.remind else "UPDATE_TASK"
    log_audit(
        actor_email=actor.email,
        department_id=updated["department_id"],
        module_code="M06",
        action=action_code,
        detail=f"Cập nhật nhiệm vụ #{task_id} ({updated['progress']}%, trạng thái {updated['status']})",
        db_path=actor.db_path,
    )
    return updated


@router.get("/m07/users")
def list_rbac_users(
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        rows = [
            dict(r)
            for r in conn.execute("SELECT * FROM users_rbac ORDER BY id ASC").fetchall()
        ]
    for r in rows:
        r["private_repo_access"] = bool(r["private_repo_access"])
        r["active"] = bool(r["active"])
    return {"users": rows}


@router.post("/m07/users")
def create_rbac_user(
    req: UserCreateRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    now = utc_now_iso()
    email = req.email.strip().lower()
    with get_conn(actor.db_path) as conn:
        dup = conn.execute(
            "SELECT id FROM users_rbac WHERE lower(email) = ?", (email,)
        ).fetchone()
        if dup:
            raise HTTPException(
                status_code=409, detail="Email cán bộ này đã tồn tại trong hệ thống."
            )
        cur = conn.execute(
            """
            INSERT INTO users_rbac(
                email, full_name, position, role, department_id, private_repo_access, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                email,
                req.full_name.strip(),
                req.position.strip(),
                req.role,
                req.department_id,
                1 if req.private_repo_access else 0,
                now,
            ),
        )
        uid = cur.lastrowid
        conn.commit()
        row = dict(
            conn.execute("SELECT * FROM users_rbac WHERE id = ?", (uid,)).fetchone()
        )
        row["private_repo_access"] = bool(row["private_repo_access"])
        row["active"] = bool(row["active"])

    log_audit(
        actor_email=actor.email,
        department_id=req.department_id,
        module_code="M07",
        action="ADD_USER_RBAC",
        detail=f"Phân quyền email {email} vào nhóm {req.department_id} ({req.role})",
        db_path=actor.db_path,
    )
    return row


@router.patch("/m07/users/{user_id}")
def patch_rbac_user(
    user_id: int,
    req: UserPatchRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        target = conn.execute(
            "SELECT * FROM users_rbac WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        if target["role"] == "owner" and not req.private_repo_access:
            raise HTTPException(
                status_code=400,
                detail="Tài khoản Chủ sở hữu luôn có toàn quyền truy cập Kho dữ liệu riêng.",
            )
        conn.execute(
            "UPDATE users_rbac SET private_repo_access = ? WHERE id = ?",
            (1 if req.private_repo_access else 0, user_id),
        )
        conn.commit()
        updated = dict(
            conn.execute("SELECT * FROM users_rbac WHERE id = ?", (user_id,)).fetchone()
        )
        updated["private_repo_access"] = bool(updated["private_repo_access"])
        updated["active"] = bool(updated["active"])

    log_audit(
        actor_email=actor.email,
        department_id=updated["department_id"],
        module_code="M07",
        action="UPDATE_USER_RBAC",
        detail=(
            f"Cập nhật quyền Kho riêng của {updated['email']}: "
            f"{'Được phép' if updated['private_repo_access'] else 'Giới hạn'}"
        ),
        db_path=actor.db_path,
    )
    return updated


@router.delete("/m07/users/{user_id}")
def delete_rbac_user(
    user_id: int,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        target = conn.execute(
            "SELECT * FROM users_rbac WHERE id = ?", (user_id,)
        ).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")
        if target["role"] == "owner":
            owner_count = conn.execute(
                "SELECT COUNT(*) AS c FROM users_rbac WHERE role = 'owner' AND active = 1"
            ).fetchone()["c"]
            if owner_count <= 1:
                raise HTTPException(
                    status_code=400,
                    detail="Không thể xóa tài khoản Chủ sở hữu duy nhất của hệ thống.",
                )
        conn.execute("DELETE FROM users_rbac WHERE id = ?", (user_id,))
        conn.commit()

    log_audit(
        actor_email=actor.email,
        department_id=target["department_id"],
        module_code="M07",
        action="REMOVE_USER_RBAC",
        detail=f"Thu hồi quyền truy cập của {target['email']}",
        db_path=actor.db_path,
    )
    return {"deleted": True, "id": user_id}


@router.put("/m07/departments/{dept_id}/instruction")
def update_department_instruction(
    dept_id: str,
    req: InstructionUpdateRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM departments WHERE id = ?", (dept_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(
                status_code=404, detail="Không tìm thấy phòng chuyên môn."
            )
        conn.execute(
            "UPDATE departments SET instruction = ?, updated_at = ? WHERE id = ?",
            (req.instruction.strip(), utc_now_iso(), dept_id),
        )
        conn.commit()
        updated = dict(
            conn.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()
        )

    log_audit(
        actor_email=actor.email,
        department_id=dept_id,
        module_code="M07",
        action="UPDATE_INSTRUCTION",
        detail=f"Cập nhật Instruction nghiệp vụ của {updated['name']}",
        db_path=actor.db_path,
    )
    return updated


@router.get("/m07/api-connectors")
def list_api_connectors(
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM api_connectors ORDER BY id ASC"
            ).fetchall()
        ]
    sanitized: list[dict[str, Any]] = []
    for r in rows:
        raw_key = r.pop("api_key", "")
        r["has_key"] = bool(raw_key)
        r["api_key_masked"] = mask_secret(raw_key)
        r["active"] = bool(r["active"])
        sanitized.append(r)
    return {"connectors": sanitized}


@router.put("/m07/api-connectors/{connector_id}")
def update_api_connector(
    connector_id: int,
    req: ConnectorUpdateRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        existing = conn.execute(
            "SELECT * FROM api_connectors WHERE id = ?", (connector_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Không tìm thấy cổng API.")

        new_key = (
            req.api_key.strip()
            if req.api_key is not None and req.api_key.strip() != ""
            else existing["api_key"]
        )
        conn.execute(
            """
            UPDATE api_connectors
            SET name = ?, provider = ?, base_url = ?, model_name = ?, api_key = ?, active = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                req.name.strip(),
                req.provider.strip(),
                req.base_url.strip(),
                req.model_name.strip(),
                new_key,
                1 if req.active else 0,
                utc_now_iso(),
                connector_id,
            ),
        )
        conn.commit()
        updated = dict(
            conn.execute(
                "SELECT * FROM api_connectors WHERE id = ?", (connector_id,)
            ).fetchone()
        )

    raw_key = updated.pop("api_key", "")
    updated["has_key"] = bool(raw_key)
    updated["api_key_masked"] = mask_secret(raw_key)
    updated["active"] = bool(updated["active"])

    log_audit(
        actor_email=actor.email,
        department_id="VP",
        module_code="M07",
        action="UPDATE_API_CONNECTOR",
        detail=f"Cập nhật cổng API '{updated['name']}' (active={updated['active']})",
        db_path=actor.db_path,
    )
    return updated


@router.get("/m07/audit-logs")
def list_audit_logs(
    limit: int = Query(default=50, ge=1, le=200),
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    with get_conn(actor.db_path) as conn:
        rows = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        ]
    return {"logs": rows}


@router.get("/m07/tenants")
def list_cloned_tenants(
    _actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    root_db = get_db_path()
    with get_conn(root_db) as conn:
        rows = [
            _sanitize_tenant_row(dict(r))
            for r in conn.execute(
                "SELECT * FROM cloned_tenants ORDER BY id DESC"
            ).fetchall()
        ]
    return {"tenants": rows}


@router.post("/m07/clone-tenant")
def clone_commune_tenant(
    req: CloneTenantRequest,
    actor: ActorContext = Depends(require_owner_actor),
) -> dict[str, Any]:
    slug = slugify_commune(req.commune_name)
    root_db = get_db_path()
    tenants_dir = (root_db.parent / "tenants").resolve()
    tenants_dir.mkdir(parents=True, exist_ok=True)
    target_db = (tenants_dir / f"{slug}.db").resolve()

    if target_db.parent != tenants_dir:
        raise HTTPException(
            status_code=400, detail="Đường dẫn định danh không hợp lệ."
        )

    with get_conn(root_db) as conn:
        existing = conn.execute(
            "SELECT id FROM cloned_tenants WHERE slug = ?", (slug,)
        ).fetchone()
        if existing or target_db.exists():
            raise HTTPException(
                status_code=409,
                detail=f"Hệ thống độc lập với mã '{slug}' đã tồn tại; không ghi đè dữ liệu cũ.",
            )

        try:
            init_db(
                db_path=target_db,
                commune_name=req.commune_name.strip(),
                owner_email=req.admin_email.strip().lower(),
            )
            now = utc_now_iso()
            cur = conn.execute(
                """
                INSERT INTO cloned_tenants(slug, commune_name, admin_email, db_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    slug,
                    req.commune_name.strip(),
                    req.admin_email.strip().lower(),
                    str(target_db),
                    now,
                ),
            )
            tid = cur.lastrowid
            conn.commit()
        except Exception:
            if target_db.exists():
                target_db.unlink(missing_ok=True)
            raise

        created = dict(
            conn.execute(
                "SELECT * FROM cloned_tenants WHERE id = ?", (tid,)
            ).fetchone()
        )

    log_audit(
        actor_email=actor.email,
        department_id="VP",
        module_code="M07",
        action="CLONE_TENANT",
        detail=f"Nhân bản hệ thống AI độc lập cho '{req.commune_name.strip()}' ({slug})",
        db_path=actor.db_path,
    )
    return _sanitize_tenant_row(created)
