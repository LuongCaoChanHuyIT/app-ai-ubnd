from datetime import datetime, timezone
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Bộ Trợ lý AI UBND Xã, Phường — Backend API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "ubnd-ai-backend",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/hello")
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
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

