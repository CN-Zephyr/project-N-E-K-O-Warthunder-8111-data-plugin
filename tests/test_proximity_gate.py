"""V2 proximity awareness release gate tests."""

from __future__ import annotations

import contextlib
import io
import json


def test_proximity_gate_passes_and_reports_safe_summary():
    from neko_warthunder.tools.proximity_gate import UNSAFE, run_gate

    result = run_gate()

    assert result["status"] == "pass"
    assert result["emitted"] == ["enemy_nearby", "air_threat_nearby", "enemy_on_six"]
    assert result["combat_stress_low_priority"] == "dropped"
    assert result["critical_preempt"] == "low_alt_danger"
    assert result["push_text_safe"] is True
    assert UNSAFE not in json.dumps(result, ensure_ascii=False)


def test_proximity_gate_cli_outputs_json():
    from neko_warthunder.tools import proximity_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = proximity_gate.main()

    payload = json.loads(output.getvalue())

    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["emitted"][-1] == "enemy_on_six"
