from pathlib import Path


def test_diagnostic_serializers_apply_central_redaction():
    source = Path(__file__).resolve().parents[1].joinpath(
        "src", "radar_app", "application.py"
    ).read_text(encoding="utf-8")
    helper = source[source.index("def _transit_source_diagnostics"):source.index("def api_transit_networks")]
    assert "sanitize_data(state.get(\"download_attempts\"" in helper
    assert "sanitize_text(state.get(\"error\"" in helper
    diagnostics = source[source.index("def api_diagnostics"):]
    assert '"feeds": sanitize_data(' in diagnostics
    assert '"overpass_mirrors": sanitize_data(' in diagnostics
