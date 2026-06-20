# neko_warthunder

War Thunder 猫娘副驾驶插件（v1）。**只读 8111、不做外挂**：消费数据层遥测，把连续数据转成分立的战斗事件，按当前战场场景仲裁后让猫娘提醒/陪伴。

> 当前状态：**M1 框架 + M2 理解/决策逻辑已实现，T1A Hosted UI Integration + T1B Minimal Panel 已完成。** Hosted UI surface/context/action smoke 已通过；未做：真机/数据层/真实开口接缝验证（见 `docs/真机验证-checklist.md`）、M3 去桩（overspeed/击杀，待数据层）。详见 `docs/实现计划-codex.md` 的「实现状态」。

## 给 Codex 的启动指令（直接复制）

```text
你将接手 NEKO 插件 plugin/plugins/neko_warthunder/（War Thunder 猫娘副驾驶）。

先读：plugin/plugins/neko_warthunder/docs/实现计划-codex.md
（重点：「实现状态」「§0 总则铁律」「§6 给 Codex 的下一步」「§7 已知坑/勿回退」）。

现状：M1 框架 + M2 理解/决策逻辑已实现；T1A Hosted UI Integration + T1B Minimal Panel 已完成；Hosted UI surface/context/action smoke 已通过；逻辑单测 29/29 过；已过一轮 Bugbot 评审并修复 6 项。

从 §6「Codex 现在就能做」开始，建议优先 T4（补集成测试）。T3/L8 子进程编排保留为后续。

铁律（§0，违反即返工）：
- 只读 8111；与数据层唯一边界 = HTTP :8112；只消费、不重算阈值。
- 输出只走 adapters/neko_dispatcher.py；每次仲裁至多 1 条；不拼最终台词（产出「事实行+要求行」，ai_behavior=respond）。
- dry_run 默认开；真投前才关。
- 绝不修改 / 不 import data_layer/（合作者代码，目录名 data process 带空格）。
- 不要重新引入 §7 列出的 6 个 Bugbot 已修问题。

验证：
- 无依赖逻辑自检：uv run python plugin/plugins/neko_warthunder/tests/run_logic_tests.py（应 29/29）
- 离线看行为/决策链路：uv run python plugin/plugins/neko_warthunder/tools/replay.py
- 完整环境：uv run pytest plugin/plugins/neko_warthunder/tests

做不了的（等人/真机/合作者，别硬做）：3 接缝真机验证（docs/真机验证-checklist.md）、M3 去桩（overspeed/击杀需数据层补 flag + player_name）。
```

## 目录

```text
neko_warthunder/
├─ core/         contracts / scenario / arbiter / safety_guard / instructions
├─ adapters/     telemetry_client（拉 :8112）/ neko_dispatcher（唯一出口）
├─ detectors/    condition（flag 边沿 FSM）/ discrete（按 id/跳变去重）
├─ contract/     真实 /api/telemetry 样本 + 契约版本（防 schema 漂移）
├─ ui/           最小面板（Hosted UI：状态 / dry_run / 安全状态 / 急停 / 测试开口）
├─ i18n/         zh-CN 占位；完整 8 locale 待后续 UI 文案扩展
├─ tests/        契约/Detector/Arbiter/Scenario 测试 + run_logic_tests.py（无依赖自检）
├─ docs/         D-B1~B5 / 实现计划-codex / 待办事项 / 真机验证-checklist
└─ data_layer/   合作者数据层（整体并入，内容不改；独立 :8112 HTTP 服务，不当 Python 模块 import）
```

## 关键约束（动手前必读 docs/）

- 与数据层唯一边界 = HTTP `:8112`（`/api/telemetry`）；只消费、不重算阈值。
- 不修改 `data_layer/` 任何内容（vendored，整包替换式更新）。其 `data process/` 目录名带空格，**绝不 import**。
- 输出只走 `neko_dispatcher`；每次仲裁至多 1 条；dry_run 默认开。

## 文档入口

- 实现路线 + 当前状态（给开发者/Codex）：`docs/实现计划-codex.md`
- 真机验证步骤（敲定 3 接缝）：`docs/真机验证-checklist.md`
- 设计：`docs/D-B1`(Scenario) / `D-B2`(BattleEvent) / `D-B3`(Detector) / `D-B4`(Arbiter) / `D-B5`(事件→数据层映射)
- 给数据层开发者的待办：`docs/待办事项.md`
- 数据层接口契约：`data_layer/data process/后端接口文档.md`
