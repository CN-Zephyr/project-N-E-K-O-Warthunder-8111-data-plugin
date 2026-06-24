"""Status reporting should stay lightweight under the live polling loop."""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
import threading
import types

from neko_warthunder.adapters.runtime_timeline import RuntimeTimeline
from neko_warthunder.core.arbiter import Arbiter
from neko_warthunder.core.contracts import BattleState, WtConfig
from neko_warthunder.core.safety_guard import SafetyGuard
from neko_warthunder.core.scenario import ScenarioResolver


def _runtime_plugin_class():
    if "plugin.sdk.plugin" not in sys.modules:
        plugin_mod = types.ModuleType("plugin")
        sdk_mod = types.ModuleType("plugin.sdk")
        plugin_sdk_mod = types.ModuleType("plugin.sdk.plugin")

        class NekoPluginBase:
            def __init__(self, ctx):
                self.ctx = ctx

        def identity_decorator(*_args, **_kwargs):
            def wrap(obj):
                return obj

            return wrap

        plugin_sdk_mod.NekoPluginBase = NekoPluginBase
        plugin_sdk_mod.neko_plugin = lambda cls: cls
        plugin_sdk_mod.plugin_entry = identity_decorator
        plugin_sdk_mod.lifecycle = identity_decorator
        plugin_sdk_mod.ui = types.SimpleNamespace(
            context=identity_decorator,
            action=identity_decorator,
        )
        plugin_sdk_mod.Ok = lambda value=None: value
        plugin_sdk_mod.Err = lambda value=None: value
        plugin_sdk_mod.SdkError = Exception

        sys.modules["plugin"] = plugin_mod
        sys.modules["plugin.sdk"] = sdk_mod
        sys.modules["plugin.sdk.plugin"] = plugin_sdk_mod

    module_name = "neko_warthunder.__runtime_under_test__"
    if module_name in sys.modules:
        return sys.modules[module_name].NekoWarthunderPlugin

    plugin_dir = pathlib.Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(module_name, plugin_dir / "__init__.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.NekoWarthunderPlugin


def _plugin_for_report_tests():
    Plugin = _runtime_plugin_class()
    plugin = object.__new__(Plugin)
    plugin.cfg = WtConfig()
    plugin.safety = SafetyGuard(plugin.cfg)
    plugin.state = BattleState(connected=True, conn_state="in_battle", in_battle=True, scenario="IN_FLIGHT")
    plugin._state_lock = threading.Lock()
    plugin._status_report_min_interval_seconds = 10.0
    plugin._last_status_report_at = 0.0
    plugin._last_status_report_snapshot = None
    plugin.reported_statuses = []

    def report_status(payload):
        plugin.reported_statuses.append(payload)

    plugin.report_status = report_status
    return plugin


def _plugin_for_action_tests():
    Plugin = _runtime_plugin_class()
    plugin = object.__new__(Plugin)
    plugin.cfg = WtConfig()
    plugin.safety = SafetyGuard(plugin.cfg)
    plugin.pushed_messages = []

    def push_message(**kwargs):
        plugin.pushed_messages.append(kwargs)

    plugin.push_message = push_message
    return plugin


def test_status_report_is_deduped_between_unchanged_poll_ticks():
    plugin = _plugin_for_report_tests()

    plugin._report(now=100.0)
    plugin._report(now=100.4)

    assert len(plugin.reported_statuses) == 1


def test_status_report_emits_immediately_when_snapshot_changes():
    plugin = _plugin_for_report_tests()

    plugin._report(now=100.0)
    plugin.state = BattleState(connected=True, conn_state="in_battle", in_battle=True, scenario="CRITICAL_RISK")
    plugin._report(now=100.4)

    assert len(plugin.reported_statuses) == 2
    assert plugin.reported_statuses[-1]["scenario"] == "CRITICAL_RISK"


def test_replay_tick_records_suppressed_decision_without_output():
    Plugin = _runtime_plugin_class()
    plugin = object.__new__(Plugin)
    plugin.cfg = WtConfig()
    plugin.safety = SafetyGuard(plugin.cfg)
    plugin.timeline = RuntimeTimeline(observability_enabled=True, max_events=10)
    plugin.resolver = ScenarioResolver()
    plugin.arbiter = Arbiter(plugin.safety)
    plugin.engine = plugin._build_engine()
    plugin.dispatcher = types.SimpleNamespace(push_event=lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError))
    plugin.logger = types.SimpleNamespace(info=lambda *_args, **_kwargs: None)

    prev = BattleState(connected=True, conn_state="in_battle", in_battle=True, vehicle_valid=True)
    cur = BattleState(
        connected=True,
        conn_state="in_battle",
        in_battle=True,
        vehicle_valid=True,
        replay=True,
        flags={
            "stall_critical": True,
            "altitude_critical": True,
            "overspeed_critical": True,
            "fuel_critical": True,
        },
        combat={
            "feed": [
                {"id": 100, "is_my_kill": True, "victim": "ReplayVictim"},
                {"id": 101, "is_my_death": True, "killer": "ReplayKiller"},
            ]
        },
        hud_notices=[{"id": 7, "code": "engine_overheat", "severity": "critical", "text": "replay overheat"}],
    )

    plugin._evaluate(prev, cur)

    observe = plugin.timeline.snapshot()
    assert observe["last_decision"]["stage"] == "detector_suppressed"
    assert observe["last_decision"]["outcome"] == "suppressed"
    assert observe["last_decision"]["reason"] == "replay"
    assert observe["last_output_status"] is None
    assert observe["last_event"] is None


def test_test_say_is_blocked_by_dry_run():
    plugin = _plugin_for_action_tests()
    plugin.cfg.dry_run = True

    result = asyncio.run(plugin.test_say("hello"))

    assert result["pushed"] is False
    assert result["blocked"] == "dry_run"
    assert plugin.pushed_messages == []


def test_test_say_is_blocked_by_manual_pause():
    plugin = _plugin_for_action_tests()
    plugin.cfg.dry_run = False
    plugin.safety.pause()

    result = asyncio.run(plugin.test_say("hello"))

    assert result["pushed"] is False
    assert result["blocked"] == "paused"
    assert plugin.pushed_messages == []
