from radar.cache_store import read_json, write_json_atomic


def test_atomic_json_roundtrip(tmp_path):
    target = tmp_path / "nested" / "cache.json"
    write_json_atomic(target, {"trains": [1, 2], "source": "Renfe"})
    assert read_json(target, {}) == {"trains": [1, 2], "source": "Renfe"}
    assert not target.with_name("cache.json.tmp").exists()


def test_invalid_or_missing_json_returns_default(tmp_path):
    target = tmp_path / "broken.json"
    target.write_text("{broken", encoding="utf-8")
    assert read_json(target, {"safe": True}) == {"safe": True}
    assert read_json(tmp_path / "missing.json", []) == []
