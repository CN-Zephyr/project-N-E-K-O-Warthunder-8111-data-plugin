# 实现计划（Codex 交接）：neko_warthunder v1

> 面向接手者的当前计划。本文以当前独立插件仓库为准，不再沿用“等待数据层补字段”的旧前提。

## 实现状态（2026-06-23）

- M1 scaffold 已实现。
- M2 Battle Awareness 理解/决策主链路已实现。
- T1A Hosted UI Integration 已完成。
- T1B Minimal Panel 已完成。
- T4 集成测试已完成。
- Hosted UI surface/context/action smoke 已通过。
- T-Safety output text sanitizer 已完成。
- T-Observe runtime decision timeline 已完成轻量实现：普通模式只保留最近摘要，debug 模式使用内存 ring buffer。
- 逻辑自检以 `uv run python tests/run_logic_tests.py` 的 `108/108 passed` 为准。
- 离线 readiness 与真机监控工具链已补齐：`tools/sample_replay.py` 负责样本覆盖率与 `session_summary`，`tools/offline_report.py` 负责安全 Markdown / JSON 汇报，`tools/live_test_plan.py` 负责把 P1/P2 待测项展开为下一轮真机“操作 / 监控 / 通过 / 失败 / 数据层缺口”清单，`tools/live_monitor.py` 负责真机测试时安全汇总 health、context、telemetry ownership 计数、free-text dry_run-only 状态与逐源 blocked 摘要、replay 降级状态、T-Observe 摘要与日志异常计数。
- 数据层 `v1.6` 已合并，包含：
  - `overspeed_warn` / `overspeed_critical`
  - enhanced `combat.feed`
  - `is_my_kill` / `is_my_death`
  - `/api/identity`
  - `replay: true` 回放降级
  - `hud_notices`
  - `awards`
- 真机/数据层/真实开口接缝仍未完整验证；2026-06-23 已完成数值安全与 owned kill/death smoke，覆盖超速 warning/critical、低油 warning/critical、低空 warning/critical、失速 warning/critical、过热 warning/critical、手动 identity、air/ground owned combat.feed 归属、`you_killed` / `you_died` dry_run，以及 `dry_run=false` 真实 push 输出。
- recovery 仍暂缓，不打开 `wants_recovery`。

## 当前边界

- 插件与数据层唯一边界是 HTTP `:8112`，主入口是 `/api/telemetry`。
- 不 import、不修改 `data_layer/`。数据层作为 vendored 目录存在，后续更新以整包合并为主。
- 输出只走 `adapters/neko_dispatcher.py`。
- dry_run 默认开启；真机确认前不要关闭。
- Detector / Scenario / Arbiter 只处理事件语义，不承担自由文本过滤职责。
- 不可信自由文本只能在 `NekoDispatcher` / prompt builder 前完成 sanitize 后进入 prompt；raw 玩家名、hudmsg、combat.feed、awards 原文只进 audit/debug。

## 分层状态

- L0 plugin scaffold / contracts：完成；`contract/telemetry_sample.json` 已补脱敏 v1.6 形状样本，真机验证时仍可另抓当前环境帧到 `.gitignore` 忽略的 `local_samples/` 做对照。
- L1 telemetry client：完成基础解析；已纳入 `hud_notices.feed` 与 `replay`，仍需要验证 data-layer `v1.6` 其他新字段。
- L2 BattleState：完成基础装配；需要纳入 v1.6 DTO seam 验证。
- L3 Scenario：完成；`replay: true` 已在 DetectorEngine 静默并 reset，且 T-Observe 会记录 `detector_suppressed/replay`，T-Live 会显示 `replay=suppressed(detector_suppressed/replay)` 与输出阻断状态；仍需真实 replay 样本验证。
- L4 Detector：已实现主链路；`overspeed` 已在真机 dry_run 中验证 `overspeed_warn` / `overspeed_critical`；`low_fuel` 已在真机 dry_run 中验证 warning / critical；`low_alt_danger`、`stall_risk`、`overheat` 均已观察到 warning / critical 基础链路；`you_killed` / `you_died` 已消费 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death`，离线 replay 合成场景也已覆盖该形状。
- L5 Arbiter：完成；`SPAWNING` 仍压制飞行安全误报，但已允许 owned combat kill 事件通过，避免真实击杀在出生 grace 内被误压。后续 M3 适配时要保持 cooldown、优先级、Scenario 门控语义不变。
- L6 Dispatcher / instructions：完成基础输出；T-Safety 已在 prompt builder 前接入，prompt / `push_message.parts[].text` 不允许包含 unsafe raw。
- L7 safety guard + Hosted UI：完成。
- T-Observe runtime decision timeline：完成轻量实现；Hosted UI context 暴露 `observe.last_event` / `last_decision` / `last_output_status`，debug timeline 默认关闭。
- L8 数据层并入：vendored 数据层已合并；插件侧子进程编排未做。
- L9 真机调参：未完成；T-Live 只读监控工具已完成，可用于下一轮真机统一测试归档。

## T-Safety：output text sanitizer

状态：已完成。

目标：防止猫娘复读不良玩家 ID、hudmsg、combat.feed、awards 原文，避免辱骂、涉政、擦边、仇恨、广告、联系方式、奇怪符号或 prompt injection 文本进入猫娘输出。

放置位置：`NekoDispatcher` / prompt builder 前。

关键策略：

- raw 只进 audit/debug。
- safe 才能进 prompt。
- 默认 generic 文案，不朗读陌生玩家名。
- 不确定时宁可不读原文。
- 不做复杂 NLP，不做大模型审核。

当前阻塞关系：

- T-Safety 本身不再阻塞；它已经作为输出安全前置层落地。
- kill/death/hudmsg/combat.feed/awards 正式播报仍需真机 dry_run 验证和对应去桩。
- 不阻塞 stall/low_alt/overheat/low_fuel/overspeed 等数值安全事件。

已覆盖测试：

- sanitizer 单测。
- dispatcher prompt 测试。
- `push_message.parts[].text` 不包含 unsafe raw 的合同测试。
- hudmsg / combat.feed / awards 常见自由文本字段族即使内容看似普通，也默认 blocked，不进入 safe prompt payload。

## M3：适配数据层 v1.6 DTO

旧定义“等待数据层补齐”已过期。新的 M3 是插件侧适配和验证：

- `overspeed`：读取 `processed.flags` 中的 `overspeed_warn` / `overspeed_critical`；2026-06-23 已真机 dry_run 验证 warning/critical 事件链路。
- `you_killed`：已监听 `combat.feed[]` 中 `is_my_kill == true` 的新 id，按 id 去重；多杀合并仍可留后续调优。
- `you_died`：已监听 `combat.feed[]` 中 `is_my_death == true` 的新 id，不再把 `vehicle_valid` 跳变当作唯一可靠死亡信号。
- `player_name`：通过 `/api/identity` 或启动参数建立权威身份；插件侧 Hosted UI/context/action seam 已完成，2026-06-23 真机已验证 `combat.self.source=manual` 与 `is_my_kill` / `is_my_death` owned 路径。`you_killed` 候选曾被 `SPAWNING` 门控压住，已修复；post-fix dry_run 与 `dry_run=false` push 已通过陆战验证。
- `replay: true`：已在 DetectorEngine 静默并 reset，避免回放触发真实播报；T-Observe 会把原因记录为 `detector_suppressed/replay`，`tools/live_monitor.py` 会汇总为 `replay_degrade.status=suppressed` / `output_blocked=true`；仍需真实 replay 样本验证。
- `overheat`：已接入 `hud_notices.feed[].code` 中的 `engine_overheat` / `oil_overheat`，以 code-only safe payload 生成现有 `overheat`；`powertrain_failure` 暂不直接播报。
- `hud_notices` / `awards`：属于自由文本风险路径，真实播报前必须先过 T-Safety。

## 真机验证

真机 checklist 从“等字段”改为“验证 v1.6 DTO 接缝”。见 `docs/真机验证-checklist.md`。2026-06-23 已完成数值安全 dry_run、owned kill/death dry_run、以及 kill/death `dry_run=false` push smoke；每轮测完后，用 `docs/真机测试结果-template.md` 记录聚合统计、安全摘要和结论；不要提交 raw 玩家名、raw HUD 文本、raw combat.feed 或 awards 原文。

需要重点确认：

- `/api/telemetry` 是否返回 `replay`。
- `/api/telemetry.processed.flags` 是否出现 `overspeed_warn` / `overspeed_critical`（2026-06-23 已通过真机 dry_run）。
- `/api/telemetry.combat.feed[]` 是否含稳定递增 id、`is_my_kill`、`is_my_death`。
- `/api/identity` 是否能由 Hosted UI 面板设置/清除权威 player_name，并反映到 `combat.self` 与 kill/death 归属标记（2026-06-23 已有真机正向证据；`you_killed` 不再被 `SPAWNING` gate 压住）。
- `hud_notices` 中的技术 code 是否能触发安全事件；raw notice 文本、`awards` 是否只进入 debug/audit 或被 T-Safety 阻断，不直接进入 prompt。
- T-Observe 的 `observe.last_decision` / `observe.last_output_status` 是否能解释未播、晚播、dry_run 输出或 dispatcher 失败。

## 推进顺序

1. M3 剩余验证：先运行 `tools/live_test_plan.py local_samples/data_process_20260620 tl0sr2` 生成下一轮真机操作清单，现场用 `tools/live_monitor.py` 做安全只读摘要，先看 `Summary` 行，再用 `replay_degrade` 字段确认 replay 静默/输出阻断，用 `free_text_safety.source_details` / `FreeText detail` 确认 awards、combat.feed、hud_notices 逐源 blocked，再按清单补 replay 样本验证、awards/free-text dry_run 验证、failure 字段策略。
2. 真机 checklist 验证 v1.6 接缝，同时用 T-Observe 与 T-Live 辅助解释决策链路。
3. 如 T-Observe 在真机里信息不足，再补 debug timeline 展示/字段。
4. kill/death/hudmsg/combat.feed/awards 去桩前复核 T-Safety prompt 合同。
5. T3/L8 子进程编排。
6. L9 真机调参和 remaining `dry_run=false` 终验。

## 已知坑 / 不要回退

- 不要把 `data_layer/` 当 Python 包 import；`data process` 目录名带空格。
- 不要把自由文本过滤塞进 Detector / Scenario / Arbiter。
- 不要复活旧的 `vehicle_valid` 作为 `you_died` 主路径。
- 不要把 recovery 作为 v1 当前任务；它只保留测试方案和 TODO。
- 不要沿用旧的 pre-T-Safety / pre-identity 测试数量；当前逻辑自检应以 `108/108 passed` 为准。
- 不要在父仓库 `N.E.K.O` 里提交这个独立插件仓库。
