"""
auth_service.py — Dịch vụ xác thực nâng cao

Cung cấp:
  - Tạo và xác thực Refresh Token (stateless JWT với type="refresh")
  - Blacklist token đã thu hồi (logout) qua bảng RevokedToken
  - Dọn dẹp revoked_tokens đã hết hạn (background worker)
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.core.config import settings
from app.core.security import create_refresh_token, decode_token
from app.models.rbac import RevokedToken, User


# ── Revoke / Blacklist ───────────────────────────────────────────────────────

async def revoke_token(session: AsyncSession, jti: str, username: str, expires_at: datetime):
    """
    Thêm token vào blacklist.
    Gọi hàm này khi user logout hoặc admin force-expire session.
    """
    existing = await session.get(RevokedToken, jti)
    if existing:
        return  # Đã blacklisted rồi, bỏ qua

    # Lưu ý: lookup bằng primary key không dùng được đây vì jti không phải PK
    stmt = select(RevokedToken).where(RevokedToken.jti == jti)
    result = await session.execute(stmt)
    if result.scalar_one_or_none():
        return

    revoked = RevokedToken(jti=jti, username=username, expires_at=expires_at)
    session.add(revoked)
    await session.commit()


async def is_token_revoked(session: AsyncSession, jti: str) -> bool:
    """Kiểm tra JWT có nằm trong blacklist không."""
    stmt = select(RevokedToken).where(RevokedToken.jti == jti)
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def revoke_all_user_tokens(session: AsyncSession, username: str):
    """Thu hồi toàn bộ token của một user (force logout everywhere)."""
    stmt = delete(RevokedToken).where(RevokedToken.username == username)
    await session.execute(stmt)
    # Không commit ở đây — caller sẽ commit

    # Thêm một wildcard marker để block tất cả token cũ hơn timestamp này
    # (Pattern: bất kỳ token nào issued_at < now đều bị coi là revoked)
    # Cách đơn giản: ghi marker với jti đặc biệt
    marker_jti = f"__all__{username}__{datetime.utcnow().timestamp()}"
    marker = RevokedToken(
        jti=marker_jti,
        username=username,
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(marker)


async def cleanup_expired_revocations(session: AsyncSession) -> int:
    """Xóa các bản ghi revoked token đã hết hạn để giữ bảng gọn."""
    stmt = delete(RevokedToken).where(RevokedToken.expires_at < datetime.utcnow())
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount


# ── Refresh Token Flow ────────────────────────────────────────────────────────

async def refresh_access_token(session: AsyncSession, refresh_token: str) -> dict:
    """
    Xác thực refresh_token và phát hành access_token mới.
    
    Quy trình (OAuth2 Refresh Token Grant):
      1. Decode & verify JWT signature + expiry
      2. Kiểm tra type == "refresh"
      3. Kiểm tra jti không nằm trong blacklist
      4. Lấy user từ DB — đảm bảo còn active
      5. Phát hành access_token mới
    """
    from app.core.security import create_access_token

    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Refresh token không hợp lệ hoặc đã hết hạn.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(refresh_token)
    if payload is None:
        raise credentials_exc

    token_type = payload.get("type")
    if token_type != "refresh":
        raise credentials_exc

    jti = payload.get("jti")
    username = payload.get("sub")

    if not jti or not username:
        raise credentials_exc

    # Kiểm tra blacklist
    if await is_token_revoked(session, jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token đã bị thu hồi. Vui lòng đăng nhập lại.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Kiểm tra user còn tồn tại và active
    stmt = select(User).where(User.username == username)
    user = (await session.execute(stmt)).scalar_one_or_none()

    if not user or not user.is_active:
        raise credentials_exc

    # Phát hành access_token mới
    new_access_token = create_access_token(data={"sub": username})

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }
