from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime
from typing import Optional

class SystemCreate(BaseModel):
    name: str 
    description: Optional[str] = None

class SystemResponse(BaseModel):
    id: UUID
    name: str # Định hình schema postgresql
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class DomainCreate(BaseModel):
    name: str 
    version: str = "v1.0"
    system_id: UUID
    description: Optional[str] = None

class DomainResponse(BaseModel):
    id: UUID
    name: str # Định hình table db
    version: str
    system_id: UUID
    description: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
