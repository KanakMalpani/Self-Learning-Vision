from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProviderHealth:
    provider_id: str
    ready: bool
    status: str
    detail: str
    model_cache_dir: str
    optional_dependencies: dict[str, bool]


def dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def insightface_health(model_cache_dir: str, model_name: str = "buffalo_l") -> ProviderHealth:
    cache_root = Path(model_cache_dir)
    model_dir = cache_root / "models" / model_name
    deps = {
        "insightface": dependency_available("insightface"),
        "onnxruntime": dependency_available("onnxruntime"),
    }
    if not all(deps.values()):
        return ProviderHealth(
            provider_id="insightface",
            ready=False,
            status="optional_dependency_missing",
            detail="Install production provider extras before selecting InsightFace.",
            model_cache_dir=str(cache_root),
            optional_dependencies=deps,
        )
    if not model_dir.exists():
        return ProviderHealth(
            provider_id="insightface",
            ready=False,
            status="model_cache_missing",
            detail="Run scripts/download_models.py --provider insightface --download to prepare local models.",
            model_cache_dir=str(cache_root),
            optional_dependencies=deps,
        )
    return ProviderHealth(
        provider_id="insightface",
        ready=True,
        status="ready",
        detail="InsightFace dependencies and model cache are present.",
        model_cache_dir=str(cache_root),
        optional_dependencies=deps,
    )


def provider_health(model_cache_dir: str) -> list[ProviderHealth]:
    return [
        ProviderHealth(
            provider_id="local-face-embedding",
            ready=True,
            status="ready",
            detail="Local fallback provider is available without model downloads.",
            model_cache_dir=str(Path(model_cache_dir)),
            optional_dependencies={},
        ),
        insightface_health(model_cache_dir),
    ]

