from __future__ import annotations

from pathlib import Path

from PIL import Image


def write_test_image(path: Path, size: tuple[int, int] = (16, 16), color: tuple[int, int, int] = (128, 128, 128)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", size, color=color)
    image.save(path, format="JPEG", quality=95, subsampling=0)


def write_duplicate_image(path: Path, source: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source.read_bytes())
