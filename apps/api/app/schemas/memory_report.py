from datetime import UTC, datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Subject(BaseModel):
    name_or_alias: str = "Unknown"
    possible_profiles: List[str] = Field(default_factory=list)


class Fact(BaseModel):
    title: str
    detail: str
    confidence: Optional[float] = None
    citations: List[str] = Field(default_factory=list)
    support_count: int = 0
    tentative: bool = False


class TimelineEvent(BaseModel):
    title: str
    date: str
    description: str = ""
    confidence: Optional[float] = None
    citations: List[str] = Field(default_factory=list)
    support_count: int = 0
    tentative: bool = False


class FaceAssessment(BaseModel):
    face_index: int
    detector_confidence: float = 0.0
    blur_score: float = 0.0
    box_size_ratio: float = 0.0
    pose_score: float = 0.0
    occlusion_score: float = 0.0
    face_quality_score: float = 0.0
    face_quality_flags: List[str] = Field(default_factory=list)


class IdentityCandidate(BaseModel):
    name_or_alias: str
    provider: str
    raw_confidence: float = 0.0
    calibrated_confidence: float = 0.0
    match_reason: str
    profile_url: Optional[str] = None
    recognition_score: float = 0.0
    recognition_decision: str = "rejected"


class MemoryReportConfidence(BaseModel):
    overall: float = 0.5
    photo: Optional[float] = None
    per_claim: Optional[Dict[str, float]] = None


class MemoryReport(BaseModel):
    subject: Subject
    executive_summary: str
    key_facts: List[Fact]
    timeline: List[TimelineEvent]
    profile_links: List[str]
    confidence: MemoryReportConfidence
    source_notes: List[str]
    caveats: List[str]
    face_assessments: List[FaceAssessment] = Field(default_factory=list)
    identity_candidates: List[IdentityCandidate] = Field(default_factory=list)
    recognition_summary: Dict[str, object] = Field(default_factory=dict)
    decision_trace: Dict[str, object] = Field(default_factory=dict)
    identity_explanation: List[str] = Field(default_factory=list)
    memory_analytics: Dict[str, object] = Field(default_factory=dict)
    recognition_source: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
