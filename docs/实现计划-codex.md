# 实现计划（Codex 交接）：neko_warthunder v1

> 面向接手者的当前计划。本文以当前独立插件仓库为准，不再沿用“等待数据层补字段”的旧前提。

## 实现状态（2026-06-21）

- M1 scaffold 已实现。
- M2 Battle Awareness 理解/决策主链路已实现。
- T1A Hosted UI Integration 已完成。
- T1B Minimal Panel 已完成。
- T4 集成测试已完成。
- Hosted UI surface/context/action smoke 已通过。
- T-Safety output text sanitizer 已完成。
- 逻辑自检以 `uv run python tests/run_logic_tests.py` 的 `66/66 passed` 为准。
- 数据层 `v1.6` 已合并，包含：
  - `overspeed_warn` / `overspeed_critical`
  - enhanced `combat.feed`
  - `is_my_kill` / `is_my_death`
  - `/api/identity`
  - `replay: true` 回放降级
  - `hud_notices`
  - `awards`
- 真机/数据层/真实开口接缝仍未完整验证。
- recovery 仍暂缓，不打开 `wants_recovery`。

## 当前边界

- 插件与数据层唯一边界是 HTTP `:8112`，主入口是 `/api/telemetry`。
- 不 import、不修改 `data_layer/`。数据层作为 vendored 目录存在，后续更新以整包合并为主。
- 输出只走 `adapters/neko_dispatcher.py`。
- dry_run 默认开启；真机确认前不要关闭。
- Detector / Scenario / Arbiter 只处理事件语义，不承担自由文本过滤职责。
- 不可信自由文本只能在 `NekoDispatcher` / prompt builder 前完成 sanitize 后进入 prompt；raw 玩家名、hudmsg、combat.feed、awards 原文只进 audit/debug。

## 分层状态

- L0 plugin scaffold / contracts：完成；`contract/telemetry_sample.json` 仍待真机抓取。
- L1 telemetry client：完成基础解析；已纳入 `hud_notices.feed` 与 `replay`，仍需要验证 data-layer `v1.6` 其他新字段。
- L2 BattleState：完成基础装配；需要纳入 v1.6 DTO seam 验证。
- L3 Scenario：完成；`replay: true` 已在 DetectorEngine 静默并 reset，仍需真实 replay 样本验证。
- L4 Detector：已实现主链路；`overspeed` 现在不再等待数据层，下一步是真机验证 `overspeed_warn` / `overspeed_critical`；`overheat` 已可消费 `hud_notices.feed[].code=engine_overheat/oil_overheat`；`you_killed` / `you_died` 已消费 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death`。
- L5 Arbiter：完成；后续 M3 适配时要保持 cooldown、优先级、Scenario 门控语义不变。
- L6 Dispatcher / instructions：完成基础输出；T-Safety 已在 prompt builder 前接入，prompt / `push_message.parts[].text` 不允许包含 unsafe raw。
- L7 safety guard + Hosted UI：完成。
- L8 数据层并入：vendored 数据层已合并；插件侧子进程编排未做。
- L9 真机调参：未完成。

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

## M3：适配数据层 v1.6 DTO

旧定义“等待数据层补齐”已过期。新的 M3 是插件侧适配和验证：

- `overspeed`：读取并验证 `processed.flags` 中的 `overspeed_warn` / `overspeed_critical`。
- `you_killed`：已监听 `combat.feed[]` 中 `is_my_kill == true` 的新 id，按 id 去重；多杀合并仍可留后续调优。
- `you_died`：已监听 `combat.feed[]` 中 `is_my_death == true` 的新 id，不再把 `vehicle_valid` 跳变当作唯一可靠死亡信号。
- `player_name`：通过 `/api/identity` 或启动参数建立权威身份；插件侧 Hosted UI/context/action seam 已完成，仍需真机验证 `combat.self` 与 `is_my_kill` / `is_my_death` 是否按手动昵称生效。
- `replay: true`：已在 DetectorEngine 静默并 reset，避免回放触发真实播报；仍需真实 replay 样本验证。
- `overheat`：已接入 `hud_notices.feed[].code` 中的 `engine_overheat` / `oil_overheat`，以 code-only safe payload 生成现有 `overheat`；`powertrain_failure` 暂不直接播报。
- `hud_notices` / `awards`：属于自由文本风险路径，真实播报前必须先过 T-Safety。

## 真机验证

真机 checklist 从“等字段”改为“验证 v1.6 DTO 接缝”。见 `docs/真机验证-checklist.md`。

需要重点确认：

- `/api/telemetry` 是否返回 `replay`。
- `/api/telemetry.processed.flags` 是否出现 `overspeed_warn` / `overspeed_critical`。
- `/api/telemetry.combat.feed[]` 是否含稳定递增 id、`is_my_kill`、`is_my_death`。
- `/api/identity` 是否能由 Hosted UI 面板设置/清除权威 player_name，并反映到 `combat.self` 与 kill/death 归属标记。
- `hud_notices` 中的技术 code 是否能触发安全事件；raw notice 文本、`awards` 是否只进入 debug/audit 或被 T-Safety 阻断，不直接进入 prompt。

## 推进顺序

1. 文档状态同步。
2. M3 剩余验证：identity 真机验证、replay 样本验证、awards/free-text dry_run 验证、failure 字段策略。
3. 真机 checklist 验证 v1.6 接缝。
4. kill/death/hudmsg/combat.feed/awards 去桩前复核 T-Safety prompt 合同。
5. T3/L8 子进程编排。
6. L9 真机调参和 dry_run=false 终验。

## 已知坑 / 不要回退

- 不要把 `data_layer/` 当 Python 包 import；`data process` 目录名带空格。
- 不要把自由文本过滤塞进 Detector / Scenario / Arbiter。
- 不要复活旧的 `vehicle_valid` 作为 `you_died` 主路径。
- 不要把 recovery 作为 v1 当前任务；它只保留测试方案和 TODO。
- 不要沿用旧的 pre-T-Safety / pre-identity 测试数量；当前逻辑自检应以 `66/66 passed` 为准。
- 不要在父仓库 `N.E.K.O` 里提交这个独立插件仓库。
