import uuid
from enum import Enum
from sqlalchemy import JSON, Column, DateTime, Enum as PgEnum, ForeignKey, Integer, Text, func
from sqlalchemy.orm import relationship

from app.models.base import Base
from app.models.types import GUID


class MemoryRunStatus(str, Enum):
    queued = "queued"
    detecting = "detecting"
    matching = "matching"
    synthesizing = "synthesizing"
    done = "done"
    failed = "failed"


class MemoryRun(Base):
    __tablename__ = "memory_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    upload_id = Column(GUID(), ForeignKey("uploads.id"), nullable=False)
    selected_face_index = Column(Integer, nullable=False)
    notes = Column(Text, nullable=True)

    status = Column(PgEnum(MemoryRunStatus), nullable=False, default=MemoryRunStatus.queued)
    memory_report = Column(JSON, nullable=True)
    last_error = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    last_failed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    upload = relationship("Upload", backref="memory_runs")
    user = relationship("User", foreign_keys=[user_id], backref="memory_runs")
    activities = relationship(
        "Activity", back_populates="memory_run", cascade="all, delete-orphan", order_by="Activity.created_at"
    )

