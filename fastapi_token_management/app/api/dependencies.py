from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import aliased
from jose import JWTError, jwt

from app.core.config import settings
from app.core.database import get_db_session
from app.models.rbac import User, Role, Permission, Group

# Scheme khai báo đầu vào của mọi endpoint bảo mật phải có HTTP Bearer Token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

# Định nghĩa các Dependency Type Hints gọn gàng
SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
TokenDep = Annotated[str, Depends(oauth2_scheme)]

async def get_current_user(session: SessionDep, token: TokenDep) -> User:
    """Dependency trích xuất và xác thực User trực tiếp từ JWT Token của Request Header"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Giải mã JWT token
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    # Query database tìm user
    stmt = select(User).where(User.username == username)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Dependency ép buộc User Auth phải ở trạng thái Active"""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user account")
    return current_user


async def check_user_permissions(
    current_user: User, 
    session: AsyncSession, 
    required_resource: str, 
    required_action: str
):
    """Logic lõi kiểm tra quyền của User (bao gồm Role và Group)."""
    # 1. Tách resource nếu định dạng theo 'system_name:domain_name'
    resource_parts = required_resource.split(':', 1)
    system_wildcard = f"{resource_parts[0]}:*" if len(resource_parts) > 1 else required_resource
    
    # 2. Tạo SQL Query liên kết User -> Role -> Permission (Hỗ trợ Group)
    UserAlias = aliased(User)
    stmt = (
        select(Permission)
        .join(Permission.roles)
        .outerjoin(Role.users)
        .outerjoin(Role.groups)
        .outerjoin(Group.users.of_type(UserAlias))
        .where(
            or_(
                User.id == current_user.id,
                UserAlias.id == current_user.id
            ),
            Permission.resource.in_([required_resource, "*", system_wildcard]),
            Permission.action.in_([required_action, "*"])
        )
    )
    
    result = await session.execute(stmt)
    perms = result.scalars().all()
    
    if not perms:
        # Ghi log Denied (Forbidden)
        from app.services.audit_service import create_audit_log
        await create_audit_log(
            session=session,
            request_type="permission",
            system=required_resource.split(":")[0] if ":" in required_resource else required_resource,
            domain=required_resource.split(":")[1] if ":" in required_resource else None,
            user=current_user.username,
            auth_status="denied",
            status="fail",
            detail=f"User lacks {required_action} permission on {required_resource}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Forbidden operation. Not enough permissions. Requires {required_action} on {required_resource}"
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
