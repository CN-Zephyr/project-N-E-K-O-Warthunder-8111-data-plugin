"""V2 completion gate tests."""

from __future__ import annotations

import contextlib
import io
import json


def test_v2_completion_gate_passes_code_offline_without_live_claim():
    from neko_warthunder.tools.v2_completion_gate import run_gate

    payload = run_gate(sample_root=None)

    assert payload["status"] == "pass"
    assert payload["verdict"] == "v2_code_offline_complete_live_evidence_pending"
    assert payload["completion"]["code_complete"] is True
    assert payload["completion"]["offline_gate_complete"] is True
    assert payload["completion"]["live_evidence_complete"] is False
    assert payload["completion"]["real_output_policy_safe"] is True
    assert payload["completion"]["raw_text_printed"] is False
    assert payload["release_policy"]["dry_run_first"] is True
    assert payload["release_policy"]["do_not_claim_live_only_without_sample"] is True
    assert payload["release_policy"]["blocked_real_output_until_live_evidence"] == [
        "enemy_on_six",
        "ground_target_nearby",
        "tailing_risk",
    ]
    assert "run_v2_readiness_with_local_sample" in payload["next_actions"]


def test_v2_completion_gate_with_local_sample_keeps_live_gaps_explicit():
    from neko_warthunder.tools.v2_completion_gate import run_gate

    payload = run_gate(sample_root="local_samples/data_process_20260620", player_name="tl0sr2")

    assert payload["status"] == "pass"
    assert payload["completion"]["code_complete"] is True
    assert payload["completion"]["offline_gate_complete"] is True
    assert payload["completion"]["live_evidence_complete"] is False
    assert "generic_enemy_proximity_events" in payload["live_evidence"]["missing"]
    assert "proximity_rear_events" in payload["live_evidence"]["missing"]
    assert "ground_target_close_candidates" in payload["live_evidence"]["missing"]
    assert payload["matrix"]["summary"]["live_evidence_complete"] is False


def test_v2_completion_gate_cli_json_and_text_are_safe():
    from neko_warthunder.tools import v2_completion_gate

    json_output = io.StringIO()
    with contextlib.redirect_stdout(json_output):
        rc = v2_completion_gate.main(["--no-sample", "--json"])
    assert rc == 0
    payload = json.loads(json_output.getvalue())
    assert payload["status"] == "pass"
    assert payload["completion"]["raw_text_printed"] is False

    text_output = io.StringIO()
    with contextlib.redirect_stdout(text_output):
        text_rc = v2_completion_gate.main(["--no-sample"])
    assert text_rc == 0
    text = text_output.getvalue()
    assert "# neko_warthunder V2 completion gate" in text
    assert "verdict: v2_code_offline_complete_live_evidence_pending" in text
    assert "raw_text_printed: false" in text
    assert "UNSAFE" not in text
    assert "raw proximity" not in text
