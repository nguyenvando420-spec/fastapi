from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional, List

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    auth_source: str
    display_name: Optional[str] = None
    is_superuser: bool = False
    last_login: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class UserDetailResponse(UserResponse):
    """Response chi tiết kèm danh sách roles, groups, và effective permissions"""
    roles: List["RoleResponse"] = []
    groups: List["GroupResponse"] = []
    effective_permissions: List["PermissionResponse"] = []
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    """Response khi login thành công — trả về cả access_token và refresh_token."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int           # Thời hạn access_token (giây)


class RefreshTokenRequest(BaseModel):
    """Request để lấy access_token mới từ refresh_token còn hạn."""
    refresh_token: str


class LogoutRequest(BaseModel):
    """
    Thu hồi toàn bộ session của user.
    Cần gửi access_token (lấy từ Authorization header) để blacklist.
    """
    all_sessions: bool = False   # True = revoke tất cả refresh token của user


class UserMe(BaseModel):
    """Profile của current user — endpoint GET /auth/me."""
    id: UUID
    username: str
    email: EmailStr
    display_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    auth_source: str
    last_login: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# --- Group Schemas ---
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_ldap_synced: bool = False
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Role Schemas ---
class RoleCreate(BaseModel):
    name: str
    description: Optional[str] = None

class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Permission Schemas ---
class PermissionCreate(BaseModel):
    resource: str
    action: str
    description: Optional[str] = None

class PermissionResponse(BaseModel):
    id: UUID
    resource: str
    action: str
    description: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# --- Assignment Schemas ---
class UserRoleAssign(BaseModel):
    role_id: UUID

class RolePermissionAssign(BaseModel):
    permission_id: UUID

class UserGroupAssign(BaseModel):
    user_id: UUID

class GroupRoleAssign(BaseModel):
    role_id: UUID

# --- Pagination ---
class PaginatedUsersResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[UserResponse]
