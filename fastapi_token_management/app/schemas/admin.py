import re
from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime
from typing import Optional, List, TypeVar, Generic


# ── Generic Paginated Response ──────────────────────────────────────────────
T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Chuẩn response phân trang cho mọi list endpoint."""
    total: int
    limit: int
    offset: int
    items: List[T]


# ── Regex validate tên System/Domain (safe SQL identifier) ───────────────────
_SAFE_NAME_RE = re.compile(r'^[a-z][a-z0-9_]{0,99}$')


def _validate_safe_name(v: str) -> str:
    """
    Chỉ cho phép tên bắt đầu bằng chữ thường, chứa a-z, 0-9, dấu gạch dưới.
    Ngăn SQL injection thông qua tên schema/table.
    """
    if not _SAFE_NAME_RE.match(v):
        raise ValueError(
            "Tên chỉ được chứa chữ thường, số và dấu gạch dưới (_), "
            "phải bắt đầu bằng chữ cái, tối đa 100 ký tự."
        )
    return v


# ── System Schemas ───────────────────────────────────────────────────────────

class SystemCreate(BaseModel):
    name: str
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_safe_name(v)


class SystemUpdate(BaseModel):
    """Chỉ cho phép cập nhật description; name là bất biến sau khi tạo schema."""
    description: Optional[str] = None


class SystemResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Domain Schemas ───────────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    """
    Tạo Domain mới — version tự động = v1, không cần user truyền vào.
    Tham khảo HashiCorp Vault: version đầu tiên luôn là 1.
    """
    name: str
    system_id: UUID
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return _validate_safe_name(v)


class DomainUpdate(BaseModel):
    """Chỉ cho phép cập nhật description."""
    description: Optional[str] = None


class DomainResponse(BaseModel):
    """Response chuẩn cho Domain, bao gồm version lifecycle info."""
    id: UUID
    name: str
    version: str
    version_number: int
    status: str
    system_id: UUID
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DomainRotateResponse(BaseModel):
    """
    Response khi rotate version thành công.
    Trả về cả version mới lẫn version cũ để client biết rõ sự thay đổi.
    Tham khảo AWS KMS RotateKeyOnDemand response.
    """
    message: str
    new_version: DomainResponse
    previous_version: DomainResponse


class DomainVersionHistory(BaseModel):
    """
    Lịch sử version của một domain.
    Tham khảo HashiCorp Vault GET /secret/metadata/:path response.
    """
    domain_name: str
    system_name: str
    total_versions: int
    versions: List[DomainResponse]
