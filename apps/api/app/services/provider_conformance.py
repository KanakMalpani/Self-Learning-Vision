from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.provider_marketplace import ProviderCard


@dataclass(frozen=True)
class ProviderConformanceCheck:
    check_id: str
    label: str
    passed: bool
    severity: str
    detail: str


def evaluate_provider_conformance(card: ProviderCard) -> dict[str, Any]:
    checks = [
        _check(
            "capabilities",
            "Advertises supported capabilities",
            bool(card.capabilities),
            "error",
            "Provider must list at least one supported capability.",
        ),
        _check(
            "privacy",
            "Documents image transfer behavior",
            bool(card.privacy_notes.strip()),
            "error",
            "Provider must explain whether images leave the device.",
        ),
        _check(
            "cost",
            "Documents cost model",
            bool(card.cost_model.strip()),
            "warning",
            "Provider should document whether it is free, paid, hosted, or deployment dependent.",
        ),
        _check(
            "setup",
            "Documents setup",
            bool(card.setup.strip()),
            "warning",
            "Provider should include setup instructions.",
        ),
        _check(
            "hosted_opt_in",
            "Hosted providers require explicit opt-in",
            not card.images_leave_device or card.mode in {"hosted_paid", "hosted_or_internal"},
            "error",
            "A provider that transfers images must be marked as hosted or internal.",
        ),
        _check(
            "runtime_entrypoint",
            "Runtime provider has an entrypoint when executable",
            card.plugin_source != "manifest" or card.status in {"manifest_only", "template"} or bool(card.entrypoint),
            "warning",
            "Executable manifest providers should include a Python entrypoint.",
        ),
    ]
    passed = all(check.passed or check.severity != "error" for check in checks)
    return {
        "provider_id": card.provider_id,
        "display_name": card.display_name,
        "passed": passed,
        "checks": [check.__dict__ for check in checks],
        "summary": {
            "errors": len([check for check in checks if not check.passed and check.severity == "error"]),
            "warnings": len([check for check in checks if not check.passed and check.severity == "warning"]),
        },
    }


def evaluate_provider_catalog(cards: list[ProviderCard]) -> dict[str, Any]:
    reports = [evaluate_provider_conformance(card) for card in cards]
    return {
        "providers": reports,
        "provider_count": len(reports),
        "passing_count": len([report for report in reports if report["passed"]]),
    }


def _check(check_id: str, label: str, passed: bool, severity: str, detail: str) -> ProviderConformanceCheck:
    return ProviderConformanceCheck(
        check_id=check_id,
        label=label,
        passed=passed,
        severity=severity,
        detail=detail,
    )
