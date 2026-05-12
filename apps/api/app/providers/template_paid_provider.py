from __future__ import annotations

import os

from app.providers.base import FaceEmbeddingProvider


class TemplatePaidEmbeddingProvider(FaceEmbeddingProvider):
    """Template for hosted or paid embedding providers.

    Copy this class, rename it, and implement the provider-specific HTTP or SDK
    call. Do not enable remote image transfer unless the user explicitly opted in.
    """

    name = "template-paid-provider"

    def __init__(self, api_key_env: str = "PAID_PROVIDER_API_KEY") -> None:
        self.api_key = os.getenv(api_key_env, "").strip()

    @property
    def is_ready(self) -> bool:
        return bool(self.api_key)

    def extract_embedding(self, image_path: str, face_box: dict) -> list[float] | None:
        _ = image_path, face_box
        raise NotImplementedError(
            "Implement this in your provider integration. Keep image transfer explicit and documented."
        )
