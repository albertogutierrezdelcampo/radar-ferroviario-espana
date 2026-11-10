import importlib.util
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("radar_app", ROOT / "app.py")
appmod = importlib.util.module_from_spec(spec); spec.loader.exec_module(appmod)
client = appmod.app.test_client()
def reset(trains=None):
    appmod.RT_CACHE.update(timestamp=0,trains=list(trains or []),diagnostics={},last_success_at=0,last_attempt_at=0,last_error=None,discarded_vehicles=0)
def test_no_optional_workers():
    reset()
    with patch.object(appmod,"ensure_background_threads",side_effect=AssertionError("optional worker")), patch.object(appmod,"fetch_json_entities",return_value=([],None,"fixture","offline")):
        r=client.get('/api/trains?snap=0')
    assert r.status_code==200 and r.get_json()['success']
def test_last_valid_cache_survives_empty_refresh():
    old=[{"id":"T1","lat":40.0,"lon":-3.0,"speed":0}]; reset(old); appmod.RT_CACHE['last_success_at']=appmod.time.time()-12
    with patch.object(appmod,"fetch_json_entities",return_value=([],None,"fixture","timeout")):
        d=client.get('/api/trains?snap=0').get_json()
    assert d['cached'] and d['trains']==old
def test_unexpected_error_is_200():
    old=[{"id":"T2","lat":41.0,"lon":-4.0,"speed":10}]; reset(old)
    with patch.object(appmod,"fetch_json_entities",side_effect=RuntimeError('broken')):
        r=client.get('/api/trains?snap=0')
    assert r.status_code==200 and r.get_json()['warning']=='refresh_failed' and r.get_json()['trains']==old
def test_malformed_vehicle_is_discarded():
    reset(); calls=[([None,'bad',{}],None,'c',None),([],None,'u',None),([],None,'l',None)]
    with patch.object(appmod,"fetch_json_entities",side_effect=calls): d=client.get('/api/trains?snap=0').get_json()
    assert d['diagnostics']['snapshot']['discarded_vehicles']==2
def test_optional_failures_are_irrelevant():
    reset()
    with patch.object(appmod,'ensure_operator_feeds',side_effect=RuntimeError()), patch.object(appmod,'ensure_metro_feeds',side_effect=RuntimeError()), patch.object(appmod,'run_overpass_query',side_effect=RuntimeError()), patch.object(appmod,'fetch_json_entities',return_value=([],None,'fixture',None)):
        r=client.get('/api/trains?snap=0')
    assert r.status_code==200
