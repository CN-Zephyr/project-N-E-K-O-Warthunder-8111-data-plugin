# neko_warthunder

War Thunder 猫娘副驾驶插件 v1。插件只消费本地数据层 HTTP `:8112`，把连续遥测整理成 Battle Awareness 事件，再经 Scenario / Arbiter / Safety / Dispatcher 决定是否让猫娘开口。

## 当前状态

- M1 scaffold + M2 Battle Awareness 主链路已实现。
- T1A Hosted UI Integration + T1B Minimal Panel 已完成，surface/context/action smoke 已通过。
- T4 集成测试已完成；T-Safety output text sanitizer 已完成；T-Observe runtime decision timeline 已完成轻量实现；T-Live live monitor summary tool 已完成；T-Output output backpressure guard 已完成；T-Kill-Coalesce 多杀合并已完成；L8 data-layer subprocess orchestration 已完成最小编排；`/api/identity` Hosted UI/action 接缝已完成；V2 proximity / objective awareness 非真机依赖部分已完成，并新增 `tools/v2_readiness.py` / `tools/v2_release_matrix.py` / `tools/v2_output_policy_gate.py` 作为 V2 收口汇总、能力矩阵和真实输出策略门禁入口；当前逻辑自检以 `239/239 passed` 为准。
- 2026-06-21 / 2026-06-23 真机 smoke 已通过：Hosted UI context/action、pause/resume 安全门、spawn、overspeed warning/critical、low_fuel warning/critical、low_alt warning/critical、stall warning/critical、overheat warning/critical、identity manual seam、owned kill/death ownership、`you_killed` / `you_died` dry_run 决策链路、`dry_run=false` 真实 push 输出均正常。
- 数据层 `v1.6` 已合并到当前独立插件仓库，包含 `overspeed_warn` / `overspeed_critical`、增强 `combat.feed`、`is_my_kill` / `is_my_death`、`/api/identity`、`replay: true` 降级、`hud_notices`、`awards`。
- 数据层字段缺口不再是“等待字段补齐”；插件侧已分项接入 `v1.6` DTO，剩余重点是真机 / 样本接缝验证。
- 插件侧已按 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death` 生成 `you_killed` / `you_died`，击杀/死亡 prompt 已按 `domain` / `cause` 使用 generic 空/陆/海措辞，不复读 raw victim 玩家名；已提供面板 `set_identity` action 调用数据层 `/api/identity` 设置/清除玩家名，并可从安全化 `active_players` 候选一键选择自己；在 `replay=true` 时静默 Detector 输出。
- 插件侧已接入 `hud_notices.feed[].code` 中的 `engine_overheat` / `oil_overheat`，可映射为现有 `overheat` 事件；raw HUD 文本不进入 prompt。
- V2 接近/目标态势感知已接入 `proximity.events` / `situation`：按 id 去重后生成 `enemy_nearby`、`air_threat_nearby`、`enemy_on_six`，短窗连续近距离后方事件会保守升级为 `tailing_risk`，并从 `situation.ground_targets` 生成低优先级 `ground_target_nearby`。普通接近和任务目标点在 COMBAT_STRESS 下被压住，空中威胁/后方威胁/持续尾随风险可进入队列，critical 安全事件仍优先。Hosted UI context / 面板暴露安全态势摘要，不暴露 raw 文本或目标 label。
- `T-Safety: output text sanitizer` 已实现，位于 `NekoDispatcher` / prompt builder 前；prompt 和 `push_message.parts[].text` 只能使用 safe / generic 文案，且已覆盖 hudmsg / combat.feed / awards 常见自由文本字段族。
- `tools/free_text_gate.py` 已纳入离线 preflight，作为 hudmsg / combat.feed / awards 去桩前的发布门禁：合成恶意玩家名、HUD、combat feed、award payload 后，验证 prompt 与 `push_message.parts[].text` 不含 raw 文本；这些路径在真机 dry_run 安全验证前仍保持 dry_run-only。
- 运行态已补 `detector_suppressed/free_text_blocked`：真机中首次看到 `awards`、`combat.feed`、`hud_notices`、`hudmsg` 或 `hud_events` 时，只记录安全来源和计数摘要，不播报、不进 prompt、不保留 raw 文本到 observe。
- `tools/replay_gate.py` 已纳入离线 preflight，作为 `replay=true` 降级发布门禁：合成带 critical flags、owned combat.feed、HUD notices、awards 的 replay 帧后，验证 Detector 不产出 candidate、Dispatcher 不构造 prompt、也不调用 `push_message`。
- `tools/deferred_hud_gate.py` 已纳入离线 preflight，作为 `powertrain_failure` 等 deferred HUD 技术通知的发布门禁：验证它们当前只可观测、不生成播报 candidate / prompt / push，且 raw HUD 文本不泄露。
- `tools/proximity_gate.py` 已纳入离线 preflight，作为 V2 接近/目标态势发布门禁：合成 proximity / situation DTO 后，验证 Detector / Arbiter / Dispatcher / `push_message.parts[].text` 的安全泛化输出和门控关系，覆盖 `tailing_risk` 持续后方威胁升级。
- `tools/v2_output_policy_gate.py` 已纳入离线 preflight，作为 V2 真实输出策略门禁：`enemy_on_six`、`tailing_risk`、`ground_target_nearby` 在缺少真机证据前默认只允许 dry_run 可观察，真实 `push_message` 会被 `v2_live_evidence_pending` 压住；只有显式开启 `v2_live_verified_real_output_enabled=true` 后才允许真实推送。
- `tools/release_readiness.py` 已作为离线汇总入口：不启动前后端、不依赖 War Thunder，只聚合 logic tests、pytest、RC 文档审计、free-text gate、replay gate、deferred HUD gate、proximity gate、V2 readiness summary、V2 release matrix、final smoke packet、synthetic replay、可选 plugin check 和本地样本报告；`release_scope` 会直接列出 `ship_status`、free-text 真实播报 blocker、样本未证明项和下一步动作，`handoff` / `handoff_status` 会合并 v1 发布状态与 V2 live evidence 缺口；通过后再进入最后一轮真机 smoke。
- `T-Observe` 已接入 Hosted UI `observe` context：普通模式保留最近一次事件/决策/输出摘要，debug 模式才返回内存 ring buffer timeline。
- `T-Output` 已在真实 `push_message` 前接入输出背压：`output_backpressure_seconds` 窗口内压住同优先级或更低优先级事件，避免主机回复队列堆积；更高优先级事件仍可通过。真实战场事件 push 现在会带统一 `coalesce_key=neko_warthunder:battle_event`，让宿主队列中尚未释放的旧战场 cue 被最新事件替换；`output_event_max_age_seconds` 默认 8s，会在真实 push 前丢弃已过期的旧事件，减少死亡后补播旧低空/超速等晚回复。
- `you_killed` 已接入轻量多杀合并：`kill_coalesce_window_seconds` 窗口内的 owned kill 会合成一条带 `kill_count` 的 generic prompt，critical 事件仍可抢占并清空待播击杀。
- L9 调参已接入雷达高度优先规则：离地/低空判断优先使用 `radio_altitude_m`（AGL），`altitude_m` 只作海拔事实展示；出生/机场起飞保护仍保留 `takeoff_low_alt_grace_seconds=45`，并新增 `takeoff_radio_altitude_enter_m=10` / `takeoff_radio_altitude_exit_m=40` 的迟滞保护。保护期间压制 `low_alt_danger`，且在雷达高度贴地保护内压制滑跑阶段 `overspeed`；不压 `stall_risk`、`overheat`、`low_fuel`、`you_died`。
- Hosted UI 面板已完成一轮信息架构整理和中文化：连接状态、战场状态、安全控制、最近决策、最近输出分区清晰，主要状态标签、风险等级、场景、数据层模式和身份识别来源均显示中文。
- `tools/live_monitor.py` 的 Summary / Observe 摘要会保留 `kill_coalesced` 决策原因，并在输出被压住或过期丢弃时直接显示 `output_backpressure` / `event_expired`；Decision detail / Output detail 会把 `selected`、`dry_run_enabled`、`kill_coalesced`、`output_backpressure`、`event_expired` 等原因翻译成中文可读解释，方便下一轮真机判断“没播/晚播”是合并、背压、过期丢弃还是其他门控导致。
- kill/death ownership 已完成真机 dry_run 与 `dry_run=false` 真实 push 验证；2026-06-23 已验证手动 identity 会反映到 `combat.self.source=manual`，空战 / 陆战 owned combat.feed 均可产生 `is_my_kill=true` 或 `is_my_death=true`，插件可生成 `you_killed` / `you_died` 并经 Arbiter / Dispatcher 输出。hudmsg / awards 等其他自由文本真实播报仍需单独 dry_run 安全验证。stall/low_alt/overheat/overspeed/low_fuel 等数值安全事件不被 T-Safety 阻塞，且本轮已观察到 dry_run 正向链路。
- recovery 已评估并暂缓；当前不要打开 `wants_recovery`。

## 给 Codex 的启动指令

```text
你将接手独立插件仓库 project-N-E-K-O-Warthunder-8111-data-plugin。

先读：
- PROJECT_STATUS.md
- docs/实现计划-codex.md
- docs/真机验证-checklist.md
- docs/统一测试前-离线检查.md
- docs/真机测试结果-template.md
- docs/样本回放-20260620.md
- docs/待办事项.md
- docs/D-B1-scenario-model.md ~ docs/D-B5-event-field-requirements.md
- data_layer/data process/后端接口文档.md

当前状态：
- Hosted UI 完成。
- T4 集成测试完成。
- 逻辑自检 239/239 passed。
- v1 RC 离线汇总入口：`uv run python tools\release_readiness.py --run`。
- 数据层 v1.6 已合并，插件侧已分项接入 kill/death、identity、replay 静默和 overheat HUD notice，仍需真机接缝验证。
- 合作者 2026-06-20 真实样本已做离线 replay 聚合报告；`tools/sample_replay.py` 现在会输出 `session_summary`、分组 validation verdict、P1/P2 `live_test_plan`、V2 proximity/situation/ground target 覆盖率、逐能力 `capability_evidence` 和 `--json` 机器可读结果，并在样本含 `replay=true` 时证明 Detector suppressed / output blocked。当前本地样本已观察到 4615 条空中 proximity、9970 帧 situation、3253 条 ground target item，但还缺后方/六点钟样本，且目标点样本尚未进入 `ground_target_nearby` 的 3000m 触发阈值；`tools/v2_readiness.py` 会汇总 V2 离线 gate、已实现事件、安全输出合同和本地样本证据，明确区分 `v2_offline_gate_complete` 与 `v2_live_evidence_complete`；`tools/v2_release_matrix.py` 会把 `enemy_nearby`、`air_threat_nearby`、`enemy_on_six`、`tailing_risk`、`ground_target_nearby` 拆成 code/offline/live-evidence/real-output-policy 能力矩阵，并显示每项能力的 observed/triggered 计数，明确哪些能力只差真机证据且保持 dry_run-first；`tools/final_smoke_packet.py` 会生成最后一轮真机 smoke 的 go/no-go、必跑命令、V2 缺口、能力矩阵摘要、remaining live actions 和安全边界；`tools/offline_report.py` 可生成安全 Markdown 或 compact JSON，并在 Markdown / JSON 中提供 Team brief、Next test focus、Operator quick checklist 与 Next live-test plan，列出已观察事件、dry_run 输出、模块 readiness、剩余真机范围和下一步缺口；`tools/rc_gap_summary.py` 可生成机器可读 RC 缺口摘要，把 sample-unproven 项和真正 blocked release 项分开；`sample_replay` / `offline_report` / `live_test_plan` 三个出口都会带上 T-Output 背压与 T-Kill-Coalesce 多杀合并复测项，且 `next_steps` 也会列出这两个现场动作；`tools/live_test_plan.py` 可把待测项展开成 Operator quick checklist 和“操作 / 监控 / 通过 / 失败 / 数据层缺口”的真机操作清单；`tools/live_monitor.py` 可在真机测试中安全汇总 health、Hosted UI context、telemetry ownership 计数、free-text dry_run-only 状态与逐源 blocked 摘要、replay 降级状态、T-Observe last decision/output 和日志异常计数；`tools/preflight.py` dry-run 输出现在带 Quick read，`--run --report-output <path>` 可在统一预检时一并运行 runtime smoke、保存报告，并在通过/失败时给出下一步操作提示。
- 真机 smoke 已完成多轮；2026-06-23 已观察到 `overspeed_warn` / `overspeed_critical`、`low_fuel`、`low_alt_danger`、`stall_risk`、`overheat`、`you_killed`、`you_died` 进入 Arbiter / Dispatcher，并验证手动 identity、owned combat.feed 归属字段和 `dry_run=false` 真实 push 输出。
- T-Observe 已完成轻量实现；真机 dry_run 已验证 `observe.last_decision` / `observe.last_output_status` 能解释 allow / preempt / cooldown / dry_run 输出。
- T-Safety 与 free-text release gate 已完成；kill/death 的安全 generic 输出已通过真机 `dry_run=false` smoke，hudmsg / awards / 其他 free-text 正式播报前仍需 dry_run 安全验证。
- L9 已接入起飞/滑跑雷达高度保护、真实战场事件队列 coalescing、事件过期丢弃和 Hosted UI 中文化；V2 proximity / objective awareness 已完成离线 gate。下一轮真机统一复测机场起飞/复活、后方/六点钟 proximity 样本、持续尾随风险 `tailing_risk`、任务目标点 `ground_target_nearby`、旧提示替换/过期丢弃、replay 与 free-text dry_run 安全。
- recovery 暂缓。

边界：
- 不 import、不修改 data_layer/。
- 与数据层唯一数据边界是 HTTP :8112；L8 只负责可选启动/关闭自己拉起的 8112 数据层进程，不 import、不修改 data_layer/。
- 输出只走 adapters/neko_dispatcher.py。
- dry_run 默认开启，真机确认前不要关闭。
- Detector / Scenario / Arbiter 不承担文本过滤职责。

优先顺序：
1. L9 下一轮真机先复测机场起飞/复活阶段：优先确认 `radio_altitude_m` 可用；雷达高度 `<=10m` 后进入滑跑保护，`>=40m` 后解除。保护期内不应播 `low_alt_danger`，且贴地滑跑阶段不应播 `overspeed`；失速、死亡等关键事件仍应能触发。同时观察真实开口时 `coalesce_key` / `event_expired` 是否减少旧低空/超速提示晚到。
2. 继续 M3 剩余验证：replay 真实样本验证、awards/free-text dry_run 安全合同、油温/动力故障字段策略；现场用 `tools/live_monitor.py` 先看 `Summary` 行，再看 `replay=suppressed(detector_suppressed/replay)`、输出阻断状态，以及 `FreeText detail` 中的 `awards=.../blocked` 等逐源摘要。
3. 继续真机 checklist，补 replay、awards/free-text dry_run 接缝；identity/ownership、`you_killed`、`you_died`、`low_fuel` 和真实 push 已有真机正向证据。
4. kill/death/hudmsg/combat.feed/awards 去桩前确认 T-Safety 合同与 `tools/free_text_gate.py` 仍覆盖 prompt / `push_message.parts[].text`。
5. L8 子进程最小编排已完成；2026-06-26 本地自验证确认 `data_layer.mode=managed/external` 可区分来源，插件 stop 会关闭 managed `8112`，不会误杀 external `8112`。
```

## 验证入口

从独立插件仓库 root 运行：

```powershell
uv run python tools\preflight.py --run
uv run python tools\release_readiness.py --run
```

单项排障时再分别运行：

```powershell
uv run python tests/run_logic_tests.py
uv run pytest -c tests\pytest.ini tests -q
uv run python tools\free_text_gate.py
uv run python tools\replay_gate.py
uv run python tools\proximity_gate.py
uv run python tools\v2_output_policy_gate.py
```

从 N.E.K.O 宿主仓库内做插件检查时，使用宿主路径：

```powershell
cd D:\Users\zheng\Documents\Code\N-E-K-O-Warthunder\N.E.K.O
uv run python -m plugin.neko_plugin_cli.cli check D:\Users\zheng\Documents\Code\N-E-K-O-Warthunder\project-N-E-K-O-Warthunder-8111-data-plugin
```

## 运行时启动注意（独立插件仓库）

本仓库是独立插件仓库；当前工作区里 `N.E.K.O\plugin\plugins\neko_warthunder` 必须是指向本仓库的 junction。手动启动宿主时，不要额外设置 `PLUGIN_CONFIG_ROOT` 指向外层工作区，否则宿主可能同时扫到 junction 和独立仓库目录，产生重复插件（例如 `neko_warthunder_1`）或加载旧副本。

```powershell
cd D:\Users\zheng\Documents\Code\N-E-K-O-Warthunder\N.E.K.O
uv run python launcher.py
```

如果 `GET http://127.0.0.1:48916/plugins` 没有列出 `neko_warthunder`，先调用：

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:48916/plugins/refresh
Invoke-RestMethod -Method Post http://127.0.0.1:48916/plugin/neko_warthunder/start
```

若 `plugins/refresh` 看到 `neko_warthunder_1`，或把 `project-N-E-K-O-Warthunder-8111-data-plugin` 当成另一份插件，先检查 junction 与启动环境，不要继续真机测试。运行态烟测通过的判据是：只启动 `neko_warthunder`，Hosted UI context 返回 `state_empty=false`，actions 可见，且 `dry_run=true` 时 `test_say` 返回 `pushed=false, blocked="dry_run"`。

## 目录

```text
neko_warthunder/
├─ core/         contracts / scenario / arbiter / safety_guard / instructions
├─ adapters/     telemetry_client（拉 :8112）/ neko_dispatcher（唯一输出口）
├─ detectors/    condition（flag 边沿 FSM）/ discrete（按 id/跳变去重）
├─ contract/     真实 /api/telemetry 样本与契约检查
├─ ui/           Hosted UI 中文化面板，按连接/战场/安全/最近决策/最近输出分区
├─ i18n/         zh-CN 占位；完整 8 locale 待后续 UI 文案扩展
├─ tests/        契约 / Detector / Arbiter / Scenario / integration 测试
├─ docs/         D-B1~B5 / 实现计划 / 待办事项 / 真机验证 checklist / recovery 测试方案
└─ data_layer/   合作者数据层，vendored，只通过 HTTP 消费
```

## 关键约束

- 数据层代码只作为 vendored 目录保存，插件侧不要修改、不要 import。
- `you_killed` / `you_died` 已消费 `combat.feed[].is_my_kill` / `combat.feed[].is_my_death`，2026-06-23 已完成陆战 dry_run 与 `dry_run=false` 真实 push 验证，空战 owned kill feed 也有正向证据。
- `tools/replay.py` 的内置合成场景已覆盖 v1.6 ownership 形状下的 `you_killed` / `you_died`。
- `overspeed` 已接入 `processed.flags` 中的 `overspeed_warn` / `overspeed_critical`；2026-06-23 真机 dry_run 已观察到 warning/critical flag、事件生成、Arbiter 放行和 Dispatcher dry_run。
- `low_alt_danger` 已增加起飞/滑跑保护：`takeoff_low_alt_grace_seconds` 默认 45s；若数据层提供 `radio_altitude_m`，插件按 `<=10m` 进入、`>=40m` 解除的 AGL 迟滞保护。离地判断统一优先 `radio_altitude_m`，有 AGL 时 prompt 不再复述 `altitude_m` 海拔；贴地滑跑保护内也压制 `overspeed`，避免机场滑跑被误当空中超速。
- 过热/炸缸真机 smoke 中，游戏 UI 已出现油温/发动机异常；插件侧已补 `hud_notices.feed[].code=engine_overheat/oil_overheat` 到 `overheat` 的映射，2026-06-23 已观察到 `overheat` dry_run 基础链路；油温/发动机细项仍等数据库补齐后再校准。`powertrain_failure` 暂不直接提升为播报事件，但会以 `detector_suppressed/deferred_hud_notice` 记录到 T-Observe / live monitor，方便现场判断“识别到了但当前策略不播”。
- `replay: true` 已在 Detector 层静默并 reset，避免回放数据触发真实播报；运行态 observe 会记录 `detector_suppressed/replay`，`tools/live_monitor.py` 会汇总 `replay_degrade.status` 与 `output_blocked`，方便统一测试时解释“为什么没播”。后续仍需要真实 replay 样本验证。
- `/api/identity` 是 player_name 的主路径；插件侧 Hosted UI/context/action 接缝已完成，面板已支持从安全化 `combat.active_players` 候选点选自己；2026-06-23 真机已验证手动身份会反映到 `combat.self.source=manual`，并能驱动 `is_my_kill` / `is_my_death` owned combat.feed 标记；`you_killed` post-fix dry_run 与 `dry_run=false` push 已通过陆战验证。
- `hud_notices` / `awards` 来自自由文本解析，真实播报前受 T-Safety 阻塞。
- V2 后方/尾随/目标点事件在真机证据补齐前受 `v2_live_verified_real_output_enabled=false` 保护：dry_run 仍可观察，真实输出默认被压住。
