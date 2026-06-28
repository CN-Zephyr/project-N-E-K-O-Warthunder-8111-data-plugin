"""Unified offline preflight helper tests."""

from __future__ import annotations

import contextlib
import io
import tempfile
import types
from pathlib import Path


def test_preflight_plan_contains_documented_checks():
    from neko_warthunder.tools import preflight

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        plugin_root = root / "plugin"
        host_root = root / "N.E.K.O"
        sample_root = plugin_root / "local_samples" / "data_process_20260620"
        sample_root.mkdir(parents=True)
        host_root.mkdir()

        checks = preflight.build_checks(plugin_root=plugin_root, host_root=host_root)
        names = [check.name for check in checks]

        assert names == [
            "logic self-check",
            "pytest",
            "free-text release gate",
            "replay degrade gate",
            "deferred HUD notice gate",
            "proximity/objective awareness gate",
            "plugin check",
            "runtime smoke",
            "synthetic replay",
            "local sample replay",
            "offline readiness report",
            "rc gap summary",
            "live test plan",
        ]
        assert checks[0].cwd == plugin_root.resolve()
        assert checks[0].cmd == ["uv", "run", "python", "tests/run_logic_tests.py"]
        assert checks[2].cmd == ["uv", "run", "python", "tools/free_text_gate.py"]
        assert "hudmsg" in checks[2].review_hint
        assert "push_message" in checks[2].review_hint
        assert checks[3].cmd == ["uv", "run", "python", "tools/replay_gate.py"]
        assert "replay=true" in checks[3].review_hint
        assert "push_message" in checks[3].review_hint
        assert checks[4].cmd == ["uv", "run", "python", "tools/deferred_hud_gate.py"]
        assert "powertrain_failure" in checks[4].review_hint
        assert checks[5].cmd == ["uv", "run", "python", "tools/proximity_gate.py"]
        assert "proximity.events" in checks[5].review_hint
        assert checks[6].cwd == host_root.resolve()
        assert checks[6].cmd[-1] == str(plugin_root.resolve())
        assert checks[7].cmd == ["uv", "run", "python", "tools/live_monitor.py", "--count", "1"]
        assert "dry_run" in checks[7].review_hint
        assert "paused" in checks[7].review_hint
        assert "8112" in checks[7].review_hint
        assert checks[-1].cmd == [
            "uv",
            "run",
            "python",
            "tools/live_test_plan.py",
            "local_samples/data_process_20260620",
            "tl0sr2",
        ]
        assert checks[-2].cmd == [
            "uv",
            "run",
            "python",
            "tools/rc_gap_summary.py",
            "local_samples/data_process_20260620",
            "tl0sr2",
        ]
        assert checks[-3].cmd == [
            "uv",
            "run",
            "python",
            "tools/offline_report.py",
            "local_samples/data_process_20260620",
            "tl0sr2",
        ]
        assert checks[-4].cmd == [
            "uv",
            "run",
            "python",
            "tools/sample_replay.py",
            "local_samples/data_process_20260620",
            "tl0sr2",
        ]


def test_preflight_plan_skips_optional_sample_when_missing():
    from neko_warthunder.tools import preflight

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        checks = preflight.build_checks(plugin_root=root, host_root=root / "missing-host")
        names = [check.name for check in checks]

        assert "plugin check" not in names
        assert "local sample replay" not in names
        assert "offline readiness report" not in names
        assert "rc gap summary" not in names
        assert "live test plan" not in names
        assert names == [
            "logic self-check",
            "pytest",
            "free-text release gate",
            "replay degrade gate",
            "deferred HUD notice gate",
            "proximity/objective awareness gate",
            "runtime smoke",
            "synthetic replay",
        ]


def test_preflight_dry_run_prints_commands_without_running():
    from neko_warthunder.tools import preflight

    with tempfile.TemporaryDirectory() as td:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = preflight.main(["--plugin-root", td])

        text = output.getvalue()
        assert rc == 0
        assert "# neko_warthunder offline preflight" in text
        assert "## Quick read" in text
        assert "baseline: logic self-check should report 217/217 passed" in text
        assert "free-text release gate must pass" in text
        assert "replay degrade gate must pass" in text
        assert "deferred HUD notice gate must pass" in text
        assert "proximity/objective awareness gate must pass" in text
        assert "if this passes: keep dry_run=true and follow the live test plan" in text
        assert "if this fails: stop before real-machine testing" in text
        assert "watch live_monitor Summary first" in text
        assert "uv run python tests/run_logic_tests.py" in text
        assert "uv run pytest -c tests/pytest.ini tests -q" in text
        assert "free-text release gate" in text
        assert "uv run python tools/free_text_gate.py" in text
        assert "replay degrade gate" in text
        assert "uv run python tools/replay_gate.py" in text
        assert "deferred HUD notice gate" in text
        assert "uv run python tools/deferred_hud_gate.py" in text
        assert "proximity/objective awareness gate" in text
        assert "uv run python tools/proximity_gate.py" in text
        assert "runtime smoke" in text
        assert "tools/live_monitor.py --count 1" in text
        assert "dry_run / paused / Hosted UI / 8112 ownership / duplicate plugin scan risk" in text
        assert "uv run python tools/replay.py" in text
        assert "use --run to execute" in text


def test_preflight_plan_points_sample_replay_to_session_summary():
    from neko_warthunder.tools import preflight

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sample_root = root / "local_samples" / "data_process_20260620"
        sample_root.mkdir(parents=True)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            rc = preflight.main(["--plugin-root", str(root), "--host-root", str(root / "missing-host")])

        text = output.getvalue()
        assert rc == 0
        assert "local sample replay" in text
        assert "review: session_summary" in text
        assert "next validation steps" in text
        assert "Operator quick checklist" in text
        assert "quick_checklist" in text
        assert "rc gap summary" in text
        assert "live test plan" in text


def test_preflight_can_write_offline_readiness_report_to_file():
    from neko_warthunder.tools import preflight

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        sample_root = root / "local_samples" / "data_process_20260620"
        report_out = root / "out" / "offline-report.md"
        sample_root.mkdir(parents=True)

        checks = preflight.build_checks(
            plugin_root=root,
            host_root=root / "missing-host",
            report_output=report_out,
        )

    offline = next(check for check in checks if check.name == "offline readiness report")
    assert offline.name == "offline readiness report"
    assert offline.cmd[-2:] == ["--output", str(report_out)]


def test_preflight_run_success_prints_next_action():
    from neko_warthunder.tools import preflight

    calls: list[list[str]] = []

    def fake_run(cmd, cwd):
        calls.append(list(cmd))
        return types.SimpleNamespace(returncode=0)

    checks = [
        preflight.Check("logic self-check", Path.cwd(), ["uv", "run", "python", "tests/run_logic_tests.py"]),
        preflight.Check("runtime smoke", Path.cwd(), ["uv", "run", "python", "tools/live_monitor.py", "--count", "1"]),
    ]
    output = io.StringIO()

    original_run = preflight.subprocess.run
    preflight.subprocess.run = fake_run
    try:
        with contextlib.redirect_stdout(output):
            rc = preflight.run_checks(checks)
    finally:
        preflight.subprocess.run = original_run

    text = output.getvalue()
    assert rc == 0
    assert len(calls) == 2
    assert "preflight passed: ready for dry_run live validation" in text
    assert "keep dry_run=true" in text


def test_preflight_run_failure_tells_operator_to_stop():
    from neko_warthunder.tools import preflight

    def fake_run(cmd, cwd):
        return types.SimpleNamespace(returncode=7)

    checks = [preflight.Check("runtime smoke", Path.cwd(), ["uv", "run", "python", "tools/live_monitor.py"])]
    output = io.StringIO()

    original_run = preflight.subprocess.run
    preflight.subprocess.run = fake_run
    try:
        with contextlib.redirect_stdout(output):
            rc = preflight.run_checks(checks)
    finally:
        preflight.subprocess.run = original_run

    text = output.getvalue()
    assert rc == 7
    assert "FAILED: runtime smoke exited with 7" in text
    assert "stop before real-machine testing" in text
