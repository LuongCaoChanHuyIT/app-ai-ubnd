from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

from fastapi import Depends, Header, HTTPException, Request

from backend.db import get_commune_name, get_conn, get_db_path


@dataclass(frozen=True)
class ActorContext:
    email: str
    full_name: str
    position: str
    role: str
    department_id: str
    private_repo_access: bool
    tenant_slug: str
    db_path: Path
    commune_name: str


def resolve_tenant_from_request(
    request: Request,
    x_tenant_slug: str = Header(default=""),
) -> tuple[str, Path, str]:
    raw_slug = (
        x_tenant_slug.strip()
        or unquote(request.cookies.get("ubnd_tenant_slug", "")).strip()
    )
    root_db = get_db_path()
    if not raw_slug or raw_slug == "default":
        return ("default", root_db, get_commune_name(root_db))

    if not re.fullmatch(r"[a-z0-9-]+", raw_slug):
        raise HTTPException(status_code=400, detail="Mã đơn vị xã/phường không hợp lệ.")

    tenants_dir = (root_db.parent / "tenants").resolve()
    target_db = (tenants_dir / f"{raw_slug}.db").resolve()
    if target_db.parent != tenants_dir or not target_db.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy cơ sở dữ liệu của đơn vị '{raw_slug}'.",
        )

    with get_conn(root_db) as conn:
        row = conn.execute(
            "SELECT commune_name FROM cloned_tenants WHERE slug = ?",
            (raw_slug,),
        ).fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"Đơn vị '{raw_slug}' chưa được đăng ký trên hệ thống.",
            )
        commune_name = row["commune_name"]

    return (raw_slug, target_db, commune_name)


def get_actor(
    request: Request,
    x_actor_email: str = Header(default=""),
    x_tenant_slug: str = Header(default=""),
) -> ActorContext:
    tenant_slug, db_path, commune_name = resolve_tenant_from_request(
        request, x_tenant_slug
    )
    raw_email = (
        x_actor_email.strip()
        or unquote(request.cookies.get("ubnd_actor_email", "")).strip()
    ).lower()

    if not raw_email:
        raise HTTPException(
            status_code=401,
            detail="Chưa xác thực danh tính cán bộ. Vui lòng chọn tài khoản làm việc hợp lệ.",
        )

    with get_conn(db_path) as conn:
        row = conn.execute(
            """
            SELECT email, full_name, position, role, department_id, private_repo_access, active
            FROM users_rbac
            WHERE lower(email) = ?
            """,
            (raw_email,),
        ).fetchone()

    if not row or not row["active"]:
        raise HTTPException(
            status_code=403,
            detail=f"Tài khoản '{raw_email}' không tồn tại hoặc không có quyền truy cập tại {commune_name}.",
        )

    return ActorContext(
        email=row["email"],
        full_name=row["full_name"],
        position=row["position"],
        role=row["role"],
        department_id=row["department_id"],
        private_repo_access=bool(row["private_repo_access"]),
        tenant_slug=tenant_slug,
        db_path=db_path,
        commune_name=commune_name,
    )


def require_owner_actor(actor: ActorContext = Depends(get_actor)) -> ActorContext:
    if actor.role != "owner":
        raise HTTPException(
            status_code=403,
            detail="Chỉ tài khoản Chủ sở hữu hệ thống (owner) mới được phép truy cập chức năng quản trị này.",
        )
    return actor


def enforce_dept_scope(actor: ActorContext, target_dept_id: str) -> None:
    normalized = (target_dept_id or "").strip().upper()
    if actor.role != "owner" and actor.department_id != normalized:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Tài khoản cán bộ thuộc bộ phận {actor.department_id} không được phép "
                f"thao tác hoặc khai thác dữ liệu của bộ phận {normalized}."
            ),
        )
