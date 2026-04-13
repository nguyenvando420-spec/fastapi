from typing import Optional
from sqlalchemy import String, ForeignKey, Boolean, UniqueConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel


class System(BaseModel):
    """
    Bảng quản lý danh sách các System.
    Mỗi System đại diện cho một Schema riêng biệt trong PostgreSQL.
    """
    __tablename__ = "systems"

    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Soft delete — không xóa vật lý, chỉ đánh dấu is_active=False
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    domains: Mapped[list["Domain"]] = relationship(
        "Domain", back_populates="system", cascade="all, delete-orphan"
    )


# ── Domain Version Status ────────────────────────────────────────────────────
# Tham khảo HashiCorp Vault Key Versioning & AWS KMS Key Rotation:
#   - active:     Version hiện hành — dùng cho tokenize mới
#   - rotated:    Version cũ — vẫn cho phép detokenize nhưng không tokenize mới
#   - deprecated: Version bị loại bỏ — không dùng cho bất kỳ thao tác nào

DOMAIN_STATUS_ACTIVE = "active"
DOMAIN_STATUS_ROTATED = "rotated"
DOMAIN_STATUS_DEPRECATED = "deprecated"
VALID_DOMAIN_STATUSES = {DOMAIN_STATUS_ACTIVE, DOMAIN_STATUS_ROTATED, DOMAIN_STATUS_DEPRECATED}


class Domain(BaseModel):
    """
    Bảng quản lý danh sách các Domain thuộc về System.
    Mỗi Domain + Version đại diện cho một Table trong schema của System.

    Version Management (tham khảo HashiCorp Vault, AWS KMS):
      - Khi tạo domain lần đầu: version_number=1, status='active'
      - Khi rotate: version_number tự tăng, version cũ chuyển sang 'rotated'
      - Version 'deprecated' sẽ bị chặn ở mọi thao tác tokenize/detokenize
    """
    __tablename__ = "domains"

    name: Mapped[str] = mapped_column(String(100), index=True)

    # Version number tự tăng theo domain — bắt đầu từ 1
    version_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    # String representation: "v1", "v2", ... (tự tính từ version_number)
    version: Mapped[str] = mapped_column(String(50), default="v1")

    # Lifecycle status: active → rotated → deprecated
    status: Mapped[str] = mapped_column(
        String(20), default=DOMAIN_STATUS_ACTIVE, server_default=DOMAIN_STATUS_ACTIVE, index=True
    )

    system_id: Mapped[str] = mapped_column(
        ForeignKey("systems.id", ondelete="CASCADE"), index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Soft delete — các token vẫn được giữ nguyên trong DB con
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    system: Mapped["System"] = relationship("System", back_populates="domains")

    # Đảm bảo mỗi (domain, version_number) là duy nhất trong cùng system
    __table_args__ = (
        UniqueConstraint("name", "version_number", "system_id", name="uq_domain_name_version_system"),
    )
