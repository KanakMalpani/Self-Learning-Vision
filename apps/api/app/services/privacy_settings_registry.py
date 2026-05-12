from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class PrivacySettingsRecord:
    local_only_mode: bool = True
    allow_hosted_providers: bool = False
    export_include_biometric_embeddings: bool = False
    export_include_upload_paths: bool = False
    data_retention_days: int | None = None
    domain_visibility: dict[str, str] = field(default_factory=dict)
    updated_at: str = ""


class PrivacySettingsRegistry:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def get(self) -> PrivacySettingsRecord:
        payload = self._load_payload()
        if not payload:
            return PrivacySettingsRecord(updated_at=datetime.now(UTC).isoformat())
        return self._record_from_payload(payload)

    def update(
        self,
        *,
        local_only_mode: bool | None = None,
        allow_hosted_providers: bool | None = None,
        export_include_biometric_embeddings: bool | None = None,
        export_include_upload_paths: bool | None = None,
        data_retention_days: int | None = None,
        domain_visibility: dict[str, str] | None = None,
    ) -> PrivacySettingsRecord:
        with self._lock:
            current = self.get()
            if local_only_mode is not None:
                current.local_only_mode = bool(local_only_mode)
            if allow_hosted_providers is not None:
                current.allow_hosted_providers = bool(allow_hosted_providers)
            if export_include_biometric_embeddings is not None:
                current.export_include_biometric_embeddings = bool(export_include_biometric_embeddings)
            if export_include_upload_paths is not None:
                current.export_include_upload_paths = bool(export_include_upload_paths)
            if data_retention_days is not None:
                current.data_retention_days = max(1, int(data_retention_days))
            if domain_visibility is not None:
                current.domain_visibility = self._sanitize_domain_visibility(domain_visibility)
            current.updated_at = datetime.now(UTC).isoformat()
            self._save_payload(asdict(current))
            return current

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

    def _record_from_payload(self, payload: dict[str, Any]) -> PrivacySettingsRecord:
        return PrivacySettingsRecord(
            local_only_mode=bool(payload.get("local_only_mode", True)),
            allow_hosted_providers=bool(payload.get("allow_hosted_providers", False)),
            export_include_biometric_embeddings=bool(payload.get("export_include_biometric_embeddings", False)),
            export_include_upload_paths=bool(payload.get("export_include_upload_paths", False)),
            data_retention_days=(
                max(1, int(payload["data_retention_days"]))
                if payload.get("data_retention_days") is not None
                else None
            ),
            domain_visibility=self._sanitize_domain_visibility(payload.get("domain_visibility")),
            updated_at=str(payload.get("updated_at") or "") or datetime.now(UTC).isoformat(),
        )

    def _sanitize_domain_visibility(self, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        allowed = {"private", "exportable", "hidden"}
        clean: dict[str, str] = {}
        for key, item in value.items():
            domain = str(key or "").strip().lower()
            visibility = str(item or "").strip().lower()
            if not domain:
                continue
            clean[domain] = visibility if visibility in allowed else "private"
        return clean
