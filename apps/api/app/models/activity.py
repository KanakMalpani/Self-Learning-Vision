import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.types import GUID


class Activity(Base):
    __tablename__ = "activities"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    memory_run_id = Column(GUID(), ForeignKey("memory_runs.id"), nullable=False)
    stage = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    memory_run = relationship("MemoryRun", back_populates="activities")

