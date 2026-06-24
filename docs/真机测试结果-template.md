# 真机测试结果记录模板

> 用途：每轮真机 / 数据层统一测试后，把结果整理成可回填到 `PROJECT_STATUS.md`、`README.md`、`docs/真机验证-checklist.md` 的短报告。不要提交原始玩家名、HUD 文本、combat feed 原文或 awards 原文。

## 基本信息

- 日期：
- 测试人：
- 插件 commit：
- 数据层来源 / commit：
- 游戏模式 / 机型：
- `dry_run`：true / false
- 是否使用 Hosted UI 设置玩家名：是 / 否
- 样本留存位置：`local_samples/...` 或本地临时目录（不要写入 tracked `contract/telemetry_sample.json`，除非已脱敏）

## 启动与健康检查

- N.E.K.O 主后端 `48911/health`：
- Hosted UI `48916/health`：
- 数据层 `8112/health`：
- Hosted UI surface `main` 是否可打开：
- `dashboard` context 是否返回：
- `PLUGIN_UI_ACTION_FAILED`：有 / 无
- Traceback / ERROR：有 / 无

## T-Live 现场摘要

> 建议用 `uv run python tools\live_monitor.py` 或 `uv run python tools\live_monitor.py --json` 记录聚合结论；不要复制 raw 玩家名、raw HUD、raw combat.feed 或 awards 原文。

- `live_monitor` health 结论：
- `live_monitor` runtime 结论：
- `live_monitor` telemetry flags：
- `live_monitor` ownership kill/death 计数：
- `live_monitor` `free_text_safety.status`：
- `live_monitor` `free_text_safety.observed_sources`：
- `live_monitor` `free_text_safety.raw_text_fields_present`：
- `live_monitor` `free_text_safety.source_details`：
- `live_monitor` `free_text_safety.blocked_reasons`：
- `live_monitor` `replay_degrade.status`：
- `live_monitor` `replay_degrade.output_blocked`：
- `live_monitor` 日志异常计数：

## 面板与 action

- `set_identity`：
  - 输入昵称：
  - `/api/identity` 结果：
  - `/api/telemetry.combat.self.source`：
  - `combat.player_name`：
- `set_dry_run`：
- `pause`：
- `resume`：
- `test_say`：

## v1.6 DTO 覆盖

- `replay` 字段：有 / 无
- `processed.flags.overspeed_warn`：有 / 无
- `processed.flags.overspeed_critical`：有 / 无
- `combat.feed[].id` 单调：是 / 否 / 未观察
- `combat.feed[].is_my_kill`：有 / 无
- `combat.feed[].is_my_death`：有 / 无
- `combat.feed[].involves_me`：有 / 无
- `combat.self.source=manual`：有 / 无
- `hud_notices.feed[].code=engine_overheat`：有 / 无
- `hud_notices.feed[].code=oil_overheat`：有 / 无
- `powertrain_failure` 或等价故障 code：有 / 无
- `awards`：有 / 无

## dry_run 事件观察

| 场景 | 是否触发 | 期望事件 | Arbiter 结果 | Dispatcher 结果 | 备注 |
|---|---|---|---|---|---|
| 失速 / 低速 |  | `stall_risk` |  |  |  |
| 低空危险 |  | `low_alt_danger` |  |  |  |
| 过热 / 油温 |  | `overheat` |  |  |  |
| 低油 |  | `low_fuel` |  |  |  |
| 超速 warning |  | `overspeed` warning |  |  |  |
| 超速 critical |  | `overspeed` critical |  |  |  |
| 我的击杀 |  | `you_killed` |  |  |  |
| 我的死亡 |  | `you_died` |  |  |  |
| 战斗结束 |  | `battle_end` |  |  |  |
| replay=true |  | 静默 / suppressed |  |  |  |

## T-Observe 结论

- `observe.last_event` 是否能说明最近事件：
- `observe.last_decision` 是否能解释 allow / drop / cooldown / scenario gate：
- `observe.last_output_status` 是否能解释 dry_run / pushed / failed：
- `kill_coalesced` 是否能说明多杀合并：
- `output_backpressure` 是否能说明输出被压住：
- 是否需要打开 debug timeline：
- 信息是否足够解释“为什么没播 / 为什么晚播”：

## T-Safety 结论

- prompt / dry_run 输出是否出现 raw 玩家名：是 / 否
- prompt / dry_run 输出是否出现 raw HUD 文本：是 / 否
- prompt / dry_run 输出是否出现 raw combat.feed 文本：是 / 否
- prompt / dry_run 输出是否出现 raw awards 原文：是 / 否
- `free_text=dry_run_only(...)` 是否在出现自由文本源时被 `live_monitor` 标出：是 / 否 / 未观察到自由文本源
- 被替换成 generic 文案的例子：
- 需要新增 sanitizer 规则吗：

## dry_run=false 真实开口

> 只有 dry_run 数值安全事件通过后才填写。kill/death/hudmsg/combat.feed/awards 不先开放真实自由文本播报。

- 是否关闭 dry_run：
- 测试事件：
- 是否正常开口：
- 是否滞后：
- 是否刷屏：
- `output_backpressure` 是否出现：
- 更高优先级事件是否能插队：
- 旧事件晚回复是否减少：
- 是否有 TTS / push_message 报错：

## T-Output / T-Kill-Coalesce 复测

- `sample_replay` / `offline_report` / `live_test_plan` / `session_summary.next_steps` 是否列出 `verify_output_backpressure`：
- `sample_replay` / `offline_report` / `live_test_plan` / `session_summary.next_steps` 是否列出 `verify_kill_coalescing`：
- 连续同/低优先级事件是否被背压压住：
- 更高优先级事件是否仍可通过：
- 短窗多杀是否合并成单条 `kill_count` 输出：
- `you_died` / critical 是否仍可抢占待播击杀：
- `tools/live_monitor.py` Summary 是否显示 `output_backpressure` / `kill_coalesced`：
- 旧回复晚到 / 多条消息堆积是否比上一轮减少：

## coverage_gaps

把 `tools/sample_replay.py` 或现场观察得到的缺口列在这里：

```text
coverage_gaps:
```

常见缺口：

- `no_replay_true_frames`
- `no_overspeed_critical_flags`
- `combat_feed_missing_ownership_fields`
- `combat_feed_no_ownership_true_frames`
- `no_manual_identity_frames`
- `no_oil_overheat_notice_codes`
- `no_powertrain_failure_notice_codes`
- `hud_notice_severity_unknown`

## 结论

- 本轮已关闭的验证项：
- 仍需下轮真机补测的项：
- 是否允许进入 `dry_run=false` 数值安全事件测试：
- 是否允许 kill/death/hudmsg/combat.feed/awards 去桩：
- 需要补代码 / 文档 / 测试：
