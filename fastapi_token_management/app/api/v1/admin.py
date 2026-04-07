from fastapi import APIRouter, Depends, status
from app.api.dependencies import SessionDep, require_permissions
from app.schemas.admin import SystemCreate, SystemResponse, DomainCreate, DomainResponse
from app.services.admin_service import create_system_db, create_domain_db

router = APIRouter()

@router.post("/systems", response_model=SystemResponse, status_code=status.HTTP_201_CREATED)
async def create_system(
    system_in: SystemCreate, 
    session: SessionDep,
    _ = Depends(require_permissions("admin:system", "create"))
):
    """
    Endpoint khởi tạo System:
    - Ghi nhận Dictionary vào Data Layer
    - Auto Run DDL `CREATE SCHEMA <system-name>` ở PostgreSQL
    """
    return await create_system_db(session, system_in)


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def create_domain(
    domain_in: DomainCreate, 
    session: SessionDep,
    _ = Depends(require_permissions("admin:domain", "create"))
):
    """
    Endpoint khởi tạo Domain (Table của System gốc):
    - Đẩy class SQLAlchemy Factory Dynamic
    - Tự động DDL table DB vật lý ngay lập tức có cột token, encrypt_dek_data, kek.
    """
    return await create_domain_db(session, domain_in)
