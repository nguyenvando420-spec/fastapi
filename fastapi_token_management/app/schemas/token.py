from pydantic import BaseModel
from typing import List, Optional
from uuid import UUID

class TokenizeRequest(BaseModel):
    system_name: str
    domain_name: str
    data: List[str]

class TokenizeResponse(BaseModel):
    message: str
    count: int
    results: dict[str, str]

class DeTokenizeRequest(BaseModel):
    system_name: str
    domain_name: str
    tokens: List[str]

class DeTokenizeResponse(BaseModel):
    results: dict[str, Optional[str]]
