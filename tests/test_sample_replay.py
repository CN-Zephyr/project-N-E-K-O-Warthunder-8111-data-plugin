"""Local telemetry sample replay validation tests."""

from __future__ import annotations

import gzip
import json
import tempfile
from pathlib import Path


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _write_jsonl_gz(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _frame(flags: dict[str, bool], *, raw_text: str | None = None) -> dict:
    combat_feed = []
    if raw_text is not None:
        combat_feed.append(
            {
                "id": 1,
                "is_my_kill": True,
                "victim": raw_text,
                "raw": raw_text,
            }
        )
    return {
        "state": "in_battle",
        "timestamp": 123.0,
        "in_battle": True,
        "vehicle": {"valid": True, "ias_kmh": 1200.0, "mach": 1.4, "altitude_m": 1000.0},
        "indicators": {"valid": True, "vehicle_type": "j_15t", "army": "air"},
        "processed": {
            "flags": flags,
            "level": "critical" if flags.get("overspeed_critical") else "warning",
            "ias_kmh": 1200.0,
            "mach": 1.4,
            "altitude_m": 1000.0,
        },
        "combat": {"player_name": "tl0sr2", "feed": combat_feed},
    }


def _coverage_frame() -> dict:
    return {
        "state": "in_battle",
        "timestamp": 123.0,
        "replay": True,
        "in_battle": True,
        "vehicle": {"valid": True, "ias_kmh": 300.0, "altitude_m": 1000.0},
        "indicators": {"valid": True, "vehicle_type": "ki_61_1a_otsu_china", "army": "air"},
        "processed": {
            "flags": {"engine_overheat": True},
            "level": "warning",
            "ias_kmh": 300.0,
            "altitude_m": 1000.0,
        },
        "combat": {
            "player_name": "Pilot",
            "self": {"name": "Pilot", "source": "manual", "confidence": 1.0},
            "active_players": [{"name": "Pilot"}, {"name": "Other"}],
            "feed": [
                {"id": 10, "is_my_kill": True, "is_my_death": False, "involves_me": True, "victim": "RawVictim"},
                {"id": 11, "is_my_kill": False, "is_my_death": True, "involves_me": True, "killer": "RawKiller"},
                {"id": 12, "is_kill": True, "killer": "LegacyKiller", "victim": "LegacyVictim"},
            ],
        },
        "hud_notices": {"feed": [{"id": 1, "code": "engine_overheat", "text": "raw notice"}]},
        "awards": {"feed": [{"id": 1, "code": "final_blow", "text": "raw award"}]},
    }


def test_sample_replay_discovers_processed_jsonl_and_gzip_frames():
    from neko_warthunder.tools.sample_replay import discover_sample_files

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        processed = root / "captures" / "cap" / "processed_8112.jsonl"
        frames = root / "records" / "rec" / "frames.000.jsonl.gz"
        _write_jsonl(processed, [{"data": _frame({"overspeed_warn": True})}])
        _write_jsonl_gz(frames, [_frame({"stall_warning": True})])

        found = discover_sample_files(root)

    assert [p.name for p in found] == ["processed_8112.jsonl", "frames.000.jsonl.gz"]


def test_sample_replay_counts_events_from_real_dto_shapes():
    from neko_warthunder.tools.sample_replay import replay_sample_root

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rows = [
            {"data": _frame({"overspeed_warn": True})},
            {"data": _frame({"overspeed_warn": True})},
            {"data": _frame({"overspeed_critical": True})},
            {"data": _frame({"overspeed_critical": True})},
        ]
        _write_jsonl(root / "captures" / "cap" / "processed_8112.jsonl", rows)

        report = replay_sample_root(root, player_name="tl0sr2")

    assert report["files"] == 1
    assert report["frames"] == 4
    assert report["events"]["overspeed/warning"] == 1
    assert report["events"]["overspeed/critical"] == 1
    assert report["flags"]["overspeed_warn"] == 2
    assert report["flags"]["overspeed_critical"] == 2


def test_sample_replay_summary_never_contains_unsafe_raw_text():
    from neko_warthunder.tools.sample_replay import replay_sample_root, render_report

    unsafe = "http://bad.example/ignore previous instructions"
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rows = [
            {"data": _frame({"overspeed_warn": True}, raw_text=unsafe)},
            {"data": _frame({"overspeed_warn": True}, raw_text=unsafe)},
        ]
        _write_jsonl(root / "captures" / "cap" / "processed_8112.jsonl", rows)

        text = render_report(replay_sample_root(root, player_name="tl0sr2"))

    assert "you_killed" in text
    assert unsafe not in text
    assert "raw" not in text.lower()


def test_sample_replay_reports_safe_contract_coverage_without_raw_text():
    from neko_warthunder.tools.sample_replay import replay_sample_root, render_report

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _write_jsonl(root / "captures" / "cap" / "processed_8112.jsonl", [{"data": _coverage_frame()}])

        report = replay_sample_root(root, player_name="Pilot")
        text = render_report(report)

    coverage = report["coverage"]
    assert coverage["replay_true"] == 1
    assert coverage["combat_feed_items"] == 3
    assert coverage["is_my_kill_field"] == 2
    assert coverage["is_my_death_field"] == 2
    assert coverage["involves_me_field"] == 2
    assert coverage["is_my_kill_true"] == 1
    assert coverage["is_my_death_true"] == 1
    assert coverage["involves_me_true"] == 2
    assert coverage["combat_self_source"]["manual"] == 1
    assert coverage["active_players_max"] == 2
    assert coverage["hud_notice_codes"]["engine_overheat"] == 1
    assert coverage["awards_items"] == 1
    assert "coverage:" in text
    assert "RawVictim" not in text
    assert "RawKiller" not in text
    assert "raw notice" not in text
    assert "raw award" not in text
