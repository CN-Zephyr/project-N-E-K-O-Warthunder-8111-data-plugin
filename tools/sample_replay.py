"""Replay local data-layer sample dumps through the plugin logic.

This tool is intended for ignored local samples under ``local_samples/``. It
does not persist output and its summaries intentionally avoid raw free text.
"""

from __future__ import annotations

import gzip
import json
import pathlib
import sys
import types
import argparse
from collections import Counter
from typing import Any, Iterable

_BASE = pathlib.Path(__file__).resolve().parent.parent
if "neko_warthunder" not in sys.modules:
    _pkg = types.ModuleType("neko_warthunder")
    _pkg.__path__ = [str(_BASE)]  # type: ignore[attr-defined]
    sys.modules["neko_warthunder"] = _pkg

from neko_warthunder.adapters.neko_dispatcher import NekoDispatcher  # noqa: E402
from neko_warthunder.adapters.telemetry_client import parse_telemetry  # noqa: E402
from neko_warthunder.adapters.event_labels import display_event_key  # noqa: E402
from neko_warthunder.core.arbiter import Arbiter  # noqa: E402
from neko_warthunder.core.contracts import BattleState, WtConfig  # noqa: E402
from neko_warthunder.core.safety_guard import SafetyGuard  # noqa: E402
from neko_warthunder.core.scenario import ScenarioResolver  # noqa: E402
from neko_warthunder.detectors._base import DetectorEngine  # noqa: E402
from neko_warthunder.detectors.condition.flight_safety import build_condition_detectors  # noqa: E402
from neko_warthunder.detectors.discrete.lifecycle import build_discrete_detectors  # noqa: E402


def discover_sample_files(root: str | pathlib.Path) -> list[pathlib.Path]:
    base = pathlib.Path(root)
    files = list(base.glob("captures/*/processed_8112.jsonl"))
    files.extend(base.glob("records/*/frames*.jsonl.gz"))
    return sorted(files, key=lambda p: p.as_posix())


def _iter_jsonl(path: pathlib.Path) -> Iterable[dict[str, Any]]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
            yield from _loads_lines(f)
        return
    with path.open("r", encoding="utf-8", errors="replace") as f:
        yield from _loads_lines(f)


def _loads_lines(lines: Iterable[str]) -> Iterable[dict[str, Any]]:
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        data = json.loads(stripped)
        if isinstance(data, dict):
            yield data


def _unwrap_payload(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data")
    return data if isinstance(data, dict) else row


def replay_sample_root(root: str | pathlib.Path, *, player_name: str = "") -> dict[str, Any]:
    files = discover_sample_files(root)
    cfg = WtConfig(
        player_name=player_name,
        dry_run=True,
        global_rate_limit_seconds=0,
        critical_preempt_cooldown_seconds=0,
        spawn_grace_seconds=0,
    )
    resolver = ScenarioResolver()
    engine = DetectorEngine(list(build_condition_detectors()) + list(build_discrete_detectors(cfg.player_name)))
    arbiter = Arbiter(SafetyGuard(cfg))
    dispatcher = NekoDispatcher(None)

    report: dict[str, Any] = {
        "root": str(pathlib.Path(root)),
        "files": len(files),
        "frames": 0,
        "states": Counter(),
        "domains": Counter(),
        "flags": Counter(),
        "events": Counter(),
        "chosen": Counter(),
        "dry_run_outputs": Counter(),
        "sample_files": [str(p.relative_to(root)) if pathlib.Path(root) in p.parents else str(p) for p in files],
        "coverage": {
            "replay_true": 0,
            "replay_candidate_events": 0,
            "replay_chosen_events": 0,
            "replay_dry_run_outputs": 0,
            "combat_feed_items": 0,
            "is_my_kill_field": 0,
            "is_my_death_field": 0,
            "involves_me_field": 0,
            "is_my_kill_true": 0,
            "is_my_death_true": 0,
            "involves_me_true": 0,
            "combat_self_source": Counter(),
            "active_players_max": 0,
            "hud_notice_codes": Counter(),
            "hud_notice_severities": Counter(),
            "hud_notice_raw_text_fields": 0,
            "awards_items": 0,
            "awards_raw_text_fields": 0,
            "combat_feed_raw_text_fields": 0,
        },
    }

    prev = BattleState()
    now = 1000.0
    for path in files:
        for row in _iter_jsonl(path):
            payload = _unwrap_payload(row)
            cur = parse_telemetry(payload)
            _record_coverage(report["coverage"], payload)
            report["frames"] += 1
            report["states"][cur.conn_state] += 1
            report["domains"][cur.domain] += 1
            for key, value in cur.flags.items():
                if value:
                    report["flags"][key] += 1

            cur.scenario = resolver.resolve(cur, now, cfg.spawn_grace_seconds)
            candidates = engine.feed(prev, cur)
            if cur.replay:
                report["coverage"]["replay_candidate_events"] += len(candidates)
            for event in candidates:
                report["events"][f"{event.event_id}/{event.level}"] += 1

            chosen, _chain = arbiter.decide(candidates, cur.scenario, now)
            if chosen is not None:
                event_key = f"{chosen.event_id}/{chosen.level}"
                report["chosen"][event_key] += 1
                if cur.replay:
                    report["coverage"]["replay_chosen_events"] += 1
                result = dispatcher.push_event(chosen, dry_run=True)
                if cur.replay:
                    report["coverage"]["replay_dry_run_outputs"] += 1
                report["dry_run_outputs"][result.split(",", 1)[0].replace("dry_run(event=", "")] += 1
            prev = cur
            now += 1.0

    return _plain_report(report)


def _record_coverage(coverage: dict[str, Any], payload: dict[str, Any]) -> None:
    if payload.get("replay") is True:
        coverage["replay_true"] += 1

    combat = payload.get("combat") if isinstance(payload.get("combat"), dict) else {}
    feed = combat.get("feed") if isinstance(combat.get("feed"), list) else []
    coverage["combat_feed_items"] += len(feed)
    coverage["combat_feed_raw_text_fields"] += _count_raw_text_items(feed)
    for item in feed:
        if not isinstance(item, dict):
            continue
        if "is_my_kill" in item:
            coverage["is_my_kill_field"] += 1
        if "is_my_death" in item:
            coverage["is_my_death_field"] += 1
        if "involves_me" in item:
            coverage["involves_me_field"] += 1
        if item.get("is_my_kill") is True:
            coverage["is_my_kill_true"] += 1
        if item.get("is_my_death") is True:
            coverage["is_my_death_true"] += 1
        if item.get("involves_me") is True:
            coverage["involves_me_true"] += 1

    self_info = combat.get("self") if isinstance(combat.get("self"), dict) else None
    if self_info:
        coverage["combat_self_source"][str(self_info.get("source") or "unknown")] += 1

    active_players = combat.get("active_players") if isinstance(combat.get("active_players"), list) else []
    coverage["active_players_max"] = max(coverage["active_players_max"], len(active_players))

    notices = payload.get("hud_notices") if isinstance(payload.get("hud_notices"), dict) else {}
    notice_feed = notices.get("feed") if isinstance(notices.get("feed"), list) else []
    coverage["hud_notice_raw_text_fields"] += _count_raw_text_items(notice_feed)
    for item in notice_feed:
        if isinstance(item, dict):
            coverage["hud_notice_codes"][str(item.get("code") or "unknown")] += 1
            coverage["hud_notice_severities"][str(item.get("severity") or "unknown")] += 1

    awards = payload.get("awards") if isinstance(payload.get("awards"), dict) else {}
    awards_feed = awards.get("feed") if isinstance(awards.get("feed"), list) else []
    coverage["awards_items"] += len(awards_feed)
    coverage["awards_raw_text_fields"] += _count_raw_text_items(awards_feed)


def _count_raw_text_items(items: list[Any]) -> int:
    return sum(1 for item in items if isinstance(item, dict) and _has_raw_text_field(item))


def _has_raw_text_field(item: dict[str, Any]) -> bool:
    raw_keys = {
        "text",
        "raw",
        "raw_text",
        "message",
        "hudmsg",
        "hud_text",
        "notice_text",
        "feed_text",
        "feed_raw",
        "award_text",
        "award_name",
        "award_title",
        "player_name",
        "enemy_name",
        "killer",
        "killer_name",
        "victim",
        "victim_name",
        "assist_name",
        "squad_name",
    }
    return any(key in item and item.get(key) not in {None, ""} for key in raw_keys)


def _plain_report(report: dict[str, Any]) -> dict[str, Any]:
    plain = dict(report)
    for key in ("states", "domains", "flags", "events", "chosen", "dry_run_outputs"):
        plain[key] = dict(report[key])
    plain["coverage"] = _plain_value(report["coverage"])
    plain["coverage_gaps"] = _coverage_gaps(plain)
    plain["session_summary"] = _session_summary(plain)
    return plain


def _session_summary(report: dict[str, Any]) -> dict[str, Any]:
    gaps = list(report.get("coverage_gaps") or [])
    next_steps = _next_steps_for_gaps(gaps)
    if report.get("files", 0) == 0:
        next_steps.insert(0, "add_sample_capture")
    if report.get("frames", 0) > 0 and not report.get("dry_run_outputs"):
        next_steps.append("inspect_detector_or_arbiter_chain")
    sample_next_steps = list(next_steps)
    next_steps.extend(_runtime_output_next_steps())

    checks = _validation_checks(report)
    return {
        "status": "ready_for_live_review" if not sample_next_steps else "needs_more_samples",
        "observed_events": sorted((report.get("events") or {}).keys()),
        "observed_event_labels": [display_event_key(key) for key in sorted((report.get("events") or {}).keys())],
        "chosen_events": sorted((report.get("chosen") or {}).keys()),
        "chosen_event_labels": [display_event_key(key) for key in sorted((report.get("chosen") or {}).keys())],
        "observed_outputs": sorted((report.get("dry_run_outputs") or {}).keys()),
        "observed_output_labels": [
            display_event_key(key) for key in sorted((report.get("dry_run_outputs") or {}).keys())
        ],
        "validation_checks": checks,
        "next_steps": _dedupe(next_steps),
        "live_test_plan": _live_test_plan(checks),
    }


def _validation_checks(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = report.get("coverage") or {}
    flags = report.get("flags") or {}
    notice_codes = coverage.get("hud_notice_codes") or {}
    severities = coverage.get("hud_notice_severities") or {}

    numeric_missing: list[str] = []
    if flags.get("overspeed_critical", 0) == 0:
        numeric_missing.append("overspeed_critical")

    ownership_missing: list[str] = []
    has_ownership_fields = (
        coverage.get("is_my_kill_field", 0) > 0
        or coverage.get("is_my_death_field", 0) > 0
        or coverage.get("involves_me_field", 0) > 0
    )
    has_owned_hit = (
        coverage.get("is_my_kill_true", 0) > 0
        or coverage.get("is_my_death_true", 0) > 0
        or coverage.get("involves_me_true", 0) > 0
    )
    combat_self_source = coverage.get("combat_self_source") or {}
    if not has_ownership_fields:
        ownership_missing.append("ownership_fields")
    elif not has_owned_hit:
        ownership_missing.append("owned_kill_or_death")
    if combat_self_source.get("manual", 0) == 0:
        ownership_missing.append("manual_identity")

    free_text_observed: list[str] = []
    free_text_missing: list[str] = []
    if coverage.get("combat_feed_items", 0) > 0:
        free_text_observed.append("combat_feed")
    else:
        free_text_missing.append("combat_feed")
    if notice_codes:
        free_text_observed.append("hud_notices")
    else:
        free_text_missing.append("hud_notices")
    if coverage.get("awards_items", 0) > 0:
        free_text_observed.append("awards")
    else:
        free_text_missing.append("awards")
    free_text_source_details = _free_text_source_details(report)
    free_text_blocked_reasons = [
        f"{source}_raw_text"
        for source, detail in free_text_source_details.items()
        if detail.get("raw_text_fields_present")
    ]

    profile_missing: list[str] = []
    if notice_codes and notice_codes.get("oil_overheat", 0) == 0:
        profile_missing.append("oil_overheat")
    if notice_codes and notice_codes.get("powertrain_failure", 0) == 0:
        profile_missing.append("powertrain_failure")
    if severities and set(severities) == {"unknown"}:
        profile_missing.append("hud_notice_severity")

    replay_frames = int(coverage.get("replay_true", 0))
    replay_candidate_events = int(coverage.get("replay_candidate_events", 0))
    replay_chosen_events = int(coverage.get("replay_chosen_events", 0))
    replay_dry_run_outputs = int(coverage.get("replay_dry_run_outputs", 0))
    replay_suppressed = (
        replay_frames > 0
        and replay_candidate_events == 0
        and replay_chosen_events == 0
        and replay_dry_run_outputs == 0
    )

    return {
        "numeric_safety": {
            "status": "ready_for_review" if not numeric_missing else "needs_more_samples",
            "missing": numeric_missing,
        },
        "ownership": {
            "status": "ready_for_review" if not ownership_missing else "needs_more_samples",
            "missing": ownership_missing,
        },
        "free_text_safety": {
            "status": "dry_run_only" if free_text_observed and not free_text_missing else "needs_more_samples",
            "observed": sorted(free_text_observed),
            "missing": sorted(free_text_missing),
            "real_output_blocked": True,
            "source_details": free_text_source_details,
            "blocked_reasons": free_text_blocked_reasons,
        },
        "replay_degrade": {
            "status": (
                "suppressed"
                if replay_suppressed
                else "needs_attention"
                if replay_frames > 0
                else "needs_more_samples"
            ),
            "missing": [] if replay_frames > 0 else ["replay_true"],
            "telemetry_replay_frames": replay_frames,
            "candidate_events": replay_candidate_events,
            "chosen_events": replay_chosen_events,
            "dry_run_outputs": replay_dry_run_outputs,
            "detector_suppressed": replay_suppressed,
            "output_blocked": replay_chosen_events == 0 and replay_dry_run_outputs == 0,
            "prompt_allowed": replay_frames == 0,
        },
        "profile_calibration": {
            "status": "ready_for_review" if not profile_missing else "needs_more_samples",
            "missing": profile_missing,
        },
    }


def _free_text_source_details(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    coverage = report.get("coverage") or {}
    detail_inputs = {
        "awards": {
            "items": coverage.get("awards_items", 0),
            "raw_text_fields_present": coverage.get("awards_raw_text_fields", 0) > 0,
        },
        "combat_feed": {
            "items": coverage.get("combat_feed_items", 0),
            "raw_text_fields_present": coverage.get("combat_feed_raw_text_fields", 0) > 0,
        },
        "hud_notices": {
            "items": sum((coverage.get("hud_notice_codes") or {}).values()),
            "raw_text_fields_present": coverage.get("hud_notice_raw_text_fields", 0) > 0,
        },
    }
    return {
        source: {
            "items": int(detail["items"]),
            "raw_text_fields_present": bool(detail["raw_text_fields_present"]),
            "prompt_allowed": False,
            "mode": "dry_run_only",
        }
        for source, detail in detail_inputs.items()
        if detail["items"] > 0
    }


def _live_test_plan(checks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    plan: list[dict[str, Any]] = []

    def add(area: str, label: str, status: str, priority: str, action: str) -> None:
        plan.append({"area": area, "label": label, "status": status, "priority": priority, "action": action})

    replay = checks.get("replay_degrade") or {}
    if replay.get("status") == "needs_more_samples":
        add("replay_degrade", "回放降级", "needs_more_samples", "P1", "capture_replay_true_sample")

    free_text = checks.get("free_text_safety") or {}
    if free_text.get("status") == "dry_run_only":
        add("free_text_safety", "自由文本安全", "dry_run_only", "P1", "run_free_text_dry_run_safety_check")
    elif free_text.get("status") == "needs_more_samples":
        add("free_text_safety", "自由文本安全", "needs_more_samples", "P1", "capture_awards_or_free_text_sample")

    ownership = checks.get("ownership") or {}
    ownership_missing = set(ownership.get("missing") or [])
    if ownership.get("status") == "needs_more_samples":
        action = "capture_owned_kill_or_death"
        if "ownership_fields" in ownership_missing:
            action = "use_v16_combat_feed_ownership_fields"
        elif "manual_identity" in ownership_missing:
            action = "set_manual_identity_before_capture"
        add("ownership", "击杀/死亡归属", "needs_more_samples", "P1", action)

    numeric = checks.get("numeric_safety") or {}
    if numeric.get("status") == "needs_more_samples":
        add("numeric_safety", "数值安全事件", "needs_more_samples", "P2", "trigger_overspeed_critical")

    profile = checks.get("profile_calibration") or {}
    profile_missing = set(profile.get("missing") or [])
    if profile.get("status") == "needs_more_samples":
        profile_actions: list[str] = []
        if "oil_overheat" in profile_missing:
            profile_actions.append("capture_oil_overheat_notice")
        if "powertrain_failure" in profile_missing:
            profile_actions.append("wait_for_powertrain_profile_or_sample")
        if "hud_notice_severity" in profile_missing:
            profile_actions.append("verify_hud_notice_severity_mapping")
        if not profile_actions:
            profile_actions.append("capture_oil_overheat_notice")
        for action in profile_actions:
            add("profile_calibration", "油温/动力故障校准", "needs_more_samples", "P2", action)

    add("runtime_output", "T-Output 真实开口背压", "needs_live_review", "P2", "verify_output_backpressure")
    add("runtime_output", "T-Kill-Coalesce 多杀合并", "needs_live_review", "P2", "verify_kill_coalescing")

    return plan


def _next_steps_for_gaps(gaps: list[str]) -> list[str]:
    mapping = {
        "no_replay_true_frames": "capture_replay_true_sample",
        "no_overspeed_critical_flags": "trigger_overspeed_critical",
        "combat_feed_missing_ownership_fields": "use_v16_combat_feed_ownership_fields",
        "combat_feed_no_ownership_true_frames": "capture_owned_kill_or_death",
        "no_manual_identity_frames": "set_manual_identity_before_capture",
        "no_awards_items": "capture_awards_or_free_text_sample",
        "no_oil_overheat_notice_codes": "capture_oil_overheat_notice",
        "no_powertrain_failure_notice_codes": "wait_for_powertrain_profile_or_sample",
        "hud_notice_severity_unknown": "verify_hud_notice_severity_mapping",
    }
    return [mapping[gap] for gap in gaps if gap in mapping]


def _runtime_output_next_steps() -> list[str]:
    return ["verify_output_backpressure", "verify_kill_coalescing"]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _coverage_gaps(report: dict[str, Any]) -> list[str]:
    coverage = report.get("coverage") or {}
    flags = report.get("flags") or {}
    gaps: list[str] = []
    if coverage.get("replay_true", 0) == 0:
        gaps.append("no_replay_true_frames")
    if flags.get("overspeed_critical", 0) == 0:
        gaps.append("no_overspeed_critical_flags")
    if coverage.get("combat_feed_items", 0) > 0 and (
        coverage.get("is_my_kill_field", 0) == 0
        and coverage.get("is_my_death_field", 0) == 0
        and coverage.get("involves_me_field", 0) == 0
    ):
        gaps.append("combat_feed_missing_ownership_fields")
    elif (
        coverage.get("is_my_kill_field", 0) > 0
        or coverage.get("is_my_death_field", 0) > 0
        or coverage.get("involves_me_field", 0) > 0
    ) and (
        coverage.get("is_my_kill_true", 0) == 0
        and coverage.get("is_my_death_true", 0) == 0
        and coverage.get("involves_me_true", 0) == 0
    ):
        gaps.append("combat_feed_no_ownership_true_frames")
    combat_self_source = coverage.get("combat_self_source") or {}
    if combat_self_source.get("manual", 0) == 0:
        gaps.append("no_manual_identity_frames")
    if coverage.get("awards_items", 0) == 0:
        gaps.append("no_awards_items")

    notice_codes = coverage.get("hud_notice_codes") or {}
    if notice_codes and notice_codes.get("oil_overheat", 0) == 0:
        gaps.append("no_oil_overheat_notice_codes")
    if notice_codes and notice_codes.get("powertrain_failure", 0) == 0:
        gaps.append("no_powertrain_failure_notice_codes")
    severities = coverage.get("hud_notice_severities") or {}
    if severities and set(severities) == {"unknown"}:
        gaps.append("hud_notice_severity_unknown")
    return gaps


def _plain_value(value: Any) -> Any:
    if isinstance(value, Counter):
        return dict(value)
    if isinstance(value, dict):
        return {k: _plain_value(v) for k, v in value.items()}
    return value


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"root: {report['root']}",
        f"files: {report['files']}",
        f"frames: {report['frames']}",
        f"states: {_fmt_counts(report['states'])}",
        f"domains: {_fmt_counts(report['domains'])}",
        f"flags: {_fmt_counts(report['flags'])}",
        f"candidate_events: {_fmt_counts(report['events'])}",
        f"chosen_events: {_fmt_counts(report['chosen'])}",
        f"dry_run_outputs: {_fmt_counts(report['dry_run_outputs'])}",
        f"coverage: {_fmt_coverage(report.get('coverage') or {})}",
        f"coverage_gaps: {_fmt_list(report.get('coverage_gaps') or [])}",
        f"session_summary: {_fmt_session_summary(report.get('session_summary') or {})}",
    ]
    return "\n".join(lines)


def _fmt_coverage(coverage: dict[str, Any]) -> str:
    if not coverage:
        return "-"
    parts: list[str] = []
    for key in (
        "replay_true",
        "replay_candidate_events",
        "replay_chosen_events",
        "replay_dry_run_outputs",
        "combat_feed_items",
        "is_my_kill_field",
        "is_my_death_field",
        "involves_me_field",
        "is_my_kill_true",
        "is_my_death_true",
        "involves_me_true",
        "active_players_max",
        "awards_items",
    ):
        parts.append(f"{key}={coverage.get(key, 0)}")
    parts.append(f"combat_self_source={_fmt_counts(coverage.get('combat_self_source') or {})}")
    parts.append(f"hud_notice_codes={_fmt_counts(coverage.get('hud_notice_codes') or {})}")
    parts.append(f"hud_notice_severities={_fmt_counts(coverage.get('hud_notice_severities') or {})}")
    return ", ".join(parts)


def _fmt_counts(counts: dict[str, int]) -> str:
    if not counts:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in sorted(counts.items()))


def _fmt_list(values: list[str]) -> str:
    if not values:
        return "-"
    return ", ".join(values)


def _fmt_session_summary(summary: dict[str, Any]) -> str:
    if not summary:
        return "-"
    return ", ".join(
        [
            f"status={summary.get('status') or 'unknown'}",
            f"observed_events={_fmt_list(list(summary.get('observed_events') or []))}",
            f"chosen_events={_fmt_list(list(summary.get('chosen_events') or []))}",
            f"observed_outputs={_fmt_list(list(summary.get('observed_outputs') or []))}",
            f"validation_checks={_fmt_validation_checks(summary.get('validation_checks') or {})}",
            f"next_steps={_fmt_list(list(summary.get('next_steps') or []))}",
            f"live_test_plan={_fmt_live_test_plan(list(summary.get('live_test_plan') or []))}",
        ]
    )


def _fmt_validation_checks(checks: dict[str, Any]) -> str:
    if not checks:
        return "-"
    parts: list[str] = []
    for key, value in checks.items():
        if not isinstance(value, dict):
            continue
        if key == "free_text_safety" and value.get("source_details"):
            detail_text = _fmt_free_text_source_details(value.get("source_details"))
            suffix = f"({detail_text})" if detail_text else ""
        elif key == "replay_degrade" and value.get("telemetry_replay_frames", 0) > 0:
            detail_text = _fmt_replay_degrade_detail(value)
            suffix = f"({detail_text})" if detail_text else ""
        else:
            detail = value.get("missing") or value.get("observed") or []
            suffix = f"({_fmt_list(list(detail))})" if detail else ""
        parts.append(f"{key}:{value.get('status') or 'unknown'}{suffix}")
    return "; ".join(parts) if parts else "-"


def _fmt_free_text_source_details(value: Any) -> str:
    details = value if isinstance(value, dict) else {}
    if not details:
        return ""
    parts: list[str] = []
    for source in sorted(details):
        detail = details.get(source) if isinstance(details.get(source), dict) else {}
        status = "blocked" if detail.get("prompt_allowed") is False else "allowed"
        parts.append(f"{source}={detail.get('items', 0)}/{status}")
    return ", ".join(parts)


def _fmt_replay_degrade_detail(value: dict[str, Any]) -> str:
    status = "suppressed" if value.get("detector_suppressed") else "needs_attention"
    return (
        f"replay={value.get('telemetry_replay_frames', 0)}/{status}, "
        f"output_blocked={value.get('output_blocked')}, "
        f"prompt_allowed={value.get('prompt_allowed')}"
    )


def _fmt_live_test_plan(plan: list[dict[str, Any]]) -> str:
    if not plan:
        return "-"
    return "; ".join(
        f"{item.get('priority')}:{item.get('label')}:{item.get('status')}->{item.get('action')}"
        for item in plan
        if isinstance(item, dict)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay local data-layer samples through neko_warthunder logic.")
    parser.add_argument("root", nargs="?", default=str(_BASE / "local_samples" / "data_process_20260620"))
    parser.add_argument("player_name", nargs="?", default="tl0sr2")
    parser.add_argument("--json", action="store_true", help="Print the full safe replay report as JSON.")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.root)
    player_name = args.player_name
    report = replay_sample_root(root, player_name=player_name)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(render_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
