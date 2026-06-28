"""Release-gate contracts for replay=true degrade mode."""

from __future__ import annotations

import contextlib
import io
import json


def test_replay_gate_passes_without_prompt_or_push_output():
    from neko_warthunder.tools import replay_gate

    result = replay_gate.run_gate()
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["status"] == "pass"
    assert result["failures"] == []
    assert result["policy"] == {
        "replay_detector_events_allowed": False,
        "replay_prompt_allowed": False,
        "replay_push_message_allowed": False,
    }
    assert result["summary"] == {
        "frames": 3,
        "candidates": 0,
        "prompts": 0,
        "push_messages": 0,
    }
    for raw in replay_gate.REPLAY_RAW_SENTINELS.values():
        assert raw not in encoded


def test_replay_gate_cli_json_is_machine_readable_and_safe():
    from neko_warthunder.tools import replay_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = replay_gate.main(["--json"])

    payload = json.loads(output.getvalue())
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["summary"]["push_messages"] == 0
    for raw in replay_gate.REPLAY_RAW_SENTINELS.values():
        assert raw not in encoded


def test_replay_gate_cli_text_reports_suppressed_without_raw_text():
    from neko_warthunder.tools import replay_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = replay_gate.main([])

    text = output.getvalue()

    assert rc == 0
    assert "status: pass" in text
    assert "replay=true frames suppressed" in text
    assert "push_messages=0" in text
    for raw in replay_gate.REPLAY_RAW_SENTINELS.values():
        assert raw not in text
