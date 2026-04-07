import asyncio
import os
import pytest
from sqlalchemy import text, NullPool
from app.core.config import settings

settings.POSTGRES_DB_ADMIN = "token_db_test_admin"
settings.POSTGRES_DB_TOKEN = "token_db_test_token"
settings.POSTGRES_SERVER = "127.0.0.1"

async def create_test_db_if_not_exists(db_name: str):
    """Kết nối vào postgres DB để tạo DB test nếu chưa có"""
    # Sử dụng chuỗi kết nối đến db 'postgres' mặc định
    admin_url = settings.get_db_url("postgres")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        result = await conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{db_name}'"))
        if not result.scalar():
            await conn.execute(text(f"CREATE DATABASE {db_name}"))
    await engine.dispose()

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from app.models.base import Base
from app.main import app
from app.core.database import get_db_session, get_token_db_session

@pytest.fixture(scope="session")
def event_loop():
    """Tạo event loop duy nhất cho toàn bộ session test."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="session")
async def admin_engine(event_loop):
    engine = create_async_engine(settings.SQLALCHEMY_ADMIN_DATABASE_URI, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="session")
async def token_engine(event_loop):
    engine = create_async_engine(settings.SQLALCHEMY_TOKEN_DATABASE_URI, echo=False, poolclass=NullPool)
    yield engine
    await engine.dispose()

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database(admin_engine, token_engine):
    """Khởi tạo sạch cả 2 database test"""
    # 0. Đảm bảo DB tồn tại
    await create_test_db_if_not_exists("token_db_test_admin")
    await create_test_db_if_not_exists("token_db_test_token")

    # 1. Setup Admin DB
    async with admin_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.run_sync(Base.metadata.create_all)
    
    # 2. Setup Token DB
    async with token_engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    yield

@pytest_asyncio.fixture
async def db_session(admin_engine):
    """Session cho Admin DB (Dùng cho hầu hết test)"""
    async with AsyncSession(admin_engine, expire_on_commit=False) as session:
        yield session
        await session.close()

@pytest_asyncio.fixture
async def token_db_session(token_engine):
    """Session cho Token DB (Dùng khi test storage)"""
    async with AsyncSession(token_engine, expire_on_commit=False) as session:
        yield session
        await session.close()

@pytest_asyncio.fixture(autouse=True)
async def override_get_db(db_session, token_db_session):
    """Override cả 2 dependency session cho app"""
    async def _get_admin_db():
        yield db_session
    async def _get_token_db():
        yield token_db_session
    
    app.dependency_overrides[get_db_session] = _get_admin_db
    app.dependency_overrides[get_token_db_session] = _get_token_db
    yield
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_token(db_session: AsyncSession) -> str:
    """Cung cấp JWT cho Admin User (Lưu trong Admin DB)"""
    from app.models.rbac import User, Role, Permission
    from app.core.security import create_access_token, get_password_hash
    import uuid
    
    username = f"user_{uuid.uuid4().hex[:8]}"
    hashed_password = get_password_hash("password123")
    
    super_perm = Permission(resource="*", action="*")
    db_session.add(super_perm)
    
    admin_role = Role(
        name=f"admin_{uuid.uuid4().hex[:8]}", 
        description="Global Admin",
        permissions=[super_perm]
    )
    db_session.add(admin_role)
    
    user = User(
        username=username,
        email=f"{username}@test.com",
        hashed_password=hashed_password,
        roles=[admin_role]
    )
    db_session.add(user)
    await db_session.commit()
    
    return create_access_token(data={"sub": user.username})
