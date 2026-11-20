from __future__ import annotations

import json

from app.services.json_store import read_json_list, read_json_object, write_json


def test_json_store_round_trips_lists_and_objects(tmp_path) -> None:
    document = tmp_path / "registry.json"
    write_json(document, [{"id": "one"}])
    assert read_json_list(document) == [{"id": "one"}]
    assert not document.with_suffix(".tmp").exists()

    write_json(document, {"preset": "balanced"})
    assert read_json_object(document) == {"preset": "balanced"}


def test_json_store_uses_fallbacks_for_missing_and_corrupt_files(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    assert read_json_list(missing) == []
    assert read_json_object(missing) == {}

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{", encoding="utf-8")
    assert read_json_list(corrupt) == []

    wrong_shape = tmp_path / "shape.json"
    wrong_shape.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert read_json_list(wrong_shape) == []
    assert read_json_object(wrong_shape) == {"not": "a list"}
