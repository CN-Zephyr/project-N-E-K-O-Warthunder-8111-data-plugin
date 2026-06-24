# 真机验证 checklist

> 当前 M1/M2 主链路、Hosted UI、T4 集成测试、T-Safety output text sanitizer、T-Observe runtime decision timeline、T-Live live monitor summary tool、T-Output output backpressure guard、T-Kill-Coalesce 多杀合并、identity Hosted UI/action 接缝已完成；逻辑自检以 `119/119 passed` 为准。数据层 `v1.6` 已合并，真机验证目标从“等待字段”改为“验证 v1.6 DTO 接缝”。

## 已完成的 Hosted UI Smoke

- 宿主可发现 `neko_warthunder` Hosted UI surface `main`。
- `dashboard` context 可返回面板状态。
- `set_dry_run` / `pause` / `resume` / `test_say` 可通过 Hosted UI action 调用。
- action 后 context 刷新符合预期。
- 未发现 `PLUGIN_UI_ACTION_FAILED`。

## 已完成的真机 dry_run Smoke（2026-06-21）

- 三个 health 均正常：主后端 `48911`、Hosted UI `48916`、数据层 `8112`。
- Hosted UI `dashboard` context 可持续返回 `dry_run`、连接状态、scenario、safety、observe last decision/output。
- T-Observe 普通模式已可通过 `observe.last_event` / `observe.last_decision` / `observe.last_output_status` 辅助判断链路停在哪一步；debug timeline 默认关闭。
- `pause` 已验证：`safety.status=paused`、`manual_paused=true`，风险事件被 Arbiter 以 `reason=paused` suppress。
- `resume` 已验证：`safety.status=running`、`manual_paused=false`，恢复后 `low_alt_danger` 可被 Arbiter allowed 并进入 dry_run dispatcher。
- `test_say` 已验证：宿主日志出现多条 `TRIGGER entry='test_say'`，未出现 `PLUGIN_UI_ACTION_FAILED`。
- `set_identity` 已通过 Hosted UI/action 链路接入，但尚未做真机玩家名归属验证。
- 数值安全链路已观察到：`stall_risk`、`low_alt_danger`，并保留此前 `overspeed`、`low_fuel`、`you_died` dry_run 观察结论。
- 未发现 Traceback / ERROR / TTS push 报错。

## 已完成的真机 dry_run Smoke（2026-06-23）

- 三个 health 均正常：主后端 `48911`、Hosted UI `48916`、数据层 `8112`；测试结束后端口已关闭。
- 同日追加空战 dry_run 监控中，`:8111` 原生遥测和 `:8112` 数据层正常，插件日志链路正常；该轮 `48911` / `48916` 未监听，因此只作为运行主链路证据，不替代 Hosted UI smoke。
- Hosted UI context 持续返回 `dry_run=true`、`conn_state=in_battle`、scenario、safety、`observe.last_event`、`observe.last_decision`、`observe.last_output_status`。
- `spawn` 已进入 Arbiter allowed，并由 Dispatcher 走 dry_run。
- `overspeed_warn` / `overspeed_critical` 已由数据层 `processed.flags` 触发；插件生成 `overspeed/enter`，Arbiter allowed，Dispatcher dry_run 输出。
- `low_fuel` 已观察到 warning / critical dry_run 输出；后续重复低油在 `COMBAT_STRESS` / `CRITICAL_RISK` 下可被 scenario gate 丢弃。
- `low_alt_danger` 已观察到 warning / critical dry_run；重复 critical 命中时可被 cooldown 丢弃。
- `stall_risk` 已观察到 warning / critical dry_run；critical 可由 Arbiter 以 `reason=preempt` 放行。
- `overheat` 已观察到 warning / critical dry_run；后续重复 critical 命中可被 cooldown 丢弃，说明基础链路和 cooldown 都可解释。
- `you_died` 已观察到 `critical` 事件并 dry_run 输出；不把 `vehicle_valid` 跳变作为主路径。
- 追加空战监控确认坠毁类 `combat.feed` 可产生 `is_my_death=true`，插件生成 `you_died/enter/critical`，Arbiter 以 `preempt` 放行，Dispatcher 输出 dry_run。
- 手动 identity 接缝已验证：Hosted UI 设置玩家名后，数据层返回 `combat.self.source=manual`，并观察到 owned `combat.feed[].is_my_kill=true` / `is_my_death=true` 路径。
- `you_killed` 已由 owned combat.feed 产生并 dry_run 输出；此前 `SPAWNING` 门控问题已修复。
- identity 设置时机已确认：若死亡 feed 在手动 identity 设置前已被 Detector 按 id 消费，后续同一 feed id 变为 `is_my_death=true` 不会补发；应在进战局前或死亡前设置 `/api/identity`。
- T-Observe 普通模式已能解释 allow / preempt / cooldown / dry_run 输出；debug timeline 仍默认关闭。
- 未发现 `PLUGIN_UI_ACTION_FAILED`、后端 Traceback、TTS/push 报错。
- 已知数据层问题：`/api/telemetry.telemetry` 字段为空，但 `processed.*` 可用；map/profile 轮询曾持续出现 `_merge_profile() missing ... army and family_rules`。该签名回归已补代码修复和测试；下次重启数据层后确认日志不再重复。

## 已完成的 kill/death 与真实 push Smoke（2026-06-23）

- 空战 owned kill：数据层返回 `domain=air`，`combat.feed` 出现 `is_my_kill=true`；用于确认 air combat.feed ownership 字段可用。
- 空战 owned death：数据层返回 `domain=air` 且新 `combat.feed` 出现 `is_my_death=true`；插件生成 `you_died`，Arbiter preempt，Dispatcher dry_run 输出。
- 陆战 owned kill：数据层返回 `domain=ground`，`combat.feed` 多条 `is_my_kill=true`；插件生成 `you_killed`，Arbiter allowed，Dispatcher dry_run 输出。
- 陆战 owned death：数据层返回 `combat.feed` 中 `is_my_death=true`；插件生成 `you_died`，Arbiter allowed，Dispatcher dry_run 输出。
- `dry_run=false` 真实 push：关闭 dry_run 后，`test_say`、`you_killed`、`you_died` 均进入 proactive bridge / `push_message` 链路；Hosted UI `observe.last_output_status` 显示 `dispatcher_pushed` / `push_message_accepted`。
- 现场确认猫娘实际开口；未发现 `PLUGIN_UI_ACTION_FAILED`、Traceback、TTS/push 报错。
- 记录边界：本节只记录聚合结论，不写 raw 玩家名、raw combat.feed 原文或 raw HUD 文本。

待复核：

- replay 降级：插件侧离线合同已覆盖 Detector 静默、`detector_suppressed/replay` 观测记录和 `live_monitor` 的 `replay_degrade` 汇总；仍需真实 `replay=true` 样本验证。
- 油温/发动机细项：过热基础链路已过；油温 / 发动机温度数据库和 `powertrain_failure` 策略仍后置，`powertrain_failure` 暂不直接播报。

## 下一轮统一测试现场顺序

> 目标：先在 `dry_run=true` 下验证 v1.6 DTO 接缝和 T-Observe 解释能力；只有数值安全事件 dry_run 稳定后，才考虑 `dry_run=false`。

1. **离线门禁**：按 `docs/统一测试前-离线检查.md` 跑完逻辑测试、pytest、plugin check、合成 replay、本地样本 replay。
2. **启动链路**：启动 N.E.K.O 宿主、Hosted UI、数据层 `:8112`，确认三项 health 正常。
   - 当前工作区通过 junction 挂载独立插件仓库；若宿主没有发现 `neko_warthunder`，用 `PLUGIN_CONFIG_ROOT=D:\Users\zheng\Documents\Code\N-E-K-O-Warthunder` 重启宿主，再调用 `/plugins/refresh` 与 `/plugin/neko_warthunder/start`。
   - Hosted UI 侧以 context `state_empty=false`、actions 包含 `set_dry_run` / `pause` / `resume` / `test_say` / `set_identity` 作为注册通过信号。
3. **打开面板**：确认 `dry_run=true`，观察 `connected` / `conn_state` / `in_battle` / `scenario` / `safety` / `observe.last_decision` / `observe.last_output_status`。
4. **基础 action**：依次点 `pause`、`resume`、`test_say`，确认没有 `PLUGIN_UI_ACTION_FAILED`；`pause` 时风险事件应被 suppress，`resume` 后恢复。
5. **identity / owned combat 回归**：在 Hosted UI 设置游戏昵称，确认 `/api/identity` 与 `/api/telemetry.combat.self.source=manual`；击杀 / 死亡时确认 `is_my_kill=true` / `is_my_death=true` 仍能生成 `you_killed` / `you_died`，并由 T-Observe 解释 Arbiter / Dispatcher 输出。
6. **数值安全事件**：优先复测 `overheat` / `oil_overheat`、`overspeed_critical`、`stall_risk`、`low_alt_danger`、`low_fuel`；每次看 `observe.last_decision` 是否能解释 allow / drop / cooldown / scenario gate。
7. **自由文本风险路径**：只在 `dry_run=true` 下观察 `combat.feed` / `hud_notices` / `awards`，确认 prompt / dry_run 输出不包含 raw 玩家名、raw HUD 文本或 awards 原文；`live_monitor` 顶部 `Summary` 应显示 free-text 状态，细节行应显示 `free_text=dry_run_only(...)`，并在 `FreeText detail` / `free_text_safety.source_details` 中给出逐源 `.../blocked`。
8. **replay 降级**：若数据层返回 `replay=true`，确认 Detector 静默、last decision 能说明 suppressed / replay，`live_monitor` 显示 `replay=suppressed(detector_suppressed/replay)` 且 `output_blocked=True`，不触发真实输出。
9. **样本留存**：把现场抓包放到 `local_samples/` 或本地临时目录，保持 `.gitignore`；仓库只提交聚合统计和脱敏结论。
10. **真实开口**：只有前面 dry_run 通过后，才关闭 dry_run；`test_say`、generic kill/death 已在 2026-06-23 通过真实 push smoke。hudmsg / awards / 其他 free-text 仍需各自 dry_run 安全验证后再开放真实播报。

每轮测完后，用 `docs/真机测试结果-template.md` 记录结果；只写聚合统计、安全摘要和结论，不写 raw 玩家名、raw HUD 文本、raw combat.feed 或 awards 原文。

### 现场速用版

| 顺序 | 用户操作 | 我方监控重点 | 通过标准 |
| --- | --- | --- | --- |
| 0 | 先跑离线门禁，或确认当天代码未变 | `tests/run_logic_tests.py`、pytest、plugin check、`tools/sample_replay.py` / `tools/live_test_plan.py` | 离线基线仍为 `119/119 passed`，操作清单包含 P1/P2 和 runtime output 复测项 |
| 1 | 启动宿主、Hosted UI、数据层，打开面板 | `48911/health`、`48916/health`、`8112/health`、Hosted UI context/actions | 三个 health 正常；`state_empty=false`；actions 含 `set_dry_run` / `pause` / `resume` / `test_say` / `set_identity` |
| 2 | 进战局前设置玩家名 | `/api/identity`、`combat.self.source`、`combat.player_name` | `combat.self.source=manual`，后续 kill/death ownership 围绕该昵称生效 |
| 3 | 保持 `dry_run=true`，打一轮常规空战或陆战 | `observe.last_event`、`observe.last_decision`、`observe.last_output_status`、`processed.flags` | 事件能解释为 allowed / preempt / cooldown / scenario_gated / dry_run 输出之一 |
| 4 | 触发或等待 owned kill / death | `combat.feed[].is_my_kill` / `is_my_death`、`you_killed` / `you_died` | 生成 generic kill/death，不含 raw 玩家名；death / critical 仍可抢占 |
| 5 | 观察 awards / hud_notices / combat.feed 自由文本源 | `free_text_safety.status`、`source_details`、prompt / dry_run 输出 | `free_text=dry_run_only(...)`，raw HUD / combat.feed / awards 原文不进入 prompt |
| 6 | 若出现 replay，继续观察不要手动触发输出 | `replay=true`、`detector_suppressed/replay`、`output_blocked` | replay 帧静默，`live_monitor` 显示 replay suppressed，不真实开口 |
| 7 | 条件允许时关闭 `dry_run`，复测数值安全或 generic kill/death | `push_message`、`last_output_status`、`output_backpressure`、`kill_coalesced` | 真实开口不刷屏；旧回复晚到减少；更高优先级事件仍可插队 |

现场优先级：

- 第一优先：replay=true、awards/free-text dry_run 安全合同。
- 第二优先：油温/发动机数据库补齐后的细项复测、powertrain_failure 是否继续不播。
- 第三优先：`dry_run=false` 数值安全事件真实开口延迟和刷屏情况。

## 剩余接缝

- NEKO 宿主加载与插件生命周期。
- 数据层 `:8112` v1.6 DTO 与插件解析（基础数值安全链路、identity/ownership、`you_killed` / `you_died` 已通过，剩余 replay/free-text 单项）。
- `dry_run` 决策链路是否能解释每一步（2026-06-23 已证明 always-on observe 摘要足够解释主要安全事件）。
- `push_message` 真实开口链路（generic kill/death 已通过，其他事件仍需按项验证）。
- T-Safety 已完成；generic kill/death 已通过真实输出 smoke，hudmsg / awards / 其他 free-text 在真机 dry_run 验证前仍不做真实播报。

## 接缝 1：插件能否被 NEKO 加载

1. 在 N.E.K.O 宿主仓库运行插件检查：

   ```powershell
   uv run python -m plugin.neko_plugin_cli.cli check D:\Users\zheng\Documents\Code\N-E-K-O-Warthunder\project-N-E-K-O-Warthunder-8111-data-plugin
   ```

   预期：`0 error`。

2. 在独立插件仓库运行逻辑自检：

   ```powershell
   uv run python tests/run_logic_tests.py
   uv run pytest -c tests\pytest.ini tests -q
   ```

   预期：`119/119 passed`。

3. 启动宿主后启动插件，确认 `status` / Hosted UI context 可返回状态。

失败定位：

- 插件检查失败：优先看 `plugin.toml`、`__init__.py`、Hosted UI surface 声明。
- context/action 失败：优先看 `@ui.context` / `@ui.action` 与 action 是否为 async。

## 接缝 2：push_message 能否让猫开口

1. 插件启动后调用 `test_say`：

   ```text
   POST /plugin/neko_warthunder/hosted-ui/action/test_say
   body: {"args": {"text": "副驾驶测试，能听到我吗？"}}
   ```

2. 预期：猫娘开口；宿主日志无 `PLUGIN_UI_ACTION_FAILED`。

失败定位：

- 对比可用插件的 `push_message` 参数。
- 只改 `adapters/neko_dispatcher.py` 的输出接缝，不改 Detector / Scenario / Arbiter。

## 接缝 3：数据层 v1.6 DTO 验证

1. 启动数据层 `:8112` 并进入一次飞行。

2. 抓取样本：

   ```powershell
   New-Item -ItemType Directory -Force local_samples\live_current | Out-Null
   curl http://localhost:8112/api/telemetry > local_samples\live_current\telemetry_sample.json
   ```

   仓库内已有一份脱敏的 v1.6 形状样本 `contract/telemetry_sample.json`，用于合同测试。真机验证时另抓当前环境帧到 `.gitignore` 覆盖的 `local_samples/` 做对照；不要把 raw 玩家名、raw HUD 文本、raw combat.feed 或 awards 原文写回 tracked contract 文件。

   已留存的本地样本可先做离线覆盖率审计：

   ```powershell
   uv run python tools/sample_replay.py local_samples/data_process_20260620 tl0sr2
   ```

   当前样本的聚合回放结论见 `docs/样本回放-20260620.md`。该报告只记录统计和缺口，不提交原始抓包文本；`session_summary` 可直接给出已观察事件、dry_run 输出、分组 validation verdict、P1/P2 `live_test_plan` 和下一步补测项。需要机器可读结果时使用 `--json`，需要可交付 Markdown 汇报时使用 `tools/offline_report.py`；需要操作清单时使用 `tools/live_test_plan.py`。`sample_replay` / `offline_report` / `live_test_plan` 三个出口与 `session_summary.next_steps` 都会列出 T-Output 背压与 T-Kill-Coalesce 多杀合并复测项；真机测试进行中用 `tools/live_monitor.py` 做只读安全摘要，先看 `Summary` 行，再查看 `free_text=dry_run_only(...)`、`FreeText detail` 和 JSON 的 `free_text_safety.source_details` 是否按预期出现。该报告包含 Team brief、Operator quick checklist 和 Next live-test plan，也可通过 `tools/preflight.py --run --report-output <path>` 在统一预检时保存并打印操作清单。

   重点看输出 `coverage:` 行里的 `is_my_kill_field` / `is_my_death_field` / `involves_me_field`、`is_my_kill_true` / `is_my_death_true` / `involves_me_true`、`combat_self_source`、`hud_notice_codes`、`hud_notice_severities`、`awards_items`、`replay_true`，以及 `coverage_gaps:` 行。如果 `coverage_gaps` 含 `combat_feed_missing_ownership_fields`，说明样本里完全没有新归属字段；如果含 `combat_feed_no_ownership_true_frames`，说明字段存在但样本没有命中我方击杀/死亡。两种情况都不能关闭 kill/death identity 验证项。若 `coverage_gaps` 含 `no_manual_identity_frames`，说明当前样本没有 `combat.self.source=manual`，不能关闭手动 `/api/identity` 接缝验证。若 `coverage_gaps` 含 `no_awards_items`、`no_overspeed_critical_flags`、`no_oil_overheat_notice_codes`、`no_powertrain_failure_notice_codes` 或 `hud_notice_severity_unknown`，说明当前样本还不能验证 awards、超速 critical、油温 notice、动力故障 notice 或 notice warning/critical 档位。

3. 必查字段：

   - 顶层 `replay` 是否存在。
   - `processed.flags` 是否能出现 `overspeed_warn` / `overspeed_critical`。
   - `combat.feed[]` 是否有稳定递增 `id`。
   - `combat.feed[]` 是否有 `is_my_kill` / `is_my_death`。
   - `combat.self` / `player_name` / `active_players` 是否符合 `/api/identity` 设定。
   - `hud_notices` 是否存在；`engine_overheat` / `oil_overheat` code 是否能触发 `overheat`，且 raw 文本不会直接进入 prompt。
   - `awards` 是否存在且不会绕过 T-Safety。

4. identity seam：

   ```text
   Hosted UI 面板输入你的游戏昵称，点击“设置玩家名”
   GET http://localhost:8112/api/identity
   Hosted UI 面板点击“清除玩家名”
   ```

   预期：设置后 `combat.self.source=manual`，`combat.player_name` 等于面板输入昵称；`combat.feed[]` 的 `is_my_kill` / `is_my_death` 能围绕该昵称生效。2026-06-23 已观察到该正向路径，并已确认 `you_killed` post-fix dry_run / push 输出。active players 点选自己仍可作为后续 UI 增强。

5. replay seam：

   - 若 `/api/telemetry` 返回 `replay: true`，插件应进入降级或静默策略。
   - `tools/live_monitor.py` 应显示 `replay=suppressed(detector_suppressed/replay)`，并在 JSON 中给出 `telemetry.replay_degrade.output_blocked=true`。
   - 回放期间不要消费派生战斗数据，不要触发真实播报。

失败定位：

- flag 名不一致：改 `core/flag_codes.py`。
- 字段路径不一致：改 `adapters/telemetry_client.py`。
- 身份识别不稳定：先要求 `/api/identity` 手动设定，不依赖低置信度自动猜测。

## 接缝 4：端到端 dry_run

1. 保持 `dry_run=true`。
2. 进入飞行，触发数值安全事件：低空、失速、过热、低油、超速。
3. 查看日志中的 scenario / detector / arbiter / dispatcher 决策链路。
4. 预期：出现可解释的 `spoken(dry_run)` 或明确丢弃原因。

注意：

- overspeed 不再是数据层缺口；2026-06-23 已验证 warning/critical flag 能触发正确事件并进入 dry_run。
- 2026-06-21 已验证 pause / resume / test_say 基础链路；2026-06-23 已验证低空 / 失速 / 超速 / 过热 / 死亡 dry_run 基础链路。
- generic kill/death 已通过真机 dry_run 与真实 push；hudmsg / awards / 其他 free-text 在真机 dry_run 验证前只做 dry_run / audit，不做正式播报。

## 接缝 5：dry_run=false 真实开口

前置：

- 数值安全事件接缝已在 dry_run 下通过。
- T-Safety 已完成；generic kill/death 已通过真机 dry_run 与真实 push。hudmsg / awards / 其他 free-text 还需要真机 dry_run 验证后，才允许测试真实播报。
- T-Output 已完成；真实开口测试时应观察 `dispatcher_suppressed / output_backpressure` 是否减少旧事件晚回复和多条消息堆积，同时确认更高优先级事件仍能通过。`tools/live_monitor.py` 的 Summary / Observe 摘要会直接显示 `output_backpressure`，并保留 `kill_coalesced` 决策原因。
- T-Kill-Coalesce 已完成；多杀 / 连杀测试时应观察 `you_killed` 是否合并为 `kill_count` 单条输出，并确认 `you_died` / critical 安全事件仍可抢占。

步骤：

1. 通过 Hosted UI 或 action 关闭 dry_run。
2. 先测试数值安全事件或 T-Safety-safe generic 事件真实开口。
3. 观察是否刷屏、滞后或抢占异常。
4. 再按 T-Safety 和 dry_run 结果决定是否开放 hudmsg / awards / 其他 free-text。

## 暂缓项

- recovery 继续暂缓。不要因为数据层 v1.6 合并就提前实现。
- T3/L8 子进程编排后置，等数据层启动方式和真机接缝更明确后再做。
