import time
import uuid
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import app.models  # Register all models for metadata creation

from app.api.v1 import auth, admin, token, rbac, audit
from app.core.database import admin_engine, token_engine
from sqlalchemy import text
from app.models.base import Base
from app.core.config import settings
from app.services.audit_service import audit_log_batch_worker, audit_cleanup_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Quản lý vòng đời ứng dụng: startup và shutdown.
    Sinh schema, init workers, dọn dẹp tài nguyên.
    """
    # 1. Khởi tạo Admin Database tables
    async with admin_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Touch Token Database engine (bảng động sẽ tạo lúc runtime)
    async with token_engine.begin() as conn:
        pass

    # 3. Chạy Background Workers cho Audit Log
    # Gắn vào event loop chính để không bị cancel giữa chừng
    audit_worker_task = asyncio.create_task(audit_log_batch_worker())
    cleanup_worker_task = asyncio.create_task(audit_cleanup_worker())

    yield  # Ứng dụng đang chạy

    # 4. Khi app chuẩn bị tắt, cancel workers và commit nốt log
    audit_worker_task.cancel()
    cleanup_worker_task.cancel()
    try:
        await asyncio.gather(audit_worker_task, cleanup_worker_task)
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.APP_VERSION,
    description="Hệ thống Tokenization & De-tokenization tự động, phân quyền RBAC và Audit Log chuẩn Enterprise.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)


# ── Middleware ───────────────────────────────────────────────────────────────

# 1. CORS Middleware (Bảo vệ API khỏi origin không cấp phép)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=settings.ALLOWED_METHODS,
    allow_headers=settings.ALLOWED_HEADERS,
)


# 2. Request ID & Timing Middleware
@app.middleware("http")
async def add_request_id_and_timing(request: Request, call_next):
    """Thêm X-Request-ID và X-Process-Time vào response header."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    # Truyền request_id vào state để lấy ở bất kỳ đâu trong request
    request.state.request_id = request_id

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# 3. Global Exception Handler (Bắt lỗi Unhandled Error 500)
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Bắt và parse mọi unhandled exception thành JSON chuẩn."""
    # Trên production có thể ẩn chi tiết lỗi
    error_detail = str(exc) if settings.APP_ENV != "production" else "Internal Server Error"
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


# ── Routes ───────────────────────────────────────────────────────────────────

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth & Identity"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin (Systems & Domains)"])
app.include_router(token.router, prefix="/api/v1/tokens", tags=["Tokenization engine"])
app.include_router(rbac.router, prefix="/api/v1/rbac", tags=["RBAC Permissions"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit Traceability"])


# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
async def health_check():
    """Enterprise Health Check Endpoint."""
    import psutil
    
    # Kiểm tra kêt nối DB (optional hard ping)
    db_status = "ok"
    try:
        async with admin_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return {
        "status": "online" if db_status == "ok" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": db_status,
        "memory_usage_mb": int(psutil.Process().memory_info().rss / 1024 / 1024),
    }


# Dành cho môi trường dev chạy trực tiếp từ main.py
if __name__ == "__main__":
    from granian import Granian
    server = Granian(
        target="app.main:app",
        address="0.0.0.0",
        port=8000,
        interface="asgi",
        reload=True
    )
    server.serve()
