"""RC gap summary tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _sample_frame() -> dict:
    return {
        "state": "in_battle",
        "timestamp": 10.0,
        "in_battle": True,
        "vehicle": {"valid": True, "ias_kmh": 900, "altitude_m": 1200},
        "indicators": {"valid": True, "vehicle_type": "fighter", "army": "air"},
        "processed": {
            "flags": {"overspeed_warn": True},
            "level": "warning",
            "ias_kmh": 900,
            "altitude_m": 1200,
        },
        "combat": {
            "self": {"name": "Pilot", "source": "auto", "confidence": 0.4},
            "feed": [{"id": 1, "is_kill": True, "killer": "RawKiller", "victim": "RawVictim", "raw": "unsafe"}],
        },
        "hud_notices": {"feed": [{"id": 1, "code": "engine_overheat", "text": "raw hud"}]},
        "awards": {"feed": [{"id": 1, "text": "raw award"}]},
        "proximity": {"events": [{"id": 1, "kind": "enter", "is_air": True, "distance_m": 1700}]},
        "situation": {"ground_targets": [{"kind": "base", "label": "raw target", "grid": "B4", "distance_m": 2300}]},
    }


def test_rc_gap_summary_reports_release_tracks_without_raw_text():
    from neko_warthunder.tools.rc_gap_summary import build_gap_summary

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_jsonl(root / "captures" / "one" / "processed_8112.jsonl", [{"data": _sample_frame()}])

        summary = build_gap_summary(root, player_name="Pilot")

    assert summary["status"] == "needs_more_samples"
    assert summary["tracks"]["v1_free_text_output"]["status"] == "blocked_for_real_output"
    assert summary["tracks"]["v2_proximity_objective"]["status"] == "needs_more_samples"
    assert "v1_free_text_output" in summary["blocked_release_items"]
    assert "v2_proximity_objective" in summary["sample_unproven_items"]
    assert "v2_proximity_objective" not in summary["blocked_release_items"]
    assert "run_free_text_dry_run_safety_check" in summary["next_actions"]
    encoded = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    assert "RawKiller" not in encoded
    assert "raw hud" not in encoded
    assert "raw award" not in encoded
    assert "raw target" not in encoded


def test_rc_gap_summary_missing_sample_is_actionable():
    from neko_warthunder.tools.rc_gap_summary import build_gap_summary

    summary = build_gap_summary(Path("missing-sample-root"), player_name="Pilot")

    assert summary["status"] == "no_sample"
    assert summary["remaining_gaps"] == ["sample_root_missing"]
    assert summary["next_actions"] == ["capture_local_telemetry_sample"]


def test_rc_gap_summary_cli_json_is_machine_readable():
    from neko_warthunder.tools import rc_gap_summary

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_jsonl(root / "captures" / "one" / "processed_8112.jsonl", [{"data": _sample_frame()}])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = rc_gap_summary.main([str(root), "Pilot", "--json"])

    payload = json.loads(output.getvalue())

    assert rc == 0
    assert payload["status"] == "needs_more_samples"
    assert "v2_proximity_objective" in payload["tracks"]


def test_rc_gap_summary_cli_text_lists_tracks():
    from neko_warthunder.tools import rc_gap_summary

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _write_jsonl(root / "captures" / "one" / "processed_8112.jsonl", [{"data": _sample_frame()}])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = rc_gap_summary.main([str(root), "Pilot"])

    text = output.getvalue()

    assert rc == 0
    assert "# neko_warthunder RC gap summary" in text
    assert "v1_free_text_output" in text
    assert "v2_proximity_objective" in text
