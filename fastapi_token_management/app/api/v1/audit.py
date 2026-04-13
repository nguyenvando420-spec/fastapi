from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from app.api.dependencies import SessionDep, require_permissions
from app.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    AuditRetentionUpdate,
    AuditStatsResponse,
)
from app.services.audit_service import get_audit_logs, cleanup_audit_logs, get_audit_stats
from app.services.setting_service import get_setting, set_setting

router = APIRouter()


@router.get("/", response_model=AuditLogListResponse)
async def list_audit_logs(
    session: SessionDep,
    request_type: Optional[str] = Query(None, description="Filter theo loại: tokenize, detokenize, permission, auth"),
    system: Optional[str] = Query(None, description="Filter theo tên System"),
    domain: Optional[str] = Query(None, description="Filter theo tên Domain"),
    user: Optional[str] = Query(None, description="Filter theo username"),
    status: Optional[str] = Query(None, description="Filter theo trạng thái: success | fail"),
    auth_status: Optional[str] = Query(None, description="Filter theo auth: allowed | denied"),
    from_date: Optional[datetime] = Query(None, description="Từ ngày (ISO 8601), VD: 2024-01-01T00:00:00"),
    to_date: Optional[datetime] = Query(None, description="Đến ngày (ISO 8601), VD: 2024-12-31T23:59:59"),
    limit: int = Query(100, le=1000, description="Số bản ghi tối đa mỗi trang"),
    offset: int = Query(0, ge=0, description="Bỏ qua N bản ghi đầu (phân trang)"),
    _ = Depends(require_permissions("admin:audit", "read")),
):
    """
    Lấy danh sách Audit Log với phân trang chuẩn.
    Trả về total count để client có thể render pagination UI.
    """
    total, items = await get_audit_logs(
        session=session,
        request_type=request_type,
        system=system,
        domain=domain,
        user=user,
        status=status,
        auth_status=auth_status,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(total=total, limit=limit, offset=offset, items=items)


@router.get("/stats", response_model=AuditStatsResponse)
async def audit_stats(
    session: SessionDep,
    _ = Depends(require_permissions("admin:audit", "read")),
):
    """
    Dashboard thống kê Audit Log:
    - Tổng requests, success/fail/denied
    - Phân tích theo loại request
    - Top 10 user active nhất
    """
    stats = await get_audit_stats(session)
    return AuditStatsResponse(**stats)


@router.get("/retention", response_model=AuditRetentionUpdate)
async def get_audit_retention(
    session: SessionDep,
    _ = Depends(require_permissions("admin:audit", "read")),
):
    """Lấy cấu hình số ngày lưu trữ log hiện tại."""
    days = await get_setting(session, "audit_retention_days", "90")
    return {"retention_days": int(days)}


@router.post("/retention")
async def update_audit_retention(
    session: SessionDep,
    data: AuditRetentionUpdate,
    _ = Depends(require_permissions("admin:audit", "write")),
):
    """
    Cập nhật số ngày lưu trữ log.
    Worker cleanup tự động sẽ áp dụng ngưỡng mới ở chu kỳ tiếp theo.
    """
    await set_setting(
        session, "audit_retention_days", str(data.retention_days),
        "Số ngày lưu trữ Audit Log"
    )
    return {"message": f"Audit retention updated to {data.retention_days} days."}


@router.post("/cleanup")
async def manual_cleanup(
    session: SessionDep,
    days: Optional[int] = Query(None, description="Xóa log cũ hơn X ngày. Mặc định: theo cấu hình hệ thống."),
    _ = Depends(require_permissions("admin:audit", "write")),
):
    """Kích hoạt dọn dẹp log thủ công (Admin only)."""
    if days is None:
        val = await get_setting(session, "audit_retention_days", "90")
        days = int(val)

    deleted_count = await cleanup_audit_logs(session, days)
    return {"message": f"Manual cleanup completed. Deleted {deleted_count} logs older than {days} days."}
