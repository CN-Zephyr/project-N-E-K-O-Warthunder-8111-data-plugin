"""RC handoff report tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _front_air_sample_frame() -> dict:
    return {
        "state": "in_battle",
        "timestamp": 1.0,
        "replay": False,
        "in_battle": True,
        "domain": "air",
        "vehicle": {"valid": True, "ias_kmh": 420.0, "altitude_m": 1200.0},
        "indicators": {"valid": True, "vehicle_type": "bf-109f-4", "army": "air"},
        "processed": {"flags": {}, "level": "info", "ias_kmh": 420.0, "altitude_m": 1200.0},
        "proximity": {
            "events": [
                {
                    "id": 91,
                    "kind": "enter",
                    "is_air": True,
                    "distance_m": 1500,
                    "clock": 2,
                    "relative_deg": 45,
                    "text": "unsafe raw proximity text",
                }
            ]
        },
        "situation": {
            "ground_targets": [
                {
                    "kind": "bombing_point",
                    "label": "unsafe raw objective label",
                    "grid": "B4",
                    "distance_m": 4200,
                }
            ],
        },
    }


def test_rc_handoff_report_no_sample_separates_v1_and_v2_without_live_claim():
    from neko_warthunder.tools.rc_handoff_report import build_report

    report = build_report(use_sample=False)

    assert report["status"] == "ready_for_rc_handoff_report"
    assert report["verdict"] == "rc_report_ready_run_offline_gate_before_live"
    assert report["v1"]["final_live_smoke_required"] is True
    assert report["v1"]["free_text_real_output_allowed"] is False
    assert report["v2"]["code_complete"] is True
    assert report["v2"]["offline_gate_complete"] is True
    assert report["v2"]["live_evidence_complete"] is False
    assert report["safety"]["dry_run_first"] is True
    assert report["safety"]["raw_text_printed"] is False
    assert report["safety"]["do_not_claim_live_only_without_sample"] is True
    assert "run_v2_readiness_with_local_sample" in report["next_actions"]


def test_rc_handoff_report_with_local_sample_lists_current_v2_gaps():
    from neko_warthunder.tools.rc_handoff_report import build_report

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        sample_rel = "local_samples/data_process_20260620"
        _write_jsonl(root / sample_rel / "captures" / "run" / "processed_8112.jsonl", [{"data": _front_air_sample_frame()}])
        report = build_report(
            plugin_root=root,
            sample_rel=sample_rel,
            player_name="Pilot",
            offline_gates_passed=True,
        )

    assert report["verdict"] == "rc_offline_ready_live_smoke_required"
    assert report["v2"]["code_complete"] is True
    assert report["v2"]["offline_gate_complete"] is True
    assert report["v2"]["live_evidence_complete"] is False
    assert "generic_enemy_proximity_events" in report["v2"]["missing_live_evidence"]
    assert "rear_threat_candidates" in report["v2"]["missing_live_evidence"]
    assert "ground_target_close_candidates" in report["v2"]["missing_live_evidence"]
    dumped = json.dumps(report, ensure_ascii=False)
    assert "unsafe raw proximity text" not in dumped
    assert "unsafe raw objective label" not in dumped
    assert "UNSAFE" not in dumped


def test_rc_handoff_report_cli_json_is_safe_and_parseable():
    from neko_warthunder.tools import rc_handoff_report

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = rc_handoff_report.main(["--no-sample", "--json"])

    payload = json.loads(output.getvalue())
    assert rc == 0
    assert payload["status"] == "ready_for_rc_handoff_report"
    assert payload["v2"]["code_complete"] is True
    assert payload["safety"]["raw_text_printed"] is False
    assert payload["safety"]["v2_live_verified_real_output_enabled"] is False


def test_rc_handoff_report_cli_text_is_handoff_oriented():
    from neko_warthunder.tools import rc_handoff_report

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = rc_handoff_report.main(["--no-sample", "--offline-gates-passed"])

    text = output.getvalue()
    assert rc == 0
    assert "# neko_warthunder RC handoff report" in text
    assert "v2_code_complete: True" in text
    assert "v2_live_evidence_complete: False" in text
    assert "dry_run_first=true" in text
    assert "raw_text_printed=false" in text
    assert "release_readiness.py --run" in text
    assert "UNSAFE" not in text
    assert "raw proximity" not in text
