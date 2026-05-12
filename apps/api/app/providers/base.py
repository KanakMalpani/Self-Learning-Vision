from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.recognition import FaceEmbeddingProvider


class VisionDetectionProvider(ABC):
    name: str

    @abstractmethod
    def detect(self, image_path: str) -> list[dict]:
        raise NotImplementedError


class ImageClassificationProvider(ABC):
    name: str

    @abstractmethod
    def classify(self, image_path: str) -> list[dict]:
        raise NotImplementedError


class ImageCaptionProvider(ABC):
    name: str

    @abstractmethod
    def caption(self, image_path: str) -> str | None:
        raise NotImplementedError


class OCRProvider(ABC):
    name: str

    @abstractmethod
    def extract_text(self, image_path: str) -> str:
        raise NotImplementedError


class MultimodalReasoningProvider(ABC):
    name: str

    @abstractmethod
    def reason(self, *, image_path: str, prompt: str) -> dict:
        raise NotImplementedError


__all__ = [
    "FaceEmbeddingProvider",
    "VisionDetectionProvider",
    "ImageClassificationProvider",
    "ImageCaptionProvider",
    "OCRProvider",
    "MultimodalReasoningProvider",
]
