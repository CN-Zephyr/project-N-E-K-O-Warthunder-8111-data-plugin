"""neko_warthunder —— War Thunder 猫娘副驾驶（M1 框架）。

只读 8112 数据层遥测，把连续数据转成分立战斗事件，按场景仲裁后让猫娘提醒/陪伴。
M1 = 框架链路（轮询 + BattleState + 安全门 + 唯一出口 + 常驻上下文 + dry_run）。
M2 接入 Scenario(D-B1) / Detector(D-B3) / Arbiter(D-B4) 后才真正产出事件。

实现路线见 docs/实现计划-codex.md。
"""

from __future__ import annotations

import threading
import time
from typing import Any

from plugin.sdk.plugin import (
    NekoPluginBase,
    neko_plugin,
    plugin_entry,
    lifecycle,
    ui,
    Ok,
    Err,
    SdkError,
)

from .adapters.neko_dispatcher import NekoDispatcher
from .adapters.runtime_timeline import RuntimeTimeline, arbiter_chain_to_observe_records
from .adapters.telemetry_client import TelemetryClient
from .core.arbiter import Arbiter
from .core.contracts import BattleState, WtConfig
from .core.instructions import WT_CONTEXT_INSTRUCTIONS, WT_RESTORE_INSTRUCTIONS
from .core.safety_guard import SafetyGuard
from .core.scenario import ScenarioResolver
from .detectors._base import DetectorEngine
from .detectors.condition.flight_safety import build_condition_detectors
from .detectors.discrete.lifecycle import build_discrete_detectors

_CONFIG_SECTION = "neko_warthunder"


@neko_plugin
class NekoWarthunderPlugin(NekoPluginBase):
    def __init__(self, ctx: Any) -> None:
        super().__init__(ctx)
        try:
            self.logger = self.enable_file_logging(log_level="INFO")
        except Exception:  # noqa: BLE001 — 文件日志不可用时退回 ctx.logger
            self.logger = ctx.logger

        self.cfg = WtConfig()
        self.client = TelemetryClient(self.cfg.data_layer_url, self.cfg.http_timeout_seconds)
        self.safety = SafetyGuard(self.cfg)
        self.timeline = RuntimeTimeline(
            observability_enabled=self.cfg.observability_enabled,
            max_events=self.cfg.observability_max_events,
            include_prompt_preview=self.cfg.observability_include_prompt_preview,
        )
        self.dispatcher = NekoDispatcher(self, timeline=self.timeline)
        self.resolver = ScenarioResolver()
        self.arbiter = Arbiter(self.safety)
        self.engine = self._build_engine()

        self.state = BattleState()
        self._state_lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._instructions_injected = False

    # ------------------------------------------------------------------ 配置
    async def _reload_config(self) -> None:
        data: dict[str, Any] = {}
        try:
            dumped = await self.config.dump(timeout=5.0)
            if isinstance(dumped, dict) and isinstance(dumped.get(_CONFIG_SECTION), dict):
                data = dumped[_CONFIG_SECTION]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning(f"config load failed, using defaults: {type(exc).__name__}")
        self._apply_config(WtConfig.from_mapping(data))

    def _apply_config(self, cfg: WtConfig) -> None:
        prev_player = self.cfg.player_name
        self.cfg = cfg
        self.client = TelemetryClient(cfg.data_layer_url, cfg.http_timeout_seconds)
        self.safety.update(cfg)
        self.timeline.configure(
            observability_enabled=cfg.observability_enabled,
            max_events=cfg.observability_max_events,
            include_prompt_preview=cfg.observability_include_prompt_preview,
        )
        # 仅 player_name 变才重建检测器：否则 dry_run 等配置切换会清零 FSM/_last_id，
        # 导致 combat.feed 里的历史击杀被当新事件重放（Bugbot 反馈）。
        if cfg.player_name != prev_player:
            self.engine = self._build_engine()

    def _build_engine(self) -> DetectorEngine:
        detectors = list(build_condition_detectors()) + list(build_discrete_detectors(self.cfg.player_name))
        return DetectorEngine(detectors)

    # --------------------------------------------------------------- 生命周期
    @lifecycle(id="startup")
    async def startup(self, **_):
        await self._reload_config()
        self.dispatcher.push_context(WT_CONTEXT_INSTRUCTIONS)
        self._instructions_injected = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="wt-poll")
        self._thread.start()
        self.logger.info(f"neko_warthunder started (dry_run={self.cfg.dry_run}, url={self.cfg.data_layer_url})")
        return Ok({"status": "running", "dry_run": self.cfg.dry_run})

    @lifecycle(id="shutdown")
    def shutdown(self, **_):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        if self._instructions_injected:
            self.dispatcher.push_context(WT_RESTORE_INSTRUCTIONS)
            self._instructions_injected = False
        self.logger.info("neko_warthunder shutdown")
        return Ok({"status": "shutdown"})

    @lifecycle(id="config_change")
    async def on_config_change(self, **_):
        await self._reload_config()
        return Ok({"status": "reloaded", "dry_run": self.cfg.dry_run})

    # ------------------------------------------------------------------ 轮询
    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:  # noqa: BLE001 — 轮询异常隔离，不杀循环
                self.logger.warning(f"tick error: {type(exc).__name__}: {exc}")
                self.safety.record_failure()
            self._stop.wait(self.cfg.poll_interval_seconds)

    def _tick(self) -> None:
        if not self.cfg.enabled:
            return
        new_state = self.client.poll()
        self.timeline.mark_tick()
        with self._state_lock:
            prev = self.state
            self.state = new_state
        self._evaluate(prev, new_state)
        self._report()

    def _evaluate(self, prev: BattleState, cur: BattleState) -> None:
        """Scenario(D-B1) + Detector(D-B3) → 候选 → Arbiter(D-B4) → dispatcher。"""
        now = time.time()
        cur.scenario = self.resolver.resolve(cur, now, self.cfg.spawn_grace_seconds)
        candidates = self.engine.feed(prev, cur)
        for candidate in candidates:
            self.timeline.record_stage(
                stage="detector_candidate",
                outcome="candidate",
                reason="detected",
                event_id=candidate.event_id,
                edge=candidate.edge,
                level=candidate.level,
                priority=candidate.priority,
                scenario=cur.scenario,
                in_battle=cur.in_battle,
                replay=cur.replay,
                safe_summary=f"{candidate.event_id}/{candidate.edge}/{candidate.level}",
            )
        chosen, chain = self.arbiter.decide(candidates, cur.scenario, now)
        for record in arbiter_chain_to_observe_records(chain, scenario=cur.scenario):
            self.timeline.record_stage(**record)
            self.timeline.record_decision(
                event_id=record.get("event_id"),
                stage=record.get("stage", "arbiter_dropped"),
                outcome=record.get("outcome", "dropped"),
                reason=record.get("reason", "unknown"),
                scenario=cur.scenario,
                safety_status=self.safety.status(),
                dry_run=self.cfg.dry_run,
            )
        if candidates or chosen is not None:
            self.logger.info(f"[arbiter] scenario={cur.scenario} chain={chain}")
        if chosen is not None:
            try:
                result = self.dispatcher.push_event(chosen, dry_run=self.cfg.dry_run)
                self.logger.info(f"[output] {result}")
            except Exception as exc:  # noqa: BLE001 — 投递失败计入安全门，不杀循环
                self.logger.warning(f"dispatch failed: {type(exc).__name__}: {exc}")
                self.safety.record_failure(now)

    def _report(self) -> None:
        with self._state_lock:
            s = self.state
        try:
            self.report_status({
                "connected": s.connected,
                "conn_state": s.conn_state,
                "in_battle": s.in_battle,
                "scenario": s.scenario,
                "level": s.level,
                "dry_run": self.cfg.dry_run,
                "safety": self.safety.status(),
            })
        except Exception:  # noqa: BLE001
            pass

    # -------------------------------------------------------------- Hosted UI
    @ui.context(id="dashboard", title="战雷猫娘副驾驶")
    async def dashboard_context(self):
        with self._state_lock:
            s = self.state
        return {
            "enabled": self.cfg.enabled,
            "dry_run": self.cfg.dry_run,
            "connected": s.connected,
            "conn_state": s.conn_state,
            "in_battle": s.in_battle,
            "domain": s.domain,
            "vehicle_type": s.vehicle_type,
            "scenario": s.scenario,
            "level": s.level,
            "safety": self.safety.snapshot(),
            "observe": self.timeline.snapshot(),
        }

    # ------------------------------------------------------------------ 动作
    @ui.action(id="set_dry_run", label="设置 dry_run", tone="primary", group="runtime", order=10, refresh_context=True)
    @plugin_entry(
        id="set_dry_run",
        name="设置 dry_run",
        description="开/关 dry_run（开=只跑链路不真投给猫娘）。",
        input_schema={"type": "object", "properties": {"value": {"type": "boolean", "default": True}}},
    )
    async def set_dry_run(self, value: bool = True, **_):
        self.cfg.dry_run = bool(value)
        return Ok({"dry_run": self.cfg.dry_run})

    @ui.action(id="pause", label="急停", tone="danger", group="runtime", order=20, refresh_context=True)
    @plugin_entry(id="pause", name="急停", description="暂停所有提醒输出。")
    async def pause(self, **_):
        self.safety.pause()
        return Ok({"safety": self.safety.status()})

    @ui.action(id="resume", label="恢复", tone="success", group="runtime", order=30, refresh_context=True)
    @plugin_entry(id="resume", name="恢复", description="恢复提醒输出并清空安全计数。")
    async def resume(self, **_):
        self.safety.resume()
        return Ok({"safety": self.safety.status()})

    @ui.action(id="test_say", label="测试开口", tone="info", group="diagnostics", order=40, refresh_context=False)
    @plugin_entry(
        id="test_say",
        name="测试开口",
        description="立即推一条测试消息给猫娘，验证 push 链路（不受 dry_run 短路；用于接缝①③自检）。",
        input_schema={"type": "object", "properties": {"text": {"type": "string", "default": "副驾驶测试：能听到我吗？"}}},
    )
    async def test_say(self, text: str = "副驾驶测试：能听到我吗？", **_):
        try:
            self.push_message(
                source="neko_warthunder",
                visibility=[],
                ai_behavior="respond",
                parts=[{"type": "text", "text": str(text)}],
                priority=5,
                metadata={"plugin": "neko_warthunder", "kind": "test"},
            )
            return Ok({"pushed": True, "text": str(text)})
        except Exception as exc:  # noqa: BLE001
            return Err(SdkError(f"test_say push failed: {exc}"))

    @plugin_entry(id="status", name="状态", description="查看当前连接/场景/安全状态。")
    def status(self, **_):
        with self._state_lock:
            s = self.state
        return Ok({
            "enabled": self.cfg.enabled,
            "dry_run": self.cfg.dry_run,
            "connected": s.connected,
            "conn_state": s.conn_state,
            "in_battle": s.in_battle,
            "domain": s.domain,
            "vehicle_type": s.vehicle_type,
            "scenario": s.scenario,
            "level": s.level,
            "safety": self.safety.snapshot(),
            "observe": self.timeline.snapshot(),
        })
