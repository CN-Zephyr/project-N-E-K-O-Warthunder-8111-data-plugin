"""Release-gate contracts for future free-text speech paths."""

from __future__ import annotations

import contextlib
import io
import json


def test_free_text_gate_passes_without_leaking_raw_sentinels():
    from neko_warthunder.tools import free_text_gate

    result = free_text_gate.run_gate()
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True)

    assert result["status"] == "pass"
    assert result["failures"] == []
    assert len(result["cases"]) == 3
    assert result["policy"] == {
        "raw_text_prompt_allowed": False,
        "hudmsg_combat_feed_awards_real_output_allowed": False,
        "requires_dry_run_validation_before_unstub": True,
    }
    for raw in free_text_gate.UNSAFE_SENTINELS.values():
        assert raw not in encoded


def test_free_text_gate_cli_json_is_machine_readable_and_safe():
    from neko_warthunder.tools import free_text_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = free_text_gate.main(["--json"])

    payload = json.loads(output.getvalue())
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    assert rc == 0
    assert payload["status"] == "pass"
    for raw in free_text_gate.UNSAFE_SENTINELS.values():
        assert raw not in encoded


def test_free_text_gate_cli_text_names_dry_run_only_policy_without_raw_text():
    from neko_warthunder.tools import free_text_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = free_text_gate.main([])

    text = output.getvalue()

    assert rc == 0
    assert "status: pass" in text
    assert "dry_run-only" in text
    for raw in free_text_gate.UNSAFE_SENTINELS.values():
        assert raw not in text
