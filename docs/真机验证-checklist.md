# 真机验证 checklist

> 当前 M1/M2 主链路、Hosted UI、T4 集成测试已完成；逻辑自检以 `32/32 passed` 为准。数据层 `v1.6` 已合并，真机验证目标从“等待字段”改为“验证 v1.6 DTO 接缝”。

## 已完成的 Hosted UI Smoke

- 宿主可发现 `neko_warthunder` Hosted UI surface `main`。
- `dashboard` context 可返回面板状态。
- `set_dry_run` / `pause` / `resume` / `test_say` 可通过 Hosted UI action 调用。
- action 后 context 刷新符合预期。
- 未发现 `PLUGIN_UI_ACTION_FAILED`。

## 剩余接缝

- NEKO 宿主加载与插件生命周期。
- 数据层 `:8112` v1.6 DTO 与插件解析。
- `dry_run` 决策链路是否能解释每一步。
- `push_message` 真实开口链路。
- T-Safety 前，kill/death/hudmsg/combat.feed/awards 不做真实自由文本播报。

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

   预期：`32/32 passed`。

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
   - `hud_notices` 是否存在且不会直接进入 prompt。
   - `awards` 是否存在且不会绕过 T-Safety。

4. identity seam：

   ```text
   GET http://localhost:8112/api/identity?name=<你的游戏昵称>
   GET http://localhost:8112/api/identity
   GET http://localhost:8112/api/identity?clear=1
   ```

   预期：设置后 `combat.feed[]` 的 `is_my_kill` / `is_my_death` 能围绕该昵称生效。前端后续应优先让用户从 active players 里点选自己。

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
- kill/death/hudmsg/combat.feed/awards 在 T-Safety 前只做 dry_run / audit，不做正式播报。

## 接缝 5：dry_run=false 真实开口

前置：

- 数值安全事件接缝已在 dry_run 下通过。
- T-Safety 已完成，才允许测试 kill/death/hudmsg/combat.feed/awards 的真实播报。

步骤：

1. 通过 Hosted UI 或 action 关闭 dry_run。
2. 只先测试数值安全事件真实开口。
3. 观察是否刷屏、滞后或抢占异常。
4. 再按 T-Safety 完成情况决定是否开放 kill/death/hudmsg/combat.feed/awards。

## 暂缓项

- recovery 继续暂缓。不要因为数据层 v1.6 合并就提前实现。
- T3/L8 子进程编排后置，等数据层启动方式和真机接缝更明确后再做。
