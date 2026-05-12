from __future__ import annotations

from pathlib import Path
from typing import List, Optional

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency in test environments
    cv2 = None

try:
    import numpy as np
except Exception:  # pragma: no cover - optional dependency in test environments
    np = None

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency in test environments
    Image = None

from app.schemas.api import FaceBox


class FaceDetectionService:
    def __init__(self, min_detection_confidence: float = 0.5):
        self.min_detection_confidence = min_detection_confidence
        self._detector: Optional[object] = None
        self._detector_mode: Optional[str] = None

    def detect_faces(self, image_path: str) -> List[FaceBox]:
        path = Path(image_path)
        if not path.exists():
            raise FileNotFoundError(f"Image not found: {path}")

        self._ensure_detector()

        if Image is None or np is None:
            raise RuntimeError("Face detection dependencies unavailable")

        with Image.open(path) as img:
            rgb = img.convert("RGB")
            np_image = np.array(rgb)

        face_boxes: List[FaceBox] = []

        if self._detector_mode == "mediapipe":
            results = self._detector.process(np_image)
            if results.detections:
                for detection in results.detections:
                    box = detection.location_data.relative_bounding_box
                    face_boxes.append(
                        FaceBox(
                            x=float(box.xmin),
                            y=float(box.ymin),
                            width=float(box.width),
                            height=float(box.height),
                            score=float(detection.score[0]) if detection.score else 0.0,
                        )
                    )
        elif self._detector_mode == "opencv":
            gray = cv2.cvtColor(np_image, cv2.COLOR_RGB2GRAY)
            detections = self._detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
            height, width = gray.shape
            for (x, y, w, h) in detections:
                face_boxes.append(
                    FaceBox(
                        x=float(x) / float(width),
                        y=float(y) / float(height),
                        width=float(w) / float(width),
                        height=float(h) / float(height),
                        score=1.0,
                    )
                )
        return face_boxes

    def match_faces(self, image_path: str) -> List[str]:  # pragma: no cover - placeholder
        """Placeholder hook for embedding-based face matching (InsightFace/ArcFace)."""
        _ = image_path
        return []

    def _ensure_detector(self) -> None:
        if self._detector_mode:
            return
        try:
            from mediapipe import solutions as mp_solutions  # type: ignore

            self._detector = mp_solutions.face_detection.FaceDetection(
                model_selection=1, min_detection_confidence=self.min_detection_confidence
            )
            self._detector_mode = "mediapipe"
            return
        except Exception:
            if cv2 is None:
                raise RuntimeError("Face detection unavailable: OpenCV dependency missing")
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            cascade = cv2.CascadeClassifier(cascade_path)
            if cascade.empty():
                raise RuntimeError("Face detection unavailable: no MediaPipe solutions or Haar cascade found")
            self._detector = cascade
            self._detector_mode = "opencv"

