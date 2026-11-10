import io
import logging
import os
import time
import zipfile

from radar.nap_service import NapGtfsService, find_download_url


def gtfs_zip(route="R1"):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\nS1,Stop,40,-3\n")
        zf.writestr("routes.txt", f"route_id,route_short_name\n{route},Line\n")
        zf.writestr("trips.txt", f"route_id,service_id,trip_id\n{route},WK,T1\n")
        zf.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nT1,10:00:00,10:00:00,S1,1\n")
    return buf.getvalue()


class Response:
    def __init__(self, *, status=200, content=b"", text="", payload=None):
        self.status_code = status; self.content = content; self.text = text; self.payload = payload
    def json(self):
        if self.payload is None: raise ValueError("not json")
        return self.payload


class Http:
    def __init__(self, responses): self.responses = list(responses); self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs)); return self.responses.pop(0)


def service(http):
    return NapGtfsService(http, logger=logging.getLogger("test.nap"), endpoint_template="https://nap/{dataset_id}")


def test_recursive_url_resolution_handles_nested_json_and_text_json():
    assert find_download_url({"data": [{"fichero": {"downloadURL": "https://x/feed.zip"}}]}) == "https://x/feed.zip"
    assert find_download_url('{"result":"https://x/feed.zip"}') == "https://x/feed.zip"


def test_nap_accepts_direct_zip_response():
    http = Http([Response(content=gtfs_zip())])
    result = service(http).download_nap(1071, "token")
    assert result.ok and result.source == "NAP 1071 direct"
    assert http.calls[0][1]["headers"] == {"ApiKey": "token"}


def test_nap_follows_json_temporary_link():
    http = Http([
        Response(payload={"data": {"downloadUrl": "https://files/feed.zip"}}),
        Response(content=gtfs_zip()),
    ])
    result = service(http).download_nap(967, "token")
    assert result.ok and result.source == "NAP 967 link"
    assert [call[0] for call in http.calls] == ["https://nap/967", "https://files/feed.zip"]


def test_invalid_remote_never_overwrites_valid_stale_cache(tmp_path):
    cache = tmp_path / "metro.zip"; original = gtfs_zip("OLD"); cache.write_bytes(original)
    old = time.time() - 1000; os.utime(cache, (old, old))
    http = Http([Response(text="Archivo no encontrado"), Response(content=b"PKbroken")])
    result = service(http).acquire(
        dataset_id=1071, token="token", fallback_urls=["https://fallback/feed.zip"],
        cache_file=cache, ttl=10, force=False,
    )
    assert result.ok and result.stale and result.status == "stale"
    assert result.content == original and cache.read_bytes() == original
    assert any("último GTFS válido" in error for error in result.errors)


def test_fresh_cache_avoids_network(tmp_path):
    cache = tmp_path / "metro.zip"; cache.write_bytes(gtfs_zip())
    http = Http([])
    result = service(http).acquire(
        dataset_id=1, token="token", fallback_urls=[], cache_file=cache, ttl=86400,
    )
    assert result.ok and result.status == "ready" and result.using_cache
    assert http.calls == []


def test_valid_download_replaces_cache_atomically(tmp_path):
    cache = tmp_path / "metro.zip"; cache.write_bytes(gtfs_zip("OLD"))
    http = Http([Response(content=gtfs_zip("NEW"))])
    result = service(http).acquire(
        dataset_id=1, token="token", fallback_urls=[], cache_file=cache, ttl=0, force=True,
    )
    assert result.ok and result.status == "downloaded"
    assert cache.read_bytes() == result.content
    assert not cache.with_name("metro.zip.tmp").exists()
