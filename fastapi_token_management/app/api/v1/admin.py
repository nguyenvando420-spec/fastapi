from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, status, Query, Path
from app.api.dependencies import SessionDep, TokenSessionDep, require_permissions
from app.schemas.admin import (
    SystemCreate, SystemUpdate, SystemResponse,
    DomainCreate, DomainUpdate, DomainResponse,
    DomainRotateResponse, DomainVersionHistory,
    PaginatedResponse,
)
from app.services.admin_service import (
    create_system_db, list_systems_db, get_system_db, update_system_db, delete_system_db,
    create_domain_db, list_domains_db, get_domain_db, update_domain_db, delete_domain_db,
    rotate_domain_version, get_domain_versions, deprecate_domain_version,
)
from app.core.database import get_token_db_session

router = APIRouter()


# ═══════════════════════════════════════════════════
#   SYSTEM (Schema) Endpoints
# ═══════════════════════════════════════════════════

@router.get("/systems", response_model=PaginatedResponse[SystemResponse])
async def list_systems(
    session: SessionDep,
    include_inactive: bool = Query(False, description="Bao gồm System đã bị vô hiệu hóa"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    _ = Depends(require_permissions("admin:system", "read")),
):
    """Lấy danh sách tất cả System đã đăng ký."""
    total, items = await list_systems_db(session, include_inactive, limit, offset)
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.post("/systems", response_model=SystemResponse, status_code=status.HTTP_201_CREATED)
async def create_system(
    system_in: SystemCreate,
    session: SessionDep,
    token_session: TokenSessionDep,
    _ = Depends(require_permissions("admin:system", "create")),
):
    """
    Khởi tạo System mới:
    - Ghi nhận metadata vào Admin DB (session)
    - Auto DDL `CREATE SCHEMA` trên Token DB (token_session)
    """
    return await create_system_db(session, token_session, system_in)


@router.get("/systems/{system_id}", response_model=SystemResponse)
async def get_system(
    system_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:system", "read")),
):
    """Lấy chi tiết một System theo ID."""
    return await get_system_db(session, str(system_id))


@router.patch("/systems/{system_id}", response_model=SystemResponse)
async def update_system(
    system_id: UUID,
    data: SystemUpdate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:system", "write")),
):
    """Cập nhật description của System (name là bất biến)."""
    return await update_system_db(session, str(system_id), data)


@router.delete("/systems/{system_id}", status_code=status.HTTP_200_OK)
async def delete_system(
    system_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:system", "delete")),
):
    """
    Soft delete System — đánh dấu is_active=False.
    Schema PostgreSQL và dữ liệu token vẫn được giữ nguyên để bảo toàn dữ liệu.
    """
    return await delete_system_db(session, str(system_id))


# ═══════════════════════════════════════════════════
#   DOMAIN (Table) Endpoints
# ═══════════════════════════════════════════════════

@router.get("/domains", response_model=PaginatedResponse[DomainResponse])
async def list_domains(
    session: SessionDep,
    system_id: Optional[UUID] = Query(None, description="Lọc theo System ID"),
    include_inactive: bool = Query(False, description="Bao gồm Domain đã bị vô hiệu hóa"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    _ = Depends(require_permissions("admin:domain", "read")),
):
    """Lấy danh sách Domain (có thể lọc theo System)."""
    total, items = await list_domains_db(
        session,
        system_id=str(system_id) if system_id else None,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )
    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    domain_in: DomainCreate,
    session: SessionDep,
    token_session: TokenSessionDep,
    _ = Depends(require_permissions("admin:domain", "create")),
):
    """
    Khởi tạo Domain mới:
    - Version tự động = v1, status = active
    - Auto DDL tạo token table `<schema>.<domain>_v1` trên Token DB
    """
    return await create_domain_db(session, token_session, domain_in)


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:domain", "read")),
):
    """Lấy chi tiết một Domain theo ID."""
    return await get_domain_db(session, str(domain_id))


@router.patch("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: UUID,
    data: DomainUpdate,
    session: SessionDep,
    _ = Depends(require_permissions("admin:domain", "write")),
):
    """Cập nhật description của Domain."""
    return await update_domain_db(session, str(domain_id), data)


@router.delete("/domains/{domain_id}", status_code=status.HTTP_200_OK)
async def delete_domain(
    domain_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:domain", "delete")),
):
    """
    Soft delete Domain — đánh dấu is_active=False.
    Dữ liệu token trong DB vẫn giữ nguyên để audit trail.
    """
    return await delete_domain_db(session, str(domain_id))


# ═══════════════════════════════════════════════════
#   DOMAIN VERSION Management
#   Tham khảo: HashiCorp Vault Key Rotation,
#              AWS KMS RotateKeyOnDemand
# ═══════════════════════════════════════════════════

@router.post(
    "/domains/{domain_id}/rotate",
    response_model=DomainRotateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rotate_domain(
    domain_id: UUID,
    session: SessionDep,
    token_session: TokenSessionDep,
    _ = Depends(require_permissions("admin:domain", "write")),
):
    """
    Rotate Domain lên version mới (tham khảo HashiCorp Vault Rotation):
    - Version cũ chuyển sang status 'rotated' (vẫn cho detokenize)
    - Tạo version mới với status 'active'
    - Tạo bảng token mới trên Token DB
    - Tất cả tokenize request sau đó sẽ dùng version mới
    """
    new_version, old_version = await rotate_domain_version(
        session, token_session, str(domain_id)
    )
    return DomainRotateResponse(
        message=f"Domain '{new_version.name}' đã rotate từ {old_version.version} lên {new_version.version}.",
        new_version=DomainResponse.model_validate(new_version),
        previous_version=DomainResponse.model_validate(old_version),
    )


@router.get(
    "/domains/{domain_id}/versions",
    response_model=DomainVersionHistory,
)
async def domain_version_history(
    domain_id: UUID,
    session: SessionDep,
    _ = Depends(require_permissions("admin:domain", "read")),
):
    """
    Xem lịch sử version của một domain.
    Tham khảo HashiCorp Vault GET /secret/metadata/:path.
    """
    domain_name, system_name, versions = await get_domain_versions(session, str(domain_id))
    return DomainVersionHistory(
        domain_name=domain_name,
        system_name=system_name,
        total_versions=len(versions),
        versions=[DomainResponse.model_validate(v) for v in versions],
    )


@router.patch(
    "/domains/{domain_id}/versions/{version_number}/deprecate",
    response_model=DomainResponse,
)
async def deprecate_version(
    domain_id: UUID,
    version_number: int = Path(..., ge=1, description="Version number cần deprecate"),
    session: SessionDep = None,
    _ = Depends(require_permissions("admin:domain", "write")),
):
    """
    Deprecate một version cụ thể — chặn detokenize trên version này.
    Chỉ version ở trạng thái 'rotated' mới deprecate được.
    Tham khảo AWS KMS DisableKey.
    """
    return await deprecate_domain_version(session, str(domain_id), version_number)
