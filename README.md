# neko_warthunder

War Thunder 猫娘副驾驶插件 v1。插件只消费本地数据层 HTTP `:8112`，把连续遥测整理成 Battle Awareness 事件，再经 Scenario / Arbiter / Safety / Dispatcher 决定是否让猫娘开口。

## 当前状态

- M1 scaffold + M2 Battle Awareness 主链路已实现。
- T1A Hosted UI Integration + T1B Minimal Panel 已完成，surface/context/action smoke 已通过。
- T4 集成测试已完成；T-Safety output text sanitizer 已完成；`/api/identity` Hosted UI/action 接缝已完成；当前逻辑自检以 `66/66 passed` 为准。
- 2026-06-21 真机 `dry_run` smoke 已通过：Hosted UI context/action、pause/resume 安全门、stall/low_alt 决策链路、dry_run dispatcher 输出均正常。
- 数据层 `v1.6` 已合并到当前独立插件仓库，包含 `overspeed_warn` / `overspeed_critical`、增强 `combat.feed`、`is_my_kill` / `is_my_death`、`/api/identity`、`replay: true` 降级、`hud_notices`、`awards`。
- 数据层字段缺口不再是“等待字段补齐”，现在是插件侧继续适配 `v1.6` DTO、待真机接缝验证。
- 插件侧已按 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death` 生成 `you_killed` / `you_died`，已提供面板 `set_identity` action 调用数据层 `/api/identity` 设置/清除玩家名，并在 `replay=true` 时静默 Detector 输出。
- 插件侧已接入 `hud_notices.feed[].code` 中的 `engine_overheat` / `oil_overheat`，可映射为现有 `overheat` 事件；raw HUD 文本不进入 prompt。
- `T-Safety: output text sanitizer` 已实现，位于 `NekoDispatcher` / prompt builder 前；prompt 和 `push_message.parts[].text` 只能使用 safe / generic 文案。
- kill/death/hudmsg/combat.feed/awards 等自由文本真实播报仍需先完成真机 dry_run 验证；stall/low_alt/overheat/low_fuel/overspeed 等数值安全事件不被 T-Safety 阻塞。
- recovery 已评估并暂缓；当前不要打开 `wants_recovery`。

## 给 Codex 的启动指令

```text
你将接手独立插件仓库 project-N-E-K-O-Warthunder-8111-data-plugin。

先读：
- PROJECT_STATUS.md
- docs/实现计划-codex.md
- docs/真机验证-checklist.md
- docs/待办事项.md
- docs/D-B1-scenario-model.md ~ docs/D-B5-event-field-requirements.md
- data_layer/data process/后端接口文档.md

当前状态：
- Hosted UI 完成。
- T4 集成测试完成。
- 逻辑自检 66/66 passed。
- 数据层 v1.6 已合并，插件侧已分项接入 kill/death、identity、replay 静默和 overheat HUD notice，仍需真机接缝验证。
- 真机 dry_run smoke 已完成一轮；过热/炸缸已补 `hud_notices` code 接入，仍需真机复测。
- T-Safety 已完成；kill/death/hudmsg/combat.feed/awards 正式播报前还需要真机 dry_run 验证。
- recovery 暂缓。

边界：
- 不 import、不修改 data_layer/。
- 与数据层唯一边界是 HTTP :8112。
- 输出只走 adapters/neko_dispatcher.py。
- dry_run 默认开启，真机确认前不要关闭。
- Detector / Scenario / Arbiter 不承担文本过滤职责。

优先顺序：
1. 继续 M3 剩余验证：identity 真机验证、replay 真实样本验证、过热真机复测与故障字段策略。
2. 继续真机 checklist，补面板设置玩家名后的 identity、replay、kill/death、过热/炸缸、自由文本 dry_run 接缝。
3. kill/death/hudmsg/combat.feed/awards 去桩前确认 T-Safety 合同仍覆盖 prompt。
4. T3/L8 子进程编排后置。
```

## 验证入口

从独立插件仓库 root 运行：

```powershell
uv run python tests/run_logic_tests.py
uv run pytest tests -q
```

从 N.E.K.O 宿主仓库内做插件检查时，使用宿主路径：

```powershell
uv run python -m plugin.neko_plugin_cli.cli check plugin/plugins/neko_warthunder
```

## 目录

```text
neko_warthunder/
├─ core/         contracts / scenario / arbiter / safety_guard / instructions
├─ adapters/     telemetry_client（拉 :8112）/ neko_dispatcher（唯一输出口）
├─ detectors/    condition（flag 边沿 FSM）/ discrete（按 id/跳变去重）
├─ contract/     真实 /api/telemetry 样本与契约检查
├─ ui/           Hosted UI 最小面板
├─ i18n/         zh-CN 占位；完整 8 locale 待后续 UI 文案扩展
├─ tests/        契约 / Detector / Arbiter / Scenario / integration 测试
├─ docs/         D-B1~B5 / 实现计划 / 待办事项 / 真机验证 checklist / recovery 测试方案
└─ data_layer/   合作者数据层，vendored，只通过 HTTP 消费
```

## 关键约束

- 数据层代码只作为 vendored 目录保存，插件侧不要修改、不要 import。
- `you_killed` / `you_died` 已消费 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death`，后续重点是真机 dry_run 验证。
- `overspeed` 后续应验证并适配 `processed.flags` 中的 `overspeed_warn` / `overspeed_critical`。
- 过热/炸缸真机 smoke 中，游戏 UI 已出现油温/发动机异常；插件侧已补 `hud_notices.feed[].code=engine_overheat/oil_overheat` 到 `overheat` 的映射，后续仍需真机复测；`powertrain_failure` 暂不直接提升为播报事件。
- `replay: true` 已在 Detector 层静默并 reset，避免回放数据触发真实播报；后续需要真实 replay 样本验证。
- `/api/identity` 是 player_name 的主路径；插件侧 Hosted UI/context/action 接缝已完成，后续需要真机验证 `combat.self` 与 `is_my_kill` / `is_my_death` 是否按手动昵称生效。
- `hud_notices` / `awards` 来自自由文本解析，真实播报前受 T-Safety 阻塞。
