from typing import Optional
from datetime import datetime
from sqlalchemy import String, ForeignKey, Table, Column, Boolean, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel, Base

# --- Bảng N-N cho cấu trúc RBAC ---

user_role = Table(
    "user_role", Base.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

role_permission = Table(
    "role_permission", Base.metadata,
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", UUID(as_uuid=True), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

group_user = Table(
    "group_user", Base.metadata,
    Column("group_id", UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

group_role = Table(
    "group_role", Base.metadata,
    Column("group_id", UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    extend_existing=True
)

# --- Các Bảng Thực Thể ---

class User(BaseModel):
    __tablename__ = "users"
    
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Các field mở rộng cho LDAP integration ---
    # Nguồn xác thực: "local" (DB nội bộ) hoặc "ldap" (LDAP/Active Directory)
    auth_source: Mapped[str] = mapped_column(String(20), default="local", server_default="local")
    # Distinguished Name từ LDAP server (chỉ user LDAP mới có)
    ldap_dn: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Tên hiển thị (mapped từ LDAP CN hoặc do admin đặt)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Superuser bypass: bỏ qua mọi permission check (tham khảo Django is_superuser)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # Thời điểm đăng nhập gần nhất
    last_login: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    roles: Mapped[list["Role"]] = relationship("Role", secondary=user_role, back_populates="users")
    groups: Mapped[list["Group"]] = relationship("Group", secondary=group_user, back_populates="users")


class Role(BaseModel):
    __tablename__ = "roles"
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    users: Mapped[list["User"]] = relationship("User", secondary=user_role, back_populates="roles")
    groups: Mapped[list["Group"]] = relationship("Group", secondary=group_role, back_populates="roles")
    permissions: Mapped[list["Permission"]] = relationship("Permission", secondary=role_permission, back_populates="roles")


class Group(BaseModel):
    __tablename__ = "groups"
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Các field mở rộng cho LDAP group sync ---
    # Distinguished Name của nhóm LDAP tương ứng
    ldap_dn: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Nhóm này được sync từ LDAP? (True = không nên xoá thủ công, sẽ bị tạo lại khi sync)
    is_ldap_synced: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    users: Mapped[list["User"]] = relationship("User", secondary=group_user, back_populates="groups")
    roles: Mapped[list["Role"]] = relationship("Role", secondary=group_role, back_populates="groups")


class Permission(BaseModel):
    __tablename__ = "permissions"
    
    # Chuỗi đại diện resource theo cú pháp 'system_name:domain_name' hoặc '*' (tất cả)
    resource: Mapped[str] = mapped_column(String(255), index=True) 
    
    # Hành động được phép thao tác: 'read', 'write', 'create', 'delete', hoặc '*'
    action: Mapped[str] = mapped_column(String(100))

    # Mô tả permission cho quản trị viên dễ hiểu
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    roles: Mapped[list["Role"]] = relationship("Role", secondary=role_permission, back_populates="permissions")

    # Đảm bảo không tạo duplicate permission (resource + action duy nhất)
    __table_args__ = (
        UniqueConstraint('resource', 'action', name='uq_permission_resource_action'),
    )


class RevokedToken(BaseModel):
    """
    Blacklist các JWT token đã bị thu hồi (logout / force expire).
    Kiểm tra table này trong get_current_user để block token đã logout.
    Tham khảo: OAuth2 Token Introspection RFC 7662.
    """
    __tablename__ = "revoked_tokens"

    # jti: JWT ID claim — định danh duy nhất của token
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    # Username chủ sở hữu token
    username: Mapped[str] = mapped_column(String(100), index=True)
    # Thời điểm token hết hạn (để có thể dọn dẹp records cũ)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
