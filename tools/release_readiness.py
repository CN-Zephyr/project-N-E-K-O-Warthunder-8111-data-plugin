"""Offline v1 release readiness helper.

This command is intentionally no-host and no-real-machine by default. It
aggregates deterministic gates and tells operators whether the branch is ready
for the final live smoke, or blocked before that point.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import types
from dataclasses import dataclass
from typing import Any, Sequence

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
    blocking: bool = True
    review_hint: str = ""


def build_checks(
    *,
    plugin_root: str | pathlib.Path,
    host_root: str | pathlib.Path | None = None,
    sample_rel: str = "local_samples/data_process_20260620",
) -> list[Check]:
    plugin = pathlib.Path(plugin_root).resolve()
    host = pathlib.Path(host_root).resolve() if host_root is not None else plugin.parent / "N.E.K.O"
    sample = plugin / pathlib.Path(sample_rel)

    checks = [
        Check("logic self-check", plugin, ["uv", "run", "python", "tests/run_logic_tests.py"]),
        Check("pytest", plugin, ["uv", "run", "pytest", "-c", "tests/pytest.ini", "tests", "-q"]),
        Check(
            "rc docs audit",
            plugin,
            ["uv", "run", "python", "tools/rc_audit.py"],
            review_hint="release/status docs must not contain stale baselines or pre-V2 blocker language",
        ),
        Check(
            "free-text release gate",
            plugin,
            ["uv", "run", "python", "tools/free_text_gate.py"],
            review_hint="raw player/HUD/combat/award text must not enter prompts or push_message text",
        ),
        Check(
            "replay degrade gate",
            plugin,
            ["uv", "run", "python", "tools/replay_gate.py"],
            review_hint="replay=true must not emit candidates, prompts, or push_message output",
        ),
        Check(
            "deferred HUD notice gate",
            plugin,
            ["uv", "run", "python", "tools/deferred_hud_gate.py"],
            review_hint="powertrain_failure must stay observable but non-speech without raw HUD text",
        ),
        Check(
            "proximity/objective awareness gate",
            plugin,
            ["uv", "run", "python", "tools/proximity_gate.py"],
            review_hint="V2 proximity.events / situation.ground_targets prompts must stay generic/safe and obey Arbiter gating",
        ),
        Check("synthetic replay", plugin, ["uv", "run", "python", "tools/replay.py"]),
    ]
    if host.exists():
        checks.append(
            Check(
                "plugin check",
                host,
                ["uv", "run", "python", "-m", "plugin.neko_plugin_cli.cli", "check", str(plugin)],
            )
        )
    if sample.exists():
        checks.extend(
            [
                Check(
                    "local sample replay",
                    plugin,
                    ["uv", "run", "python", "tools/sample_replay.py", sample_rel, "tl0sr2"],
                    review_hint="review session_summary and remaining live scope",
                ),
                Check(
                    "offline readiness report",
                    plugin,
                    ["uv", "run", "python", "tools/offline_report.py", sample_rel, "tl0sr2"],
                    review_hint="safe Markdown readiness report",
                ),
                Check(
                    "rc gap summary",
                    plugin,
                    ["uv", "run", "python", "tools/rc_gap_summary.py", sample_rel, "tl0sr2"],
                    review_hint="machine-readable v1/v2 remaining gap summary without raw telemetry text",
                ),
                Check(
                    "live test plan",
                    plugin,
                    ["uv", "run", "python", "tools/live_test_plan.py", sample_rel, "tl0sr2"],
                    review_hint="operator checklist for the final live smoke",
                ),
            ]
        )
    return checks


def run_checks(checks: Sequence[Check]) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for check in checks:
        completed = subprocess.run(check.cmd, cwd=check.cwd)
        results.append(
            {
                "name": check.name,
                "returncode": completed.returncode,
                "blocking": check.blocking,
                "cmd": " ".join(check.cmd),
            }
        )
        if check.blocking and completed.returncode != 0:
            return {
                "status": "fail",
                "verdict": "blocked",
                "checks": results,
                "next_step": f"fix {check.name} before final live smoke",
            }
    return {
        "status": "pass",
        "verdict": "ready_for_final_live_smoke",
        "checks": results,
        "next_step": "run one focused final live smoke with dry_run first",
    }


def plan_payload(checks: Sequence[Check]) -> dict[str, Any]:
    return {
        "status": "plan",
        "verdict": "not_run",
        "checks": [
            {
                "name": check.name,
                "cmd": " ".join(check.cmd),
                "cwd": str(check.cwd),
                "blocking": check.blocking,
                "review_hint": check.review_hint,
            }
            for check in checks
        ],
        "next_step": "run with --run; if pass, proceed to final live smoke",
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = [
        "# neko_warthunder v1 release readiness",
        f"status: {payload['status']}",
        f"verdict: {payload['verdict']}",
        f"next: {payload['next_step']}",
        "",
        "checks:",
    ]
    for index, check in enumerate(payload["checks"], start=1):
        suffix = ""
        if "returncode" in check:
            suffix = f" -> {check['returncode']}"
        lines.append(f"{index}. {check['name']}{suffix}")
        lines.append(f"   cmd: {check['cmd']}")
        if check.get("review_hint"):
            lines.append(f"   review: {check['review_hint']}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check v1 offline release readiness.")
    parser.add_argument("--plugin-root", default=str(_BASE), help="Standalone plugin repository root.")
    parser.add_argument(
        "--host-root",
        default=str(_BASE.parent / "N.E.K.O"),
        help="N.E.K.O host repository root for optional plugin check.",
    )
    parser.add_argument("--run", action="store_true", help="Execute checks instead of printing the plan.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    checks = build_checks(plugin_root=args.plugin_root, host_root=args.host_root)
    payload = run_checks(checks) if args.run else plan_payload(checks)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    else:
        print(render_text(payload), end="")
    return 0 if payload["status"] in {"plan", "pass"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
