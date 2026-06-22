from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, Any
from app.models.asset import AssetType, AssetStatus

class AssetBase(BaseModel):
    type: AssetType
    value: str
    source: str
    tags: list[str] = []
    asset_metadata: dict[str, Any] = Field(default={}) 

class AssetCreate(AssetBase):
    id: Optional[str] = None 
    status: Optional[AssetStatus] = AssetStatus.ACTIVE

class AssetUpdate(BaseModel):
    value: Optional[str] = None
    status: Optional[AssetStatus] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    asset_metadata: Optional[dict[str, Any]] = Field(default=None)

class AssetResponse(AssetBase):
    id: str
    status: AssetStatus
    first_seen: datetime
    last_seen: datetime
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)