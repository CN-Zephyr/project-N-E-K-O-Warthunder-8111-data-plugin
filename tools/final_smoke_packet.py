"""Build the final live-smoke handoff packet.

This helper is intentionally read-only. It does not start N.E.K.O, War
Thunder, or the data layer. It turns the existing release scope, V2 readiness,
and live-test plan into one operator packet for the last live validation pass.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import types
from typing import Any

_BASE = pathlib.Path(__file__).resolve().parent.parent
if "neko_warthunder" not in sys.modules:
    _pkg = types.ModuleType("neko_warthunder")
    _pkg.__path__ = [str(_BASE)]  # type: ignore[attr-defined]
    sys.modules["neko_warthunder"] = _pkg

from neko_warthunder.tools.live_test_plan import build_compact_plan  # noqa: E402
from neko_warthunder.tools.rc_gap_summary import build_gap_summary  # noqa: E402
from neko_warthunder.tools.release_readiness import build_handoff, build_release_scope  # noqa: E402
from neko_warthunder.tools.v2_release_matrix import build_v2_release_matrix  # noqa: E402
from neko_warthunder.tools.v2_readiness import build_v2_readiness  # noqa: E402


def build_packet(
    *,
    plugin_root: str | pathlib.Path = _BASE,
    sample_rel: str = "local_samples/data_process_20260620",
    player_name: str = "tl0sr2",
    offline_gates_passed: bool = False,
) -> dict[str, Any]:
    root = pathlib.Path(plugin_root).resolve()
    sample = root / pathlib.Path(sample_rel)
    sample_summary = build_gap_summary(sample, player_name=player_name) if sample.exists() else None
    release_scope = build_release_scope(sample_summary)
    v2_summary = build_v2_readiness(sample_root=sample if sample.exists() else None, player_name=player_name)
    v2_matrix = build_v2_release_matrix(sample_root=sample if sample.exists() else None, player_name=player_name)
    handoff = build_handoff(release_scope, v2_summary)
    live_plan = build_compact_plan(sample, player_name=player_name) if sample.exists() else None

    return {
        "status": "ready_for_final_live_smoke_packet",
        "offline_gate_status": "passed" if offline_gates_passed else "must_run",
        "go_no_go": _go_no_go(handoff, offline_gates_passed=offline_gates_passed),
        "commands": {
            "offline_gate": "uv run python tools\\release_readiness.py --run",
            "live_monitor_once": "uv run python tools\\live_monitor.py --count 1",
            "v2_readiness": f"uv run python tools\\v2_readiness.py {sample_rel} {player_name}",
            "v2_release_matrix": f"uv run python tools\\v2_release_matrix.py {sample_rel} {player_name}",
            "live_test_plan": f"uv run python tools\\live_test_plan.py {sample_rel} {player_name}",
        },
        "handoff": handoff,
        "v1_release_scope": release_scope,
        "v2_release_scope": v2_summary.get("release_scope") or {},
        "v2_live_evidence": v2_summary.get("live_evidence") or {},
        "v2_release_matrix": {
            "verdict": v2_matrix.get("verdict"),
            "summary": v2_matrix.get("summary") or {},
            "capabilities": v2_matrix.get("capabilities") or [],
        },
        "operator_quick_checklist": (live_plan or {}).get("quick_checklist") or [],
        "remaining_live_actions": _dedupe(
            list(handoff.get("next_actions") or []) + list((live_plan or {}).get("next_steps") or [])
        ),
        "safety_boundary": {
            "dry_run_first": True,
            "free_text_real_output_allowed": bool(release_scope.get("free_text_real_output_allowed")),
            "raw_text_printed": False,
            "do_not_claim_live_only_without_sample": True,
        },
    }


def _go_no_go(handoff: dict[str, Any], *, offline_gates_passed: bool) -> str:
    if handoff.get("status") != "ready_for_final_live_smoke":
        return "no_go_fix_offline_gate"
    if not offline_gates_passed:
        return "review_required_run_offline_gate"
    return "go_dry_run_final_smoke"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def render_text(packet: dict[str, Any]) -> str:
    commands = packet.get("commands") or {}
    handoff = packet.get("handoff") or {}
    v2 = handoff.get("v2") or {}
    lines = [
        "# neko_warthunder final smoke packet",
        f"status: {packet.get('status')}",
        f"offline_gate_status: {packet.get('offline_gate_status')}",
        f"go_no_go: {packet.get('go_no_go')}",
        f"handoff_status: {handoff.get('status')}",
        f"v2_offline_gate_complete: {v2.get('offline_gate_complete')}",
        f"v2_live_evidence_complete: {v2.get('live_evidence_complete')}",
        "v2_missing: " + (", ".join(v2.get("missing") or []) or "-"),
        "",
        "commands:",
    ]
    for key in ["offline_gate", "live_monitor_once", "v2_readiness", "v2_release_matrix", "live_test_plan"]:
        lines.append(f"- {key}: `{commands.get(key)}`")
    lines.extend(
        [
            "",
            "remaining_live_actions: " + (", ".join(packet.get("remaining_live_actions") or []) or "-"),
            "safety: dry_run_first=true, raw_text_printed=false",
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the final neko_warthunder live-smoke packet.")
    parser.add_argument("--plugin-root", default=str(_BASE), help="Standalone plugin repository root.")
    parser.add_argument("--sample-rel", default="local_samples/data_process_20260620")
    parser.add_argument("--player-name", default="tl0sr2")
    parser.add_argument(
        "--offline-gates-passed",
        action="store_true",
        help="Mark the packet as ready for dry_run smoke after release_readiness --run has passed.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args(argv)

    packet = build_packet(
        plugin_root=args.plugin_root,
        sample_rel=args.sample_rel,
        player_name=args.player_name,
        offline_gates_passed=args.offline_gates_passed,
    )
    if args.json:
        print(json.dumps(packet, ensure_ascii=False, sort_keys=True))
    else:
        print(render_text(packet), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
