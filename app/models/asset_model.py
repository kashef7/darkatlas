from sqlalchemy import Column, ARRAY, String, DateTime, Enum, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
from datetime import datetime, timezone
import enum
import uuid


class AssetType(str, enum.Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    SERVICE = "service"
    CERTIFICATE = "certificate"
    TECHNOLOGY = "technology"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class Asset(Base):
    __tablename__ = "assets"

    # Explicit callable lambda to produce string UUIDs — never raw uuid.UUID objects
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    type = Column(Enum(AssetType), nullable=False, index=True)
    status = Column(Enum(AssetStatus), default=AssetStatus.ACTIVE, nullable=False, index=True)
    value = Column(String, nullable=False, index=True)

    # Timezone-aware timestamps for correct UTC handling
    first_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    source = Column(String, nullable=False)
    tags = Column(ARRAY(String), default=list)
    asset_metadata = Column(JSONB, default=dict)

    # Database-level composite unique constraint to prevent race-condition twin inserts
    __table_args__ = (
        UniqueConstraint("type", "value", name="uq_asset_type_value"),
    )