from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID


class AuditLogResponse(BaseModel):
    """Response đầy đủ cho một bản ghi Audit Log."""
    id: UUID
    request_type: str
    request_id: Optional[str]      # Correlation ID
    system: Optional[str]
    domain: Optional[str]
    user: Optional[str]
    version: Optional[str]
    ip_address: Optional[str]      # IP của client
    http_method: Optional[str]
    path: Optional[str]
    request_time: datetime
    duration: float
    total_token: int
    auth_status: str
    status: str
    detail: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    """Response phân trang cho danh sách Audit Log."""
    total: int
    limit: int
    offset: int
    items: List[AuditLogResponse]


class AuditRetentionUpdate(BaseModel):
    """Cập nhật số ngày lưu trữ log."""
    retention_days: int


class AuditStatsByType(BaseModel):
    """Thống kê log theo loại request."""
    request_type: str
    total: int
    success: int
    fail: int
    denied: int


class AuditStatsResponse(BaseModel):
    """Dashboard thống kê Audit Log."""
    total_requests: int
    total_success: int
    total_fail: int
    total_denied: int
    by_type: List[AuditStatsByType]
    top_users: List[Dict[str, Any]]   # [{"user": "alice", "count": 120}]
