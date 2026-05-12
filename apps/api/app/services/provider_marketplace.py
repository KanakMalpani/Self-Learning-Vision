from __future__ import annotations

import json
import importlib
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import settings


PROVIDER_CAPABILITIES = {
    "face_embedding",
    "face_detection",
    "object_detection",
    "image_classification",
    "captioning",
    "ocr",
    "multimodal_reasoning",
}


@dataclass
class ProviderCard:
    provider_id: str
    display_name: str
    mode: str
    capabilities: list[str]
    status: str
    images_leave_device: bool = False
    embeddings_stored_locally: bool = True
    enabled_by_default: bool = False
    recommended_for: list[str] = field(default_factory=list)
    env_vars: list[str] = field(default_factory=list)
    expected_dimensions: int | None = None
    latency_profile: str = "unknown"
    cost_model: str = "free"
    setup: str = ""
    privacy_notes: str = ""
    entrypoint: str | None = None
    manifest_path: str | None = None
    plugin_source: str = "built_in"


class ProviderPluginRegistry:
    """File-backed provider catalog.

    Users can add JSON manifests without changing Python code. If a manifest has
    an `entrypoint`, the backend can instantiate it for supported runtime paths.
    """

    def __init__(self, manifest_dirs: list[str | Path] | None = None, *, include_default: bool = True) -> None:
        default_dir = Path(__file__).resolve().parents[1] / "providers" / "manifests"
        configured_dirs = [
            Path(item.strip())
            for item in settings.provider_plugin_dirs.split(";")
            if item.strip()
        ]
        defaults = [default_dir] if include_default else []
        self.manifest_dirs = [*defaults, *configured_dirs, *(Path(item) for item in (manifest_dirs or []))]

    def list_cards(self) -> list[ProviderCard]:
        cards: list[ProviderCard] = []
        for manifest_dir in self.manifest_dirs:
            if not manifest_dir.exists() or not manifest_dir.is_dir():
                continue
            for path in sorted(manifest_dir.glob("*.json")):
                card = self._card_from_manifest(path)
                if card is not None:
                    cards.append(card)
        return cards

    def find_card(self, provider_id: str) -> ProviderCard | None:
        needle = provider_id.strip().lower()
        return next((card for card in self.list_cards() if card.provider_id == needle), None)

    def build_face_embedding_provider(self, provider_id: str):
        card = self.find_card(provider_id)
        if card is None or "face_embedding" not in card.capabilities or not card.entrypoint:
            return None
        try:
            module_name, class_name = card.entrypoint.split(":", 1)
            module = importlib.import_module(module_name)
            provider_class = getattr(module, class_name)
            provider = provider_class()
        except Exception:
            return None
        if not hasattr(provider, "extract_embedding"):
            return None
        return provider if getattr(provider, "is_ready", True) else None

    def _card_from_manifest(self, path: Path) -> ProviderCard | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        provider_id = self._clean_id(payload.get("provider_id"))
        display_name = str(payload.get("display_name") or "").strip()
        capabilities = self._capabilities(payload.get("capabilities"))
        if not provider_id or not display_name or not capabilities:
            return None
        return ProviderCard(
            provider_id=provider_id,
            display_name=display_name,
            mode=str(payload.get("mode") or "local_free").strip() or "local_free",
            capabilities=capabilities,
            status=str(payload.get("status") or "manifest_ready").strip() or "manifest_ready",
            images_leave_device=bool(payload.get("images_leave_device") or False),
            embeddings_stored_locally=bool(payload.get("embeddings_stored_locally", True)),
            enabled_by_default=bool(payload.get("enabled_by_default") or False),
            recommended_for=self._string_list(payload.get("recommended_for")),
            env_vars=self._string_list(payload.get("env_vars")),
            expected_dimensions=self._optional_int(payload.get("expected_dimensions")),
            latency_profile=str(payload.get("latency_profile") or "deployment dependent"),
            cost_model=str(payload.get("cost_model") or "deployment dependent"),
            setup=str(payload.get("setup") or ""),
            privacy_notes=str(payload.get("privacy_notes") or ""),
            entrypoint=str(payload.get("entrypoint") or "") or None,
            manifest_path=f"{path.parent.name}/{path.name}",
            plugin_source="manifest",
        )

    def _capabilities(self, value: object) -> list[str]:
        return [
            capability
            for capability in self._string_list(value)
            if capability in PROVIDER_CAPABILITIES
        ]

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        seen: set[str] = set()
        out: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if not text:
                continue
            normalized = text.lower().replace("-", "_")
            if normalized in seen:
                continue
            seen.add(normalized)
            out.append(normalized if text == normalized else text)
        return out

    def _optional_int(self, value: object) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _clean_id(self, value: object) -> str:
        raw = str(value or "").strip().lower()
        cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in raw)
        return cleaned.strip("-_")


class ProviderMarketplace:
    def __init__(self, plugin_registry: ProviderPluginRegistry | None = None) -> None:
        self.plugin_registry = plugin_registry or ProviderPluginRegistry()

    def list_cards(self, *, privacy_local_only: bool = True, allow_hosted: bool = False) -> list[ProviderCard]:
        by_id: dict[str, ProviderCard] = {card.provider_id: card for card in self._base_cards()}
        for card in self.plugin_registry.list_cards():
            by_id.setdefault(card.provider_id, card)
        return [
            self._card_with_policy_status(card, privacy_local_only=privacy_local_only, allow_hosted=allow_hosted)
            for card in by_id.values()
        ]

    def find_card(
        self,
        provider_id: str,
        *,
        privacy_local_only: bool = True,
        allow_hosted: bool = False,
    ) -> ProviderCard | None:
        needle = provider_id.strip().lower()
        for card in self.list_cards(privacy_local_only=privacy_local_only, allow_hosted=allow_hosted):
            if card.provider_id == needle:
                return card
        return None

    def provider_supports(self, *, provider_id: str, capability: str) -> bool:
        card = self.find_card(provider_id, privacy_local_only=False, allow_hosted=True)
        return card is not None and capability in card.capabilities

    def build_face_embedding_provider(self, provider_id: str):
        return self.plugin_registry.build_face_embedding_provider(provider_id)

    def _base_cards(self) -> list[ProviderCard]:
        local_ready = self._local_ready()
        insightface_available = self._insightface_available()
        paid_ready = bool(settings.paid_provider_api_key.strip()) and settings.paid_provider_enabled
        return [
            ProviderCard(
                provider_id="local-face-embedding",
                display_name="Local Face Embedding",
                mode="local_free",
                capabilities=["face_embedding"],
                status="ready" if local_ready else "unavailable",
                images_leave_device=False,
                embeddings_stored_locally=True,
                enabled_by_default=True,
                recommended_for=["development", "privacy-first demos", "CPU-only setup"],
                expected_dimensions=None,
                latency_profile="low to medium on CPU",
                cost_model="free",
                setup="Installed with the default app dependencies.",
                privacy_notes="Images stay on the local machine.",
            ),
            ProviderCard(
                provider_id="insightface",
                display_name="InsightFace / ArcFace",
                mode="local_free",
                capabilities=["face_embedding", "face_detection"],
                status="available" if insightface_available else "optional_dependency_missing",
                images_leave_device=False,
                embeddings_stored_locally=True,
                enabled_by_default=False,
                recommended_for=["higher quality local face embeddings", "GPU acceleration"],
                expected_dimensions=512,
                latency_profile="medium on CPU, low on GPU",
                cost_model="free",
                setup="Install InsightFace and ONNX Runtime providers appropriate for your hardware.",
                privacy_notes="Images stay local when installed locally.",
            ),
            ProviderCard(
                provider_id="template-paid-provider",
                display_name="Template Hosted Provider",
                mode="hosted_paid",
                capabilities=[
                    "face_embedding",
                    "image_classification",
                    "captioning",
                    "ocr",
                    "multimodal_reasoning",
                ],
                status="ready" if paid_ready else "not_configured",
                images_leave_device=True,
                embeddings_stored_locally=True,
                enabled_by_default=False,
                recommended_for=["custom model servers", "hosted APIs", "enterprise integrations"],
                env_vars=["PAID_PROVIDER_ENABLED", "PAID_PROVIDER_API_KEY"],
                expected_dimensions=None,
                latency_profile="provider dependent",
                cost_model="paid or hosted",
                setup="Copy apps/api/app/providers/template_paid_provider.py and implement the provider call.",
                privacy_notes="Images may leave the device. Requires explicit hosted-provider privacy opt-in.",
            ),
            ProviderCard(
                provider_id="custom-http-provider",
                display_name="Custom HTTP Provider",
                mode="hosted_or_internal",
                capabilities=[
                    "face_embedding",
                    "object_detection",
                    "image_classification",
                    "captioning",
                    "ocr",
                    "multimodal_reasoning",
                ],
                status="template",
                images_leave_device=True,
                embeddings_stored_locally=True,
                enabled_by_default=False,
                recommended_for=["self-hosted model servers", "edge devices", "internal APIs"],
                env_vars=["CUSTOM_PROVIDER_URL", "CUSTOM_PROVIDER_API_KEY"],
                expected_dimensions=None,
                latency_profile="deployment dependent",
                cost_model="deployment dependent",
                setup="Implement a provider class behind the contracts in apps/api/app/providers/base.py.",
                privacy_notes="Treat as hosted unless the endpoint is on a trusted local network.",
            ),
        ]

    def _card_with_policy_status(
        self,
        card: ProviderCard,
        *,
        privacy_local_only: bool,
        allow_hosted: bool,
    ) -> ProviderCard:
        hosted = card.mode in {"hosted_paid", "hosted_or_internal"} or card.images_leave_device
        if hosted and (privacy_local_only or not allow_hosted):
            card.status = "blocked_by_privacy_policy"
        return card

    def _local_ready(self) -> bool:
        try:
            from PIL import Image  # noqa: F401

            return True
        except Exception:
            return False

    def _insightface_available(self) -> bool:
        try:
            import insightface  # noqa: F401

            return True
        except Exception:
            return False


@dataclass
class ProviderSelectionRecord:
    selections: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""


class ProviderSelectionRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get(self) -> ProviderSelectionRecord:
        payload = self._load_payload()
        selections = payload.get("selections")
        return ProviderSelectionRecord(
            selections=self._sanitize_selections(selections),
            updated_at=str(payload.get("updated_at") or "") or datetime.now(UTC).isoformat(),
        )

    def set_selection(self, *, capability: str, provider_id: str) -> ProviderSelectionRecord:
        clean_capability = self.normalize_capability(capability)
        if clean_capability not in PROVIDER_CAPABILITIES:
            raise ValueError(f"Unsupported provider capability: {capability}")
        clean_provider = provider_id.strip().lower()
        if not clean_provider:
            raise ValueError("provider_id is required")
        with self._lock:
            record = self.get()
            record.selections[clean_capability] = clean_provider
            record.updated_at = datetime.now(UTC).isoformat()
            self._save_payload(asdict(record))
            return record

    def selected_provider_for(self, capability: str) -> str | None:
        return self.get().selections.get(self.normalize_capability(capability))

    def _load_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_payload(self, payload: dict[str, Any]) -> None:
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _sanitize_selections(self, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        clean: dict[str, str] = {}
        for key, item in value.items():
            capability = self.normalize_capability(str(key))
            provider_id = str(item or "").strip().lower()
            if capability in PROVIDER_CAPABILITIES and provider_id:
                clean[capability] = provider_id
        return clean

    @staticmethod
    def normalize_capability(capability: str) -> str:
        return capability.strip().lower().replace("-", "_")
