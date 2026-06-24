"""提示仲裁器（D-B4）。候选 BattleEvent + 当前 Scenario → 至多 1 条输出。

流水线：Scenario 门控 → cooldown 去重 → 分流(抢占/限流) → 抢占立即 / 单槽窗口择优 + 全局限流。
返回 (选中事件 | None, 决策链路)；决策链路供 dry_run 日志解释"为什么说/没说"。
"""

from __future__ import annotations

from typing import Any

from .contracts import BattleEvent, category_allowed
from .safety_guard import SafetyGuard


class Arbiter:
    def __init__(self, safety: SafetyGuard) -> None:
        self.safety = safety
        self._last_fired: dict[str, float] = {}
        self._window_best: BattleEvent | None = None
        self._kill_window: BattleEvent | None = None
        self._kill_window_started_at: float = 0.0

    def reset(self) -> None:
        self._last_fired.clear()
        self._window_best = None
        self._kill_window = None
        self._kill_window_started_at = 0.0

    def decide(self, candidates: list[BattleEvent], scenario: str, now: float) -> tuple[BattleEvent | None, list[dict[str, Any]]]:
        chain: list[dict[str, Any]] = []

        if self.safety.stopped:
            for c in candidates:
                chain.append(_rec(c, "suppressed", self.safety.status()))
            return None, chain

        # [1] Scenario 门控 + [2] cooldown 去重
        survivors: list[BattleEvent] = []
        for c in candidates:
            if not category_allowed(scenario, c.category):
                chain.append(_rec(c, "dropped", f"scenario_gated({scenario})"))
                continue
            cd = c.spec.cooldown_seconds
            if cd > 0 and (now - self._last_fired.get(c.event_id, -1e9)) < cd:
                chain.append(_rec(c, "dropped", "cooldown"))
                continue
            survivors.append(c)

        preempt = [c for c in survivors if c.preempt_eligible]
        normal = [c for c in survivors if not c.preempt_eligible]

        # [3]/[4] 抢占通道
        if preempt:
            best = _top(preempt)
            crit_remaining = self.safety.critical_cooldown_remaining(now)
            if crit_remaining > 0 and best.priority < 10:
                chain.append(_rec(best, "suppressed", f"critical_cooldown({crit_remaining:.1f}s)"))
            else:
                self._fire(best, now, critical=True)
                self._window_best = None  # 抢占清空 warning 窗口（不补播）
                if self._kill_window is not None:
                    chain.append(_rec(self._kill_window, "dropped", "lost_to_preempt"))
                    self._kill_window = None
                    self._kill_window_started_at = 0.0
                chain.append(_rec(best, "spoken", "preempt"))
                for c in survivors:
                    if c is not best:
                        chain.append(_rec(c, "dropped", "lost_to_preempt"))
                return best, chain

        # [5] 限流通道：单槽窗口择优（留最高 priority），到点 flush
        kill_coalesce_window = self.safety.config.kill_coalesce_window_seconds
        if kill_coalesce_window > 0:
            kill_events = [c for c in normal if c.event_id == "you_killed"]
            normal = [c for c in normal if c.event_id != "you_killed"]
            for c in kill_events:
                self._buffer_kill(c, now)
                chain.append(_rec(c, "buffered", "kill_coalescing"))

        if normal:
            best = _top(normal)
            if self._window_best is None or _rank(best) > _rank(self._window_best):
                self._window_best = best
            for c in normal:
                if c is not best:
                    chain.append(_rec(c, "dropped", "lost_in_window"))

        rate_remaining = self.safety.rate_limit_remaining(now)
        if (
            self._kill_window is not None
            and kill_coalesce_window > 0
            and now - self._kill_window_started_at >= kill_coalesce_window
            and rate_remaining <= 0
        ):
            chosen = self._kill_window
            self._kill_window = None
            self._kill_window_started_at = 0.0
            if not category_allowed(scenario, chosen.category):
                chain.append(_rec(chosen, "dropped", f"scenario_gated_on_flush({scenario})"))
                return None, chain
            self._fire(chosen, now, critical=False)
            chain.append(_rec(chosen, "spoken", "kill_coalesced"))
            return chosen, chain

        if self._window_best is not None and rate_remaining <= 0:
            chosen = self._window_best
            self._window_best = None
            # flush 时按【当前】scenario 重新门控：缓冲期内场景可能已切到 DEAD/BATTLE_ENDED/OUT_OF_BATTLE
            if not category_allowed(scenario, chosen.category):
                chain.append(_rec(chosen, "dropped", f"scenario_gated_on_flush({scenario})"))
                return None, chain
            self._fire(chosen, now, critical=False)
            chain.append(_rec(chosen, "spoken", "window_flush"))
            return chosen, chain

        if self._window_best is not None:
            chain.append(_rec(self._window_best, "buffered", f"rate_limited({rate_remaining:.1f}s)"))
        return None, chain

    def _fire(self, event: BattleEvent, now: float, *, critical: bool) -> None:
        self._last_fired[event.event_id] = now
        self.safety.mark_output(critical=critical, now=now)

    def _buffer_kill(self, event: BattleEvent, now: float) -> None:
        if self._kill_window is None:
            payload = dict(event.payload)
            payload["kill_count"] = int(payload.get("kill_count") or 1)
            self._kill_window = BattleEvent(
                event.event_id,
                edge=event.edge,
                payload=payload,
                ts=event.ts,
                level=event.level,
            )
            self._kill_window_started_at = now
            return

        payload = dict(self._kill_window.payload)
        payload["kill_count"] = int(payload.get("kill_count") or 1) + int(event.payload.get("kill_count") or 1)
        if event.payload.get("victim") is not None:
            payload["victim"] = event.payload.get("victim")
        if event.payload.get("victim_vehicle") is not None:
            payload["victim_vehicle"] = event.payload.get("victim_vehicle")
        self._kill_window = BattleEvent(
            self._kill_window.event_id,
            edge=self._kill_window.edge,
            payload=payload,
            ts=max(self._kill_window.ts, event.ts),
            level=self._kill_window.level,
        )


def _rank(e: BattleEvent) -> tuple[int, int, float]:
    return (e.priority, e.severity, e.ts)


def _top(events: list[BattleEvent]) -> BattleEvent:
    return max(events, key=_rank)


def _rec(e: BattleEvent, result: str, reason: str) -> dict[str, Any]:
    return {"event_id": e.event_id, "edge": e.edge, "level": e.level, "result": result, "reason": reason}
