"""唯一 NEKO 输出边界（D-B4）。

所有开口只走这里：把 BattleEvent 拼成"事实行 + 要求行"prompt（带 {MASTER_NAME} 占位符，
宿主按会话展开），经 push_message(visibility=[], ai_behavior="respond") 交给猫娘 LLM 润色。
dry_run 时短路、绝不真投。常驻场景上下文走 push_context(ai_behavior="read")。
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ..core.contracts import BattleEvent
from .runtime_timeline import RuntimeTimeline
from .text_safety import sanitize_event_payload

# 每个事件的"要求行"意图（不写最终台词，台词归角色 LLM）。
_INTENT: dict[str, str] = {
    "stall_risk": "濒临失速，提醒 {MASTER_NAME} 赶紧加速/松杆改出",
    "low_alt_danger": "离地太近还在下沉，催 {MASTER_NAME} 立刻拉起",
    "overspeed": "速度过头，提醒 {MASTER_NAME} 收油门改出、别把翼子拉掉",
    "overheat": "发动机过热，建议 {MASTER_NAME} 收油门散热",
    "low_fuel": "油不多了，提醒 {MASTER_NAME} 留意返航/续航",
    "you_killed": "为 {MASTER_NAME} 刚才的击杀庆祝/调侃一句",
    "you_died": "{MASTER_NAME} 被击落了，简短共情安慰一句",
    "spawn": "出场跟 {MASTER_NAME} 打个招呼、就位",
    "battle_end": "这局结束了，给 {MASTER_NAME} 收个尾/小结一句",
}

_RECOVERY_INTENT = "刚才的危险解除了，跟 {MASTER_NAME} 说句'好险、稳住了'之类的"


def _output_backpressure_seconds(plugin: Any) -> float:
    cfg = getattr(plugin, "cfg", None)
    try:
        return max(0.0, float(getattr(cfg, "output_backpressure_seconds", 20.0)))
    except (TypeError, ValueError):
        return 20.0


def _fact_line(event: BattleEvent) -> str:
    p, _ = sanitize_event_payload(event.event_id, event.payload)
    bits: list[str] = []
    order = [
        ("ias_kmh", "IAS {:.0f}km/h"),
        ("aoa_deg", "迎角 {:.0f}°"),
        ("altitude_m", "高度 {:.0f}m"),
        ("climb_ms", "垂速 {:+.0f}m/s"),
        ("mach", "M {:.2f}"),
        ("fuel_fraction", "余油 {:.0%}"),
        ("temp_c", "温度 {:.0f}℃"),
        ("kill_count", "连杀 {}"),
        ("victim", "击落 {}"),
        ("cause", "{}"),
        ("result", "战果 {}"),
    ]
    for key, fmt in order:
        if key in p and p[key] is not None:
            try:
                bits.append(fmt.format(p[key]))
            except (ValueError, TypeError):
                pass
    return "、".join(bits)


class NekoDispatcher:
    def __init__(
        self,
        plugin: Any,
        *,
        timeline: RuntimeTimeline | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.plugin = plugin
        self.timeline = timeline
        self.logger = getattr(plugin, "logger", None)
        self._clock = clock or time.time
        self._last_push_at: float | None = None
        self._last_push_priority = -1

    def build_prompt(self, event: BattleEvent) -> str:
        intent = _RECOVERY_INTENT if event.edge == "recovery" else _INTENT.get(event.event_id, "")
        fact = _fact_line(event)
        lines = []
        if fact:
            lines.append(f"[当前] {fact}")
        lines.append(f"[要求] {intent}。一句话、口语化、像副驾驶喊话，别复述数据、别解释流程。")
        return "\n".join(lines)

    def push_event(self, event: BattleEvent, *, dry_run: bool) -> str:
        """把一个 BattleEvent 投给猫娘。dry_run 时只返回摘要、不真投。"""
        if dry_run:
            text = self.build_prompt(event)
            if self.timeline:
                self.timeline.record_stage(
                    stage="dispatcher_dry_run",
                    outcome="dry_run",
                    reason="dry_run_enabled",
                    event_id=event.event_id,
                    edge=event.edge,
                    level=event.level,
                    priority=event.priority,
                    dry_run=True,
                    safe_summary=f"{event.event_id}/{event.edge}/{event.level}",
                )
            return f"dry_run(event={event.event_id}/{event.edge}/{event.level}, prio={event.priority}, preempt={event.preempt_eligible})"
        now = self._clock()
        if self._is_backpressured(event, now):
            if self.timeline:
                self.timeline.record_stage(
                    stage="dispatcher_suppressed",
                    outcome="dropped",
                    reason="output_backpressure",
                    event_id=event.event_id,
                    edge=event.edge,
                    level=event.level,
                    priority=event.priority,
                    dry_run=False,
                    safe_summary=f"{event.event_id}/{event.edge}/{event.level}",
                )
            return f"suppressed(event={event.event_id}/{event.edge}, reason=output_backpressure)"
        text = self.build_prompt(event)
        try:
            self.plugin.push_message(
                source="neko_warthunder",
                visibility=[],
                ai_behavior="respond",
                parts=[{"type": "text", "text": text}],
                priority=event.priority,
                metadata={"plugin": "neko_warthunder", "event_id": event.event_id, "level": event.level},
            )
        except Exception as exc:
            if self.timeline:
                self.timeline.record_stage(
                    stage="dispatcher_failed",
                    outcome="failed",
                    reason=type(exc).__name__,
                    event_id=event.event_id,
                    edge=event.edge,
                    level=event.level,
                    priority=event.priority,
                    dry_run=False,
                )
            raise
        self._last_push_at = now
        self._last_push_priority = event.priority
        if self.timeline:
            self.timeline.record_stage(
                stage="dispatcher_pushed",
                outcome="pushed",
                reason="push_message_accepted",
                event_id=event.event_id,
                edge=event.edge,
                level=event.level,
                priority=event.priority,
                dry_run=False,
                safe_summary=f"{event.event_id}/{event.edge}/{event.level}",
            )
        return f"pushed(event={event.event_id}/{event.edge})"

    def _is_backpressured(self, event: BattleEvent, now: float) -> bool:
        guard = _output_backpressure_seconds(self.plugin)
        if guard <= 0 or self._last_push_at is None:
            return False
        if now - self._last_push_at >= guard:
            return False
        return event.priority <= self._last_push_priority

    def push_context(self, text: str) -> None:
        """注入/恢复常驻场景上下文（ai_behavior='read'，不触发回复）。"""
        try:
            self.plugin.push_message(
                source="neko_warthunder",
                visibility=[],
                ai_behavior="read",
                parts=[{"type": "text", "text": text}],
                priority=0,
                metadata={"plugin": "neko_warthunder", "kind": "context"},
            )
        except Exception as exc:  # noqa: BLE001 — 上下文注入失败不致命
            if self.logger:
                self.logger.warning(f"push_context failed: {type(exc).__name__}")
