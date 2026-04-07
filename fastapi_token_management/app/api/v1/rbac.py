from fastapi import APIRouter, Depends, status
from app.api.dependencies import SessionDep, require_permissions
from app.schemas.rbac import (
    UserCreate, UserResponse,
    RoleCreate, RoleResponse,
    PermissionCreate, PermissionResponse,
    GroupCreate, GroupResponse,
    UserRoleAssign, RolePermissionAssign,
    UserGroupAssign, GroupRoleAssign
)
from app.services.rbac_service import (
    create_user, create_role, create_permission, create_group,
    assign_role_to_user, assign_perm_to_role,
    assign_user_to_group, assign_role_to_group
)
from uuid import UUID

router = APIRouter()

# --- User Management ---
@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, 
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "create"))
):
    """Tạo User mới (Yêu cầu quyền admin:users:create)"""
    return await create_user(session, user_in)

@router.post("/users/{user_id}/roles", status_code=status.HTTP_200_OK)
async def assign_user_role(
    user_id: UUID,
    assign_in: UserRoleAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "write"))
):
    """Gán Role cho User (Yêu cầu quyền admin:users:write)"""
    return await assign_role_to_user(session, user_id, assign_in.role_id)

# --- Group Management ---
@router.post("/groups", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def add_group(
    group_in: GroupCreate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "create"))
):
    """Tạo Group mới (Yêu cầu quyền admin:groups:create)"""
    return await create_group(session, group_in)

@router.post("/groups/{group_id}/users", status_code=status.HTTP_200_OK)
async def add_user_to_rbac_group(
    group_id: UUID,
    assign_in: UserGroupAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "write"))
):
    """Gán User vào Group (Yêu cầu quyền admin:groups:write)"""
    return await assign_user_to_group(session, assign_in.user_id, group_id)

@router.post("/groups/{group_id}/roles", status_code=status.HTTP_200_OK)
async def assign_group_role(
    group_id: UUID,
    assign_in: GroupRoleAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "write"))
):
    """Gán Role cho Group (Yêu cầu quyền admin:groups:write)"""
    return await assign_role_to_group(session, group_id, assign_in.role_id)

# --- Role Management ---
@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def add_role(
    role_in: RoleCreate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:roles", "create"))
):
    """Tạo Role mới (Yêu cầu quyền admin:roles:create)"""
    return await create_role(session, role_in)

@router.post("/roles/{role_id}/permissions", status_code=status.HTTP_200_OK)
async def assign_role_permission(
    role_id: UUID,
    assign_in: RolePermissionAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:roles", "write"))
):
    """Gán Permission cho Role (Yêu cầu quyền admin:roles:write)"""
    return await assign_perm_to_role(session, role_id, assign_in.permission_id)

# --- Permission Management ---
@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def add_permission(
    perm_in: PermissionCreate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:permissions", "create"))
):
    """Tạo Permission mới (Yêu cầu quyền admin:permissions:create)"""
    return await create_permission(session, perm_in)
