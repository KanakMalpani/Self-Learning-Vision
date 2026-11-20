"""Atomic JSON documents for the local registries."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


def read_json(path: str | Path, fallback: T) -> T:
    document = Path(path)
    if not document.exists():
        return fallback
    try:
        return json.loads(document.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def read_json_list(path: str | Path) -> list:
    payload = read_json(path, [])
    return payload if isinstance(payload, list) else []


def read_json_object(path: str | Path) -> dict:
    payload = read_json(path, {})
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: object) -> None:
    document = Path(path)
    document.parent.mkdir(parents=True, exist_ok=True)
    temporary = document.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(document)
