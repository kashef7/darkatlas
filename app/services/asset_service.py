import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import desc, asc, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.asset_model import Asset, AssetStatus
from app.schemas.asset_schema import AssetCreate, AssetUpdate


# ---------------------------------------------------------------------------
# Internal Utilities
# ---------------------------------------------------------------------------

def _deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Recursively merges `incoming` into a copy of `base`.

    Rules:
    - If a key exists as a nested dict in *both* objects, recurse into it.
    - Otherwise, the incoming value overwrites the base value.
    - Keys present only in base are preserved untouched.
    """
    result = base.copy()
    for key, value in incoming.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _handle_asset_duplication(db: Session, item_data: dict[str, Any]) -> tuple[Asset, bool]:
    """Core deduplication and merge engine for a single asset payload.

    Returns:
        A tuple of (asset_orm_object, was_existing) where was_existing=True
        means the record already existed and was updated (re-sighted).
    """
    existing_asset = (
        db.query(Asset)
        .filter(
            Asset.type == item_data.get("type"),
            Asset.value == item_data.get("value"),
        )
        .first()
    )

    if existing_asset:
        # --- Re-Sighting Lifecycle Update ---
        # Use timezone-aware UTC timestamp for compliance with modern Python standards
        existing_asset.last_seen = datetime.now(timezone.utc)

        # Automatically restore operational status from stale or archived states
        if existing_asset.status in (AssetStatus.STALE, AssetStatus.ARCHIVED):
            existing_asset.status = AssetStatus.ACTIVE

        # Tag union: merge without duplicates, preserving historical tag set
        incoming_tags: list[str] = item_data.get("tags") or []
        existing_tags: list[str] = existing_asset.tags or []
        existing_asset.tags = list(set(existing_tags) | set(incoming_tags))

        # Deep recursive metadata merge — preserves nested JSON context
        incoming_meta: dict[str, Any] = item_data.get("asset_metadata") or {}
        existing_meta: dict[str, Any] = existing_asset.asset_metadata or {}
        existing_asset.asset_metadata = _deep_merge(existing_meta, incoming_meta)

        return existing_asset, True

    else:
        # --- New Asset Creation ---
        new_id = item_data.get("id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        new_asset = Asset(
            id=new_id,
            type=item_data.get("type"),
            value=item_data.get("value"),
            status=item_data.get("status", AssetStatus.ACTIVE),
            source=item_data.get("source"),
            tags=item_data.get("tags") or [],
            asset_metadata=item_data.get("asset_metadata") or {},
            first_seen=now,
            last_seen=now,
        )
        db.add(new_asset)
        return new_asset, False


# ---------------------------------------------------------------------------
# Public Service API
# ---------------------------------------------------------------------------

def create_new_asset(db: Session, payload: AssetCreate) -> Asset:
    """Creates a new asset or updates an existing one via the idempotent merging engine."""
    # model_dump() uses field names (asset_metadata), not aliases — correct for internal use
    db_data = payload.model_dump()
    asset, _ = _handle_asset_duplication(db, db_data)
    db.commit()
    db.refresh(asset)
    return asset


def process_bulk_import(db: Session, raw_assets: list[dict]) -> dict:
    """Ingests an array of scanned assets using per-item savepoint transactions.

    Each item is wrapped in an isolated db.begin_nested() savepoint. If a
    single item fails validation or database insertion, only that savepoint is
    rolled back — the rest of the batch continues processing uninterrupted.

    Returns:
        {
            "created": <int>,
            "updated_merged": <int>,
            "failed": [{"index": i, "message": "...", "input": {...}}, ...]
        }
    """
    created_count = 0
    updated_count = 0
    failed_list: list[dict[str, Any]] = []

    for index, raw_item in enumerate(raw_assets):
        # Open a micro-savepoint for this individual item
        sp = db.begin_nested()
        try:
            # Validate and normalise through Pydantic — catches structural errors early.
            # AssetCreate accepts both "metadata" and "asset_metadata" key spellings.
            validated = AssetCreate.model_validate(raw_item)

            # model_dump() returns field-name keys (asset_metadata), suitable for ORM
            item_data = validated.model_dump()

            _, was_existing = _handle_asset_duplication(db, item_data)

            # Release savepoint — this item is safely written to the session
            sp.commit()

            if was_existing:
                updated_count += 1
            else:
                created_count += 1

        except ValidationError as exc:
            sp.rollback()
            failed_list.append({
                "index": index,
                "message": f"Validation error: {exc.error_count()} issue(s) — {exc.errors()[0]['msg']}",
                "input": raw_item,
            })

        except KeyError as exc:
            sp.rollback()
            failed_list.append({
                "index": index,
                "message": f"Missing required key: {exc}",
                "input": raw_item,
            })

        except SQLAlchemyError as exc:
            sp.rollback()
            failed_list.append({
                "index": index,
                "message": f"Database error: {str(exc)}",
                "input": raw_item,
            })

        except Exception as exc:  # noqa: BLE001 — broad catch intentional for batch resilience
            sp.rollback()
            failed_list.append({
                "index": index,
                "message": f"Unexpected error: {str(exc)}",
                "input": raw_item,
            })

    # Commit the main transaction — all successfully processed savepoints persist
    db.commit()

    return {
        "created": created_count,
        "updated_merged": updated_count,
        "failed": failed_list,
    }


def get_asset_by_id(db: Session, asset_id: str) -> Asset | None:
    """Retrieves a single asset by its primary key identifier."""
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
    sort_order: str = "desc",
) -> list[Asset]:
    """Retrieves a paginated list of assets applying search queries, filters, and custom sorting."""
    query = db.query(Asset)

    if type:
        query = query.filter(Asset.type == type)
    if status:
        query = query.filter(Asset.status == status)
    if tag:
        if db.get_bind().dialect.name == "postgresql":
            query = query.filter(Asset.tags.any(tag))
        else:
            tag_table = func.json_each(Asset.tags).table_valued("value")
            query = query.filter(tag_table.c.value == tag)
    if value_contains:
        query = query.filter(Asset.value.ilike(f"%{value_contains}%"))

    sort_column = getattr(Asset, sort_by, Asset.first_seen)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(asc(sort_column))

    offset_value = (page - 1) * size
    return query.offset(offset_value).limit(size).all()


def update_existing_asset(db: Session, asset_id: str, payload: AssetUpdate) -> Asset | None:
    """Modifies an existing asset's mutable properties via a safe PATCH operation."""
    db_asset = get_asset_by_id(db, asset_id)
    if not db_asset:
        return None

    # exclude_unset=True ensures only explicitly provided fields are updated
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_asset, key, value)

    db_asset.last_seen = datetime.now(timezone.utc)
    db.commit()
    db.refresh(db_asset)
    return db_asset


def delete_asset_by_id(db: Session, asset_id: str) -> bool:
    """Permanently removes a record from database storage."""
    db_asset = get_asset_by_id(db, asset_id)
    if not db_asset:
        return False

    db.delete(db_asset)
    db.commit()
    return True