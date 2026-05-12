from __future__ import annotations

from pathlib import Path

from app.services.active_learning_registry import ActiveLearningRegistry


def test_active_learning_registry_dedupes_pending_questions(tmp_path: Path) -> None:
    registry = ActiveLearningRegistry(tmp_path / "questions.json")

    first = registry.upsert_question(
        question_type="confirm_match",
        prompt="Is this Ada?",
        dedupe_key="confirm:upload-a:0:ada",
        confidence=0.61,
        priority=80,
        candidate_label="Ada",
    )
    second = registry.upsert_question(
        question_type="confirm_match",
        prompt="Is this Ada Lovelace?",
        dedupe_key="confirm:upload-a:0:ada",
        confidence=0.68,
        priority=90,
        candidate_label="Ada",
    )

    assert first.question_id == second.question_id
    assert second.prompt == "Is this Ada Lovelace?"
    assert second.priority == 90
    assert second.confidence == 0.68
    assert registry.pending_count() == 1


def test_active_learning_registry_keeps_new_question_after_answer(tmp_path: Path) -> None:
    registry = ActiveLearningRegistry(tmp_path / "questions.json")
    first = registry.upsert_question(
        question_type="label_unknown_cluster",
        prompt="Who is this familiar unknown person?",
        dedupe_key="unknown:cluster-a",
        unknown_cluster_id="cluster-a",
    )

    answered = registry.answer_question(
        question_id=first.question_id,
        action="label",
        label="Maya",
        notes="met at demo day",
        tags=["builder", "builder"],
    )
    assert answered is not None
    assert answered.status == "answered"
    assert answered.response is not None
    assert answered.response.label == "Maya"
    assert answered.response.tags == ["builder"]

    second = registry.upsert_question(
        question_type="label_unknown_cluster",
        prompt="Who is this familiar unknown person?",
        dedupe_key="unknown:cluster-a",
        unknown_cluster_id="cluster-a",
    )

    assert second.question_id != first.question_id
    assert registry.pending_count() == 1
    assert len(registry.list_questions()) == 2


def test_active_learning_registry_dismisses_question(tmp_path: Path) -> None:
    registry = ActiveLearningRegistry(tmp_path / "questions.json")
    question = registry.upsert_question(
        question_type="review_memory",
        prompt="Should this be remembered?",
        dedupe_key="review:upload-a",
    )

    dismissed = registry.answer_question(question_id=question.question_id, action="dismiss")

    assert dismissed is not None
    assert dismissed.status == "dismissed"
    assert registry.pending_count() == 0
