from datetime import datetime
import uuid
from sqlalchemy import String, func, text
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID

class TokenBase(DeclarativeBase):
    """Base dành riêng cho Token Database (Tránh mix với Admin Base)"""
    pass

def create_dynamic_token_model(schema_name: str, table_name: str):
    """
    Factory function sinh ra một class SQLAlchemy (Table) kế thừa động.
    Khi gọi hàm này, hệ thống sẽ ánh xạ (map) vào đúng schema và table do user định nghĩa.
    
    Bảng này tuân thủ cấu trúc của đề bài:
    - Lưu token
    - Dữ liệu bị mã hóa DEK + Data
    - KEK lưu theo record token
    - 2 metadata là id và created_at
    """
    
    class DynamicToken(TokenBase):
        __tablename__ = table_name
        __table_args__ = {'schema': schema_name, 'extend_existing': True}

        id: Mapped[uuid.UUID] = mapped_column(
            UUID(as_uuid=True), 
            primary_key=True, 
            server_default=text("gen_random_uuid()")
        )
        
        # Output trả về của quá trình generate. (Có thể là hmac signature, uuid, alphanumeric...)
        token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
        
        # Đây là (DEK + Data) đã bị mã hóa
        encrypt_dek_data: Mapped[str] = mapped_column(String, nullable=False)
        
        # Key Encryption Key dùng để bọc/mở DEK
        kek: Mapped[str] = mapped_column(String, nullable=False)
        
        created_at: Mapped[datetime] = mapped_column(server_default=func.now())
        
    return DynamicToken
