import uuid
from pathlib import Path
from typing import Tuple

from fastapi import UploadFile


class StorageService:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_upload(self, file: UploadFile) -> Tuple[str, str]:
        suffix = Path(file.filename or "upload").suffix or ".bin"
        file_id = f"{uuid.uuid4()}{suffix}"
        path = self.base_dir / file_id
        with path.open("wb") as f:
            f.write(file.file.read())
        return str(path), file_id

    def save_bytes(self, payload: bytes, suffix: str = ".jpg", subdir: str = "") -> Tuple[str, str]:
        clean_suffix = suffix if suffix.startswith(".") else f".{suffix}"
        file_id = f"{uuid.uuid4()}{clean_suffix}"
        target_dir = self.base_dir / subdir if subdir else self.base_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / file_id
        with path.open("wb") as f:
            f.write(payload)
        return str(path), file_id

