from pydantic import BaseModel, field_validator
from typing import List, Optional, Dict
from uuid import UUID


# Giới hạn tối đa mỗi batch — phù hợp với enterprise tokenization platforms
MAX_BATCH_SIZE = 1_000


class TokenizeRequest(BaseModel):
    system_name: str
    domain_name: str
    data: List[str]

    @field_validator("data")
    @classmethod
    def validate_data_size(cls, v: List[str]) -> List[str]:
        if len(v) == 0:
            raise ValueError("Danh sách data không được rỗng.")
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(f"Tối đa {MAX_BATCH_SIZE} items mỗi request. Nhận được {len(v)}.")
        return v


class TokenizeResponse(BaseModel):
    message: str
    count: int
    results: Dict[str, str]          # {original_data: token}


class DeTokenizeRequest(BaseModel):
    system_name: str
    domain_name: str
    tokens: List[str]

    @field_validator("tokens")
    @classmethod
    def validate_tokens_size(cls, v: List[str]) -> List[str]:
        if len(v) == 0:
            raise ValueError("Danh sách tokens không được rỗng.")
        if len(v) > MAX_BATCH_SIZE:
            raise ValueError(f"Tối đa {MAX_BATCH_SIZE} tokens mỗi request. Nhận được {len(v)}.")
        return v


class DeTokenizeResponse(BaseModel):
    results: Dict[str, Optional[str]]   # {token: decrypted_data or None}
    missing_tokens: List[str]           # Token không tìm thấy trong DB


class TokenDomainStats(BaseModel):
    """Thống kê token count cho một domain."""
    system: str
    domain: str
    version: str
    token_count: int


class TokenStatsResponse(BaseModel):
    """Response tổng hợp thống kê token."""
    items: List[TokenDomainStats]
