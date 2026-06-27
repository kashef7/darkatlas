import uuid
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.relationship import Relationship
from app.models.asset import Asset
from app.schemas.relationship import RelationshipCreate
from fastapi import HTTPException, status


def _validate_relationship_rules(source_type: str, target_type: str):
    """Enforces the strict graph modeling rules dictated by ASM architecture."""
    # Convert enums to strings if necessary
    s_type = source_type.value if hasattr(source_type, 'value') else source_type
    t_type = target_type.value if hasattr(target_type, 'value') else target_type

    valid_pairs = [
        ("subdomain", "domain"),            # subdomain -> domain
        ("service", "ip_address"),          # service -> ip_address
        ("ip_address", "subdomain"),        # ip_address -> subdomain (resolution)
        ("subdomain", "ip_address"),        # subdomain -> ip_address (resolution)
        ("certificate", "domain"),          # certificate -> domain
        ("certificate", "subdomain"),       # certificate -> subdomain
        ("technology", "subdomain"),        # technology -> subdomain
        ("technology", "service")           # technology -> service
    ]

    if (s_type, t_type) not in valid_pairs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid relationship rule: Cannot link {s_type} -> {t_type}."
        )


def create_relationship(db: Session, payload: RelationshipCreate) -> Relationship:
    """Validates and creates an edge link between two assets."""
    
    source_asset = db.query(Asset).filter(Asset.id == payload.source_id).first()
    target_asset = db.query(Asset).filter(Asset.id == payload.target_id).first()

    if not source_asset or not target_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source or Target asset does not exist."
        )

    _validate_relationship_rules(source_asset.type, target_asset.type)

    existing = db.query(Relationship).filter(
        Relationship.source_id == payload.source_id,
        Relationship.target_id == payload.target_id,
        Relationship.type == payload.type
    ).first()

    if existing:
        return existing

    new_relationship = Relationship(
        id=str(uuid.uuid4()),
        source_id=payload.source_id,
        target_id=payload.target_id,
        type=payload.type
    )
    db.add(new_relationship)
    db.commit()
    db.refresh(new_relationship)
    
    return new_relationship

def get_asset_graph(db: Session, asset_id: str) -> dict:
    """Fetches an asset, all relationships touching it, and all connected assets."""
    
    center_asset = db.query(Asset).filter(Asset.id == asset_id).first()
    if not center_asset:
        raise HTTPException(status_code=404, detail="Asset not found.")

    edges = db.query(Relationship).filter(
        or_(
            Relationship.source_id == asset_id,
            Relationship.target_id == asset_id
        )
    ).all()

    connected_asset_ids = set()
    for edge in edges:
        connected_asset_ids.add(edge.source_id)
        connected_asset_ids.add(edge.target_id)
        
    connected_asset_ids.discard(asset_id)

    connected_assets = []
    if connected_asset_ids:
        connected_assets = db.query(Asset).filter(Asset.id.in_(connected_asset_ids)).all()
    return {
        "nodes": [center_asset] + connected_assets,
        "edges": edges
    }