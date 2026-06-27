from sqlalchemy import Column, String, ForeignKey
from app.database import Base
import uuid

class AssetRelationship(Base):
    __tablename__ = "relationships"

    id = Column(String(36) , primary_key=True , default=uuid.uuid4)
    source_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(String, ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False) 