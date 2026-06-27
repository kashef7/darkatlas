from pydantic import BaseModel, ConfigDict
from typing import List
from app.schemas.asset_schema import AssetResponse

class RelationshipBase(BaseModel):
    type: str

class RelationshipCreate(RelationshipBase):
    source_id: str
    target_id: str

class RelationshipResponse(RelationshipBase):
    id: str
    source_id: str
    target_id: str
    
    model_config = ConfigDict(from_attributes=True)

class GraphResponse(BaseModel):
    nodes: List[AssetResponse]
    edges: List[RelationshipResponse]