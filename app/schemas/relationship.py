from pydantic import BaseModel, ConfigDict
from typing import Optional

class RelationshipBase(BaseModel):
    type: str

class RelationshipCreate(BaseModel):
    source_id: str
    target_id: str
    type: str 

class RelationshipUpdate(BaseModel):
    type: Optional[str] = None

class RelationshipResponse(RelationshipBase):
    id: str 
    source_id: str
    target_id: str
    model_config = ConfigDict(from_attributes=True)