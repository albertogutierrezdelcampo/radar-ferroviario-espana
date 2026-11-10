from pathlib import Path


def test_application_uses_authoritative_metro_config_before_state_creation():
    source = Path(__file__).resolve().parents[1].joinpath(
        "src", "radar_app", "application.py"
    ).read_text(encoding="utf-8")
    imported = source.index("from radar.config import METRO_GTFS as CONFIG_METRO_GTFS")
    override = source.index("METRO_GTFS = CONFIG_METRO_GTFS")
    state = source.index("STATE = create_application_state(")
    assert imported < override < state


def test_legacy_ids_cannot_be_runtime_values():
    source = Path(__file__).resolve().parents[1].joinpath(
        "src", "radar_app", "application.py"
    ).read_text(encoding="utf-8")
    runtime_section = source[source.index("METRO_GTFS = CONFIG_METRO_GTFS"):]
    assert '"nap_id":967' not in runtime_section
    assert '"nap_id":1071' not in runtime_section
