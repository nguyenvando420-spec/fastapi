from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from fastapi import HTTPException, status
from app.models.admin import System, Domain
from app.schemas.admin import SystemCreate, DomainCreate
from app.models.dynamic_token import create_dynamic_token_model

async def create_system_db(session: AsyncSession, system_in: SystemCreate) -> System:
    """Đăng ký System (Dictionary Lookup) VÀ tự động tạo Schema chứa nó trên Postgres"""
    # 1. Tra dictionary xem Schema name có bị trùng lặp chưa
    stmt = select(System).where(System.name == system_in.name)
    if (await session.execute(stmt)).scalars().first():
        raise HTTPException(status_code=400, detail="Schema (System) đã tồn tại")

    new_system = System(name=system_in.name, description=system_in.description)
    session.add(new_system)
    
    # 2. Sinh DDL lệnh RAW để tạo schema động trong database
    # Phải bắt commit trước để tránh lock nếu DDL fail (Bởi Postgresql đòi DDL chạy sạch)
    await session.flush() 
    
    try:
        await session.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{system_in.name}";'))
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Không thể tạo schema CSDL: {str(e)}")
        
    await session.commit()
    await session.refresh(new_system)
    return new_system

async def create_domain_db(session: AsyncSession, domain_in: DomainCreate) -> Domain:
    """Đăng ký Domain (Table Entity) VÀ tự động tạo Table Token bằng class runtime"""
    # 1. Verify existence of the parent system (Schema)
    system = await session.get(System, domain_in.system_id)
    if not system:
        raise HTTPException(status_code=404, detail="System ID (Schema gốc) không hợp lệ")
        
    # 2. Check overlap
    stmt = select(Domain).where((Domain.name == domain_in.name) & (Domain.system_id == domain_in.system_id))
    if (await session.execute(stmt)).scalars().first():
         raise HTTPException(status_code=400, detail="Bảng dữ liệu Table (Domain) đã tồn tại trong System này")
         
    new_domain = Domain(
        name=domain_in.name, 
        version=domain_in.version, 
        system_id=domain_in.system_id, 
        description=domain_in.description
    )
    session.add(new_domain)
    await session.flush()

    # 3. Động học (Runtime) mượn Factory để đẻ ra object Model Table từ file dynamic_token
    DynamicModel = create_dynamic_token_model(schema_name=system.name, table_name=domain_in.name)
    
    # 4. Yêu cầu SQLAlchemy DDL tạo bảng này dựa trên connection async hiện tại
    def create_table_ddl(conn):
        DynamicModel.__table__.create(conn, checkfirst=True)
    
    try:
        conn = await session.connection()
        await conn.run_sync(create_table_ddl)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=f"Không thể tạo table: {str(e)}")
        
    await session.commit()
    await session.refresh(new_domain)
    return new_domain
