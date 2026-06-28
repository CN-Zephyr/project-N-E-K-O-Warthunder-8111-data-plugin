"""V2 readiness summary tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _v2_live_frame(event_id: int, *, timestamp: float, proximity_distance_m: int, target_distance_m: int) -> dict:
    return {
        "state": "in_battle",
        "timestamp": timestamp,
        "replay": False,
        "in_battle": True,
        "domain": "air",
        "vehicle": {"valid": True, "ias_kmh": 420.0, "altitude_m": 1300.0},
        "indicators": {"valid": True, "vehicle_type": "ki_61_1a_otsu_china", "army": "air"},
        "processed": {
            "flags": {},
            "level": "info",
            "ias_kmh": 420.0,
            "altitude_m": 1300.0,
        },
        "combat": {
            "player_name": "Pilot",
            "self": {"name": "Pilot", "source": "manual", "confidence": 1.0},
            "feed": [],
        },
        "proximity": {
            "events": [
                {
                    "id": event_id,
                    "kind": "enter",
                    "type": "fighter",
                    "category": "enemy_air",
                    "is_air": True,
                    "distance_m": proximity_distance_m,
                    "clock": 6,
                    "relative_deg": 175,
                    "text": "unsafe raw rear proximity",
                }
            ]
        },
        "situation": {
            "air_threat_count": 1,
            "ground_targets": [
                {
                    "kind": "bombing_point",
                    "label": "unsafe raw objective label",
                    "grid": "B4",
                    "distance_m": target_distance_m,
                    "bearing_deg": 90,
                }
            ],
        },
    }


def _v2_generic_frame(event_id: int, *, timestamp: float) -> dict:
    frame = _v2_live_frame(event_id, timestamp=timestamp, proximity_distance_m=1400, target_distance_m=4200)
    frame["proximity"] = {
        "events": [
            {
                "id": event_id,
                "kind": "enter",
                "type": "tank",
                "category": "enemy_ground",
                "is_air": False,
                "distance_m": 1500,
                "clock": 2,
                "relative_deg": 40,
                "text": "unsafe raw generic proximity",
            }
        ]
    }
    return frame


def _v2_air_frame(event_id: int, *, timestamp: float) -> dict:
    frame = _v2_live_frame(event_id, timestamp=timestamp, proximity_distance_m=1400, target_distance_m=4200)
    frame["proximity"]["events"][0]["clock"] = 2
    frame["proximity"]["events"][0]["relative_deg"] = 45
    frame["proximity"]["events"][0]["text"] = "unsafe raw air proximity"
    return frame


def test_v2_readiness_no_sample_marks_offline_complete_without_live_claim():
    from neko_warthunder.tools.v2_readiness import build_v2_readiness

    payload = build_v2_readiness(sample_root=None)

    assert payload["status"] == "pass"
    assert payload["verdict"] == "v2_offline_complete_sample_not_checked"
    assert payload["offline_scope"]["status"] == "complete"
    assert payload["offline_scope"]["implemented_events"] == [
        "enemy_nearby",
        "air_threat_nearby",
        "enemy_on_six",
        "tailing_risk",
        "ground_target_nearby",
    ]
    assert payload["release_scope"]["v2_code_complete"] is True
    assert payload["release_scope"]["v2_live_evidence_complete"] is False
    assert "run_v2_readiness_with_local_sample" in payload["live_evidence"]["next_actions"]


def test_v2_readiness_with_complete_sample_closes_live_evidence_safely():
    from neko_warthunder.tools.v2_readiness import build_v2_readiness

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_jsonl(
            root / "captures" / "run" / "processed_8112.jsonl",
            [
                {"data": _v2_generic_frame(90, timestamp=0.0)},
                {"data": _v2_air_frame(99, timestamp=0.5)},
                {"data": _v2_live_frame(100, timestamp=1.0, proximity_distance_m=850, target_distance_m=1200)},
                {"data": _v2_live_frame(101, timestamp=2.0, proximity_distance_m=700, target_distance_m=1100)},
            ],
        )
        payload = build_v2_readiness(sample_root=root, player_name="Pilot")

    assert payload["verdict"] == "v2_complete_with_sample_evidence"
    assert payload["live_evidence"]["status"] == "complete"
    assert payload["live_evidence"]["missing"] == []
    evidence = payload["live_evidence"]["capability_evidence"]
    assert evidence["enemy_on_six"]["trigger_count"] == 1
    assert evidence["tailing_risk"]["observed_count"] == 2
    assert evidence["tailing_risk"]["trigger_count"] == 1
    assert evidence["ground_target_nearby"]["observed_count"] == 2
    assert evidence["ground_target_nearby"]["trigger_count"] == 1
    assert payload["release_scope"]["v2_live_evidence_complete"] is True
    text = json.dumps(payload, ensure_ascii=False)
    assert "unsafe raw rear proximity" not in text
    assert "unsafe raw objective label" not in text


def test_v2_readiness_cli_json_is_machine_readable():
    from neko_warthunder.tools import v2_readiness

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = v2_readiness.main(["--no-sample", "--json"])

    payload = json.loads(output.getvalue())
    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["release_scope"]["v2_offline_gate_complete"] is True


def test_v2_readiness_cli_text_names_remaining_actions():
    from neko_warthunder.tools import v2_readiness

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = v2_readiness.main(["missing-sample-root"])

    text = output.getvalue()
    assert rc == 0
    assert "# neko_warthunder V2 readiness" in text
    assert "live_evidence: needs_live_sample" in text
    assert "capability_evidence: -" in text
    assert "capture_local_telemetry_sample" in text
