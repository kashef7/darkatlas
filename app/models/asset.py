from sqlalchemy import Column, ARRAY , String, DateTime, Enum
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
from datetime import datetime
import enum
import uuid

class AssetType(str,enum.Enum):
  DOMAIN = "domain"
  SUBDOMAIN = "subdomain"
  IP_ADDRESS = "ip_address"
  SERVICE = "service"
  CERTIFICATE = "certificate"
  TECHNOLOGY = "technology"
  

class AssetStatus(str,enum.Enum):
  ACTIVE = "active"
  STALE = "stale"
  ARCHIVED = "archived"

class Asset(Base):
  __tablename__ = "assets"
  id = Column(String(36) , primary_key=True , default=uuid.uuid4)
  type = Column(Enum(AssetType) , nullable=False)
  status = Column(Enum(AssetStatus) , default=AssetStatus.ACTIVE , nullable=False)
  value = Column(String,nullable=False, index=True)
  first_seen = Column(DateTime,default=datetime.utcnow , nullable=False)
  last_seen = Column(DateTime,default=datetime.utcnow,nullable=False)
  source = Column(String,nullable=False)
  tags = Column(ARRAY(String),default=[])
  asset_metadata = Column(JSONB,default={})
  