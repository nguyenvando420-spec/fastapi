from fastapi import FastAPI
from contextlib import asynccontextmanager
import asyncio
from app.api.v1 import auth, admin, token, rbac, audit
from app.core.database import admin_engine, token_engine
from app.models.base import Base
from app.services.audit_service import audit_log_batch_worker, audit_cleanup_worker
import app.models  # Import to register all models for metadata creation

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Khởi tạo table trong Metadata cho cả 2 Database (Development)
    # Admin DB: Chứa metadata, rbac, audit...
    async with admin_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Token DB: Dự kiến sẽ tạo schema/table động qua API, 
    # nhưng ta có thể đảm bảo engine này sẵn sàng.
    # (Base.metadata.create_all ở đây sẽ không tạo gì nếu các model động chưa được định nghĩa tĩnh)
    async with token_engine.begin() as conn:
        pass
    
    # 2. Khởi động Background Workers cho Audit Log (Dùng admin loop)
    audit_worker_task = asyncio.create_task(audit_log_batch_worker())
    cleanup_worker_task = asyncio.create_task(audit_cleanup_worker())
    
    yield
    
    # 3. Cleanup khi server tắt
    audit_worker_task.cancel()
    cleanup_worker_task.cancel()
    try:
        await asyncio.gather(audit_worker_task, cleanup_worker_task)
    except asyncio.CancelledError:
        pass

app = FastAPI(
    title="FastAPI Token Management Platform API",
    lifespan=lifespan
)

# Setup CORS, Middleware errors...

# Import Routes API Modules
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth: Identity Auth & Register"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin: System (Schema) & Domain (Table) Setup"])
app.include_router(token.router, prefix="/api/v1/tokens", tags=["Tokenization: Bulk Tokenize & De-tokenize"])
app.include_router(rbac.router, prefix="/api/v1/rbac", tags=["RBAC: Role Based Access Control"])
app.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit: System Traceability & Request Logs"])

@app.get("/")
def health_check():
    return {
        "status": "online", 
        "architecture": "Event-driven Fastapi + PostgreSQL Asyncpg + Polars Engine"
    }

# Lệnh Run cục bộ dành cho dev debugging
if __name__ == "__main__":
    from granian import Granian
    import os
    
    server = Granian(
        target="app.main:app", 
        address="0.0.0.0", 
        port=8000, 
        interface="asgi",
        reload=True
    )
    server.serve()
