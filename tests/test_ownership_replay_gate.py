"""Ownership replay gate tests."""

from __future__ import annotations

import contextlib
import io
import json


def test_ownership_replay_gate_passes_manual_identity_inference():
    from neko_warthunder.tools import ownership_replay_gate

    result = ownership_replay_gate.run_gate()

    assert result["status"] == "pass"
    assert result["failures"] == []
    assert [case["name"] for case in result["cases"]] == [
        "manual_identity_inference",
        "inference_opt_in",
        "wrong_identity",
    ]
    assert result["cases"][0]["owned_kills"] == 1
    assert result["cases"][0]["owned_deaths"] == 1
    assert result["cases"][0]["noise_items"] == 1
    assert result["cases"][0]["events"].count("you_killed") == 1
    assert result["cases"][0]["events"].count("you_died") == 1
    assert "you_killed" not in result["cases"][1]["events"]
    assert "you_died" not in result["cases"][2]["events"]
    assert result["policy"]["legacy_ownership_inference_is_opt_in"] is True
    assert result["policy"]["interference_combat_feed_must_stay_unowned"] is True


def test_ownership_replay_gate_text_is_safe():
    from neko_warthunder.tools import ownership_replay_gate

    text = ownership_replay_gate.render_text(ownership_replay_gate.run_gate())

    assert "# neko_warthunder ownership replay gate" in text
    assert "status: pass" in text
    assert "manual identity is required" in text
    assert "you_killed" in text
    assert "tl0sr2" not in text
    assert "CN-Zephyr" not in text
    assert "NoisePlayer" not in text


def test_ownership_replay_gate_cli_json():
    from neko_warthunder.tools import ownership_replay_gate

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        rc = ownership_replay_gate.main(["--json"])

    payload = json.loads(output.getvalue())
    assert rc == 0
    assert payload["status"] == "pass"
    assert payload["cases"][0]["identity_source"] == "manual"
