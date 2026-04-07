from typing import Optional
from sqlalchemy import String, Integer, Float, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel
from datetime import datetime

class AuditLog(BaseModel):
    __tablename__ = "audit_logs"
    
    # meta
    request_type: Mapped[str] = mapped_column(String(50), index=True) # tokenize, detokenize, permission, etc
    system: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    domain: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    user: Mapped[Optional[str]] = mapped_column(String(100), index=True) # username
    version: Mapped[Optional[str]] = mapped_column(String(50))
    
    # metrics
    request_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    duration: Mapped[float] = mapped_column(Float) # in seconds
    total_token: Mapped[int] = mapped_column(Integer, default=0)
    
    # status
    auth_status: Mapped[str] = mapped_column(String(20)) # allowed, denied
    status: Mapped[str] = mapped_column(String(20)) # success, fail
    
    # detail
    detail: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True) # reason for fail/denied
