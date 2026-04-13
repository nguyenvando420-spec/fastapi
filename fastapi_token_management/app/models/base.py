import uuid
from datetime import datetime
from sqlalchemy import func, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    """Cơ sở (Base) cho tất cả các SQLAlchemy Models của dự án"""
    pass

class BaseModel(Base):
    """
    Abstract Model cung cấp sẵn các cột mặc định cho mọi bảng (id, created_at, updated_at).
    Sử dụng timezone=True để tương thích chuẩn Enterprise.
    """
    __abstract__ = True

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
