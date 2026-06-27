from pydantic import BaseModel, ConfigDict, Field, model_validator
from datetime import datetime
from typing import Optional, Any
from app.models.asset_model import AssetType, AssetStatus


def _map_metadata_key(data: Any) -> Any:
    """Map incoming JSON 'metadata' key to asset_metadata without touching ORM .metadata."""
    if isinstance(data, dict) and "metadata" in data and "asset_metadata" not in data:
        data = dict(data)
        data["asset_metadata"] = data.pop("metadata")
    return data


class AssetBase(BaseModel):
    """Base DTO — the public API field name is `metadata`; the ORM column is `asset_metadata`.
    Incoming JSON may use `metadata`; responses serialize as `metadata` via serialization_alias.
    validation_alias is intentionally NOT used — SQLAlchemy ORM instances expose a `.metadata`
    attribute (the table MetaData registry) which would collide with Pydantic alias resolution.
    """

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    type: AssetType
    value: str
    source: str
    tags: list[str] = Field(default_factory=list)

    asset_metadata: dict[str, Any] = Field(
        default_factory=dict,
        serialization_alias="metadata",
    )

    @model_validator(mode="before")
    @classmethod
    def accept_metadata_alias(cls, data: Any) -> Any:
        return _map_metadata_key(data)


class AssetCreate(AssetBase):
    id: Optional[str] = None
    status: Optional[AssetStatus] = AssetStatus.ACTIVE


class AssetUpdate(BaseModel):
    """Partial PATCH DTO — same aliasing rules as AssetBase."""

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)

    value: Optional[str] = None
    status: Optional[AssetStatus] = None
    source: Optional[str] = None
    tags: Optional[list[str]] = None
    asset_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        serialization_alias="metadata",
    )

    @model_validator(mode="before")
    @classmethod
    def accept_metadata_alias(cls, data: Any) -> Any:
        return _map_metadata_key(data)


class AssetResponse(AssetBase):
    """Full read DTO — inherits aliasing from AssetBase."""

    id: str
    status: AssetStatus
    first_seen: datetime
    last_seen: datetime