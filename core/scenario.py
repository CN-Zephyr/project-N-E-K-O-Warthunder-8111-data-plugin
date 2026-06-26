"""Scenario 轻量 phase 机（D-B1）。

确定性、单态、用固定优先级解析；只做提示门控，不做战局理解。
存活/出生/死亡用 `vehicle_valid`（在战且有载具遥测=存活）作 v1 启发式——
不依赖 player_name，但属粗判（见 docs/D-B1 未决项）。
"""

from __future__ import annotations

from .contracts import (
    BATTLE_ENDED,
    COMBAT_STRESS,
    CRITICAL_RISK,
    DEAD,
    IN_FLIGHT,
    OUT_OF_BATTLE,
    SPAWNING,
    BattleState,
)

# mission_status 里被视为"对局已结束"的取值（保守集；未知结束态不误判为 BATTLE_ENDED）。
_END_STATUSES = frozenset({"win", "won", "victory", "fail", "failed", "lost", "defeat", "left", "ended", "finished"})

# COMBAT_STRESS 纯物理代理（D-B1 §5）：高 G 或刚受创 → 进入；窗口内维持。
_STRESS_G_THRESHOLD = 5.0
_STRESS_WINDOW_SECONDS = 8.0


class ScenarioResolver:
    def __init__(self) -> None:
        self._prev_alive: bool = False
        self._spawn_at: float = 0.0
        self._stress_until: float = 0.0
        self._last_hud_id: int = -1  # 已见过的最大 damage 事件 id（hud_events 是累积的，只认新增）

    def reset(self) -> None:
        self._prev_alive = False
        self._spawn_at = 0.0
        self._stress_until = 0.0
        self._last_hud_id = -1

    def resolve(self, state: BattleState, now: float, grace_seconds: float) -> str:
        scenario = self._classify(state, now, grace_seconds)
        self._prev_alive = bool(state.in_battle and state.vehicle_valid and not state.dead)
        return scenario

    def seconds_since_spawn(self, now: float) -> float | None:
        if self._spawn_at <= 0:
            return None
        return max(0.0, now - self._spawn_at)

    def _classify(self, state: BattleState, now: float, grace_seconds: float) -> str:
        if not state.connected or state.conn_state == "offline":
            self._stress_until = 0.0
            self._last_hud_id = -1
            return OUT_OF_BATTLE

        if (state.mission_status or "").lower() in _END_STATUSES:
            return BATTLE_ENDED

        if not state.in_battle:
            self._stress_until = 0.0
            self._last_hud_id = -1
            return OUT_OF_BATTLE

        if state.dead:
            return DEAD

        alive = state.vehicle_valid
        if not alive:
            # 在战但无载具遥测：之前活着=刚阵亡；否则=正在进场/加载
            return DEAD if self._prev_alive else SPAWNING

        # 存活：检测(重)出生沿，刷新 grace
        if not self._prev_alive:
            self._spawn_at = now
        if now - self._spawn_at < grace_seconds:
            return SPAWNING

        if state.any_critical_flag():
            return CRITICAL_RISK

        if self._combat_stress(state, now):
            return COMBAT_STRESS

        return IN_FLIGHT

    def _combat_stress(self, state: BattleState, now: float) -> bool:
        triggered = False
        if state.g_now is not None and abs(state.g_now) >= _STRESS_G_THRESHOLD:
            triggered = True
        # 只在“新”受创时触发：hud_events 累积，按 damage 事件 id 取增量，避免永久卡在 COMBAT_STRESS
        max_dmg_id: int | None = None
        for e in state.hud_events:
            if str(e.get("kind")) != "damage":
                continue
            try:
                eid = int(e.get("id"))
            except (TypeError, ValueError):
                continue
            if max_dmg_id is None or eid > max_dmg_id:
                max_dmg_id = eid
        if max_dmg_id is not None:
            if max_dmg_id < self._last_hud_id:  # 新对局 id 回退 → 重置
                self._last_hud_id = -1
            if max_dmg_id > self._last_hud_id:
                triggered = True
                self._last_hud_id = max_dmg_id
        if triggered:
            self._stress_until = now + _STRESS_WINDOW_SECONDS
        return now < self._stress_until
