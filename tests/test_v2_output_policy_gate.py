"""V2 real-output policy gate tests."""

from __future__ import annotations

import contextlib
import io
import json


def test_v2_output_policy_gate_suppresses_unverified_real_output():
    from neko_warthunder.tools.v2_output_policy_gate import run_gate

    payload = run_gate()
    policy = payload["policy"]

    assert payload["status"] == "pass"
    assert policy["v2_live_verified_real_output_enabled_default"] is False
    assert policy["gated_events"] == ["enemy_on_six", "ground_target_nearby", "tailing_risk"]
    assert policy["real_output_suppressed_until_verified"] == policy["gated_events"]
    assert policy["explicit_enable_pushes"] == policy["gated_events"]
    assert policy["raw_text_printed"] is False


def test_v2_output_policy_gate_does_not_leak_raw_text():
    from neko_warthunder.tools.v2_output_policy_gate import UNSAFE, run_gate

    payload = run_gate()

    assert UNSAFE not in json.dumps(payload, ensure_ascii=False)
    assert "ignore previous instructions" not in json.dumps(payload, ensure_ascii=False)


def test_v2_output_policy_gate_cli_json_and_text_are_safe():
    from neko_warthunder.tools import v2_output_policy_gate

    json_output = io.StringIO()
    with contextlib.redirect_stdout(json_output):
        rc = v2_output_policy_gate.main(["--json"])
    payload = json.loads(json_output.getvalue())

    text_output = io.StringIO()
    with contextlib.redirect_stdout(text_output):
        text_rc = v2_output_policy_gate.main([])

    assert rc == 0
    assert text_rc == 0
    assert payload["status"] == "pass"
    assert "# neko_warthunder V2 output policy gate" in text_output.getvalue()
    assert "v2_live_evidence_pending" not in json_output.getvalue()
