from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Subject(BaseModel):
    name_or_alias: str = "Unknown"
    possible_profiles: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    title: str
    detail: str
    confidence: float | None = None
    citations: list[str] = Field(default_factory=list)
    support_count: int = 0
    tentative: bool = False


class TimelineEvent(BaseModel):
    title: str
    date: str
    description: str = ""
    confidence: float | None = None
    citations: list[str] = Field(default_factory=list)
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
    face_quality_flags: list[str] = Field(default_factory=list)


class IdentityCandidate(BaseModel):
    name_or_alias: str
    provider: str
    raw_confidence: float = 0.0
    calibrated_confidence: float = 0.0
    match_reason: str
    profile_url: str | None = None
    recognition_score: float = 0.0
    recognition_decision: str = "rejected"


class MemoryReportConfidence(BaseModel):
    overall: float = 0.5
    photo: float | None = None
    per_claim: dict[str, float] | None = None


class MemoryReport(BaseModel):
    subject: Subject
    executive_summary: str
    key_facts: list[Fact]
    timeline: list[TimelineEvent]
    profile_links: list[str]
    confidence: MemoryReportConfidence
    source_notes: list[str]
    caveats: list[str]
    face_assessments: list[FaceAssessment] = Field(default_factory=list)
    identity_candidates: list[IdentityCandidate] = Field(default_factory=list)
    recognition_summary: dict[str, object] = Field(default_factory=dict)
    decision_trace: dict[str, object] = Field(default_factory=dict)
    identity_explanation: list[str] = Field(default_factory=list)
    memory_analytics: dict[str, object] = Field(default_factory=dict)
    recognition_source: str | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
