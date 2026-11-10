from pathlib import Path


def test_progressive_track_stages_bypass_prior_stage_cooldown():
    source = Path(__file__).resolve().parents[1].joinpath("src", "radar_app", "application.py").read_text(encoding="utf-8")
    assert 'load_cycle_id = f"tracks-{int(STATIC_CACHE[' in source
    assert 'ignore_cooldown=True' in source
    assert 'cycle_id=f"{load_cycle_id}-stage-{stage_num}"' in source
    assert 'cache_key=f"seed-stage-{stage_num}-v2",' in source
