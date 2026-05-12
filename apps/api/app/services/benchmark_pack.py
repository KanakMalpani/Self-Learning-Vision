from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    domain_type: str
    task: str
    description: str
    expected_signals: list[str] = field(default_factory=list)
    privacy_level: str = "synthetic_metadata_only"


BENCHMARK_CASES = [
    BenchmarkCase(
        case_id="person-repeat-unknown",
        domain_type="person",
        task="unknown_cluster_review",
        description="Two consent-safe synthetic face observations should remain unknown until labeled.",
        expected_signals=["unknown", "clustered_after_repeat", "active_learning_question"],
    ),
    BenchmarkCase(
        case_id="product-sku-memory",
        domain_type="product",
        task="template_memory_creation",
        description="A product memory should track brand, SKU, category, and condition.",
        expected_signals=["template_fields_present", "user_confirmed_label"],
    ),
    BenchmarkCase(
        case_id="document-ocr-review",
        domain_type="document",
        task="ocr_review",
        description="A document memory should ask what text should be remembered before saving claims.",
        expected_signals=["ocr_provider_available_or_skipped", "review_question"],
    ),
    BenchmarkCase(
        case_id="inventory-count-review",
        domain_type="inventory",
        task="quantity_review",
        description="An inventory memory should ask for quantity, storage location, and reorder state.",
        expected_signals=["missing_quantity_question", "missing_location_question"],
    ),
    BenchmarkCase(
        case_id="place-landmark-review",
        domain_type="place",
        task="place_disambiguation",
        description="A place memory should capture visual landmarks and avoid overconfident matches.",
        expected_signals=["landmark_prompt", "uncertainty_when_sparse"],
    ),
]


def build_benchmark_pack() -> dict[str, object]:
    return {
        "schema_version": "benchmark-pack.v1",
        "name": "Self-Learning Vision Offline Benchmark Pack",
        "description": "Consent-safe metadata-only cases for comparing providers and memory behavior.",
        "cases": [asdict(case) for case in BENCHMARK_CASES],
        "case_count": len(BENCHMARK_CASES),
        "redaction": {
            "raw_images": "not_included",
            "biometric_embeddings": "not_included",
            "real_personal_data": "not_included",
        },
        "usage": [
            "Create synthetic or user-owned local fixtures for each case.",
            "Run the same cases before and after changing providers.",
            "Compare uncertainty rate, correction rate, estimated precision, and estimated recall.",
        ],
    }
