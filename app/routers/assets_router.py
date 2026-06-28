from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.asset_schema import AssetCreate, AssetResponse, AssetUpdate
from app.services import asset_service
from typing import Literal
from app.dependencies import require_admin, require_editor_or_admin

router = APIRouter(prefix="/assets", tags=["Assets"])


# ===========================================================================
# IMPORTANT: Static routes MUST be registered before parameterized routes.
# /bulk-import is registered first to prevent FastAPI from intercepting it as
# /{asset_id} = "bulk-import" at runtime.
# ===========================================================================

@router.post("/bulk-import", status_code=status.HTTP_201_CREATED)
def bulk_import(
    payload: list[dict],
    db: Session = Depends(get_db),
    _ = Depends(require_admin),
):
    """Accepts an array of scanned assets and processes them in a fault-tolerant
    savepoint-based batch transaction. Each item is individually recoverable.
    """
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payload list cannot be empty.",
        )
    result = asset_service.process_bulk_import(db, payload)
    return {
        "message": "Bulk data processing completed successfully.",
        "details": result,
    }


@router.get("/", response_model=list[AssetResponse])
def read_assets(
    page: int = Query(default=1, ge=1, description="The page number to retrieve"),
    size: int = Query(default=20, ge=1, le=100, description="Number of results per page"),
    type: str | None = Query(default=None, description="Filter by asset type"),
    status: str | None = Query(default=None, description="Filter by asset lifecycle status"),
    tag: str | None = Query(default=None, description="Filter by a single specific tag"),
    value_contains: str | None = Query(
        default=None, description="Case-insensitive substring search over asset values"
    ),
    sort_by: Literal["first_seen", "last_seen", "value", "type"] = Query(default="first_seen"),
    sort_order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db),
):
    """Retrieves a paginated list of assets matching optional filter criteria."""
    return asset_service.get_all_assets(
        db=db,
        page=page,
        size=size,
        type=type,
        status=status,
        tag=tag,
        value_contains=value_contains,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    _ = Depends(require_editor_or_admin),
):
    """Creates a new tracked asset or merges into an existing one via the idempotent engine."""
    return asset_service.create_new_asset(db, payload)


@router.get("/{asset_id}", response_model=AssetResponse)
def read_single_asset(asset_id: str, db: Session = Depends(get_db)):
    """Fetches a full asset record by its unique identifier."""
    asset = asset_service.get_asset_by_id(db, asset_id)
    if not asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID '{asset_id}' not found.",
        )
    return asset


@router.patch("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    _ = Depends(require_editor_or_admin),
):
    """Applies a safe PATCH delta over mutable asset metadata fields."""
    updated_asset = asset_service.update_existing_asset(db, asset_id, payload)
    if not updated_asset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID '{asset_id}' not found. Update rejected.",
        )
    return updated_asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    _ = Depends(require_admin),
):
    """Permanently removes an asset from active database state."""
    success = asset_service.delete_asset_by_id(db, asset_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asset with ID '{asset_id}' not found. Erasure rejected.",
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{asset_id}/stale", response_model=AssetResponse)
def flag_asset_stale(
    asset_id: str,
    db: Session = Depends(get_db),
    _ = Depends(require_editor_or_admin),
):
    """Manually marks an asset as stale via the standard update service."""
    stale_payload = AssetUpdate(status="stale")
    updated_asset = asset_service.update_existing_asset(db, asset_id, stale_payload)
    if not updated_asset:
        raise HTTPException(status_code=404, detail="Target asset not found.")
    return updated_asset