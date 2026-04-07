from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import BaseModel

class SystemSetting(BaseModel):
    """
    Lưu trữ các cấu hình linh hoạt của hệ thống dưới dạng Key-Value.
    Ví dụ: audit_retention_days = "90"
    """
    __tablename__ = "system_settings"
    
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    value: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(String(255), nullable=True)
