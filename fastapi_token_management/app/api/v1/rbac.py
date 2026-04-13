from fastapi import APIRouter, Depends, Query, status
from typing import Optional, List
from app.api.dependencies import SessionDep, require_permissions, get_current_active_user
from app.schemas.rbac import (
    UserCreate, UserResponse, UserDetailResponse,
    RoleCreate, RoleResponse,
    PermissionCreate, PermissionResponse,
    GroupCreate, GroupResponse,
    UserRoleAssign, RolePermissionAssign,
    UserGroupAssign, GroupRoleAssign,
    PaginatedUsersResponse
)
from app.services.rbac_service import (
    create_user, create_role, create_permission, create_group,
    assign_role_to_user, assign_perm_to_role,
    assign_user_to_group, assign_role_to_group,
    list_users, get_user_detail, get_user_effective_permissions,
    list_roles, list_groups, list_permissions,
    remove_role_from_user, remove_user_from_group,
    deactivate_user, remove_perm_from_role
)
from app.models.rbac import User
from uuid import UUID

router = APIRouter()

# ═══════════════════════════════════════════════
# User Management
# ═══════════════════════════════════════════════

@router.get("/users/me", response_model=UserDetailResponse)
async def get_my_profile(
    session: SessionDep,
    current_user: User = Depends(get_current_active_user)
):
    """Xem thông tin profile và quyền của user hiện tại"""
    user = await get_user_detail(session, current_user.id)
    effective_perms = await get_user_effective_permissions(session, current_user.id)
    return UserDetailResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        auth_source=user.auth_source,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        last_login=user.last_login,
        created_at=user.created_at,
        roles=[r for r in user.roles],
        groups=[g for g in user.groups],
        effective_permissions=effective_perms
    )

@router.get("/users", response_model=PaginatedUsersResponse)
async def get_users(
    session: SessionDep,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    auth_source: Optional[str] = Query(None, description="Filter: 'local' hoặc 'ldap'"),
    _ = Depends(require_permissions("admin:users", "read"))
):
    """Liệt kê danh sách users (có phân trang, filter theo auth_source)"""
    users, total = await list_users(session, skip=skip, limit=limit, auth_source=auth_source)
    return PaginatedUsersResponse(total=total, skip=skip, limit=limit, items=users)

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_in: UserCreate, 
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "create"))
):
    """Tạo User mới (Yêu cầu quyền admin:users:create)"""
    return await create_user(session, user_in)

@router.get("/users/{user_id}", response_model=UserDetailResponse)
async def get_user_info(
    user_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "read"))
):
    """Xem chi tiết User + roles + groups + effective permissions"""
    user = await get_user_detail(session, user_id)
    effective_perms = await get_user_effective_permissions(session, user_id)
    return UserDetailResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        auth_source=user.auth_source,
        display_name=user.display_name,
        is_superuser=user.is_superuser,
        last_login=user.last_login,
        created_at=user.created_at,
        roles=[r for r in user.roles],
        groups=[g for g in user.groups],
        effective_permissions=effective_perms
    )

@router.post("/users/{user_id}/roles", status_code=status.HTTP_200_OK)
async def assign_user_role(
    user_id: UUID,
    assign_in: UserRoleAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "write"))
):
    """Gán Role cho User (Yêu cầu quyền admin:users:write)"""
    return await assign_role_to_user(session, user_id, assign_in.role_id)

@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_200_OK)
async def unassign_user_role(
    user_id: UUID,
    role_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "write"))
):
    """Gỡ Role khỏi User (Yêu cầu quyền admin:users:write)"""
    return await remove_role_from_user(session, user_id, role_id)

@router.patch("/users/{user_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_user_account(
    user_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "write"))
):
    """Vô hiệu hoá tài khoản User (Yêu cầu quyền admin:users:write)"""
    return await deactivate_user(session, user_id)

# ═══════════════════════════════════════════════
# Group Management
# ═══════════════════════════════════════════════

@router.get("/groups", response_model=List[GroupResponse])
async def get_groups(
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "read"))
):
    """Liệt kê tất cả Groups"""
    return await list_groups(session)

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

@router.delete("/groups/{group_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_rbac_group(
    group_id: UUID,
    user_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "write"))
):
    """Gỡ User khỏi Group (Yêu cầu quyền admin:groups:write)"""
    return await remove_user_from_group(session, user_id, group_id)

@router.post("/groups/{group_id}/roles", status_code=status.HTTP_200_OK)
async def assign_group_role(
    group_id: UUID,
    assign_in: GroupRoleAssign,
    session: SessionDep,
    _ = Depends(require_permissions("admin:groups", "write"))
):
    """Gán Role cho Group (Yêu cầu quyền admin:groups:write)"""
    return await assign_role_to_group(session, group_id, assign_in.role_id)

# ═══════════════════════════════════════════════
# Role Management
# ═══════════════════════════════════════════════

@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    session: SessionDep,
    _ = Depends(require_permissions("admin:roles", "read"))
):
    """Liệt kê tất cả Roles"""
    return await list_roles(session)

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

@router.delete("/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_200_OK)
async def unassign_role_permission(
    role_id: UUID,
    permission_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:roles", "write"))
):
    """Gỡ Permission khỏi Role (Yêu cầu quyền admin:roles:write)"""
    return await remove_perm_from_role(session, role_id, permission_id)

# ═══════════════════════════════════════════════
# Permission Management
# ═══════════════════════════════════════════════

@router.get("/permissions", response_model=List[PermissionResponse])
async def get_permissions(
    session: SessionDep,
    _ = Depends(require_permissions("admin:permissions", "read"))
):
    """Liệt kê tất cả Permissions"""
    return await list_permissions(session)

@router.post("/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
async def add_permission(
    perm_in: PermissionCreate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:permissions", "create"))
):
    """Tạo Permission mới (Yêu cầu quyền admin:permissions:create)"""
    return await create_permission(session, perm_in)
