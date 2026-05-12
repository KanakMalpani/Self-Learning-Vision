from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


QuestionStatus = Literal["pending", "answered", "dismissed"]
QuestionType = Literal["confirm_match", "label_unknown_cluster", "review_memory"]


@dataclass
class ActiveLearningResponse:
    action: str
    label: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)
    answered_at: str = ""


@dataclass
class ActiveLearningQuestion:
    question_id: str
    question_type: QuestionType
    prompt: str
    domain_type: str = "person"
    status: QuestionStatus = "pending"
    priority: int = 50
    priority_reason: str = ""
    confidence: float = 0.0
    source_signal_ids: list[str] = field(default_factory=list)
    learning_value: float = 0.0
    risk_level: str = "medium"
    cooldown_until: str | None = None
    dedupe_key: str = ""
    suggested_action: str = ""
    memory_run_id: str | None = None
    upload_id: str | None = None
    selected_face_index: int | None = None
    candidate_label: str | None = None
    candidate_reference_id: str | None = None
    unknown_cluster_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    response: ActiveLearningResponse | None = None
    created_at: str = ""
    updated_at: str = ""


class ActiveLearningRegistry:
    """Local queue of small user questions that improve memory quality."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def list_questions(self, status: str | None = None) -> list[ActiveLearningQuestion]:
        questions = [self._question_from_payload(item) for item in self._load_payload()]
        records = [record for record in questions if record is not None]
        if status:
            normalized = self._normalize_status(status)
            records = [record for record in records if record.status == normalized]
        return sorted(records, key=lambda item: (item.status != "pending", -item.priority, item.created_at))

    def pending_count(self) -> int:
        return len(self.list_questions("pending"))

    def find(self, question_id: str) -> ActiveLearningQuestion | None:
        needle = question_id.strip()
        if not needle:
            return None
        for question in self.list_questions():
            if question.question_id == needle:
                return question
        return None

    def upsert_question(
        self,
        *,
        question_type: QuestionType,
        prompt: str,
        dedupe_key: str,
        domain_type: str = "person",
        priority: int = 50,
        priority_reason: str = "",
        confidence: float = 0.0,
        source_signal_ids: list[str] | None = None,
        learning_value: float = 0.0,
        risk_level: str = "medium",
        cooldown_until: str | None = None,
        suggested_action: str = "",
        memory_run_id: str | None = None,
        upload_id: str | None = None,
        selected_face_index: int | None = None,
        candidate_label: str | None = None,
        candidate_reference_id: str | None = None,
        unknown_cluster_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> ActiveLearningQuestion:
        clean_prompt = prompt.strip()
        clean_dedupe_key = dedupe_key.strip()
        if not clean_prompt:
            raise ValueError("Active-learning prompt is required")
        if not clean_dedupe_key:
            raise ValueError("Active-learning dedupe key is required")

        with self._lock:
            records = [self._question_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()

            for record in records:
                if record.dedupe_key != clean_dedupe_key or record.status != "pending":
                    continue
                record.prompt = clean_prompt
                record.priority = self._normalize_priority(priority)
                record.priority_reason = priority_reason.strip()
                record.confidence = self._clamp_confidence(confidence)
                record.source_signal_ids = self._sanitize_list(source_signal_ids)
                record.learning_value = self._clamp_confidence(learning_value)
                record.risk_level = self._normalize_risk(risk_level)
                record.cooldown_until = cooldown_until.strip() if cooldown_until else None
                record.context = {**record.context, **self._sanitize_mapping(context)}
                record.updated_at = now_iso
                self._save_payload([asdict(item) for item in records])
                return record

            record = ActiveLearningQuestion(
                question_id=str(uuid4()),
                question_type=question_type,
                prompt=clean_prompt,
                domain_type=self._normalize_domain(domain_type),
                status="pending",
                priority=self._normalize_priority(priority),
                priority_reason=priority_reason.strip(),
                confidence=self._clamp_confidence(confidence),
                source_signal_ids=self._sanitize_list(source_signal_ids),
                learning_value=self._clamp_confidence(learning_value),
                risk_level=self._normalize_risk(risk_level),
                cooldown_until=cooldown_until.strip() if cooldown_until else None,
                dedupe_key=clean_dedupe_key,
                suggested_action=suggested_action.strip(),
                memory_run_id=memory_run_id,
                upload_id=upload_id,
                selected_face_index=selected_face_index,
                candidate_label=candidate_label.strip() if candidate_label else None,
                candidate_reference_id=candidate_reference_id,
                unknown_cluster_id=unknown_cluster_id,
                context=self._sanitize_mapping(context),
                created_at=now_iso,
                updated_at=now_iso,
            )
            records.append(record)
            self._save_payload([asdict(item) for item in records])
            return record

    def answer_question(
        self,
        *,
        question_id: str,
        action: str,
        label: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> ActiveLearningQuestion | None:
        clean_action = action.strip().lower()
        if not clean_action:
            raise ValueError("Active-learning response action is required")

        with self._lock:
            records = [self._question_from_payload(item) for item in self._load_payload()]
            records = [record for record in records if record is not None]
            now_iso = datetime.now(UTC).isoformat()

            for record in records:
                if record.question_id != question_id:
                    continue
                record.status = "dismissed" if clean_action == "dismiss" else "answered"
                record.response = ActiveLearningResponse(
                    action=clean_action,
                    label=label.strip() if label else None,
                    notes=notes.strip() if notes else None,
                    tags=self._sanitize_list(tags),
                    answered_at=now_iso,
                )
                record.updated_at = now_iso
                self._save_payload([asdict(item) for item in records])
                return record
        return None

    def _load_payload(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return payload if isinstance(payload, list) else []

    def _save_payload(self, payload: list[dict[str, Any]]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _question_from_payload(self, item: dict[str, Any]) -> ActiveLearningQuestion | None:
        if not isinstance(item, dict):
            return None
        prompt = str(item.get("prompt") or "").strip()
        dedupe_key = str(item.get("dedupe_key") or "").strip()
        if not prompt or not dedupe_key:
            return None
        now_iso = datetime.now(UTC).isoformat()
        response_payload = item.get("response")
        response = None
        if isinstance(response_payload, dict):
            response = ActiveLearningResponse(
                action=str(response_payload.get("action") or "").strip().lower(),
                label=str(response_payload.get("label") or "") or None,
                notes=str(response_payload.get("notes") or "") or None,
                tags=self._sanitize_list(response_payload.get("tags")),
                answered_at=str(response_payload.get("answered_at") or "") or now_iso,
            )

        question_type = str(item.get("question_type") or "review_memory")
        if question_type not in {"confirm_match", "label_unknown_cluster", "review_memory"}:
            question_type = "review_memory"
        return ActiveLearningQuestion(
            question_id=str(item.get("question_id") or uuid4()),
            question_type=question_type,  # type: ignore[arg-type]
            prompt=prompt,
            domain_type=self._normalize_domain(str(item.get("domain_type") or "person")),
            status=self._normalize_status(str(item.get("status") or "pending")),
            priority=self._normalize_priority(item.get("priority") or 50),
            priority_reason=str(item.get("priority_reason") or ""),
            confidence=self._clamp_confidence(item.get("confidence") or 0.0),
            source_signal_ids=self._sanitize_list(item.get("source_signal_ids")),
            learning_value=self._clamp_confidence(item.get("learning_value") or 0.0),
            risk_level=self._normalize_risk(str(item.get("risk_level") or "medium")),
            cooldown_until=str(item.get("cooldown_until") or "") or None,
            dedupe_key=dedupe_key,
            suggested_action=str(item.get("suggested_action") or ""),
            memory_run_id=str(item.get("memory_run_id") or "") or None,
            upload_id=str(item.get("upload_id") or "") or None,
            selected_face_index=(
                max(0, int(item.get("selected_face_index")))
                if item.get("selected_face_index") is not None
                else None
            ),
            candidate_label=str(item.get("candidate_label") or "") or None,
            candidate_reference_id=str(item.get("candidate_reference_id") or "") or None,
            unknown_cluster_id=str(item.get("unknown_cluster_id") or "") or None,
            context=self._sanitize_mapping(item.get("context")),
            response=response,
            created_at=str(item.get("created_at") or "") or now_iso,
            updated_at=str(item.get("updated_at") or "") or now_iso,
        )

    def _normalize_status(self, value: str) -> QuestionStatus:
        normalized = value.strip().lower()
        return normalized if normalized in {"pending", "answered", "dismissed"} else "pending"  # type: ignore[return-value]

    def _normalize_priority(self, value: object) -> int:
        try:
            priority = int(value)
        except (TypeError, ValueError):
            priority = 50
        return max(0, min(100, priority))

    def _normalize_risk(self, value: str) -> str:
        normalized = value.strip().lower()
        return normalized if normalized in {"low", "medium", "high"} else "medium"

    def _clamp_confidence(self, value: object) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.0
        return round(max(0.0, min(1.0, confidence)), 6)

    def _sanitize_mapping(self, value: object) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        return {str(key): item for key, item in value.items() if str(key or "").strip()}

    def _sanitize_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: set[str] = set()
        clean: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            clean.append(text)
        return clean

    def _normalize_domain(self, value: str) -> str:
        normalized = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in value.lower())
        normalized = normalized.strip("_-")
        return normalized or "custom"
