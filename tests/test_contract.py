"""契约：parse_telemetry 把 /api/telemetry 归一化成 BattleState（接缝②回归）。"""

from __future__ import annotations

from neko_warthunder.adapters.telemetry_client import parse_telemetry
from neko_warthunder.core.contracts import EVENT_CATALOG


def _sample() -> dict:
    return {
        "state": "in_battle",
        "in_battle": True,
        "domain": "air",
        "timestamp": 123.0,
        "vehicle": {"valid": True, "ias_kmh": 180.0, "aoa_deg": 16.0, "altitude_m": 400.0, "climb_ms": -12.0, "mach": 0.3, "load_factor": 4.5},
        "indicators": {"valid": True, "vehicle_type": "bf-109f-4", "army": "air"},
        "processed": {
            "flags": {"stall_warning": True, "altitude_low": True},
            "level": "warning",
            "ias_kmh": 180.0, "aoa_deg": 16.0, "altitude_m": 400.0,
            "fuel_fraction": 0.42, "g_now": 4.5, "water_temp_c": 112.0,
        },
        "hud_events": [{"id": 1, "kind": "damage", "msg": "x"}],
        "combat": {"player_name": "Me", "my": {"kills": 2, "deaths": 0}, "feed": []},
        "mission_status": "running",
        "meta": {"fast": {"age_sec": 0.1}},
    }


def test_parse_in_battle():
    s = parse_telemetry(_sample())
    assert s.connected and s.in_battle and s.conn_state == "in_battle"
    assert s.vehicle_valid is True
    assert s.domain == "air" and s.vehicle_type == "bf-109f-4"
    assert s.ias_kmh == 180.0 and s.altitude_m == 400.0 and s.climb_ms == -12.0
    assert s.flag("stall_warning") and s.flag("altitude_low")
    assert s.any_critical_flag() is False  # 只有 warning 级
    assert s.fuel_fraction == 0.42 and s.water_temp_c == 112.0


def test_parse_offline():
    s = parse_telemetry(None)
    assert s.connected is False and s.conn_state == "offline" and s.in_battle is False
    assert s.vehicle_valid is False


def test_critical_flag():
    payload = _sample()
    payload["processed"]["flags"] = {"stall_critical": True}
    s = parse_telemetry(payload)
    assert s.any_critical_flag() is True


def test_parse_replay_flag():
    payload = _sample()
    payload["replay"] = True
    s = parse_telemetry(payload)
    assert getattr(s, "replay", False) is True


def test_parse_dead_and_profile_fields_from_v18_contract():
    payload = _sample()
    payload["dead"] = True
    payload["domain_label"] = "Air"
    payload["processed"]["profile_matched"] = True
    payload["processed"]["profile_source"] = "family"
    payload["processed"]["profile_family"] = "Bf 109"
    s = parse_telemetry(payload)
    assert s.dead is True
    assert s.domain_label == "Air"
    assert s.profile_matched is True
    assert s.profile_source == "family"
    assert s.profile_family == "Bf 109"


def test_parse_hud_notices_feed_without_losing_raw_contract():
    payload = _sample()
    payload["hud_notices"] = {
        "feed": [
            {"id": 42, "code": "engine_overheat", "severity": "warning", "text": "水温过高"},
        ],
    }
    s = parse_telemetry(payload)
    assert s.hud_notices == payload["hud_notices"]["feed"]
    assert s.raw["hud_notices"]["feed"][0]["text"] == "水温过高"


def test_v16_event_catalog_entries_are_not_marked_blocked():
    for event_id in ("overspeed", "you_killed", "you_died"):
        assert EVENT_CATALOG[event_id].blocked is False
