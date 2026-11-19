"""HTTP routes for evaluation."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.api.support import (
    _benchmark_run_item,
    _evaluation_context,
    get_benchmark_run_registry,
)
from app.core.config import settings
from app.core.db import get_db
from app.models import MemoryRun, Upload, User
from app.schemas import (
    BenchmarkPackResponse,
    BenchmarkRunCreateRequest,
    BenchmarkRunItem,
    BenchmarkRunListResponse,
    EvaluationDatasetResponse,
    EvaluationMetricsResponse,
    ProviderScorecardResponse,
)
from app.services.benchmark_pack import build_benchmark_pack
from app.services.evaluation import (
    build_evaluation_dataset,
    build_evaluation_metrics,
    build_provider_scorecard,
)

router = APIRouter(tags=["evaluation"])


def _context_metrics(context: dict[str, object]) -> dict[str, object]:
    active_learning = context["active_learning_registry"]
    signal_registry = context["learning_signal_registry"]
    pending_count = active_learning.pending_count() + signal_registry.pending_count()
    return build_evaluation_metrics(
        memory_runs=context["memory_runs"],
        active_learning_questions=context["active_learning_questions"],
        corrections=context["corrections"],
        memory_entities=context["memory_entities"],
        learning_signals=context["learning_signals"],
        memory_health_distribution=context["memory_health_distribution"],
        review_inbox_pending_count=pending_count,
        lifecycle_summary=context["lifecycle_summary"],
    )


@router.get("/api/v1/evaluation/summary")
def evaluation_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    references = context["references"]
    unknown_registry = context["unknown_registry"]
    entity_registry = context["entity_registry"]
    active_learning_registry = context["active_learning_registry"]
    correction_registry = context["correction_registry"]
    privacy_settings = context["privacy_settings"]
    provider_selection = context["provider_selection"]
    memory_run_count = db.query(MemoryRun).filter(MemoryRun.user_id == current_user.id).count()
    upload_count = db.query(Upload).filter(Upload.user_id == current_user.id).count()
    clusters = unknown_registry.list_clusters()
    domain_counts = {
        domain_type: entity_registry.entity_count(domain_type)
        for domain_type in entity_registry.list_domain_types()
    }
    lifecycle_summary = context["lifecycle_summary"]
    metrics = _context_metrics(context)

    return JSONResponse(
        {
            "memory_runs": memory_run_count,
            "uploads": upload_count,
            "memory_entities": entity_registry.entity_count(),
            "memory_domains": domain_counts,
            "memory_lifecycle": lifecycle_summary,
            "active_learning_pending_questions": active_learning_registry.pending_count(),
            "corrections": correction_registry.count(),
            "privacy": {
                "local_only_mode": privacy_settings.local_only_mode,
                "allow_hosted_providers": privacy_settings.allow_hosted_providers,
                "export_include_biometric_embeddings": False,
                "export_include_upload_paths": privacy_settings.export_include_upload_paths,
            },
            "provider_selections": provider_selection.selections,
            "identity_references": references.reference_count(),
            "unknown_samples": unknown_registry.sample_count(),
            "unknown_clusters": len(clusters),
            "suggested_clusters": len(
                [cluster for cluster in clusters if cluster.suggested_for_enrollment]
            ),
            "provider": references.provider_name() or settings.embedding_provider,
            "evaluation_metrics": metrics,
        }
    )


@router.get("/api/v1/evaluation/metrics", response_model=EvaluationMetricsResponse)
def evaluation_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationMetricsResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    return EvaluationMetricsResponse(**_context_metrics(context))


@router.get("/api/v1/evaluation/dataset", response_model=EvaluationDatasetResponse)
def evaluation_dataset(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvaluationDatasetResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    return EvaluationDatasetResponse(
        **build_evaluation_dataset(
            active_learning_questions=context["active_learning_questions"],
            corrections=context["corrections"],
            memory_entities=context["memory_entities"],
        )
    )


@router.get("/api/v1/evaluation/provider-scorecard", response_model=ProviderScorecardResponse)
def evaluation_provider_scorecard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ProviderScorecardResponse:
    context = _evaluation_context(db=db, current_user=current_user)
    metrics = _context_metrics(context)
    provider_selection = context["provider_selection"]
    return ProviderScorecardResponse(
        **build_provider_scorecard(
            provider_cards=context["provider_cards"],
            provider_selections=provider_selection.selections,
            evaluation_metrics=metrics,
        )
    )


@router.get("/api/v1/evaluation/benchmark-pack", response_model=BenchmarkPackResponse)
def evaluation_benchmark_pack() -> BenchmarkPackResponse:
    return BenchmarkPackResponse(**build_benchmark_pack())


@router.get("/api/v1/evaluation/benchmark-runs", response_model=BenchmarkRunListResponse)
def list_evaluation_benchmark_runs(
    current_user: User = Depends(get_current_user),
) -> BenchmarkRunListResponse:
    records = get_benchmark_run_registry(str(current_user.id)).list_runs()
    return BenchmarkRunListResponse(
        runs=[_benchmark_run_item(record) for record in records],
        run_count=len(records),
    )


@router.post("/api/v1/evaluation/benchmark-runs", response_model=BenchmarkRunItem, status_code=201)
def create_evaluation_benchmark_run(
    payload: BenchmarkRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BenchmarkRunItem:
    context = _evaluation_context(db=db, current_user=current_user)
    metrics = _context_metrics(context)
    provider_selection = context["provider_selection"]
    record = get_benchmark_run_registry(str(current_user.id)).add_run(
        label=payload.label,
        notes=payload.notes,
        benchmark_case_ids=payload.benchmark_case_ids,
        provider_selections=provider_selection.selections,
        metrics=metrics,
    )
    return _benchmark_run_item(record)
