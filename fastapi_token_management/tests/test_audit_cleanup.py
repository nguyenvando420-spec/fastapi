import pytest
import uuid
import asyncio
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select, text
from app.main import app
from app.models.audit import AuditLog
from app.models.setting import SystemSetting
from app.services.audit_service import cleanup_audit_logs, get_audit_log_queue, flush_audit_log_queue

@pytest.mark.asyncio
async def test_audit_log_pruning_service(db_session):
    """Xác minh service xóa đúng log cũ"""
    # 1. Tạo log mới (1 ngày trước)
    log_new = AuditLog(
        request_type="test",
        request_time=datetime.now(timezone.utc) - timedelta(days=1),
        duration=0.1,
        status="success",
        auth_status="allowed"
    )
    # 2. Tạo log cũ (100 ngày trước)
    log_old = AuditLog(
        request_type="test",
        request_time=datetime.now(timezone.utc) - timedelta(days=100),
        duration=0.1,
        status="success",
        auth_status="allowed"
    )
    db_session.add_all([log_new, log_old])
    await db_session.commit()

    # 3. Chạy cleanup với mốc 90 ngày
    deleted = await cleanup_audit_logs(db_session, days=90)
    assert deleted >= 1

    # 4. Kiểm tra lại DB
    result = await db_session.execute(select(AuditLog).where(AuditLog.request_type == "test"))
    remaining_logs = result.scalars().all()
    
    # Chỉ còn log_new
    assert len(remaining_logs) >= 1
    for log in remaining_logs:
        assert log.request_time > (datetime.now(timezone.utc) - timedelta(days=90))

@pytest.mark.asyncio
async def test_audit_retention_api(db_session, auth_token):
    """Xác minh API cấu hình retention hoạt động"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Lấy giá trị mặc định
        resp = await ac.get("/api/v1/audit/retention", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["retention_days"] == 90

        # 2. Cập nhật giá trị mới (Admin only: write)
        resp_update = await ac.post("/api/v1/audit/retention", json={"retention_days": 30}, headers=headers)
        assert resp_update.status_code == 200

        # 3. Kiểm tra lại giá trị đã lưu
        resp_check = await ac.get("/api/v1/audit/retention", headers=headers)
        assert resp_check.json()["retention_days"] == 30

@pytest.mark.asyncio
async def test_manual_cleanup_api(db_session, auth_token):
    """Xác minh API kích hoạt dọn dẹp thủ công"""
    headers = {"Authorization": f"Bearer {auth_token}"}
    
    # Tạo 1 log cực cũ
    log_very_old = AuditLog(
        request_type="manual_test",
        request_time=datetime.now(timezone.utc) - timedelta(days=500),
        duration=0.5,
        status="success",
        auth_status="allowed"
    )
    db_session.add(log_very_old)
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Gọi API cleanup thủ công
        resp = await ac.post("/api/v1/audit/cleanup?days=365", headers=headers)
        assert resp.status_code == 200
        assert "Deleted" in resp.json()["message"]
        
        # Verify log đã mất
        result = await db_session.execute(select(AuditLog).where(AuditLog.request_type == "manual_test"))
        assert result.scalars().first() is None
