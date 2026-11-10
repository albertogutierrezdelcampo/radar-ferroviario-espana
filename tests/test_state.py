from radar.state import create_application_state


def test_state_instances_do_not_share_mutable_caches():
    metro = {"m": {"name": "Metro", "color": "#fff", "source": "test"}}
    operator = {"o": {"name": "Operator", "color": "#000", "source": "test"}}
    first = create_application_state(metro, operator, ["https://overpass.test"])
    second = create_application_state(metro, operator, ["https://overpass.test"])
    first.metro_cache["m"]["stations"].append({"id": "1"})
    first.static_cache["stations"].append({"id": "2"})
    assert second.metro_cache["m"]["stations"] == []
    assert second.static_cache["stations"] == []


def test_state_initializes_source_metadata_and_health():
    state = create_application_state(
        {"m": {"name": "Metro", "color": "#fff", "source": "NAP"}},
        {"o": {"name": "Operator", "color": "#000", "source": "GTFS"}},
        ["https://overpass.test"],
    )
    assert state.metro_cache["m"]["status"] == "pending"
    assert state.open_access_cache["o"]["loaded"] is False
    assert state.overpass_endpoint_health["https://overpass.test"]["fails"] == 0
