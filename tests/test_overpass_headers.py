from radar.extensions import OVERPASS_HTTP


def test_overpass_uses_dedicated_headers_without_generic_csv_accept():
    assert OVERPASS_HTTP.headers["Accept"] == "application/json"
    assert OVERPASS_HTTP.headers["Content-Type"].startswith("application/x-www-form-urlencoded")
    assert "RadarFerroviarioEspana" in OVERPASS_HTTP.headers["User-Agent"]
    assert "text/csv" not in OVERPASS_HTTP.headers["Accept"]
