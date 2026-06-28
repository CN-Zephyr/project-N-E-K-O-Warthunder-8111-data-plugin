"""Discrete detectors for safe data-layer situation summaries.

The data layer already separates mission ground targets from combat enemies.
The plugin only consumes safe metadata from ``situation.ground_targets`` and
turns nearby objective facts into low-priority awareness events.
"""

from __future__ import annotations

from typing import Any

from ...core.contracts import BattleEvent, BattleState
from .._base import DiscreteDetector

_DEFAULT_TARGET_DISTANCE_M = 3000.0


class GroundTargetDetector(DiscreteDetector):
    id = "ground_target_nearby"

    def __init__(self, *, distance_m: float = _DEFAULT_TARGET_DISTANCE_M) -> None:
        self.distance_m = max(0.0, float(distance_m))
        self._last_key: tuple[str, str, int] | None = None

    def reset(self) -> None:
        self._last_key = None

    def detect(self, prev: BattleState, cur: BattleState) -> BattleEvent | None:
        if not (cur.in_battle and cur.vehicle_valid and not cur.dead):
            return None
        if cur.domain not in {"air", "heli"}:
            return None

        targets = cur.situation.get("ground_targets") if isinstance(cur.situation, dict) else None
        if not isinstance(targets, list):
            return None

        nearest = _nearest_target(targets, self.distance_m)
        if nearest is None:
            return None

        key = _target_key(nearest)
        if key == self._last_key:
            return None
        self._last_key = key

        return BattleEvent(
            "ground_target_nearby",
            payload=_payload(nearest),
            ts=cur.timestamp or 0.0,
            level="warning",
        )


def _nearest_target(targets: list[Any], max_distance_m: float) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    best_distance = float("inf")
    for item in targets:
        if not isinstance(item, dict):
            continue
        distance = _as_float(item.get("distance_m"))
        if distance is None or distance > max_distance_m:
            continue
        if distance < best_distance:
            best = item
            best_distance = distance
    return best


def _target_key(item: dict[str, Any]) -> tuple[str, str, int]:
    kind = _safe_short_text(item.get("kind")) or "target"
    grid = _safe_short_text(item.get("grid")) or ""
    distance = _as_float(item.get("distance_m")) or 0.0
    return kind, grid, int(distance // 500)


def _payload(item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "target_kind": _safe_short_text(item.get("kind")),
        "grid": _safe_short_text(item.get("grid")),
        "distance_m": _as_float(item.get("distance_m")),
        "bearing_deg": _as_float(item.get("bearing_deg")),
        "relative_deg": _as_float(item.get("relative_deg")),
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_short_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 32:
        return None
    return text
