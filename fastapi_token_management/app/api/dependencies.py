from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_db_session
from app.models.rbac import User, Role, Permission, Group, user_role, role_permission, group_user, group_role

# Scheme khai báo đầu vào của mọi endpoint bảo mật phải có HTTP Bearer Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Định nghĩa các Dependency Type Hints gọn gàng
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
from app.core.database import get_token_db_session
TokenSessionDep = Annotated[AsyncSession, Depends(get_token_db_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]

async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """Dependency trích xuất và xác thực User trực tiếp từ JWT Access Token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token xác thực không hợp lệ",
        headers={"WWW-Authenticate": "Bearer"},
    )
    from app.core.security import decode_token
    from app.services.auth_service import is_token_revoked

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    # Phải là access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai loại token. Vui lòng cung cấp Access Token hợp lệ.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    username: str = payload.get("sub")
    jti: str = payload.get("jti")
    if username is None or jti is None:
        raise credentials_exception

    # Token có nằm trong blacklist không?
    if await is_token_revoked(session, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session đã hết hạn do đăng xuất ở nơi khác. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"}
        )
        
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Dependency ép buộc User Auth phải ở trạng thái Active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị vô hiệu hóa.")
    return current_user


async def check_user_permissions(
    current_user: User,
    session: AsyncSession,
    required_resource: str,
    required_action: str
):
    """
    Kiểm tra quyền của User trên resource cụ thể.
    
    Superuser Bypass:
      Nếu user có is_superuser=True → cho phép ngay, không cần query permission.
      (Tham khảo Django is_superuser, Keycloak realm admin)
    
    Hỗ trợ 2 con đường:
      1) Trực tiếp: User → user_role → Role → role_permission → Permission
      2) Qua Group: User → group_user → Group → group_role → Role → role_permission → Permission
    Resource wildcard: 'system:*' và '*' đều được chấp nhận.
    """
    # --- Superuser Bypass ---
    if current_user.is_superuser:
        return True

    # 1. Tính các resource pattern hợp lệ
    resource_parts = required_resource.split(':', 1)
    system_wildcard = f"{resource_parts[0]}:*" if len(resource_parts) > 1 else required_resource
    allowed_resources = [required_resource, "*", system_wildcard]
    allowed_actions = [required_action, "*"]

    # 2a. Subquery — Path trực tiếp: User → Role → Permission
    direct_subq = (
        select(Permission.id)
        .join(role_permission, Permission.id == role_permission.c.permission_id)
        .join(user_role, role_permission.c.role_id == user_role.c.role_id)
        .where(
            user_role.c.user_id == current_user.id,
            Permission.resource.in_(allowed_resources),
            Permission.action.in_(allowed_actions),
        )
    ).subquery()

    # 2b. Subquery — Path qua Group: User → Group → Role → Permission
    group_subq = (
        select(Permission.id)
        .join(role_permission, Permission.id == role_permission.c.permission_id)
        .join(group_role, role_permission.c.role_id == group_role.c.role_id)
        .join(group_user, group_role.c.group_id == group_user.c.group_id)
        .where(
            group_user.c.user_id == current_user.id,
            Permission.resource.in_(allowed_resources),
            Permission.action.in_(allowed_actions),
        )
    ).subquery()

    # 3. Kết hợp: tìm ít nhất 1 permission khớp từ bất kỳ path nào
    stmt = (
        select(Permission)
        .where(
            or_(
                Permission.id.in_(select(direct_subq)),
                Permission.id.in_(select(group_subq)),
            )
        )
        .limit(1)
    )

    result = await session.execute(stmt)
    perm = result.scalar_one_or_none()

    if perm is None:
        # Ghi audit log khi bị từ chối
        from app.services.audit_service import create_audit_log
        await create_audit_log(
            session=session,
            request_type="permission",
            system=resource_parts[0],
            domain=resource_parts[1] if len(resource_parts) > 1 else None,
            user=current_user.username,
            auth_status="denied",
            status="fail",
            detail=f"User '{current_user.username}' lacks '{required_action}' permission on '{required_resource}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden: requires '{required_action}' on '{required_resource}'"
        )
    return True

def require_permissions(required_resource: str, required_action: str):
    """Dependency Factory cho các resource tĩnh."""
    async def permission_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
        session: SessionDep
    ):
        await check_user_permissions(current_user, session, required_resource, required_action)
        return current_user
    return permission_checker

async def require_token_permissions(
    action: str,
    req: any, # TokenizeRequest hoặc DeTokenizeRequest
    current_user: Annotated[User, Depends(get_current_active_user)],
    session: SessionDep
):
    """Dependency động: Lấy system/domain từ Body để kiểm tra quyền."""
    resource = f"{req.system_name}:{req.domain_name}"
    await check_user_permissions(current_user, session, resource, action)
    return current_user
