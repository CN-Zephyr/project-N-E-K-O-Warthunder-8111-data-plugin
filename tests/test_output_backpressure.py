"""Output backpressure contracts for real push_message calls."""

from __future__ import annotations

from neko_warthunder.adapters.neko_dispatcher import NekoDispatcher
from neko_warthunder.adapters.runtime_timeline import RuntimeTimeline
from neko_warthunder.core.contracts import BattleEvent, WtConfig


class FakePlugin:
    def __init__(self) -> None:
        self.cfg = WtConfig(output_backpressure_seconds=20.0)
        self.calls: list[dict] = []

    def push_message(self, **kwargs) -> None:
        self.calls.append(kwargs)


def _clock(values: list[float]):
    def tick() -> float:
        return values.pop(0)

    return tick


def test_real_output_backpressure_suppresses_same_or_lower_priority_pushes():
    plugin = FakePlugin()
    timeline = RuntimeTimeline(observability_enabled=True, max_events=10)
    dispatcher = NekoDispatcher(plugin, timeline=timeline, clock=_clock([100.0, 105.0]))

    first = dispatcher.push_event(BattleEvent("you_killed"), dry_run=False)
    second = dispatcher.push_event(BattleEvent("spawn"), dry_run=False)

    assert first.startswith("pushed(")
    assert second == "suppressed(event=spawn/enter, reason=output_backpressure)"
    assert len(plugin.calls) == 1
    snapshot = timeline.snapshot()
    assert snapshot["last_output_status"]["stage"] == "dispatcher_suppressed"
    assert snapshot["last_output_status"]["reason"] == "output_backpressure"


def test_real_output_backpressure_allows_higher_priority_event_to_preempt_queue_guard():
    plugin = FakePlugin()
    dispatcher = NekoDispatcher(plugin, clock=_clock([100.0, 105.0]))

    dispatcher.push_event(BattleEvent("you_killed"), dry_run=False)
    result = dispatcher.push_event(BattleEvent("low_alt_danger", level="critical"), dry_run=False)

    assert result.startswith("pushed(event=low_alt_danger/enter)")
    assert len(plugin.calls) == 2
    assert plugin.calls[-1]["metadata"]["event_id"] == "low_alt_danger"


def test_real_event_pushes_use_battle_coalesce_key_to_replace_stale_host_queue():
    plugin = FakePlugin()
    dispatcher = NekoDispatcher(plugin, clock=_clock([100.0, 105.0]))

    dispatcher.push_event(BattleEvent("low_alt_danger", level="warning"), dry_run=False)
    dispatcher.push_event(BattleEvent("you_died", level="critical"), dry_run=False)

    assert len(plugin.calls) == 2
    assert plugin.calls[0]["metadata"]["event_id"] == "low_alt_danger"
    assert plugin.calls[1]["metadata"]["event_id"] == "you_died"
    assert plugin.calls[0]["coalesce_key"] == "neko_warthunder:battle_event"
    assert plugin.calls[1]["coalesce_key"] == "neko_warthunder:battle_event"


def test_real_output_drops_expired_battle_event_before_push():
    plugin = FakePlugin()
    plugin.cfg.output_event_max_age_seconds = 5.0
    timeline = RuntimeTimeline(observability_enabled=True, max_events=10)
    dispatcher = NekoDispatcher(plugin, timeline=timeline, clock=_clock([100.0]))

    result = dispatcher.push_event(BattleEvent("low_alt_danger", level="warning", ts=90.0), dry_run=False)

    assert result == "suppressed(event=low_alt_danger/enter, reason=event_expired)"
    assert plugin.calls == []
    status = timeline.snapshot()["last_output_status"]
    assert status["stage"] == "dispatcher_suppressed"
    assert status["reason"] == "event_expired"


def test_output_backpressure_does_not_affect_dry_run_decisions():
    plugin = FakePlugin()
    dispatcher = NekoDispatcher(plugin, clock=_clock([100.0, 105.0]))

    first = dispatcher.push_event(BattleEvent("you_killed"), dry_run=True)
    second = dispatcher.push_event(BattleEvent("spawn"), dry_run=True)

    assert first.startswith("dry_run(")
    assert second.startswith("dry_run(")
    assert plugin.calls == []
