from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings

# 1. Engine & Session cho Admin Database (Dữ liệu quản trị, RBAC, Audit, Metadata)
admin_engine = create_async_engine(
    settings.SQLALCHEMY_ADMIN_DATABASE_URI,
    echo=False,
    future=True,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=settings.POOL_TIMEOUT,
    pool_recycle=1800,
)
AdminSessionLocal = async_sessionmaker(
    bind=admin_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# 2. Engine & Session cho Token Database (Chỉ chứa các bảng dữ liệu token động)
token_engine = create_async_engine(
    settings.SQLALCHEMY_TOKEN_DATABASE_URI,
    echo=False,
    future=True,
    pool_size=settings.POOL_SIZE,
    max_overflow=settings.MAX_OVERFLOW,
    pool_timeout=settings.POOL_TIMEOUT,
    pool_recycle=1800,
)
TokenSessionLocal = async_sessionmaker(
    bind=token_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cung cấp session cho Admin Database (Mặc định)"""
    async with AdminSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def get_token_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency cung cấp session cho Token Database (Dành cho token storage)"""
    async with TokenSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
