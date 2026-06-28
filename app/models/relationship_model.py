from sqlalchemy import Column, String, ForeignKey
from app.database import Base
import uuid


class AssetRelationship(Base):
    __tablename__ = "relationships"

    # Explicit callable lambda — produces string UUID, not raw uuid.UUID objects
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)