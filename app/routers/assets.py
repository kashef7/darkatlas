from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.services import asset_service
from typing import Literal

router = APIRouter(prefix="/assets", tags=["Assets"])

@router.get("/", response_model=list[AssetResponse])
def read_assets(
    page: int = Query(default=1, ge=1, description="The page number to retrieve"),
    size: int = Query(default=20, ge=1, le=100, description="Number of results per page"),

    type: str | None = Query(default=None, description="Filter by asset type"),
    status: str | None = Query(default=None, description="Filter by asset lifecycle status"),
    tag: str | None = Query(default=None, description="Filter by a single specific tag tag"),
    value_contains: str | None = Query(default=None, description="Case-insensitive substring search over asset values"),

    sort_by: Literal["first_seen", "last_seen", "value", "type"] = Query(default="first_seen"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    
    db: Session = Depends(get_db)
):
    """Retrieves a paginated list of assets matching optional criteria filters."""
    return asset_service.get_all_assets(
        db=db,
        page=page,
        size=size,
        type=type,
        status=status,
        tag=tag,
        value_contains=value_contains,
        sort_by=sort_by,
        sort_order=sort_order
    )

@router.get("/{asset_id}", response_model=AssetResponse)
def read_single_asset(asset_id: str, db: Session = Depends(get_db)):
    """Fetches full asset records by their unique identifier key."""
    asset = asset_service.get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Asset with ID '{asset_id}' not found."
        )
    return asset

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)):
    """Creates a new tracked asset inventory infrastructure signature record."""
    return asset_service.create_new_asset(db, payload)


@router.patch("/{asset_id}", response_model=AssetResponse)
def update_asset(asset_id: str, payload: AssetUpdate, db: Session = Depends(get_db)):
    """Applies a safe properties delta alteration PATCH over mutable asset metadata fields."""
    updated_asset = asset_service.update_existing_asset(db, asset_id, payload)
    if not updated_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Asset with ID '{asset_id}' not found. Update rejected."
        )
    return updated_asset

@router.delete("/{asset_id}", status_code=status.HTTP_200_OK)
def delete_asset(asset_id: str, db: Session = Depends(get_db)):
    """Removes a signature tracker completely out of active database state inventories."""
    success = asset_service.delete_asset_by_id(db, asset_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail=f"Asset with ID '{asset_id}' not found. Erasure rejected."
        )
    return {"message": f"Asset '{asset_id}' successfully deleted out of data states."}