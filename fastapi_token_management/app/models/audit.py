from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from datetime import datetime, timezone


class AuditLog(BaseModel):
    """
    Bảng ghi log toàn diện cho mọi request quan trọng.
    Các trường được bổ sung chuẩn enterprise:
      - request_id: Correlation ID để trace request qua nhiều service
      - ip_address: IP của client (hỗ trợ X-Forwarded-For)
      - http_method: GET/POST/DELETE...
      - path: Đường dẫn API được gọi
    """
    __tablename__ = "audit_logs"

    # ── Metadata của request ──────────────────────────────────────────────
    # Kiểu hành động: tokenize | detokenize | permission | auth | admin
    request_type: Mapped[str] = mapped_column(String(50), index=True)
    # Correlation ID theo dõi request xuyên suốt (UUID v4)
    request_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    # Hệ thống và domain được thao tác
    system: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    # Người dùng thực hiện
    user: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    # Version của domain được sử dụng
    version: Mapped[Optional[str]] = mapped_column(String(50))
    # IP address của client (IPv4/IPv6)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    # HTTP method và path
    http_method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # ── Metrics hiệu năng ────────────────────────────────────────────────
    request_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    duration: Mapped[float] = mapped_column(Float, default=0.0)    # Thời gian xử lý (giây)
    total_token: Mapped[int] = mapped_column(Integer, default=0)  # Số lượng token được xử lý

    # ── Kết quả ─────────────────────────────────────────────────────────
    # auth_status: allowed | denied
    auth_status: Mapped[str] = mapped_column(String(20))
    # status: success | fail
    status: Mapped[str] = mapped_column(String(20))
    # Chi tiết lỗi / lý do từ chối
    detail: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
