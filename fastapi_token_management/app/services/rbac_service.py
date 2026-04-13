from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.rbac import (
    User, Role, Permission, Group,
    user_role, role_permission, group_user, group_role
)
from app.schemas.rbac import (
    UserCreate, RoleCreate, PermissionCreate, GroupCreate,
    UserRoleAssign, RolePermissionAssign, UserGroupAssign, GroupRoleAssign
)
from app.core.security import get_password_hash
from uuid import UUID
from typing import Optional

# ═══════════════════════════════════════════════
# CREATE Operations
# ═══════════════════════════════════════════════

async def create_user(session: AsyncSession, user_in: UserCreate) -> User:
    """Tạo user trong DB: Kiểm tra trùng id/email và Hash mật khẩu"""
    stmt = select(User).where((User.username == user_in.username) | (User.email == user_in.email))
    result = await session.execute(stmt)
    
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tài khoản user hoặc email này đã tồn tại trong hệ thống.",
        )
    
    hashed_password = get_password_hash(user_in.password)
    
    db_user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password
    )
    
    session.add(db_user)
    await session.commit()
    await session.refresh(db_user)
    
    return db_user

async def create_role(session: AsyncSession, role_in: RoleCreate) -> Role:
    """Tạo Role mới"""
    stmt = select(Role).where(Role.name == role_in.name)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Role already exists")
    
    db_role = Role(name=role_in.name, description=role_in.description)
    session.add(db_role)
    await session.commit()
    await session.refresh(db_role)
    return db_role

async def create_permission(session: AsyncSession, perm_in: PermissionCreate) -> Permission:
    """Tạo Permission mới"""
    stmt = select(Permission).where(
        (Permission.resource == perm_in.resource) & (Permission.action == perm_in.action)
    )
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Permission already exists")
    
    db_perm = Permission(
        resource=perm_in.resource,
        action=perm_in.action,
        description=perm_in.description
    )
    session.add(db_perm)
    await session.commit()
    await session.refresh(db_perm)
    return db_perm

async def create_group(session: AsyncSession, group_in: GroupCreate) -> Group:
    """Tạo Group mới"""
    stmt = select(Group).where(Group.name == group_in.name)
    result = await session.execute(stmt)
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Group already exists")
    
    db_group = Group(name=group_in.name, description=group_in.description)
    session.add(db_group)
    await session.commit()
    await session.refresh(db_group)
    return db_group

# ═══════════════════════════════════════════════
# ASSIGN Operations
# ═══════════════════════════════════════════════

async def assign_role_to_user(session: AsyncSession, user_id: UUID, role_id: UUID):
    """Gán Role cho User"""
    user_stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    role_stmt = select(Role).where(Role.id == role_id)
    
    user_res = await session.execute(user_stmt)
    role_res = await session.execute(role_stmt)
    
    user = user_res.scalar_one_or_none()
    role = role_res.scalar_one_or_none()
    
    if not user or not role:
        raise HTTPException(status_code=404, detail="User or Role not found")
    
    if role in user.roles:
        raise HTTPException(status_code=400, detail=f"User '{user.username}' already has role '{role.name}'")
    
    try:
        user.roles.append(role)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign role: {str(e)}")
    
    return {"message": f"Role {role.name} assigned to user {user.username}"}

async def assign_perm_to_role(session: AsyncSession, role_id: UUID, perm_id: UUID):
    """Gán Permission cho Role"""
    role_stmt = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    perm_stmt = select(Permission).where(Permission.id == perm_id)
    
    role_res = await session.execute(role_stmt)
    perm_res = await session.execute(perm_stmt)
    
    role = role_res.scalar_one_or_none()
    perm = perm_res.scalar_one_or_none()
    
    if not role or not perm:
        raise HTTPException(status_code=404, detail="Role or Permission not found")
    
    if perm in role.permissions:
        raise HTTPException(status_code=400, detail=f"Role '{role.name}' already has this permission")
    
    try:
        role.permissions.append(perm)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign permission: {str(e)}")
    
    return {"message": f"Permission {perm.resource}:{perm.action} assigned to role {role.name}"}

async def assign_user_to_group(session: AsyncSession, user_id: UUID, group_id: UUID):
    """Gán User vào Group"""
    user_stmt = select(User).options(selectinload(User.groups)).where(User.id == user_id)
    group_stmt = select(Group).where(Group.id == group_id)
    
    user_res = await session.execute(user_stmt)
    group_res = await session.execute(group_stmt)
    
    user = user_res.scalar_one_or_none()
    group = group_res.scalar_one_or_none()
    
    if not user or not group:
        raise HTTPException(status_code=404, detail="User or Group not found")
    
    if group in user.groups:
        raise HTTPException(status_code=400, detail=f"User '{user.username}' already in group '{group.name}'")
    
    try:
        user.groups.append(group)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign group: {str(e)}")
    
    return {"message": f"User {user.username} added to group {group.name}"}

async def assign_role_to_group(session: AsyncSession, group_id: UUID, role_id: UUID):
    """Gán Role cho Group"""
    group_stmt = select(Group).options(selectinload(Group.roles)).where(Group.id == group_id)
    role_stmt = select(Role).where(Role.id == role_id)
    
    group_res = await session.execute(group_stmt)
    role_res = await session.execute(role_stmt)
    
    group = group_res.scalar_one_or_none()
    role = role_res.scalar_one_or_none()
    
    if not group or not role:
        raise HTTPException(status_code=404, detail="Group or Role not found")
    
    if role in group.roles:
        raise HTTPException(status_code=400, detail=f"Group '{group.name}' already has role '{role.name}'")
    
    try:
        group.roles.append(role)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign role to group: {str(e)}")
    
    return {"message": f"Role {role.name} assigned to group {group.name}"}


# ═══════════════════════════════════════════════
# READ / LIST Operations
# ═══════════════════════════════════════════════

async def list_users(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    auth_source: Optional[str] = None
) -> tuple[list[User], int]:
    """
    Phân trang danh sách users.
    
    Args:
        auth_source: Filter theo nguồn xác thực ("local" | "ldap" | None = tất cả)
    
    Returns:
        Tuple (list users, total count)
    """
    base_query = select(User)
    count_query = select(func.count(User.id))
    
    if auth_source:
        base_query = base_query.where(User.auth_source == auth_source)
        count_query = count_query.where(User.auth_source == auth_source)
    
    # Total count
    total = (await session.execute(count_query)).scalar()
    
    # Paginated results
    stmt = base_query.order_by(User.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(stmt)
    users = result.scalars().all()
    
    return list(users), total


async def get_user_detail(session: AsyncSession, user_id: UUID) -> User:
    """Lấy chi tiết user kèm roles, groups"""
    stmt = (
        select(User)
        .options(
            selectinload(User.roles).selectinload(Role.permissions),
            selectinload(User.groups).selectinload(Group.roles).selectinload(Role.permissions)
        )
        .where(User.id == user_id)
    )
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user


async def get_user_effective_permissions(session: AsyncSession, user_id: UUID) -> list[Permission]:
    """
    Lấy tất cả permissions hiệu lực của user (direct + qua group).
    Kết quả đã được deduplicate.
    """
    # Direct: User → Role → Permission
    direct_stmt = (
        select(Permission)
        .join(role_permission, Permission.id == role_permission.c.permission_id)
        .join(user_role, role_permission.c.role_id == user_role.c.role_id)
        .where(user_role.c.user_id == user_id)
    )
    
    # Via Group: User → Group → Role → Permission
    group_stmt = (
        select(Permission)
        .join(role_permission, Permission.id == role_permission.c.permission_id)
        .join(group_role, role_permission.c.role_id == group_role.c.role_id)
        .join(group_user, group_role.c.group_id == group_user.c.group_id)
        .where(group_user.c.user_id == user_id)
    )
    
    # Union + deduplicate
    union_stmt = direct_stmt.union(group_stmt)
    result = await session.execute(union_stmt)
    
    return list(result.scalars().all())


async def list_roles(session: AsyncSession) -> list[Role]:
    """Liệt kê tất cả roles"""
    stmt = select(Role).order_by(Role.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_groups(session: AsyncSession) -> list[Group]:
    """Liệt kê tất cả groups"""
    stmt = select(Group).order_by(Group.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_permissions(session: AsyncSession) -> list[Permission]:
    """Liệt kê tất cả permissions"""
    stmt = select(Permission).order_by(Permission.resource, Permission.action)
    result = await session.execute(stmt)
    return list(result.scalars().all())


# ═══════════════════════════════════════════════
# REMOVE / DEACTIVATE Operations
# ═══════════════════════════════════════════════

async def remove_role_from_user(session: AsyncSession, user_id: UUID, role_id: UUID):
    """Gỡ Role khỏi User"""
    user_stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role_to_remove = None
    for r in user.roles:
        if r.id == role_id:
            role_to_remove = r
            break
    
    if not role_to_remove:
        raise HTTPException(status_code=404, detail="User does not have this role")
    
    user.roles.remove(role_to_remove)
    await session.commit()
    
    return {"message": f"Role '{role_to_remove.name}' removed from user '{user.username}'"}


async def remove_user_from_group(session: AsyncSession, user_id: UUID, group_id: UUID):
    """Gỡ User khỏi Group"""
    user_stmt = select(User).options(selectinload(User.groups)).where(User.id == user_id)
    user = (await session.execute(user_stmt)).scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    group_to_remove = None
    for g in user.groups:
        if g.id == group_id:
            group_to_remove = g
            break
    
    if not group_to_remove:
        raise HTTPException(status_code=404, detail="User is not in this group")
    
    user.groups.remove(group_to_remove)
    await session.commit()
    
    return {"message": f"User '{user.username}' removed from group '{group_to_remove.name}'"}


async def deactivate_user(session: AsyncSession, user_id: UUID):
    """Set user is_active=False"""
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.is_active = False
    await session.commit()
    
    return {"message": f"User '{user.username}' has been deactivated"}


async def remove_perm_from_role(session: AsyncSession, role_id: UUID, perm_id: UUID):
    """Gỡ Permission khỏi Role"""
    role_stmt = select(Role).options(selectinload(Role.permissions)).where(Role.id == role_id)
    role = (await session.execute(role_stmt)).scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    perm_to_remove = None
    for p in role.permissions:
        if p.id == perm_id:
            perm_to_remove = p
            break
    
    if not perm_to_remove:
        raise HTTPException(status_code=404, detail="Role does not have this permission")
    
    role.permissions.remove(perm_to_remove)
    await session.commit()
    
    return {"message": f"Permission '{perm_to_remove.resource}:{perm_to_remove.action}' removed from role '{role.name}'"}
