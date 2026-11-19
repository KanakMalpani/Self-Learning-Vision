from __future__ import annotations

from app.main import app

EXPECTED_ROUTES = (
    "GET /openapi.json",
    "GET /docs",
    "GET /docs/oauth2-redirect",
    "GET /redoc",
    "POST /api/v1/auth/register",
    "POST /api/v1/auth/login",
    "GET /api/v1/auth/me",
    "GET /health",
    "GET /ready",
    "POST /api/v1/upload",
    "POST /api/v1/identity/references",
    "POST /api/v1/memory-runs/{memory_run_id}/reference",
    "GET /api/v1/memory-domains",
    "GET /api/v1/memory-domain-templates",
    "GET /api/v1/memory-domain-templates/{template_id}",
    "POST /api/v1/memory-domain-templates/{template_id}/entities",
    "GET /api/v1/memory-entities",
    "GET /api/v1/memory-entities/search",
    "POST /api/v1/memory-entities",
    "GET /api/v1/memory-entities/{entity_id}",
    "PATCH /api/v1/memory-entities/{entity_id}",
    "GET /api/v1/memory-entities/{entity_id}/detail",
    "GET /api/v1/memory-entities/{entity_id}/confidence-ledger",
    "POST /api/v1/memory-entities/{entity_id}/active-learning/domain-review",
    "GET /api/v1/learning/signals",
    "GET /api/v1/learning/policy",
    "PUT /api/v1/learning/policy",
    "GET /api/v1/learning/policy/simulation",
    "POST /api/v1/learning/signals/{signal_id}/dismiss",
    "GET /api/v1/learning/review-inbox",
    "POST /api/v1/memory-entities/{entity_id}/learning/replay",
    "GET /api/v1/privacy/settings",
    "PUT /api/v1/privacy/settings",
    "GET /api/v1/providers",
    "GET /api/v1/provider-plugins",
    "GET /api/v1/provider-conformance",
    "GET /api/v1/providers/health",
    "GET /api/v1/providers/selection",
    "PUT /api/v1/providers/selection",
    "GET /api/v1/memory-lifecycle/summary",
    "POST /api/v1/memory-lifecycle/decay-stale",
    "POST /api/v1/memory-entities/{entity_id}/lifecycle/reinforce",
    "POST /api/v1/memory-entities/{entity_id}/lifecycle/contradiction",
    "GET /api/v1/corrections",
    "POST /api/v1/corrections/{correction_id}/undo",
    "POST /api/v1/memory-entities/{entity_id}/corrections/rename",
    "POST /api/v1/memory-entities/{entity_id}/corrections/forget",
    "POST /api/v1/memory-entities/{entity_id}/corrections/not-this",
    "POST /api/v1/memory-entities/{entity_id}/corrections/merge",
    "POST /api/v1/memory-entities/{entity_id}/corrections/split",
    "GET /api/v1/active-learning/questions",
    "POST /api/v1/active-learning/questions/{question_id}/response",
    "POST /api/v1/memory-runs",
    "GET /api/v1/memory-runs/{memory_run_id}",
    "GET /api/v1/memory-runs",
    "GET /api/v1/memory-run-events/stream",
    "DELETE /api/v1/upload/{upload_id}",
    "DELETE /api/v1/memory-runs/{memory_run_id}",
    "GET /api/v1/data/export",
    "POST /api/v1/data/vault/export",
    "POST /api/v1/data/vault/import",
    "GET /api/v1/evaluation/summary",
    "GET /api/v1/evaluation/metrics",
    "GET /api/v1/evaluation/dataset",
    "GET /api/v1/evaluation/provider-scorecard",
    "GET /api/v1/evaluation/benchmark-pack",
    "GET /api/v1/evaluation/benchmark-runs",
    "POST /api/v1/evaluation/benchmark-runs",
    "DELETE /api/v1/data/purge",
)


def test_http_route_surface_matches_split_contract() -> None:
    found: list[str] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in sorted(set(methods) - {"HEAD", "OPTIONS"}):
            found.append(f"{method} {path}")
    assert tuple(sorted(found)) == tuple(sorted(EXPECTED_ROUTES))
