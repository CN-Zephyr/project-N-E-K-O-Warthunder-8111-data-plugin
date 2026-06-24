"""Arbiter 仲裁（D-B4）：门控 / 抢占 / 单槽窗口 / 限流 / ≤1 条。"""

from __future__ import annotations

from neko_warthunder.core.arbiter import Arbiter
from neko_warthunder.core.contracts import (
    COMBAT_STRESS,
    CRITICAL_RISK,
    DEAD,
    IN_FLIGHT,
    SPAWNING,
    BattleEvent,
    WtConfig,
)
from neko_warthunder.core.safety_guard import SafetyGuard


def _arb() -> Arbiter:
    return Arbiter(SafetyGuard(WtConfig()))


def test_scenario_gating_drops_low_fuel_in_combat():
    chosen, chain = _arb().decide([BattleEvent("low_fuel", level="warning")], COMBAT_STRESS, 1000.0)
    assert chosen is None
    assert any(c["result"] == "dropped" and "scenario_gated" in c["reason"] for c in chain)


def test_spawning_allows_owned_kill_event():
    arb = _arb()
    chosen, chain = arb.decide([BattleEvent("you_killed", level="warning")], SPAWNING, 1000.0)
    flushed, flush_chain = arb.decide([], SPAWNING, 1002.1)
    assert chosen is None
    assert any(c["result"] == "buffered" and c["reason"] == "kill_coalescing" for c in chain)
    assert flushed is not None and flushed.event_id == "you_killed"
    assert any(c["result"] == "spoken" and c["reason"] == "kill_coalesced" for c in flush_chain)


def test_spawning_still_gates_flight_safety_warning():
    chosen, chain = _arb().decide([BattleEvent("overheat", level="warning")], SPAWNING, 1000.0)
    assert chosen is None
    assert any(c["result"] == "dropped" and c["reason"] == "scenario_gated(SPAWNING)" for c in chain)


def test_idle_immediate_warning():
    chosen, _ = _arb().decide([BattleEvent("low_fuel", level="warning")], IN_FLIGHT, 1000.0)
    assert chosen is not None and chosen.event_id == "low_fuel"


def test_critical_preempts_immediately():
    chosen, chain = _arb().decide([BattleEvent("stall_risk", level="critical")], CRITICAL_RISK, 1000.0)
    assert chosen is not None and chosen.event_id == "stall_risk"
    assert any(c["result"] == "spoken" and c["reason"] == "preempt" for c in chain)


def test_single_output_two_criticals():
    chosen, chain = _arb().decide(
        [BattleEvent("stall_risk", level="critical"), BattleEvent("low_alt_danger", level="critical")],
        CRITICAL_RISK,
        1000.0,
    )
    assert chosen is not None and chosen.event_id == "low_alt_danger"  # 同 priority，severity 9>8
    assert sum(1 for c in chain if c["result"] == "spoken") == 1


def test_rate_limit_buffer_then_flush():
    arb = _arb()
    a, _ = arb.decide([BattleEvent("overheat", level="warning")], IN_FLIGHT, 1000.0)
    assert a is not None and a.event_id == "overheat"               # 空闲即时
    b, _ = arb.decide([BattleEvent("low_fuel", level="warning")], IN_FLIGHT, 1003.0)
    assert b is None                                                # 12s 限流内 → 缓冲
    c, _ = arb.decide([], IN_FLIGHT, 1013.0)
    assert c is not None and c.event_id == "low_fuel"               # 窗口到点 flush


def test_cooldown_drops_repeat():
    arb = _arb()
    arb.decide([BattleEvent("overheat", level="warning")], IN_FLIGHT, 1000.0)
    chosen, chain = arb.decide([BattleEvent("overheat", level="warning")], IN_FLIGHT, 1005.0)
    assert chosen is None
    assert any(c["result"] == "dropped" and c["reason"] == "cooldown" for c in chain)


def test_paused_suppresses_all():
    arb = _arb()
    arb.safety.pause()
    chosen, chain = arb.decide([BattleEvent("stall_risk", level="critical")], CRITICAL_RISK, 1000.0)
    assert chosen is None
    assert any(c["result"] == "suppressed" for c in chain)


def test_window_flush_dropped_if_scenario_changed():
    arb = _arb()
    a, _ = arb.decide([BattleEvent("overheat", level="warning")], IN_FLIGHT, 1000.0)
    assert a is not None                                            # 占用限流时钟
    b, _ = arb.decide([BattleEvent("low_fuel", level="warning")], IN_FLIGHT, 1003.0)
    assert b is None                                                # 缓冲
    c, chain = arb.decide([], DEAD, 1013.0)                         # 窗口到点但场景已切 DEAD
    assert c is None
    assert any("scenario_gated_on_flush" in x["reason"] for x in chain)
