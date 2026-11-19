from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from typing import AsyncIterator

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from backend.db import init_db
from backend.routers.docs_and_files import router as docs_and_files_router
from backend.routers.ops_and_admin import router as ops_and_admin_router
from backend.routers.workspace import router as workspace_router

DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def _resolve_allowed_origins() -> list[str]:
    raw = os.environ.get("UBND_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(DEFAULT_DEV_ORIGINS)
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed or list(DEFAULT_DEV_ORIGINS)


def create_app() -> FastAPI:
    is_prod = os.environ.get("UBND_ENV", "development").strip().lower() == "production"
    application = FastAPI(
        title="Bộ Trợ lý AI UBND Xã, Phường — Backend API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=_resolve_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(workspace_router)
    application.include_router(docs_and_files_router)
    application.include_router(ops_and_admin_router)

    @application.get("/api/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "ubnd-ai-backend",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @application.get("/api/hello")
    def say_hello(
        name: str | None = Query(default=None, description="Tên đơn vị hoặc cán bộ"),
    ) -> dict[str, str]:
        cleaned = name.strip() if name else ""
        message = (
            f"Xin chào {cleaned} từ Backend Bộ Trợ lý AI!"
            if cleaned
            else "Xin chào từ Backend Bộ Trợ lý AI UBND xã, phường!"
        )
        return {
            "message": message,
            "service": "ubnd-ai-backend",
            "version": "1.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return application


app = create_app()
