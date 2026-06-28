"""Deferred HUD notice release gate tests."""

from __future__ import annotations

import contextlib
import io
import json


def test_deferred_hud_gate_keeps_powertrain_failure_non_speech():
    from neko_warthunder.tools import deferred_hud_gate

    result = deferred_hud_gate.run_gate()

    assert result["status"] == "pass"
    assert result["summary"]["deferred_notice"] == "powertrain_failure"
    assert result["summary"]["deferred_candidates"] == 0
    assert result["summary"]["prompt_built_for_deferred_notice"] is False
    assert result["summary"]["push_called_for_deferred_notice"] is False
    assert result["policy"]["powertrain_failure_speech_allowed"] is False


def test_deferred_hud_gate_json_does_not_leak_raw_hud_text():
    from neko_warthunder.tools import deferred_hud_gate

    result = deferred_hud_gate.run_gate()
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert deferred_hud_gate.RAW_HUD_SENTINEL not in encoded
    assert result["summary"]["raw_text_safe"] is True


def test_deferred_hud_gate_cli_json_is_machine_readable():
    from neko_warthunder.tools import deferred_hud_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = deferred_hud_gate.main(["--json"])

    payload = json.loads(output.getvalue())

    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["summary"]["deferred_notice"] == "powertrain_failure"


def test_deferred_hud_gate_cli_text_explains_policy():
    from neko_warthunder.tools import deferred_hud_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = deferred_hud_gate.main([])

    text = output.getvalue()

    assert rc == 0
    assert "# neko_warthunder deferred HUD notice gate" in text
    assert "powertrain_failure deferred" in text
    assert "non-speech" in text
