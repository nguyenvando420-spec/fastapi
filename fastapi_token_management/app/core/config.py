import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI Token Management"
    
    # Database Settings (Pydantic sẽ tự nạp từ ENV nếu có)
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    
    # Admin Database (Users, Roles, Audit, Metadata)
    POSTGRES_DB_ADMIN: str = "admin_db"
    
    # Token Database (Token tables)
    POSTGRES_DB_TOKEN: str = "token_db"
    
    # Config Connection Pool cho asyncpg
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30

    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_jwt_key_development_only")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7 # Mặc định 7 ngày

    # Initial User Setup
    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "admin_password_123"

    def get_db_url(self, db_name: str) -> str:
        """Sinh ra chuỗi kết nối cho một database cụ thể"""
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{db_name}"

    @property
    def SQLALCHEMY_ADMIN_DATABASE_URI(self) -> str:
        return self.get_db_url(self.POSTGRES_DB_ADMIN)

    @property
    def SQLALCHEMY_TOKEN_DATABASE_URI(self) -> str:
        return self.get_db_url(self.POSTGRES_DB_TOKEN)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore")

settings = Settings()
