from pathlib import Path


def test_productive_parser_delegates_to_modular_gtfs_layer():
    source = Path(__file__).resolve().parents[1].joinpath("src", "radar_app", "application.py").read_text(encoding="utf-8")
    function = source[source.index("def parse_operator_gtfs"):source.index("def load_operator_gtfs")]
    assert "open_gtfs_archive(" in function
    assert "active_service_ids(" in function
    assert "zipfile.ZipFile" not in function
    assert "_read_gtfs_csv" not in function
