from typing import Optional
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import BaseModel

class System(BaseModel):
    """
    Bảng quản lý danh sách các System.
    Mỗi System đại diện cho một Schema riêng biệt trong PostgreSQL.
    """
    __tablename__ = "systems"
    
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    domains: Mapped[list["Domain"]] = relationship("Domain", back_populates="system", cascade="all, delete-orphan")

class Domain(BaseModel):
    """
    Bảng quản lý danh sách các Domain thuộc về System.
    Mỗi Domain và Version đại diện cho một Table trong schema của System.
    """
    __tablename__ = "domains"
    
    name: Mapped[str] = mapped_column(String(100), index=True)
    version: Mapped[str] = mapped_column(String(50), default="v1")
    system_id: Mapped[str] = mapped_column(ForeignKey("systems.id", ondelete="CASCADE"), index=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    system: Mapped["System"] = relationship("System", back_populates="domains")
