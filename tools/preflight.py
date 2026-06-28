"""Unified offline preflight helper for the next live test.

By default this prints the documented offline checks. Pass ``--run`` to execute
them in order. Optional checks are included only when their local paths exist.
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import types
from dataclasses import dataclass
from typing import Sequence

_BASE = pathlib.Path(__file__).resolve().parent.parent
if "neko_warthunder" not in sys.modules:
    _pkg = types.ModuleType("neko_warthunder")
    _pkg.__path__ = [str(_BASE)]  # type: ignore[attr-defined]
    sys.modules["neko_warthunder"] = _pkg


@dataclass(frozen=True)
class Check:
    name: str
    cwd: pathlib.Path
    cmd: list[str]
    review_hint: str = ""


def build_checks(
    *,
    plugin_root: str | pathlib.Path,
    host_root: str | pathlib.Path | None = None,
    sample_rel: str = "local_samples/data_process_20260620",
    report_output: str | pathlib.Path | None = None,
) -> list[Check]:
    plugin = pathlib.Path(plugin_root).resolve()
    host = pathlib.Path(host_root).resolve() if host_root is not None else plugin.parent / "N.E.K.O"
    sample = plugin / pathlib.Path(sample_rel)

    checks = [
        Check("logic self-check", plugin, ["uv", "run", "python", "tests/run_logic_tests.py"]),
        Check("pytest", plugin, ["uv", "run", "pytest", "-c", "tests/pytest.ini", "tests", "-q"]),
        Check(
            "free-text release gate",
            plugin,
            ["uv", "run", "python", "tools/free_text_gate.py"],
            "hudmsg / combat.feed / awards raw text must stay out of prompt and push_message text",
        ),
        Check(
            "replay degrade gate",
            plugin,
            ["uv", "run", "python", "tools/replay_gate.py"],
            "replay=true frames must not emit Detector candidates, prompts, or push_message output",
        ),
        Check(
            "deferred HUD notice gate",
            plugin,
            ["uv", "run", "python", "tools/deferred_hud_gate.py"],
            "powertrain_failure HUD notices must stay observable but non-speech without raw HUD text",
        ),
        Check(
            "proximity/objective awareness gate",
            plugin,
            ["uv", "run", "python", "tools/proximity_gate.py"],
            "V2 proximity.events / situation.ground_targets must produce safe metadata prompts and obey Arbiter gating",
        ),
    ]
    if host.exists():
        checks.append(
            Check(
                "plugin check",
                host,
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "plugin.neko_plugin_cli.cli",
                    "check",
                    str(plugin),
                ],
            )
        )
    checks.append(
        Check(
            "runtime smoke",
            plugin,
            ["uv", "run", "python", "tools/live_monitor.py", "--count", "1"],
            "dry_run / paused / Hosted UI / 8112 ownership / duplicate plugin scan risk",
        )
    )
    checks.append(Check("synthetic replay", plugin, ["uv", "run", "python", "tools/replay.py"]))
    if sample.exists():
        checks.append(
            Check(
                "local sample replay",
                plugin,
                ["uv", "run", "python", "tools/sample_replay.py", sample_rel, "tl0sr2"],
                "session_summary for observed outputs and next validation steps",
            )
        )
        checks.append(
            Check(
                "offline readiness report",
                plugin,
                _offline_report_cmd(sample_rel, report_output),
                "Markdown summary with Team brief, Operator quick checklist, quick_checklist JSON, and next live-test scope",
            )
        )
        checks.append(
            Check(
                "rc gap summary",
                plugin,
                ["uv", "run", "python", "tools/rc_gap_summary.py", sample_rel, "tl0sr2"],
                "compact v1/v2 remaining gap summary for release handoff without raw telemetry text",
            )
        )
        checks.append(
            Check(
                "live test plan",
                plugin,
                ["uv", "run", "python", "tools/live_test_plan.py", sample_rel, "tl0sr2"],
                "Operator quick checklist plus detailed operation steps for the next live validation run",
            )
        )
    return checks


def _offline_report_cmd(sample_rel: str, report_output: str | pathlib.Path | None) -> list[str]:
    cmd = ["uv", "run", "python", "tools/offline_report.py", sample_rel, "tl0sr2"]
    if report_output is not None:
        cmd.extend(["--output", str(report_output)])
    return cmd


def _format_cmd(check: Check) -> str:
    return " ".join(check.cmd)


def print_plan(checks: Sequence[Check]) -> None:
    print("# neko_warthunder offline preflight")
    print("## Quick read")
    print("- baseline: logic self-check should report 215/215 passed")
    print("- free-text release gate must pass before hudmsg / combat.feed / awards can be unstubbed")
    print("- replay degrade gate must pass before replay=true traffic can be considered safe")
    print("- deferred HUD notice gate must pass before powertrain_failure strategy can change")
    print("- proximity/objective awareness gate must pass before V2 proximity/objective prompts can be considered safe")
    print("- watch live_monitor Summary first for health, dry_run, Hosted UI, 8112, and output reasons")
    print("- if this passes: keep dry_run=true and follow the live test plan")
    print("- if this fails: stop before real-machine testing and fix the failed check")
    print("\n## Checks")
    for index, check in enumerate(checks, start=1):
        print(f"{index}. {check.name}")
        print(f"   cwd: {check.cwd}")
        print(f"   cmd: {_format_cmd(check)}")
        if check.review_hint:
            print(f"   review: {check.review_hint}")
    print("\nuse --run to execute")


def run_checks(checks: Sequence[Check]) -> int:
    for check in checks:
        print(f"\n==> {check.name}")
        print(f"cwd: {check.cwd}")
        print(f"cmd: {_format_cmd(check)}")
        completed = subprocess.run(check.cmd, cwd=check.cwd)
        if completed.returncode != 0:
            print(f"FAILED: {check.name} exited with {completed.returncode}")
            print("stop before real-machine testing; fix this check first")
            return completed.returncode
    print("\npreflight passed: ready for dry_run live validation")
    print("keep dry_run=true, then follow tools/live_test_plan.py and watch live_monitor Summary first")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or print neko_warthunder offline preflight checks.")
    parser.add_argument("--plugin-root", default=str(_BASE), help="Standalone plugin repository root.")
    parser.add_argument(
        "--host-root",
        default=str(_BASE.parent / "N.E.K.O"),
        help="N.E.K.O host repository root for plugin check.",
    )
    parser.add_argument("--run", action="store_true", help="Execute checks instead of only printing them.")
    parser.add_argument("--report-output", help="Write the offline readiness Markdown report to this path.")
    args = parser.parse_args(argv)

    checks = build_checks(plugin_root=args.plugin_root, host_root=args.host_root, report_output=args.report_output)
    if not args.run:
        print_plan(checks)
        return 0
    return run_checks(checks)


if __name__ == "__main__":
    raise SystemExit(main())
