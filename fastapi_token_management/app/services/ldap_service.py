"""
LDAP Authentication & Group Sync Service
=========================================
Tham khảo kiến trúc Keycloak User Federation:
- Bind → Search → Verify → Sync (user + groups)
- Sử dụng ldap3 library (synchronous) wrapped trong run_in_threadpool cho async compat

Chỉ được sử dụng khi AUTH_BACKEND="ldap" trong config.
"""
import logging
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.models.rbac import User, Group, group_user
from app.core.security import get_password_hash

logger = logging.getLogger(__name__)

# Placeholder password cho LDAP users (họ không dùng local password)
LDAP_PLACEHOLDER_PASSWORD = "@@LDAP_MANAGED_PASSWORD_DO_NOT_USE@@"


def _get_ldap_connection():
    """
    Tạo LDAP connection sử dụng service account (bind DN) để tìm kiếm.
    Được gọi trong thread pool vì ldap3 là synchronous.
    
    Returns:
        ldap3.Connection đã bind thành công
    
    Raises:
        ImportError: Nếu chưa cài đặt ldap3
        Exception: Nếu không thể kết nối LDAP server
    """
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
    except ImportError:
        raise ImportError(
            "Package 'ldap3' chưa được cài đặt. "
            "Chạy: poetry add ldap3 hoặc pip install ldap3"
        )
    
    server = Server(
        settings.LDAP_SERVER,
        port=settings.LDAP_PORT,
        use_ssl=settings.LDAP_USE_SSL,
        get_info=ALL,
        connect_timeout=settings.LDAP_CONNECTION_TIMEOUT
    )
    
    conn = Connection(
        server,
        user=settings.LDAP_BIND_DN,
        password=settings.LDAP_BIND_PASSWORD,
        auto_bind=True,
        read_only=True,
        receive_timeout=settings.LDAP_CONNECTION_TIMEOUT
    )
    
    return conn


def _ldap_authenticate_sync(username: str, password: str) -> Optional[dict]:
    """
    Xác thực user qua LDAP (synchronous).
    
    Flow (tham khảo Keycloak):
      1. Bind với service account → search user DN
      2. Unbind service account
      3. Re-bind với user DN + password để verify
    
    Returns:
        dict chứa thông tin user nếu thành công, None nếu thất bại
    """
    try:
        from ldap3 import Server, Connection, ALL, SUBTREE
    except ImportError:
        raise ImportError("Package 'ldap3' chưa được cài đặt.")
    
    # --- Step 1: Search user DN bằng service account ---
    try:
        service_conn = _get_ldap_connection()
    except Exception as e:
        logger.error(f"LDAP: Không thể kết nối bằng service account: {e}")
        return None
    
    try:
        search_filter = settings.LDAP_USER_SEARCH_FILTER.replace("{username}", username)
        
        service_conn.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=[
                settings.LDAP_USER_ATTR_USERNAME,
                settings.LDAP_USER_ATTR_EMAIL,
                settings.LDAP_USER_ATTR_DISPLAY_NAME,
                "memberOf"  # Lấy danh sách groups user thuộc về
            ]
        )
        
        if not service_conn.entries:
            logger.warning(f"LDAP: Không tìm thấy user '{username}'")
            return None
        
        user_entry = service_conn.entries[0]
        user_dn = str(user_entry.entry_dn)
        
        # Trích xuất attributes
        user_info = {
            "dn": user_dn,
            "username": str(getattr(user_entry, settings.LDAP_USER_ATTR_USERNAME, username)),
            "email": str(getattr(user_entry, settings.LDAP_USER_ATTR_EMAIL, f"{username}@ldap.local")),
            "display_name": str(getattr(user_entry, settings.LDAP_USER_ATTR_DISPLAY_NAME, username)),
            "groups": []
        }
        
        # Lấy danh sách groups từ memberOf
        if hasattr(user_entry, "memberOf"):
            user_info["groups"] = [str(g) for g in user_entry.memberOf]
    
    finally:
        service_conn.unbind()
    
    # --- Step 2: Verify password bằng user bind ---
    try:
        server = Server(
            settings.LDAP_SERVER,
            port=settings.LDAP_PORT,
            use_ssl=settings.LDAP_USE_SSL,
            connect_timeout=settings.LDAP_CONNECTION_TIMEOUT
        )
        
        user_conn = Connection(
            server,
            user=user_dn,
            password=password,
            authentication="SIMPLE",
            receive_timeout=settings.LDAP_CONNECTION_TIMEOUT
        )
        
        if not user_conn.bind():
            logger.warning(f"LDAP: Sai password cho user '{username}' (DN: {user_dn})")
            return None
        
        user_conn.unbind()
        
    except Exception as e:
        logger.error(f"LDAP: Lỗi xác thực user '{username}': {e}")
        return None
    
    logger.info(f"LDAP: Xác thực thành công cho user '{username}'")
    return user_info


def _ldap_get_user_groups_sync(username: str) -> list[str]:
    """
    Lấy danh sách LDAP groups mà user thuộc về (synchronous).
    Sử dụng khi cần refresh groups mà không cần xác thực lại.
    
    Returns:
        List các group DNs
    """
    try:
        from ldap3 import SUBTREE
    except ImportError:
        return []
    
    try:
        conn = _get_ldap_connection()
        
        search_filter = settings.LDAP_USER_SEARCH_FILTER.replace("{username}", username)
        conn.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=search_filter,
            search_scope=SUBTREE,
            attributes=["memberOf"]
        )
        
        if not conn.entries:
            return []
        
        user_entry = conn.entries[0]
        groups = [str(g) for g in user_entry.memberOf] if hasattr(user_entry, "memberOf") else []
        
        conn.unbind()
        return groups
        
    except Exception as e:
        logger.error(f"LDAP: Lỗi lấy groups cho user '{username}': {e}")
        return []


async def authenticate_ldap(username: str, password: str) -> Optional[dict]:
    """
    Async wrapper cho LDAP authentication.
    Chạy ldap3 sync code trong thread pool để không block event loop.
    
    Returns:
        dict chứa user info hoặc None nếu thất bại
    """
    return await run_in_threadpool(_ldap_authenticate_sync, username, password)


async def get_ldap_user_groups(username: str) -> list[str]:
    """Async wrapper lấy LDAP groups."""
    return await run_in_threadpool(_ldap_get_user_groups_sync, username)


def _extract_cn_from_dn(dn: str) -> str:
    """
    Trích xuất Common Name (CN) từ Distinguished Name.
    VD: 'cn=developers,ou=groups,dc=example,dc=com' → 'developers'
    """
    for part in dn.split(","):
        part = part.strip()
        if part.lower().startswith("cn="):
            return part[3:]
    return dn


async def sync_ldap_user_to_local(
    session: AsyncSession,
    ldap_info: dict
) -> User:
    """
    Upsert (tạo hoặc cập nhật) user local từ thông tin LDAP.
    Tham khảo Keycloak User Federation: LDAP user được mirror vào local DB.
    
    - Nếu user chưa tồn tại: tạo mới với auth_source="ldap"
    - Nếu user đã tồn tại: cập nhật email, display_name, last_login
    - Password được set thành placeholder (LDAP quản lý password)
    
    Args:
        session: AsyncSession database
        ldap_info: dict từ authenticate_ldap()
    
    Returns:
        User object đã sync
    """
    stmt = select(User).options(
        selectinload(User.groups),
        selectinload(User.roles)
    ).where(User.username == ldap_info["username"])
    
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        # Tạo user mới từ LDAP
        user = User(
            username=ldap_info["username"],
            email=ldap_info.get("email", f"{ldap_info['username']}@ldap.local"),
            hashed_password=get_password_hash(LDAP_PLACEHOLDER_PASSWORD),
            is_active=True,
            auth_source="ldap",
            ldap_dn=ldap_info.get("dn"),
            display_name=ldap_info.get("display_name"),
            last_login=datetime.utcnow()
        )
        session.add(user)
        await session.flush()
        
        # Re-fetch with relationships
        stmt = select(User).options(
            selectinload(User.groups),
            selectinload(User.roles)
        ).where(User.id == user.id)
        result = await session.execute(stmt)
        user = result.scalar_one()
        
        logger.info(f"LDAP Sync: Tạo user local mới '{user.username}' (auth_source=ldap)")
    else:
        # Cập nhật thông tin user hiện có
        user.email = ldap_info.get("email", user.email)
        user.display_name = ldap_info.get("display_name", user.display_name)
        user.ldap_dn = ldap_info.get("dn", user.ldap_dn)
        user.auth_source = "ldap"
        user.last_login = datetime.utcnow()
        
        logger.info(f"LDAP Sync: Cập nhật user '{user.username}'")
    
    return user


async def sync_ldap_groups(
    session: AsyncSession,
    user: User,
    ldap_group_dns: list[str]
) -> None:
    """
    Đồng bộ LDAP groups → RBAC groups.
    Tham khảo Keycloak Group Mapper:
    
    1. Với mỗi LDAP group DN:
       - Tìm hoặc tạo RBAC Group tương ứng (match by ldap_dn hoặc name)
       - Mark group là is_ldap_synced=True
    2. Gán user vào các groups tương ứng
    3. Loại bỏ user khỏi các LDAP-synced groups mà user không còn thuộc về
    
    Args:
        session: AsyncSession
        user: User đã sync
        ldap_group_dns: List các group DNs từ LDAP
    """
    if not settings.LDAP_SYNC_GROUPS or not ldap_group_dns:
        return
    
    current_ldap_groups = set()
    
    for group_dn in ldap_group_dns:
        group_name = _extract_cn_from_dn(group_dn)
        
        # Tìm group theo ldap_dn trước, rồi theo name
        stmt = select(Group).options(selectinload(Group.users)).where(Group.ldap_dn == group_dn)
        result = await session.execute(stmt)
        group = result.scalar_one_or_none()
        
        if group is None:
            # Tìm theo tên
            stmt = select(Group).options(selectinload(Group.users)).where(Group.name == group_name)
            result = await session.execute(stmt)
            group = result.scalar_one_or_none()
        
        if group is None:
            # Tạo group mới
            group = Group(
                name=group_name,
                description=f"Auto-synced from LDAP: {group_dn}",
                ldap_dn=group_dn,
                is_ldap_synced=True
            )
            session.add(group)
            await session.flush()
            
            # Re-fetch with users relationship
            stmt = select(Group).options(selectinload(Group.users)).where(Group.id == group.id)
            result = await session.execute(stmt)
            group = result.scalar_one()
            
            logger.info(f"LDAP Sync: Tạo group mới '{group_name}' từ LDAP")
        else:
            # Cập nhật LDAP tracking
            group.ldap_dn = group_dn
            group.is_ldap_synced = True
        
        # Gán user vào group nếu chưa có
        if user not in group.users:
            group.users.append(user)
            logger.info(f"LDAP Sync: Gán user '{user.username}' vào group '{group.name}'")
        
        current_ldap_groups.add(group.name)
    
    # Loại bỏ user khỏi LDAP-synced groups mà user không còn thuộc về
    for group in list(user.groups):
        if group.is_ldap_synced and group.name not in current_ldap_groups:
            user.groups.remove(group)
            logger.info(
                f"LDAP Sync: Gỡ user '{user.username}' khỏi group '{group.name}' "
                f"(user không còn trong LDAP group tương ứng)"
            )
    
    await session.flush()
    logger.info(
        f"LDAP Sync: User '{user.username}' thuộc {len(current_ldap_groups)} LDAP groups: "
        f"{current_ldap_groups}"
    )
