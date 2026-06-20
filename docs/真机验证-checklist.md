# 真机验证 checklist（敲定 3 个未验证接缝）

> 当前 M1 框架 + M2 逻辑已就绪、T1A/T1B Hosted UI 已完成，29/29 逻辑自检通过、lint 干净。Hosted UI surface/context/action smoke 已通过。剩余仍需在 NEKO 宿主 + 数据层 + 游戏环境里验证真实接缝。
> 按顺序走，每步标了"失败改哪个文件"。

## 已完成的 Hosted UI smoke

- 宿主可发现 `neko_warthunder` 的 Hosted UI surface `main`。
- `dashboard` context 可返回面板状态。
- `set_dry_run` / `pause` / `resume` / `test_say` 可通过 Hosted UI action 调用，且状态刷新符合预期。
- 未发现 `PLUGIN_UI_ACTION_FAILED`。

## 剩余接缝

- 真机/数据层 `/api/telemetry` 字段与 flag 名验证。
- 真实 `push_message` 开口验证。
- dry_run 关掉后的端到端真机验证。

## 接缝① 插件能否被 NEKO 加载（不用开游戏）

1. 静态校验：
   ```
   uv run python -m plugin.neko_plugin_cli.cli check plugin/plugins/neko_warthunder
   ```
   预期：0 error（模板 warning 可接受）。
2. 单测（完整环境）：
   ```
   uv run pytest plugin/plugins/neko_warthunder/tests -q
   ```
   预期：全过（含逻辑 29 项）。逻辑自检用 `uv run python plugin/plugins/neko_warthunder/tests/run_logic_tests.py`。
3. 启动：起 NEKO（memory_server + main_server），`POST /plugin/neko_warthunder/start`，看日志 `neko_warthunder started`；调 `status` 动作能返回。
- ❌ 失败：多半是 `plugin.toml` 的 `entry`/SDK 版本，或 `__init__.py` 某个 import。改 `plugin.toml` / `__init__.py`。

## 接缝③ push_message 能否让猫开口（不用开游戏）

> 先验③，因为它不依赖游戏，能最快确认"输出链路通不通"。

1. 插件已 `/start` 后，调诊断动作（不受 dry_run 短路）：
   ```
   POST /plugin/neko_warthunder/hosted-ui/action/test_say   （或 /plugin/trigger，entry_id=test_say）
   body: {"args": {"text": "副驾驶测试，能听到我吗？"}}
   ```
2. 预期：**猫娘开口说话**；main_server 日志出现 `send_lanlan_response`（猫回应标记）。
- ❌ 哑了：对比能用的插件（如 memo_reminder）的 push 参数，调 `adapters/neko_dispatcher.py` 里的 `visibility` / `ai_behavior`（先试和 memo 一致）。改这一处。

## 接缝② 真实 /api/telemetry 字段/flag 名

1. 数据层 `:8112` 跑起来 + 进一次测试飞行，抓一帧：
   ```
   curl http://localhost:8112/api/telemetry > plugin/plugins/neko_warthunder/contract/telemetry_sample.json
   ```
2. 看解析报告（字段是否填上、flag 名对不对）：
   ```
   uv run python plugin/plugins/neko_warthunder/tests/test_real_sample.py
   ```
   重点看两行：「我们假设里真实样本未出现的 flag」「真实样本里我们没映射的 flag」。
- ❌ flag 名对不上：改 `core/flag_codes.py`（flag 名）一处；字段路径不对：改 `adapters/telemetry_client.py` 的 `parse_telemetry` 一处。

## 端到端（接缝全过后）

1. dry_run 保持开，进一次飞行，触发事件（低空/失速/出生等）→ 看日志决策链路出现 `spoken(dry_run)`（证明 scenario→detector→arbiter→dispatcher 全通）。
2. dry_run 关掉（`set_dry_run value=false`），再触发 → 猫真开口。
3. 据决策链路日志微调阈值/冷却/grace（集中在 `plugin.toml` 配置 + `core/scenario.py`/`flag_codes.py`）。

## 之后（M3，等数据层）

- overspeed flag、hudmsg/击杀解析、player_name 注入到位后：去桩（`detectors/condition/flight_safety.py` 的 overspeed 自然生效；`detectors/discrete/lifecycle.py` 的 KillDetector 配 player_name 生效）。
