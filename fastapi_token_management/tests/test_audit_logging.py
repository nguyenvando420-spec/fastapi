import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from sqlalchemy import select, text
from app.models.audit import AuditLog
from app.models.admin import System, Domain
from app.services.audit_service import get_audit_log_queue, flush_audit_log_queue
import asyncio
import uuid
import pytest_asyncio

@pytest.mark.asyncio
async def test_audit_logging_tokenize(override_get_db, db_session, token_db_session, auth_token):
    """Xác minh log được ghi sau khi gọi Tokenize thành công"""
    # 1. Setup Data
    system = System(name="audit_sys", description="audit test")
    db_session.add(system)
    await db_session.flush()
    
    domain = Domain(name="audit_dom", system_id=system.id, version="v1.2")
    db_session.add(domain)
    await db_session.flush()
    
    # Tạo schema và table vật lý TRÊN TOKEN DATABASE
    from sqlalchemy import text
    await token_db_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system.name}"'))
    table_ddl = f'CREATE TABLE IF NOT EXISTS "{system.name}"."{domain.name}" (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), token TEXT UNIQUE, encrypt_dek_data TEXT, kek TEXT, created_at TIMESTAMP, updated_at TIMESTAMP)'
    await token_db_session.execute(text(table_ddl))
    await token_db_session.commit()

    headers = {"Authorization": f"Bearer {auth_token}"}
    payload = {
        "system_name": system.name,
        "domain_name": domain.name,
        "data": ["data1", "data2"]
    }
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.post("/api/v1/tokens/tokenize", json=payload, headers=headers)
        assert resp.status_code == 201
        
        # 2. Thủ công Flush log trong queue vào DB để kiểm tra (Fast & Stable)
        await flush_audit_log_queue(db_session)
        
        # 3. Kiểm tra Log trong Database
        # Cần tạo session mới hoặc đảm bảo commit cũ đã xong. db_session của test đang sync.
        stmt = select(AuditLog).where(
            AuditLog.request_type == "tokenize",
            AuditLog.system == system.name,
            AuditLog.domain == domain.name
        ).order_by(AuditLog.id.desc())
        
        result = await db_session.execute(stmt)
        log = result.scalars().first()
        
        assert log is not None
        assert log.auth_status == "allowed"
        assert log.status == "success"
        assert log.total_token == 2
        assert log.duration > 0
        assert log.version == "v1.2"

@pytest.mark.asyncio
async def test_audit_logging_denied(override_get_db, db_session, auth_token):
    """Xác minh log được ghi khi bị từ chối truy cập (403)"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Tạo User mới (No roles)
        username = f"no_privilege_{uuid.uuid4().hex[:6]}"
        await ac.post("/api/v1/rbac/users", json={
            "username": username,
            "email": f"{username}@test.com",
            "password": "password123"
        }, headers=headers)
        
        # Login lấy token
        resp_login = await ac.post("/api/v1/auth/login", data={"username": username, "password": "password123"})
        new_token = resp_login.json()["access_token"]
        new_headers = {"Authorization": f"Bearer {new_token}"}
        
        # 2. Thử truy cập admin API (Sẽ bị 403)
        # Endpoint: POST /api/v1/admin/systems require 'admin:systems' 'create'
        resp = await ac.post("/api/v1/admin/systems", json={"name": "hacker_sys", "description": "no"}, headers=new_headers)
        assert resp.status_code == 403
        
        # Thủ công Flush log
        await flush_audit_log_queue(db_session)
        
        # 3. Kiểm tra Log 'denied'
        stmt = select(AuditLog).where(
            AuditLog.auth_status == "denied",
            AuditLog.user == username
        ).order_by(AuditLog.id.desc())
        
        result = await db_session.execute(stmt)
        log = result.scalars().first()
        
        assert log is not None
        assert log.status == "fail"
        assert log.request_type == "permission"
        assert log.system == "admin" # Từ resource 'admin:systems'

@pytest.mark.asyncio
async def test_audit_retrieval_api(override_get_db, db_session, auth_token):
    """Xác minh API lấy danh sách log có bảo vệ bởi permission"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Gọi API lấy log (Admin có quyền super '*' nên sẽ OK)
        resp = await ac.get("/api/v1/audit/", headers=headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        
        # 2. Thử filter
        resp_filter = await ac.get("/api/v1/audit/?request_type=tokenize", headers=headers)
        assert resp_filter.status_code == 200
