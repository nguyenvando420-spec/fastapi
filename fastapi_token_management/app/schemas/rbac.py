from pydantic import BaseModel, EmailStr, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

# --- Group Schemas ---
class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None

class GroupResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
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

class PermissionResponse(BaseModel):
    id: UUID
    resource: str
    action: str
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
