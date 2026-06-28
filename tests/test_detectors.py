"""Detector：边沿 FSM（confirm/迟滞/re-arm）+ 离散去重（D-B3）。"""

from __future__ import annotations

from neko_warthunder.adapters.telemetry_client import parse_telemetry
from neko_warthunder.core import contracts as C
from neko_warthunder.detectors._base import ConditionDetector, DetectorEngine
from neko_warthunder.detectors.condition.flight_safety import build_condition_detectors
from neko_warthunder.detectors.discrete.lifecycle import DeathDetector, KillDetector, SpawnDetector
from neko_warthunder.detectors.discrete.notices import HudNoticeDetector


def _st(flags=None):
    return C.BattleState(flags=flags or {})


def test_condition_enter_after_confirm():
    d = ConditionDetector("stall_risk", [("stall_warning", "stall_critical")], confirm_enter=2, confirm_exit=2)
    prev = C.BattleState()
    assert d.feed(prev, _st({"stall_warning": True})) is None        # confirming 1/2
    ev = d.feed(prev, _st({"stall_warning": True}))                  # confirming 2/2 -> ACTIVE
    assert ev is not None and ev.event_id == "stall_risk" and ev.edge == "enter" and ev.level == "warning"
    assert d.feed(prev, _st({"stall_warning": True})) is None        # 持续期不重发


def test_condition_debounce_spike():
    d = ConditionDetector("stall_risk", [("stall_warning", "stall_critical")], confirm_enter=2)
    prev = C.BattleState()
    assert d.feed(prev, _st({"stall_warning": True})) is None        # 1
    assert d.feed(prev, _st({})) is None                             # 单帧尖刺被滤，回 ARMED
    assert d.feed(prev, _st({"stall_warning": True})) is None        # 重新计数 1/2


def test_condition_rearm():
    d = ConditionDetector("low_fuel", [("fuel_low", "fuel_critical")], confirm_enter=1, confirm_exit=1)
    prev = C.BattleState()
    assert d.feed(prev, _st({"fuel_low": True})).event_id == "low_fuel"   # confirm_enter=1 当拍触发
    assert d.feed(prev, _st({})) is None                                  # 退出 -> re-arm
    assert d.feed(prev, _st({"fuel_low": True})).event_id == "low_fuel"   # 再次触发


def test_condition_critical_level():
    d = ConditionDetector("stall_risk", [("stall_warning", "stall_critical")], confirm_enter=1)
    ev = d.feed(C.BattleState(), _st({"stall_critical": True}))
    assert ev is not None and ev.level == "critical"


def test_condition_escalation_reemits_critical():
    """warning 持续中升级到 critical：应重发一条 critical enter（可抢占）。"""
    d = ConditionDetector("stall_risk", [("stall_warning", "stall_critical")], confirm_enter=1, confirm_exit=2)
    prev = C.BattleState()
    ev1 = d.feed(prev, _st({"stall_warning": True}))
    assert ev1 is not None and ev1.level == "warning"
    ev2 = d.feed(prev, _st({"stall_critical": True}))   # 升级
    assert ev2 is not None and ev2.level == "critical" and ev2.edge == "enter"
    assert d.feed(prev, _st({"stall_critical": True})) is None  # 升级后不重复


def test_spawn_detector():
    det = SpawnDetector()
    prev = C.BattleState(connected=True, in_battle=False, vehicle_valid=False)
    cur = C.BattleState(connected=True, in_battle=True, vehicle_valid=True, vehicle_type="bf-109f-4")
    ev = det.feed(prev, cur)
    assert ev is not None and ev.event_id == "spawn" and ev.payload.get("vehicle_type") == "bf-109f-4"
    assert det.feed(cur, cur) is None  # 已存活不再触发


def test_spawn_not_fired_after_telemetry_blip():
    det = SpawnDetector()
    blip = C.BattleState(connected=False)  # 遥测瞬断
    cur = C.BattleState(connected=True, in_battle=True, vehicle_valid=True)
    assert det.feed(blip, cur) is None  # prev 断连 → 不误判重生


def test_death_detector():
    det = DeathDetector()
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    cur = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        combat={"feed": [{"id": 3, "is_my_death": True, "killer": "Opponent", "action": "crashed"}]},
    )
    ev = det.feed(prev, cur)
    assert ev is not None and ev.event_id == "you_died" and ev.level == "critical"


def test_kill_dedup_monotonic():
    det = KillDetector("Me")
    feed1 = {"player_name": "Me", "feed": [{"id": 5, "is_kill": True, "is_my_kill": True, "killer": "Me", "victim": "A"}]}
    cur1 = C.BattleState(in_battle=True, vehicle_valid=True, combat=feed1)
    ev = det.feed(C.BattleState(), cur1)
    assert ev is not None and ev.event_id == "you_killed"
    assert det.feed(cur1, cur1) is None  # 同一 feed 不重发
    feed2 = {"player_name": "Me", "feed": [{"id": 8, "is_kill": True, "is_my_kill": True, "killer": "Me", "victim": "B"}, {"id": 5, "is_kill": True, "is_my_kill": True, "killer": "Me", "victim": "A"}]}
    cur2 = C.BattleState(in_battle=True, vehicle_valid=True, combat=feed2)
    ev2 = det.feed(cur1, cur2)
    assert ev2 is not None and ev2.payload.get("victim") == "B"  # 只发新 id


def test_kill_requires_is_my_kill_flag():
    det = KillDetector("")
    feed = {"feed": [{"id": 1, "is_kill": True, "killer": "Someone", "victim": "X"}]}
    cur = C.BattleState(in_battle=True, vehicle_valid=True, combat=feed)
    assert det.feed(C.BattleState(), cur) is None


def test_overspeed_warn_and_critical_flags_emit_events():
    engine = DetectorEngine(list(build_condition_detectors()))
    prev = C.BattleState(in_battle=True, vehicle_valid=True)

    warn = C.BattleState(in_battle=True, vehicle_valid=True, flags={"overspeed_warn": True}, ias_kmh=760.0)
    assert engine.feed(prev, warn) == []
    events = engine.feed(warn, warn)
    assert len(events) == 1
    assert events[0].event_id == "overspeed"
    assert events[0].level == "warning"

    critical = C.BattleState(in_battle=True, vehicle_valid=True, flags={"overspeed_critical": True}, ias_kmh=880.0)
    events = engine.feed(warn, critical)
    assert len(events) == 1
    assert events[0].event_id == "overspeed"
    assert events[0].level == "critical"


def test_low_alt_payload_carries_radio_altitude_for_agl_context():
    engine = DetectorEngine(list(build_condition_detectors()))
    prev = C.BattleState(in_battle=True, vehicle_valid=True)

    low_1 = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        flags={"altitude_critical": True},
        altitude_m=1067.0,
        radio_altitude_m=8.0,
        climb_ms=-3.0,
    )
    low_2 = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        flags={"altitude_critical": True},
        altitude_m=1060.0,
        radio_altitude_m=7.0,
        climb_ms=-4.0,
    )

    assert engine.feed(prev, low_1) == []
    events = engine.feed(low_1, low_2)

    assert len(events) == 1
    assert events[0].event_id == "low_alt_danger"
    assert events[0].payload["radio_altitude_m"] == 7.0
    assert events[0].payload["altitude_m"] == 1060.0


def test_aoa_flags_do_not_emit_stall_risk():
    engine = DetectorEngine(list(build_condition_detectors()))
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    high_aoa = C.BattleState(in_battle=True, vehicle_valid=True, flags={"aoa_high": True}, aoa_deg=19.0)

    assert engine.feed(prev, high_aoa) == []
    assert engine.feed(high_aoa, high_aoa) == []


def test_kill_detector_uses_is_my_kill_flag():
    det = KillDetector("Me")
    feed = {
        "player_name": "Me",
        "feed": [{"id": 10, "is_kill": True, "is_my_kill": True, "killer": "OtherName", "victim": "Target"}],
    }
    cur = C.BattleState(in_battle=True, vehicle_valid=True, combat=feed)
    ev = det.feed(C.BattleState(), cur)
    assert ev is not None and ev.event_id == "you_killed"
    assert ev.payload.get("victim") == "Target"


def test_kill_detector_carries_domain_for_output_wording():
    det = KillDetector("Me")
    feed = {"feed": [{"id": 12, "is_my_kill": True, "victim": "Target", "victim_vehicle": "Tank"}]}
    cur = C.BattleState(in_battle=True, vehicle_valid=True, domain="ground", combat=feed)

    ev = det.feed(C.BattleState(), cur)

    assert ev is not None and ev.payload.get("domain") == "ground"


def test_death_detector_uses_is_my_death_flag():
    det = DeathDetector()
    feed = {
        "player_name": "Me",
        "feed": [
            {
                "id": 20,
                "is_kill": True,
                "is_my_death": True,
                "killer": "Opponent",
                "victim": "Me",
                "action": "shot_down",
            }
        ],
    }
    cur = C.BattleState(in_battle=True, vehicle_valid=True, combat=feed)
    ev = det.feed(C.BattleState(in_battle=True, vehicle_valid=True), cur)
    assert ev is not None and ev.event_id == "you_died"
    assert ev.payload.get("killer_name") == "Opponent"
    assert ev.payload.get("cause") == "shot_down"


def test_death_detector_carries_domain_for_output_wording():
    det = DeathDetector()
    feed = {"feed": [{"id": 22, "is_my_death": True, "killer": "Opponent", "action": "destroyed"}]}
    cur = C.BattleState(in_battle=True, vehicle_valid=False, domain="ground", combat=feed)

    ev = det.feed(C.BattleState(in_battle=True, vehicle_valid=True), cur)

    assert ev is not None and ev.payload.get("domain") == "ground"


def test_vehicle_valid_drop_is_not_death_signal():
    det = DeathDetector()
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    cur = C.BattleState(in_battle=True, vehicle_valid=False, combat={"feed": []})
    assert det.feed(prev, cur) is None


def test_replay_telemetry_suppresses_detector_events():
    payload = {
        "state": "in_battle",
        "in_battle": True,
        "replay": True,
        "timestamp": 123.0,
        "combat": {"feed": [{"id": 1, "is_my_death": True, "killer": "Opponent"}]},
        "processed": {"flags": {"overspeed_critical": True}},
    }
    prev = C.BattleState(connected=True, in_battle=True, vehicle_valid=True)
    cur = parse_telemetry(payload)
    engine = DetectorEngine(list(build_condition_detectors()) + [DeathDetector()])
    assert engine.feed(prev, cur) == []


def test_hud_notice_overheat_emits_safe_overheat_event_once():
    det = HudNoticeDetector()
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    cur = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        timestamp=200.0,
        hud_notices=[
            {
                "id": 7,
                "code": "engine_overheat",
                "severity": "warning",
                "text": "水温过高 raw text must not enter payload",
            }
        ],
    )
    ev = det.feed(prev, cur)
    assert ev is not None
    assert ev.event_id == "overheat"
    assert ev.level == "warning"
    assert ev.payload == {"source": "hud_notice", "notice_code": "engine_overheat"}
    assert det.feed(cur, cur) is None


def test_hud_notice_uses_data_layer_level_field():
    det = HudNoticeDetector()
    cur = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        timestamp=201.0,
        hud_notices=[{"id": 10, "code": "engine_overheat", "level": "critical", "message": "engine disabled"}],
    )

    ev = det.feed(C.BattleState(in_battle=True, vehicle_valid=True), cur)

    assert ev is not None
    assert ev.event_id == "overheat"
    assert ev.level == "critical"


def test_hud_notice_powertrain_failure_is_not_promoted_to_speech_event_yet():
    det = HudNoticeDetector()
    cur = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        hud_notices=[{"id": 8, "code": "powertrain_failure", "severity": "critical", "text": "动力系统故障"}],
    )
    assert det.feed(C.BattleState(in_battle=True, vehicle_valid=True), cur) is None


def test_dead_state_suppresses_overheat_candidates():
    engine = DetectorEngine(list(build_condition_detectors()) + [HudNoticeDetector()])
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    dead = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        dead=True,
        flags={"engine_overheat_critical": True},
        hud_notices=[{"id": 11, "code": "engine_overheat", "severity": "critical", "text": "raw overheat"}],
    )

    assert engine.feed(prev, dead) == []
    assert engine.feed(dead, dead) == []


def test_dead_state_allows_death_event_and_blocks_overheat_same_tick():
    engine = DetectorEngine(list(build_condition_detectors()) + [DeathDetector(), HudNoticeDetector()])
    prev = C.BattleState(in_battle=True, vehicle_valid=True)
    dead = C.BattleState(
        in_battle=True,
        vehicle_valid=True,
        dead=True,
        flags={"engine_overheat_critical": True},
        combat={"feed": [{"id": 30, "is_my_death": True, "killer": "Opponent", "action": "crashed"}]},
        hud_notices=[{"id": 12, "code": "engine_overheat", "severity": "critical", "text": "raw overheat"}],
    )

    events = engine.feed(prev, dead)

    assert [ev.event_id for ev in events] == ["you_died"]
    assert events[0].payload.get("cause") == "crashed"


def test_spawn_detector_ignores_dead_state_with_stale_vehicle_valid():
    det = SpawnDetector()
    prev = C.BattleState(connected=True, in_battle=True, vehicle_valid=False, dead=True)
    cur = C.BattleState(connected=True, in_battle=True, vehicle_valid=True, dead=True, vehicle_type="bf-109f-4")

    assert det.feed(prev, cur) is None


def test_hud_notice_overheat_requires_live_vehicle():
    det = HudNoticeDetector()
    cur = C.BattleState(
        in_battle=True,
        vehicle_valid=False,
        hud_notices=[{"id": 9, "code": "oil_overheat", "severity": "warning", "text": "油温过高"}],
    )
    assert det.feed(C.BattleState(in_battle=True, vehicle_valid=True), cur) is None
