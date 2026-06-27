from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.relationship import RelationshipCreate, RelationshipResponse, GraphResponse
from app.services import relationship_service

router = APIRouter(prefix="/relationships", tags=["Relationships"])

@router.post("/", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED)
def create_relationship_link(payload: RelationshipCreate, db: Session = Depends(get_db)):
    """
    Creates a directional graph relationship between two existing assets.
    Enforces strict architectural rules (e.g., subdomain -> domain).
    """
    return relationship_service.create_relationship(db, payload)


@router.get("/graph/{asset_id}", response_model=GraphResponse)
def read_asset_graph(asset_id: str, db: Session = Depends(get_db)):
    """
    Retrieves the complete relationship network for a specific asset.
    Returns standard 'nodes' and 'edges' arrays optimized for graph visualization UI.
    """
    return relationship_service.get_asset_graph(db, asset_id)