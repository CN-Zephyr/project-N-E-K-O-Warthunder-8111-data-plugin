"""Discrete detectors for data-layer proximity edge events.

The data layer already performs map tracking and emits ``proximity.events`` as
edge-triggered facts. The plugin only consumes those facts, deduplicates by
event id, and promotes safe metadata into low-priority awareness events.
"""

from __future__ import annotations

from typing import Any

from ...core.contracts import BattleEvent, BattleState
from .._base import DiscreteDetector


_BEHIND_CLOCKS = {5, 6, 7}


class ProximityDetector(DiscreteDetector):
    id = "proximity"

    def __init__(self) -> None:
        self._last_id: int = -1

    def reset(self) -> None:
        self._last_id = -1

    def detect(self, prev: BattleState, cur: BattleState) -> BattleEvent | None:
        if not (cur.in_battle and cur.vehicle_valid and not cur.dead):
            return None

        events = [item for item in cur.proximity_events if isinstance(item, dict)]
        ids = [_event_id(item) for item in events]
        ids = [eid for eid in ids if eid is not None]
        if not ids:
            return None
        max_id = max(ids)
        if max_id < self._last_id:
            self._last_id = -1

        newest: dict[str, Any] | None = None
        newest_rank: tuple[int, int] = (-1, -1)
        for item in events:
            eid = _event_id(item)
            if eid is None or eid <= self._last_id:
                continue
            event_id = _awareness_event_id(item)
            rank = (_event_priority(event_id), eid)
            if rank > newest_rank:
                newest = item
                newest_rank = rank

        self._last_id = max(self._last_id, max_id)
        if newest is None:
            return None

        event_id = _awareness_event_id(newest)
        return BattleEvent(event_id, payload=_payload(newest), ts=cur.timestamp or 0.0, level="warning")


def _event_id(item: dict[str, Any]) -> int | None:
    try:
        return int(item.get("id"))
    except (TypeError, ValueError):
        return None


def _awareness_event_id(item: dict[str, Any]) -> str:
    if _is_behind(item):
        return "enemy_on_six"
    if item.get("is_air") is True:
        return "air_threat_nearby"
    return "enemy_nearby"


def _is_behind(item: dict[str, Any]) -> bool:
    clock = _as_int(item.get("clock"))
    if clock in _BEHIND_CLOCKS:
        return True
    rel = _as_float(item.get("relative_deg"))
    return rel is not None and abs(rel) >= 135.0


def _event_priority(event_id: str) -> int:
    if event_id == "enemy_on_six":
        return 3
    if event_id == "air_threat_nearby":
        return 2
    return 1


def _payload(item: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "kind": _safe_short_text(item.get("kind")),
        "target_type": _safe_short_text(item.get("type")),
        "category": _safe_short_text(item.get("category")),
        "is_air": bool(item.get("is_air", False)),
        "distance_m": _as_float(item.get("distance_m")),
        "bearing_deg": _as_float(item.get("bearing_deg")),
        "compass": _safe_short_text(item.get("compass")),
        "clock": _as_int(item.get("clock")),
        "relative_deg": _as_float(item.get("relative_deg")),
        "threshold_m": _as_float(item.get("threshold_m")),
    }
    return {key: value for key, value in payload.items() if value is not None and value != ""}


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_short_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or len(text) > 32:
        return None
    return text
