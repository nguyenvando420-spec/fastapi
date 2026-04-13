import re
import uuid
from typing import Optional, List
from sqlalchemy import select, text, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.models.admin import (
    System, Domain,
    DOMAIN_STATUS_ACTIVE, DOMAIN_STATUS_ROTATED, DOMAIN_STATUS_DEPRECATED,
)
from app.schemas.admin import SystemCreate, SystemUpdate, DomainCreate, DomainUpdate
from app.models.dynamic_token import create_dynamic_token_model
from app.core.database import token_engine
from datetime import datetime, timezone


# ── Helpers ───────────────────────────────────────────────────────────────────

def _assert_safe_name(name: str):
    """
    Double-check tên đã qua Pydantic validator.
    Guard cuối cùng trước khi tên được dùng trong DDL raw SQL.
    """
    if not re.match(r'^[a-z][a-z0-9_]{0,99}$', name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tên không an toàn cho SQL: '{name}'"
        )


def _make_table_name(domain_name: str, version_number: int) -> str:
    """
    Tạo tên bảng token vật lý: {domain}_v{version_number}
    Ví dụ: credit_card_v1, credit_card_v2
    """
    return f"{domain_name}_v{version_number}"


# ── System CRUD ───────────────────────────────────────────────────────────────

async def create_system_db(
    session: AsyncSession, token_session: AsyncSession, system_in: SystemCreate
) -> System:
    """Đăng ký System (Admin DB) và tạo Schema (Token DB)."""
    _assert_safe_name(system_in.name)

    stmt = select(System).where(System.name == system_in.name)
    if (await session.execute(stmt)).scalars().first():
        raise HTTPException(status_code=400, detail=f"System '{system_in.name}' đã tồn tại.")

    new_system = System(name=system_in.name, description=system_in.description)
    session.add(new_system)
    await session.flush()

    try:
        # Thực thi DDL trên token_session được inject từ API
        await token_session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system_in.name}";'))
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khởi tạo schema trong Token DB: {str(e)}"
        )

    await session.commit()
    await session.refresh(new_system)
    return new_system


async def list_systems_db(
    session: AsyncSession,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, List[System]]:
    """Lấy danh sách System kèm tổng số bản ghi (phục vụ pagination)."""
    base = select(System)
    if not include_inactive:
        base = base.where(System.is_active == True)

    total_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    stmt = base.order_by(System.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return total, result.scalars().all()


async def get_system_db(session: AsyncSession, system_id: str) -> System:
    """Lấy System theo ID — 404 nếu không tìm thấy hoặc đã xóa."""
    system = await session.get(System, system_id)
    if not system or not system.is_active:
        raise HTTPException(status_code=404, detail="System không tìm thấy.")
    return system


async def update_system_db(
    session: AsyncSession, system_id: str, data: SystemUpdate
) -> System:
    """Cập nhật description của System (name là bất biến sau khi tạo schema)."""
    system = await get_system_db(session, system_id)
    if data.description is not None:
        system.description = data.description
    session.add(system)
    await session.commit()
    await session.refresh(system)
    return system


async def delete_system_db(session: AsyncSession, system_id: str) -> dict:
    """
    Soft delete System: đánh dấu is_active=False.
    Schema PostgreSQL vẫn được giữ để tránh mất token data.
    """
    system = await get_system_db(session, system_id)
    system.is_active = False
    session.add(system)
    await session.commit()
    return {"message": f"System '{system.name}' đã được vô hiệu hóa (soft delete)."}


# ── Domain CRUD ───────────────────────────────────────────────────────────────

async def create_domain_db(
    session: AsyncSession, token_session: AsyncSession, domain_in: DomainCreate
) -> Domain:
    """
    Đăng ký Domain (Admin DB) và tạo Token Table (Token DB).
    Version tự động = v1, status = active.
    Tham khảo HashiCorp Vault: version đầu tiên luôn là 1.
    """
    _assert_safe_name(domain_in.name)

    system = await session.get(System, str(domain_in.system_id))
    if not system or not system.is_active:
        raise HTTPException(status_code=404, detail="System ID không hợp lệ hoặc đã bị xóa.")

    # Kiểm tra domain name đã tồn tại trong system chưa (bất kỳ version nào)
    stmt = select(Domain).where(
        Domain.name == domain_in.name,
        Domain.system_id == str(domain_in.system_id),
        Domain.is_active == True,
    )
    if (await session.execute(stmt)).scalars().first():
        raise HTTPException(status_code=400, detail="Domain đã tồn tại trong System này.")

    # Tạo domain với version_number=1, version="v1", status="active"
    new_domain = Domain(
        name=domain_in.name,
        version_number=1,
        version="v1",
        status=DOMAIN_STATUS_ACTIVE,
        system_id=str(domain_in.system_id),
        description=domain_in.description,
    )
    session.add(new_domain)
    await session.flush()

    # Tạo bảng token vật lý: <schema>.<domain>_v1
    table_name = _make_table_name(domain_in.name, 1)
    DynamicModel = create_dynamic_token_model(schema_name=system.name, table_name=table_name)

    try:
        conn = await token_session.connection()
        await conn.run_sync(lambda sync_conn: DynamicModel.__table__.create(sync_conn, checkfirst=True))
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khởi tạo bảng token trong Token DB: {str(e)}"
        )

    await session.commit()
    await session.refresh(new_domain)
    return new_domain


async def rotate_domain_version(
    session: AsyncSession, token_session: AsyncSession, domain_id: str
) -> tuple[Domain, Domain]:
    """
    Rotate Domain lên version mới (tham khảo HashiCorp Vault Key Rotation, AWS KMS RotateKeyOnDemand).

    1. Tìm domain hiện tại (active version)
    2. Chuyển version cũ sang status 'rotated'
    3. Tạo record Domain mới với version_number + 1, status 'active'
    4. Tạo bảng token mới trên Token DB
    5. Return (new_domain, old_domain)
    """
    # 1. Lấy domain gốc để xác định name + system
    current_domain = await session.get(Domain, domain_id)
    if not current_domain or not current_domain.is_active:
        raise HTTPException(status_code=404, detail="Domain không tìm thấy.")

    # Tìm version active hiện tại của domain này
    stmt = (
        select(Domain)
        .where(
            Domain.name == current_domain.name,
            Domain.system_id == current_domain.system_id,
            Domain.status == DOMAIN_STATUS_ACTIVE,
            Domain.is_active == True,
        )
        .order_by(desc(Domain.version_number))
        .limit(1)
    )
    result = await session.execute(stmt)
    active_version = result.scalar_one_or_none()

    if not active_version:
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy version active nào để rotate."
        )

    # Lấy system info
    system = await session.get(System, active_version.system_id)
    if not system or not system.is_active:
        raise HTTPException(status_code=404, detail="System không hợp lệ.")

    # 2. Chuyển version cũ → rotated
    active_version.status = DOMAIN_STATUS_ROTATED
    session.add(active_version)

    # 3. Tạo version mới
    new_version_number = active_version.version_number + 1
    new_domain = Domain(
        name=active_version.name,
        version_number=new_version_number,
        version=f"v{new_version_number}",
        status=DOMAIN_STATUS_ACTIVE,
        system_id=active_version.system_id,
        description=active_version.description,
    )
    session.add(new_domain)
    await session.flush()

    # 4. Tạo bảng token mới trên Token DB
    table_name = _make_table_name(active_version.name, new_version_number)
    DynamicModel = create_dynamic_token_model(schema_name=system.name, table_name=table_name)

    try:
        conn = await token_session.connection()
        await conn.run_sync(lambda sync_conn: DynamicModel.__table__.create(sync_conn, checkfirst=True))
    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi khởi tạo bảng token version mới: {str(e)}"
        )

    await session.commit()
    await session.refresh(new_domain)
    await session.refresh(active_version)
    return new_domain, active_version


async def get_domain_versions(
    session: AsyncSession, domain_id: str
) -> tuple[str, str, List[Domain]]:
    """
    Lấy lịch sử tất cả version của một domain.
    Tham khảo HashiCorp Vault GET /secret/metadata/:path.
    Return: (domain_name, system_name, list_of_versions)
    """
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain không tìm thấy.")

    system = await session.get(System, domain.system_id)

    # Lấy tất cả version của domain này
    stmt = (
        select(Domain)
        .where(
            Domain.name == domain.name,
            Domain.system_id == domain.system_id,
            Domain.is_active == True,
        )
        .order_by(desc(Domain.version_number))
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    return domain.name, system.name if system else "unknown", versions


async def deprecate_domain_version(
    session: AsyncSession, domain_id: str, version_number: int
) -> Domain:
    """
    Deprecate một version cụ thể — không cho detokenize nữa.
    Tham khảo AWS KMS DisableKey / HashiCorp Vault destroy version.
    """
    domain = await session.get(Domain, domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail="Domain không tìm thấy.")

    # Tìm version cụ thể
    stmt = select(Domain).where(
        Domain.name == domain.name,
        Domain.system_id == domain.system_id,
        Domain.version_number == version_number,
        Domain.is_active == True,
    )
    result = await session.execute(stmt)
    target_version = result.scalar_one_or_none()

    if not target_version:
        raise HTTPException(
            status_code=404,
            detail=f"Version v{version_number} không tìm thấy."
        )

    if target_version.status == DOMAIN_STATUS_DEPRECATED:
        raise HTTPException(
            status_code=400,
            detail=f"Version v{version_number} đã ở trạng thái deprecated."
        )

    if target_version.status == DOMAIN_STATUS_ACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Không thể deprecate version đang active. Hãy rotate trước."
        )

    target_version.status = DOMAIN_STATUS_DEPRECATED
    session.add(target_version)
    await session.commit()
    await session.refresh(target_version)
    return target_version


async def list_domains_db(
    session: AsyncSession,
    system_id: Optional[str] = None,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> tuple[int, List[Domain]]:
    """Lấy danh sách Domain kèm total count."""
    base = select(Domain)
    if system_id:
        base = base.where(Domain.system_id == system_id)
    if not include_inactive:
        base = base.where(Domain.is_active == True)

    total_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total = total_result.scalar_one()

    stmt = base.order_by(Domain.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(stmt)
    return total, result.scalars().all()


async def get_domain_db(session: AsyncSession, domain_id: str) -> Domain:
    """Lấy Domain theo ID — 404 nếu không tìm thấy."""
    domain = await session.get(Domain, domain_id)
    if not domain or not domain.is_active:
        raise HTTPException(status_code=404, detail="Domain không tìm thấy.")
    return domain


async def update_domain_db(
    session: AsyncSession, domain_id: str, data: DomainUpdate
) -> Domain:
    """Cập nhật description của Domain."""
    domain = await get_domain_db(session, domain_id)
    if data.description is not None:
        domain.description = data.description
    session.add(domain)
    await session.commit()
    await session.refresh(domain)
    return domain


async def delete_domain_db(session: AsyncSession, domain_id: str) -> dict:
    """Soft delete Domain — giữ nguyên token table trong DB."""
    domain = await get_domain_db(session, domain_id)
    domain.is_active = False
    session.add(domain)
    await session.commit()
    return {"message": f"Domain '{domain.name}' đã được vô hiệu hóa (soft delete)."}
