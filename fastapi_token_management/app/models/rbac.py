from typing import Optional
from sqlalchemy import String, ForeignKey, Table, Column, Boolean
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

    users: Mapped[list["User"]] = relationship("User", secondary=group_user, back_populates="groups")
    roles: Mapped[list["Role"]] = relationship("Role", secondary=group_role, back_populates="groups")


class Permission(BaseModel):
    __tablename__ = "permissions"
    
    # Chuỗi đại diện resource theo cú pháp 'system_name:domain_name' hoặc '*' (tất cả)
    resource: Mapped[str] = mapped_column(String(255), index=True) 
    
    # Hành động được phép thao tác: 'read', 'write', 'create', 'delete', hoặc '*'
    action: Mapped[str] = mapped_column(String(100))

    roles: Mapped[list["Role"]] = relationship("Role", secondary=role_permission, back_populates="permissions")
