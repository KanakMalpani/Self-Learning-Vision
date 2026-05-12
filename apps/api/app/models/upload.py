import uuid
from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, func
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.types import GUID


class Upload(Base):
    __tablename__ = "uploads"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    file_path = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    face_boxes = Column(JSON, nullable=False, default=lambda: [])
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="uploads")

