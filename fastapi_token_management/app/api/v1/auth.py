from typing import Annotated
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt

from app.api.dependencies import SessionDep, require_permissions, get_current_active_user
from app.schemas.rbac import (
    UserCreate, UserResponse, Token,
    RefreshTokenRequest, LogoutRequest, UserMe,
)
from app.services.rbac_service import create_user
from app.services.auth_service import revoke_token, refresh_access_token
from app.models.rbac import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import settings
from sqlalchemy import select

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:users", "create")),
):
    """
    Tạo tài khoản User mới (yêu cầu quyền admin:users:create).
    Chỉ tạo user local (auth_source="local"). User LDAP được tạo tự động khi login.
    """
    return await create_user(session, user_in)


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep,
):
    """
    Xác thực và phát hành JWT token.

    **Dual-mode Authentication:**
    - `AUTH_BACKEND=local` → xác thực qua DB nội bộ (bcrypt)
    - `AUTH_BACKEND=ldap` → xác thực qua LDAP server, sync user & groups

    **Response:**
    - `access_token` — dùng cho mọi API call (ngắn hạn)
    - `refresh_token` — dùng để gia hạn access_token (dài hạn)
    - `expires_in` — thời hạn access_token (giây)
    """
    if settings.AUTH_BACKEND == "ldap":
        from app.services.ldap_service import (
            authenticate_ldap,
            sync_ldap_user_to_local,
            sync_ldap_groups,
        )

        ldap_info = await authenticate_ldap(form_data.username, form_data.password)
        if ldap_info is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="LDAP: Sai username hoặc password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await sync_ldap_user_to_local(session, ldap_info)
        if settings.LDAP_SYNC_GROUPS and ldap_info.get("groups"):
            await sync_ldap_groups(session, user, ldap_info["groups"])
        await session.commit()

    else:
        stmt = select(User).where(User.username == form_data.username)
        user = (await session.execute(stmt)).scalar_one_or_none()

        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sai username hoặc password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user.last_login = datetime.utcnow()
        await session.commit()

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị khoá.")

    access_token = create_access_token(data={"sub": user.username})
    refresh_token = create_refresh_token(data={"sub": user.username})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh")
async def refresh_token(
    body: RefreshTokenRequest,
    session: SessionDep,
):
    """
    Lấy `access_token` mới từ `refresh_token` còn hạn.
    Không cần đăng nhập lại — chuẩn OAuth2 Refresh Token Grant.
    """
    return await refresh_access_token(session, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    session: SessionDep,
    current_user: User = Depends(get_current_active_user),
):
    """
    Thu hồi access token hiện tại (đưa vào blacklist).
    Token bị blacklist sẽ không thể dùng được nữa dù chưa hết hạn.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=400, detail="Không tìm thấy Bearer token.")

    token_str = auth_header.removeprefix("Bearer ").strip()
    payload = decode_token(token_str)
    if payload is None:
        raise HTTPException(status_code=400, detail="Token không hợp lệ.")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=400, detail="Token thiếu JTI claim.")

    from datetime import datetime, timezone
    exp_ts = payload.get("exp")
    if exp_ts:
        # payload['exp'] luôn là UTC timestamp theo spec JWT
        expires_at = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
    else:
        expires_at = datetime.now(timezone.utc)

    await revoke_token(session, jti=jti, username=current_user.username, expires_at=expires_at)


@router.get("/me", response_model=UserMe)
async def get_me(current_user: User = Depends(get_current_active_user)):
    """
    Lấy thông tin profile của user đang đăng nhập.
    Không cần quyền đặc biệt — mọi user đã login đều truy cập được.
    """
    return UserMe.model_validate(current_user)
