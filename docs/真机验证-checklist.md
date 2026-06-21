# 真机验证 checklist

> 当前 M1/M2 主链路、Hosted UI、T4 集成测试、T-Safety output text sanitizer、identity Hosted UI/action 接缝已完成；逻辑自检以 `66/66 passed` 为准。数据层 `v1.6` 已合并，真机验证目标从“等待字段”改为“验证 v1.6 DTO 接缝”。

## 已完成的 Hosted UI Smoke

- 宿主可发现 `neko_warthunder` Hosted UI surface `main`。
- `dashboard` context 可返回面板状态。
- `set_dry_run` / `pause` / `resume` / `test_say` 可通过 Hosted UI action 调用。
- action 后 context 刷新符合预期。
- 未发现 `PLUGIN_UI_ACTION_FAILED`。

## 已完成的真机 dry_run Smoke（2026-06-21）

- 三个 health 均正常：主后端 `48911`、Hosted UI `48916`、数据层 `8112`。
- Hosted UI `dashboard` context 可持续返回 `dry_run`、连接状态、scenario、safety、observe last decision/output。
- `pause` 已验证：`safety.status=paused`、`manual_paused=true`，风险事件被 Arbiter 以 `reason=paused` suppress。
- `resume` 已验证：`safety.status=running`、`manual_paused=false`，恢复后 `low_alt_danger` 可被 Arbiter allowed 并进入 dry_run dispatcher。
- `test_say` 已验证：宿主日志出现多条 `TRIGGER entry='test_say'`，未出现 `PLUGIN_UI_ACTION_FAILED`。
- `set_identity` 已通过 Hosted UI/action 链路接入，但尚未做真机玩家名归属验证。
- 数值安全链路已观察到：`stall_risk`、`low_alt_danger`，并保留此前 `overspeed`、`low_fuel`、`you_died` dry_run 观察结论。
- 未发现 Traceback / ERROR / TTS push 报错。

待复核：

- 过热/炸缸：真机 UI 出现油温橙/红、发动机黄、炸缸现象；插件侧已补 `hud_notices.feed[].code=engine_overheat/oil_overheat` 到 `overheat` 的映射。后续需要真机复测该接缝；`powertrain_failure` 暂不直接播报。

## 剩余接缝

- NEKO 宿主加载与插件生命周期。
- 数据层 `:8112` v1.6 DTO 与插件解析。
- `dry_run` 决策链路是否能解释每一步（基础安全链路已通过一轮，剩余见下方待复核）。
- `push_message` 真实开口链路。
- T-Safety 已完成；kill/death/hudmsg/combat.feed/awards 在真机 dry_run 验证前仍不做真实自由文本播报。

## 接缝 1：插件能否被 NEKO 加载

1. 在 N.E.K.O 宿主仓库运行插件检查：

   ```powershell
   uv run python -m plugin.neko_plugin_cli.cli check plugin/plugins/neko_warthunder
   ```

   预期：`0 error`。

2. 在独立插件仓库运行逻辑自检：

   ```powershell
   uv run python tests/run_logic_tests.py
   ```

   预期：`66/66 passed`。

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
   curl http://localhost:8112/api/telemetry > contract/telemetry_sample.json
   ```

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

   预期：设置后 `combat.self.source=manual`，`combat.player_name` 等于面板输入昵称；后续 `combat.feed[]` 的 `is_my_kill` / `is_my_death` 能围绕该昵称生效。active players 点选自己仍可作为后续 UI 增强。

5. replay seam：

   - 若 `/api/telemetry` 返回 `replay: true`，插件应进入降级或静默策略。
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

- overspeed 不再是数据层缺口，但插件侧仍需要验证 flag 是否能触发正确事件。
- 2026-06-21 已验证低空 / 失速 / pause / resume / test_say 基础链路；过热/炸缸已补插件侧 `hud_notices` code 映射，仍需真机 dry_run 复测。
- kill/death/hudmsg/combat.feed/awards 在真机 dry_run 验证前只做 dry_run / audit，不做正式播报。

## 接缝 5：dry_run=false 真实开口

前置：

- 数值安全事件接缝已在 dry_run 下通过。
- T-Safety 已完成；还需要真机 dry_run 验证后，才允许测试 kill/death/hudmsg/combat.feed/awards 的真实播报。

步骤：

1. 通过 Hosted UI 或 action 关闭 dry_run。
2. 只先测试数值安全事件真实开口。
3. 观察是否刷屏、滞后或抢占异常。
4. 再按 T-Safety 完成情况决定是否开放 kill/death/hudmsg/combat.feed/awards。

## 暂缓项

- recovery 继续暂缓。不要因为数据层 v1.6 合并就提前实现。
- T3/L8 子进程编排后置，等数据层启动方式和真机接缝更明确后再做。
