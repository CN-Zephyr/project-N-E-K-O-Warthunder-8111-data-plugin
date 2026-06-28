"""V2 release matrix tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _frame(event_id: int, *, timestamp: float, rear: bool, distance_m: int, target_distance_m: int) -> dict:
    return {
        "state": "in_battle",
        "timestamp": timestamp,
        "replay": False,
        "in_battle": True,
        "domain": "air",
        "vehicle": {"valid": True, "ias_kmh": 420.0, "altitude_m": 1200.0},
        "indicators": {"valid": True, "vehicle_type": "bf-109f-4", "army": "air"},
        "processed": {"flags": {}, "level": "info", "ias_kmh": 420.0, "altitude_m": 1200.0},
        "proximity": {
            "events": [
                {
                    "id": event_id,
                    "kind": "enter",
                    "is_air": True,
                    "distance_m": distance_m,
                    "clock": 6 if rear else 2,
                    "relative_deg": 178 if rear else 45,
                    "text": "UNSAFE raw proximity text",
                }
            ]
        },
        "situation": {
            "ground_targets": [
                {
                    "kind": "bombing_point",
                    "label": "UNSAFE raw target label",
                    "grid": "B4",
                    "distance_m": target_distance_m,
                }
            ],
        },
    }


def test_v2_release_matrix_no_sample_is_code_complete_but_live_unchecked():
    from neko_warthunder.tools.v2_release_matrix import build_v2_release_matrix

    payload = build_v2_release_matrix(sample_root=None)

    assert payload["verdict"] == "v2_code_complete_live_pending"
    assert payload["summary"]["code_complete"] is True
    assert payload["summary"]["offline_gate_complete"] is True
    assert payload["summary"]["live_evidence_complete"] is False
    assert {row["id"] for row in payload["capabilities"]} == {
        "enemy_nearby",
        "air_threat_nearby",
        "enemy_on_six",
        "tailing_risk",
        "ground_target_nearby",
    }
    assert all(row["raw_text_allowed"] is False for row in payload["capabilities"])
    assert all(row["live_evidence_status"] == "not_checked" for row in payload["capabilities"])


def test_v2_release_matrix_marks_missing_live_only_capabilities_without_raw_text():
    from neko_warthunder.tools.v2_release_matrix import build_v2_release_matrix

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_jsonl(
            root / "captures" / "run" / "processed_8112.jsonl",
            [{"data": _frame(1, timestamp=1.0, rear=False, distance_m=1800, target_distance_m=4200)}],
        )
        payload = build_v2_release_matrix(sample_root=root)

    rows = {row["id"]: row for row in payload["capabilities"]}
    assert payload["verdict"] == "v2_code_complete_live_pending"
    assert rows["enemy_nearby"]["live_evidence_status"] == "covered_by_current_sample"
    assert rows["air_threat_nearby"]["live_evidence_status"] == "covered_by_current_sample"
    assert rows["enemy_on_six"]["live_evidence_status"] == "needs_live_sample"
    assert rows["tailing_risk"]["live_evidence_status"] == "needs_live_sample"
    assert rows["ground_target_nearby"]["live_evidence_status"] == "needs_live_sample"
    assert "enemy_on_six" in payload["summary"]["blocked_real_output_until_live_evidence"]
    encoded = json.dumps(payload, ensure_ascii=False)
    assert "UNSAFE raw proximity text" not in encoded
    assert "UNSAFE raw target label" not in encoded


def test_v2_release_matrix_complete_sample_closes_live_evidence():
    from neko_warthunder.tools.v2_release_matrix import build_v2_release_matrix

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_jsonl(
            root / "captures" / "run" / "processed_8112.jsonl",
            [
                {"data": _frame(10, timestamp=1.0, rear=True, distance_m=850, target_distance_m=1200)},
                {"data": _frame(11, timestamp=2.0, rear=True, distance_m=700, target_distance_m=1100)},
            ],
        )
        payload = build_v2_release_matrix(sample_root=root)

    assert payload["verdict"] == "v2_live_verified"
    assert payload["summary"]["live_evidence_complete"] is True
    assert payload["summary"]["blocked_real_output_until_live_evidence"] == []
    assert all(row["live_evidence_status"] == "complete" for row in payload["capabilities"])


def test_v2_release_matrix_cli_outputs_json_and_text():
    from neko_warthunder.tools import v2_release_matrix

    json_output = io.StringIO()
    with contextlib.redirect_stdout(json_output):
        rc = v2_release_matrix.main(["--no-sample", "--json"])
    payload = json.loads(json_output.getvalue())

    text_output = io.StringIO()
    with contextlib.redirect_stdout(text_output):
        text_rc = v2_release_matrix.main(["--no-sample"])

    assert rc == 0
    assert text_rc == 0
    assert payload["summary"]["code_complete"] is True
    assert "# neko_warthunder V2 release matrix" in text_output.getvalue()
    assert "enemy_on_six" in text_output.getvalue()
