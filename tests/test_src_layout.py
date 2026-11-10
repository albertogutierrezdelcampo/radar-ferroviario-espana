from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_root_app_is_a_small_compatibility_entrypoint():
    app_file = ROOT / "app.py"
    assert len(app_file.read_text(encoding="utf-8").splitlines()) < 40
    assert (ROOT / "src" / "radar_app" / "application.py").is_file()


def test_src_radar_package_is_importable():
    import radar.gtfs
    import radar.state
    assert radar.gtfs.__name__ == "radar.gtfs"


def test_compatibility_loader_executes_implementation_in_its_namespace():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'exec(compile(' in source
    assert 'globals(), globals()' in source
    assert 'SRC_DIR' in source
