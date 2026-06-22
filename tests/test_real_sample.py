"""接缝②自检：把真实 /api/telemetry 样本喂 parse_telemetry，核对字段/flag。

用法：
- 抓 raw 样本：`curl http://localhost:8112/api/telemetry > local_samples/live_current/telemetry_sample.json`
- 只有脱敏后的样本才允许更新 `contract/telemetry_sample.json`。
- 看报告：`uv run python plugin/plugins/neko_warthunder/tests/test_real_sample.py`
- 或随单测一起跑（无样本则跳过，不报失败）。
"""

from __future__ import annotations

import json
import pathlib

from neko_warthunder.adapters.telemetry_client import parse_telemetry
from neko_warthunder.core.flag_codes import CONDITION_FLAG_GROUPS

_SAMPLE = pathlib.Path(__file__).resolve().parent.parent / "contract" / "telemetry_sample.json"


def _expected_flag_names() -> set[str]:
    names: set[str] = set()
    for groups in CONDITION_FLAG_GROUPS.values():
        for warn, crit in groups:
            names.add(warn)
            names.add(crit)
    return names


def _report() -> str:
    if not _SAMPLE.exists():
        return f"(no sample at {_SAMPLE}; 抓一帧 /api/telemetry 存到此处再跑)"
    payload = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    s = parse_telemetry(payload)
    real_flags = set(s.flags.keys())
    expected = _expected_flag_names()
    lines = [
        f"connected={s.connected} state={s.conn_state} in_battle={s.in_battle} vehicle_valid={s.vehicle_valid}",
        f"domain={s.domain} vehicle_type={s.vehicle_type}",
        f"ias={s.ias_kmh} aoa={s.aoa_deg} alt={s.altitude_m} climb={s.climb_ms} fuel_frac={s.fuel_fraction}",
        f"flags(real)={sorted(real_flags)}",
        f"我们假设里【真实样本未出现】的 flag（可能只是该帧未触发，非必然错）：{sorted(expected - real_flags)}",
        f"真实样本里【我们没映射】的 flag：{sorted(real_flags - expected)}",
    ]
    return "\n".join(lines)


def test_real_sample_if_present():
    """有样本则断言解析不崩、关键结构成立；无样本则跳过（pass）。"""
    if not _SAMPLE.exists():
        return
    payload = json.loads(_SAMPLE.read_text(encoding="utf-8"))
    s = parse_telemetry(payload)
    assert s.connected is True
    assert isinstance(s.flags, dict)
    # 在战样本应能拿到载具/速度等任一字段（粗校验解析有效）
    if s.in_battle:
        assert s.conn_state == "in_battle"


def test_contract_telemetry_sample_is_sanitized_v16_shape():
    assert _SAMPLE.exists()
    payload = json.loads(_SAMPLE.read_text(encoding="utf-8"))

    s = parse_telemetry(payload)

    assert s.connected is True
    assert s.in_battle is True
    assert s.conn_state == "in_battle"
    assert s.domain == "air"
    assert s.vehicle_valid is True
    assert s.flag("overspeed_warn") is True
    assert s.combat["self"]["source"] == "manual"
    assert s.hud_notices[0]["code"] == "engine_overheat"
    assert payload["awards"]["feed"][0]["code"] == "final_blow"
    assert "raw" not in payload
    assert "text" not in payload["hud_notices"]["feed"][0]
    assert "text" not in payload["awards"]["feed"][0]


if __name__ == "__main__":
    print(_report())
