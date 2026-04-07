from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from app.api.dependencies import SessionDep, require_permissions
from app.schemas.audit import AuditLogResponse, AuditRetentionUpdate
from app.services.audit_service import get_audit_logs, cleanup_audit_logs
from app.services.setting_service import get_setting, set_setting

router = APIRouter()

@router.get("/", response_model=List[AuditLogResponse])
async def list_audit_logs(
    session: SessionDep,
    request_type: Optional[str] = Query(None, description="Filter by type (tokenize, detokenize, etc)"),
    system: Optional[str] = Query(None, description="Filter by system name"),
    domain: Optional[str] = Query(None, description="Filter by domain name"),
    user: Optional[str] = Query(None, description="Filter by username"),
    status: Optional[str] = Query(None, description="Filter by status (success, fail)"),
    auth_status: Optional[str] = Query(None, description="Filter by auth status (allowed, denied)"),
    limit: int = Query(100, le=1000),
    offset: int = 0,
    _ = Depends(require_permissions("admin:audit", "read"))
):
    """
    Lấy danh sách Audit Log (Yêu cầu quyền admin:audit:read).
    Hệ thống khác có thể call API này để tích hợp giám sát hoặc hậu kiểm.
    """
    return await get_audit_logs(
        session=session,
        request_type=request_type,
        system=system,
        domain=domain,
        user=user,
        status=status,
        auth_status=auth_status,
        limit=limit,
        offset=offset
    )

@router.get("/retention", response_model=AuditRetentionUpdate)
async def get_audit_retention(session: SessionDep, _ = Depends(require_permissions("admin:audit", "read"))):
    """
    Lấy số ngày lưu trữ log hiện tại (Admin only).
    """
    days = await get_setting(session, "audit_retention_days", "90")
    return {"retention_days": int(days)}

@router.post("/retention")
async def update_audit_retention(
    session: SessionDep, 
    data: AuditRetentionUpdate,
    _ = Depends(require_permissions("admin:audit", "write"))
):
    """
    Cập nhật số ngày lưu trữ log (Admin only).
    Nếu giảm số ngày, hệ thống sẽ tự động quét xóa ở chu kỳ tiếp theo.
    """
    await set_setting(session, "audit_retention_days", str(data.retention_days), "Số ngày lưu trữ Audit Log")
    return {"message": f"Audit retention updated to {data.retention_days} days"}

@router.post("/cleanup")
async def manual_cleanup(
    session: SessionDep,
    days: Optional[int] = Query(None, description="Xóa log cũ hơn X ngày. Nếu không truyền, dùng cấu hình hệ thống."),
    _ = Depends(require_permissions("admin:audit", "write"))
):
    """
    Kích hoạt dọn dẹp log thủ công (Admin only).
    """
    if days is None:
        val = await get_setting(session, "audit_retention_days", "90")
        days = int(val)
    
    deleted_count = await cleanup_audit_logs(session, days)
    return {"message": f"Manual cleanup completed. Deleted {deleted_count} logs older than {days} days."}
