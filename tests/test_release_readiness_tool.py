"""Release readiness helper tests."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import types
from pathlib import Path


def test_release_readiness_plan_lists_offline_release_gates():
    from neko_warthunder.tools import release_readiness

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        host = root / "N.E.K.O"
        sample = root / "plugin" / "local_samples" / "data_process_20260620"
        host.mkdir()
        sample.mkdir(parents=True)

        checks = release_readiness.build_checks(plugin_root=root / "plugin", host_root=host)
        names = [check.name for check in checks]

        assert names == [
            "logic self-check",
            "pytest",
            "rc docs audit",
            "free-text release gate",
            "replay degrade gate",
            "deferred HUD notice gate",
            "proximity/objective awareness gate",
            "synthetic replay",
            "plugin check",
            "local sample replay",
            "offline readiness report",
            "live test plan",
        ]
        assert checks[2].cmd == ["uv", "run", "python", "tools/rc_audit.py"]
        assert checks[4].cmd == ["uv", "run", "python", "tools/replay_gate.py"]
        assert checks[5].cmd == ["uv", "run", "python", "tools/deferred_hud_gate.py"]
        assert checks[6].cmd == ["uv", "run", "python", "tools/proximity_gate.py"]
        assert checks[7].cmd == ["uv", "run", "python", "tools/replay.py"]


def test_release_readiness_plan_does_not_require_running_services():
    from neko_warthunder.tools import release_readiness

    with tempfile.TemporaryDirectory() as td:
        checks = release_readiness.build_checks(plugin_root=td, host_root=Path(td) / "missing-host")
        names = [check.name for check in checks]

        assert "runtime smoke" not in names
        assert "live monitor" not in names
        assert names == [
            "logic self-check",
            "pytest",
            "rc docs audit",
            "free-text release gate",
            "replay degrade gate",
            "deferred HUD notice gate",
            "proximity/objective awareness gate",
            "synthetic replay",
        ]


def test_release_readiness_run_success_returns_rc_verdict():
    from neko_warthunder.tools import release_readiness

    calls: list[list[str]] = []

    def fake_run(cmd, cwd):
        calls.append(list(cmd))
        return types.SimpleNamespace(returncode=0)

    checks = [
        release_readiness.Check("logic self-check", Path.cwd(), ["uv", "run", "python", "tests/run_logic_tests.py"]),
        release_readiness.Check("replay degrade gate", Path.cwd(), ["uv", "run", "python", "tools/replay_gate.py"]),
    ]
    original_run = release_readiness.subprocess.run
    release_readiness.subprocess.run = fake_run
    try:
        result = release_readiness.run_checks(checks)
    finally:
        release_readiness.subprocess.run = original_run

    assert len(calls) == 2
    assert result["status"] == "pass"
    assert result["verdict"] == "ready_for_final_live_smoke"


def test_release_readiness_run_failure_blocks_rc():
    from neko_warthunder.tools import release_readiness

    def fake_run(cmd, cwd):
        return types.SimpleNamespace(returncode=9)

    checks = [release_readiness.Check("pytest", Path.cwd(), ["uv", "run", "pytest"])]
    original_run = release_readiness.subprocess.run
    release_readiness.subprocess.run = fake_run
    try:
        result = release_readiness.run_checks(checks)
    finally:
        release_readiness.subprocess.run = original_run

    assert result["status"] == "fail"
    assert result["verdict"] == "blocked"
    assert result["checks"][0]["returncode"] == 9


def test_release_readiness_cli_json_is_machine_readable():
    from neko_warthunder.tools import release_readiness

    output = io.StringIO()
    with tempfile.TemporaryDirectory() as td:
        with contextlib.redirect_stdout(output):
            rc = release_readiness.main(["--plugin-root", td, "--host-root", str(Path(td) / "missing"), "--json"])

    payload = json.loads(output.getvalue())

    assert rc == 0
    assert payload["status"] == "plan"
    assert payload["verdict"] == "not_run"
    assert "rc docs audit" in [check["name"] for check in payload["checks"]]
    assert "replay degrade gate" in [check["name"] for check in payload["checks"]]
    assert "deferred HUD notice gate" in [check["name"] for check in payload["checks"]]
    assert "proximity/objective awareness gate" in [check["name"] for check in payload["checks"]]


def test_release_readiness_cli_text_names_next_step():
    from neko_warthunder.tools import release_readiness

    output = io.StringIO()
    with tempfile.TemporaryDirectory() as td:
        with contextlib.redirect_stdout(output):
            rc = release_readiness.main(["--plugin-root", td, "--host-root", str(Path(td) / "missing")])

    text = output.getvalue()

    assert rc == 0
    assert "# neko_warthunder v1 release readiness" in text
    assert "replay degrade gate" in text
    assert "deferred HUD notice gate" in text
    assert "proximity/objective awareness gate" in text
    assert "final live smoke" in text
