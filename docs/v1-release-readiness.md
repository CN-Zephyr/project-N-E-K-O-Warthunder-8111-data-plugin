# v1 Release Readiness

> 状态：准备发布候选前的离线门禁说明。本文不替代真机 smoke，只回答“现在代码能不能进入最后一轮真机验收”。

## 当前结论

- 离线逻辑基线：`209/209 passed`。
- `tools/free_text_gate.py` 已作为自由文本发布门禁，防止玩家名、hudmsg、combat.feed、awards 原文进入 prompt 或 `push_message.parts[].text`。
- `tools/replay_gate.py` 已作为 replay 降级发布门禁，证明 `replay=true` 帧不会产生 Detector candidate、prompt 或真实 `push_message`。
- `tools/deferred_hud_gate.py` 已作为 deferred HUD notice 发布门禁，证明 `powertrain_failure` 当前只可观测、不播报、不泄露 raw HUD 文本。
- `tools/proximity_gate.py` 已作为 V2 proximity / objective awareness 门禁，证明 `proximity.events` / `situation.ground_targets` 只生成 safe generic prompt，并覆盖 `tailing_risk` 持续后方威胁升级与 Arbiter gating。
- `tools/release_readiness.py` 已作为 v1 RC 离线汇总入口。它不启动前后端，不依赖 War Thunder，只聚合可自动化门禁。

## 推荐命令

只看计划：

```powershell
uv run python tools\release_readiness.py
```

执行离线 RC 门禁：

```powershell
uv run python tools\release_readiness.py --run
```

机器可读输出：

```powershell
uv run python tools\release_readiness.py --json
uv run python tools\release_readiness.py --run --json
```

完整真机前预检仍可使用：

```powershell
uv run python tools\preflight.py --run
```

## Release Readiness 覆盖项

- `tests/run_logic_tests.py`
- `pytest -c tests/pytest.ini tests -q`
- `tools/free_text_gate.py`
- `tools/replay_gate.py`
- `tools/replay.py`
- 可选：宿主存在时运行 `plugin check`
- 可选：本地样本存在时运行 `sample_replay`、`offline_report`、`live_test_plan`

## 已知限制

- 真机 airport spawn / takeoff / respawn rollout 仍需要最终回归，尤其是雷达高度保护、低空抑制和贴地滑跑超速抑制。
- `replay=true` 已有离线 gate，但真实 replay 样本仍需要补。
- `hudmsg` / `combat.feed` / `awards` 仍保持保守策略；正式自由文本播报前必须继续走 T-Safety 与真机 dry_run 验证。
- 油温、发动机细项、载具阈值仍依赖数据层数据库/profile 后续补齐。
- recovery、复杂 HUD 播报不属于 v1 发布阻塞项；V2 proximity / objective awareness 的非真机依赖部分已完成，后方/六点钟样本、持续尾随风险 `tailing_risk` 和近任务目标点触发样本留到统一真机验证。

## 发布前最后一轮真机 Smoke

通过 `release_readiness --run` 后，再做一次聚焦真机 smoke：

1. 机场出生 / 复活 / 滑跑：AGL `<=10m` 进入保护，`>=40m` 解除保护。
2. 保护期内不误报 `low_alt_danger`，贴地滑跑保护内不误报 `overspeed`。
3. `stall_risk`、`you_died`、`low_fuel`、`overheat` 不被起飞保护误伤。
4. `dry_run=false` 下确认 `event_expired` / output backpressure 能减少旧事件晚播。
5. 如出现 replay/free-text 样本，确认 live monitor 显示 suppressed / blocked，且没有 unsafe raw 文本进入输出。
