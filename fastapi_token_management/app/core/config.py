import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Thông tin ứng dụng ──────────────────────────────────────────────────
    PROJECT_NAME: str = "FastAPI Token Management"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"         # development | staging | production

    # ── PostgreSQL ───────────────────────────────────────────────────────────
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB_ADMIN: str = "admin_db"  # Chứa: RBAC, Audit, Metadata
    POSTGRES_DB_TOKEN: str = "token_db"  # Chứa: Token tables (schema động)

    # ── Connection Pool ──────────────────────────────────────────────────────
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 10
    POOL_TIMEOUT: int = 30

    # ── JWT Authentication ───────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super_secret_jwt_key_development_only")
    ALGORITHM: str = "HS256"
    # Access token: ngắn hạn (60 phút mặc định)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    # Refresh token: dài hạn (7 ngày mặc định)
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Danh sách domain được phép gọi API (production nên set cụ thể)
    ALLOWED_ORIGINS: List[str] = ["*"]
    ALLOWED_METHODS: List[str] = ["*"]
    ALLOWED_HEADERS: List[str] = ["*"]

    # ── Initial Admin User ───────────────────────────────────────────────────
    FIRST_SUPERUSER: str = "admin"
    FIRST_SUPERUSER_EMAIL: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "Admin_Password_123"

    # ── Auth Backend ─────────────────────────────────────────────────────────
    # "local" = xác thực qua DB nội bộ | "ldap" = xác thực qua LDAP/AD
    AUTH_BACKEND: str = "local"

    # ── LDAP Settings (chỉ dùng khi AUTH_BACKEND="ldap") ────────────────────
    LDAP_SERVER: str = ""
    LDAP_PORT: int = 389
    LDAP_USE_SSL: bool = False
    LDAP_BIND_DN: str = ""
    LDAP_BIND_PASSWORD: str = ""
    LDAP_BASE_DN: str = ""
    LDAP_USER_SEARCH_FILTER: str = "(uid={username})"
    LDAP_USER_ATTR_USERNAME: str = "uid"
    LDAP_USER_ATTR_EMAIL: str = "mail"
    LDAP_USER_ATTR_DISPLAY_NAME: str = "cn"
    LDAP_GROUP_SEARCH_BASE: str = ""
    LDAP_GROUP_SEARCH_FILTER: str = "(objectClass=groupOfNames)"
    LDAP_GROUP_MEMBER_ATTR: str = "member"
    LDAP_GROUP_NAME_ATTR: str = "cn"
    LDAP_SYNC_GROUPS: bool = True
    LDAP_CONNECTION_TIMEOUT: int = 10

    # ── Helpers ──────────────────────────────────────────────────────────────

    def get_db_url(self, db_name: str) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{db_name}"
        )

    @property
    def SQLALCHEMY_ADMIN_DATABASE_URI(self) -> str:
        return self.get_db_url(self.POSTGRES_DB_ADMIN)

    @property
    def SQLALCHEMY_TOKEN_DATABASE_URI(self) -> str:
        return self.get_db_url(self.POSTGRES_DB_TOKEN)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
