from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from fastapi import HTTPException, status
from app.models.rbac import User, Role, Permission, Group
from app.schemas.rbac import (
    UserCreate, RoleCreate, PermissionCreate, GroupCreate,
    UserRoleAssign, RolePermissionAssign, UserGroupAssign, GroupRoleAssign
)
from app.core.security import get_password_hash
from uuid import UUID

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
    
    db_perm = Permission(resource=perm_in.resource, action=perm_in.action)
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
    
    try:
        group.roles.append(role)
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to assign role to group: {str(e)}")
    
    return {"message": f"Role {role.name} assigned to group {group.name}"}
