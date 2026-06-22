import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetUpdate
from sqlalchemy import desc, asc

def get_asset_by_id(db: Session, asset_id: str) -> Asset | None:
    """Fetches a single asset from the database by its primary key ID."""
    return db.query(Asset).filter(Asset.id == asset_id).first()


def get_all_assets(
    db: Session, 
    page: int = 1, 
    size: int = 20,
    type: str | None = None,
    status: str | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: str = "first_seen",
    sort_order: str = "desc"
) -> list[Asset]:
    """Retrieves assets dynamically applying filters, sorting, and page-based pagination."""
    
    query = db.query(Asset)

    if type:
        query = query.filter(Asset.type == type)
        
    if status:
        query = query.filter(Asset.status == status)
        
    if tag:
        query = query.filter(Asset.tags.any(tag))
        
    if value_contains:
        query = query.filter(Asset.value.ilike(f"%{value_contains}%"))

    sort_column = getattr(Asset, sort_by, Asset.first_seen)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))
    offset_value = (page - 1) * size
    return query.offset(offset_value).limit(size).all()

def create_new_asset(db: Session, payload: AssetCreate) -> Asset:
    """Validates and writes a brand new asset record to the database."""
    db_data = payload.model_dump()
    new_asset = Asset(**db_data)
    db.add(new_asset)
    db.commit()
    db.refresh(new_asset) 
    return new_asset

def update_existing_asset(db: Session, asset_id: str, payload: AssetUpdate) -> Asset | None:
    """Applies a partial update (PATCH) to an existing asset dynamically."""
    db_asset = get_asset_by_id(db, asset_id)
    if not db_asset:
        return None

    update_data = payload.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(db_asset, key, value)

    db_asset.last_seen = datetime.utcnow()

    db.commit()
    db.refresh(db_asset)
    return db_asset

def delete_asset_by_id(db: Session, asset_id: str) -> bool:
    """Removes an asset from the database. Returns True if deleted, False if not found."""
    db_asset = get_asset_by_id(db, asset_id)
    if not db_asset:
        return False

    db.delete(db_asset)
    db.commit()
    return True