from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List
from uuid import UUID

class AuditLogResponse(BaseModel):
    id: UUID
    request_type: str
    system: Optional[str]
    domain: Optional[str]
    user: Optional[str]
    version: Optional[str]
    request_time: datetime
    duration: float
    total_token: int
    auth_status: str
    status: str
    detail: Optional[str]
    
    model_config = ConfigDict(from_attributes=True)

class AuditLogListResponse(BaseModel):
    total: int
    logs: List[AuditLogResponse]

class AuditRetentionUpdate(BaseModel):
    retention_days: int
