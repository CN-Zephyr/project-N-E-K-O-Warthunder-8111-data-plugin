# 实现计划（Codex 交接）· neko_warthunder v1

> 面向 AI 编码代理（Codex）的实现交接。分层 → 分步 → 带验收。
> 设计依据：同目录 D-B1（Scenario）/ D-B2（BattleEvent）/ D-B3（Detector）/ D-B4（Arbiter）/ D-B5（事件→数据层映射）。
> 范围：v1 RB 空战，9 个事件，消费数据层 HTTP `:8112`。

---

## 实现状态（v0.2 已落地 · 2026-06-20）

**M1 框架 ✅ + M2 逻辑 ✅ 已实现；T1A Hosted UI Integration ✅ + T1B Minimal Panel ✅ 已完成；逻辑单测 29/29 过、lint 0、`py_compile` 过；已过一轮 Bugbot 评审并修复 6 项（窗口 flush 漏门控 / COMBAT_STRESS 卡死 / critical 升级不重报 / 瞬断误报 spawn / 配置重载重放击杀 / 击杀去重非确定）。** Hosted UI surface/context/action smoke 已通过；真机/数据层/真实开口接缝未验证（见文末 3 接缝）。

分层状态：
- L0 脚手架+契约骨架 ✅（`plugin.toml` / `__init__.py` / `core/contracts.py`；`contract/telemetry_sample.json` ⏳ 待真机抓）
- L1 telemetry_client ✅ ・ L2 BattleState ✅ ・ L3 scenario ✅ ・ L4 detectors ✅（overspeed/you_killed 打桩；you_died 用 vehicle_valid 跳变已可触发）
- L5 arbiter ✅ ・ L6 dispatcher+instructions ✅ ・ L7 safety_guard ✅ + Hosted UI 最小面板 ✅
- L8 数据层并入 ✅（`data_layer/` 已并入；启动拉起 :8112 子进程编排 ⏳ 未做）・ L9 真机调参 ⏳

自检入口：
- 无依赖逻辑自检：`uv run python plugin/plugins/neko_warthunder/tests/run_logic_tests.py`（29/29）
- 离线回放/仿真：`uv run python plugin/plugins/neko_warthunder/tools/replay.py`（内置场景；或传真机帧 JSON）——离线看猫会在什么时刻说什么 + 决策链路
- 完整环境：`uv run pytest plugin/plugins/neko_warthunder/tests`
- 接缝自检：`test_say` 动作（验①③）/ `tests/test_real_sample.py`（验②）/ `docs/真机验证-checklist.md`

待办：① T4 补集成测试；② 3 个接缝真机验证（见 checklist）；③ T3/L8 子进程编排；④ M3 去桩（overspeed/you_killed 需数据层 flag + player_name）→ M4 真机调参终验。

---

## 0. 给 Codex 的总则（先读，铁律）

1. **必读文档**：本插件 `docs/` 下 D-B1~B5；数据层接口 `data_layer/data process/后端接口文档.md`（插件内 vendored）。
2. **架构母本**：参照已验证插件 `neko_roast`（直播锐评，在 `CN-Zephyr/N.E.K.O` 的 `Roast` 分支）。可照搬其 `safety_guard` / 唯一出口 `dispatcher` / `dry_run` / 单槽窗口择优 / `event_bus`(可选) / `module_registry`(可选) / 五层兜底。
3. **边界铁律**：
   - 数据层与我们唯一边界 = HTTP `:8112`（`/api/telemetry`）。我们**只消费**，不重算阈值。
   - **不修改合作者文件夹任何内容**（vendored，整包替换式更新）。其目录 `data process` 带空格，**绝不当 Python 模块 import**。
   - 输出**只走** `neko_dispatcher`（唯一出口）；Detector / Scenario / Arbiter **不得**直接 `push_message`。
   - **每次仲裁至多 1 条**输出。
   - 我们这层**不拼最终台词**：产出"事实行 + 要求行" prompt，口吻交角色 LLM（`ai_behavior="respond"`）。
4. **dry_run 默认开**：全链路跑、最后一步短路不真投；真机调参确认后才关。
5. **不做**：敌情感知 / map / PNG / 复杂 AI 战术（v1 范围）。

## 1. 前置门（什么能现在做，什么要等）

- **DTO 冻结门**：理想顺序是 G1~G5 通过、冻结 DTO 后再建骨架。但数据层接口已稳定文档化，**L0~L7 的框架与"非阻塞事件"可先按当前契约实现**（dry_run）。
- **数据层阻塞项**（这些事件先打桩/标 TODO，待合作者补齐再接线）：
  - `overspeed`：等数据层 `overspeed_warn/critical` flag。
  - `you_killed` / `you_died`：等 hudmsg/击杀解析稳定 + `player_name` 注入。
- **可立即实现（6 事件 + 全框架）**：`stall_risk`、`overheat`、`low_fuel`、`low_alt_danger`、`spawn`、`battle_end`。

## 2. 结构（✅ 已落地，下方即当前真实目录）

```text
plugin/plugins/neko_warthunder/
├─ __init__.py            插件类 + @lifecycle + @timer_interval(轮询) + @ui.action
├─ plugin.toml            id/entry/sdk 版本 + [neko_warthunder] 配置 + 最小面板声明
├─ core/
│  ├─ contracts.py        BattleEvent / BattleState / WtConfig + 事件类别/severity 表
│  ├─ scenario.py         D-B1 phase 机 + 解析器
│  ├─ arbiter.py          D-B4 仲裁
│  ├─ safety_guard.py     限流/队列/急停/dry_run（照搬 neko_roast）
│  └─ instructions.py     常驻战雷场景上下文 + restore
├─ adapters/
│  ├─ telemetry_client.py 轮询 :8112/api/telemetry → BattleState
│  └─ neko_dispatcher.py  唯一出口 push_message（照搬 neko_roast，去头像）
├─ detectors/
│  ├─ _base.py            Detector 协议 + 引擎 + 注册表
│  ├─ condition/          flag 边沿 FSM：stall/overheat/low_fuel/low_alt/overspeed(待)
│  └─ discrete/           按 id/跳变去重：you_killed(待)/you_died(待)/spawn/battle_end
├─ data_layer/            ✅ 合作者数据层整包并入（内容不改）
├─ contract/              ⏳ telemetry_sample.json 待真机抓（test_real_sample 会用它）
├─ ui/panel.tsx           ✅ 最小 Hosted UI 面板（状态 / dry_run / 安全状态 / 急停 / 测试开口）
├─ i18n/zh-CN.json        ✅（占位；完整 8 locale 待面板落地）
├─ tests/                 ✅ test_{contract,scenario,detectors,arbiter,real_sample}.py + conftest + run_logic_tests.py
└─ docs/                  ✅ D-B1~B5 + 本文件 + 待办事项 + 真机验证-checklist
```

---

## 3. 分层实现（L0~L9）

> 每层：**目标 / 依据 / 产出 / 步骤 / 验收**。层间有依赖，按序推进。

### L0 脚手架 + 契约固定
- 目标：插件能被 NEKO 加载；契约样本与版本固定。
- 依据：neko_roast 的 `plugin.toml` / `__init__.py` 形态；数据层接口文档。
- 产出：`plugin.toml`、`__init__.py`（空壳生命周期）、`contract/telemetry_sample.json`、`contract/schema_version.txt`、`core/contracts.py`（`BattleEvent`{event_id,edge,payload,ts}、`BattleState`、`WtConfig`{dry_run 默认 true, poll_hz, rate_limit_sec, 各 cooldown/severity...}）。
- 步骤：① 抓一份真实 `/api/telemetry` 存入 `contract/`；② 按接口文档定义 `BattleState`（含 raw 字段 + `processed.flags`）；③ `plugin.toml` 设 `auto_start=false`、声明面板。
- 验收：`POST /plugin/neko_warthunder/start` 后插件就绪；`dry_run=true` 默认。

### L1 数据接入 telemetry_client
- 目标：稳定把 `:8112` 拉成 BattleState 流。
- 依据：接口文档；D-B5。
- 产出：`adapters/telemetry_client.py`。
- 步骤：① 异步 GET `/api/telemetry`（超时+退避+重连）；② 解析 `state`(offline/not_in_battle/in_battle)、`indicators`、`processed.flags/level`、`hud_events`、`combat`；③ 映射进 `BattleState`；④ 连不上/`not_in_battle` 时安全降级（不崩、不误判死亡）。
- 验收：数据层开着→稳定出 BattleState；数据层关掉→优雅降级无异常。

### L2 BattleState 组装 + 历史
- 目标：维护当前态 + 短历史环形缓冲。
- 依据：D-B5。
- 产出：`core/contracts.py` 中 BattleState 装配逻辑（或独立小模块）。
- 步骤：① 每 tick 更新当前 BattleState；② 保留最近 N 秒历史（趋势/兜底用）；③ 暴露只读视图给 Scenario / Detector。
- 验收：BattleState 反映最新帧 + flags；下游只读不改。

### L3 Scenario phase 机
- 目标：实现 D-B1 的 7 态单态机。
- 依据：**D-B1**（含解析优先级、grace、门控矩阵）。
- 产出：`core/scenario.py`。
- 步骤：① 实现解析优先级（OUT_OF_BATTLE→BATTLE_ENDED→DEAD→SPAWNING→CRITICAL_RISK→COMBAT_STRESS→IN_FLIGHT）；② SPAWNING grace 计时器；③ CRITICAL_RISK 由危急 detector(`stall_critical`/`altitude_critical`/`overspeed_critical`)激活驱动；④ COMBAT_STRESS 用 `hud_events` 受创 + `Ny` 代理。
- 验收（=G2）：喂 `contract/` 真机语料，逐场景进入/退出正确、单态无抖。

### L4 Detector 注册表
- 目标：D-B3 的"候选事件"产出，防 if/else。
- 依据：**D-B3**（两个家族 + 数据源边沿语义分类）。
- 产出：`detectors/_base.py`（协议+引擎+注册表）、`detectors/condition/*`、`detectors/discrete/*`。
- 步骤：
  - ① `_base`：定义 Detector 协议（输入 BattleState 只读视图 → 0/1 候选）、通用引擎（每 tick 跑注册表收候选）。
  - ② condition 家族（电平 flag → 边沿 FSM）：ARMED→CONFIRMING→ACTIVE→CONFIRMING_EXIT；enter 谓词=上游 flag 真、exit=flag 假；confirm/迟滞/re-arm。实现 stall/overheat/low_fuel/low_alt；**overspeed 打桩**（flag 名预留，待数据层）。
  - ③ discrete 家族（已边沿/跳变 → 去重）：spawn(state→in_battle/vehicle_type 跳变)、battle_end(mission_status)；**you_killed/you_died 打桩**（接 combat.feed/hud_events，待数据层 + player_name）。
  - ④ 注册表声明式：加事件=加描述符，引擎零 `if event_id==`。
- 验收（=G3）：每事件在其场景样本触发、别处不误触；电平 vs 已边沿消费正确。

### L5 Arbiter
- 目标：D-B4 仲裁，候选→≤1 条输出。
- 依据：**D-B4** + D-B1 门控矩阵 + D-B2 severity/priority/cooldown/抢占。
- 产出：`core/arbiter.py`。
- 步骤：① Scenario 门控（查矩阵丢弃）；② 去重/合并(cooldown、多杀合并、you_died 双路合一)；③ 分流(抢占资格={危急集合∪you_died}∩数据层critical)；④ critical 抢占(绕限流+清窗口+防风暴冷却)；⑤ warning 单槽窗口择优(priority 最高)；⑥ 全局限流 flush；⑦ 单一出口≤1。dry_run 记决策链路。
- 验收（=G4）：多事件序列仲裁正确；dry_run 链路可解释每条说/不说。

### L6 输出 dispatcher + instructions
- 目标：唯一出口 + 常驻语境。
- 依据：neko_roast `neko_dispatcher` / `instructions`；D-B2 提示意图。
- 产出：`adapters/neko_dispatcher.py`、`core/instructions.py`。
- 步骤：① dispatcher 照搬 neko_roast（去头像），`push_message(visibility=[], ai_behavior="respond", parts=[{text}])`，`target_lanlan` 解析，dry_run 短路；② 把 D-B2 各事件"提示意图"拼成"事实行+要求行"prompt（带 `{MASTER_NAME}` 占位符）；③ 启动注入常驻战雷上下文(`read`)、关闭发 restore。
- 验收：dry_run 显示正确 payload；关 dry_run 后猫按人设开口。

### L7 安全 + 最小面板
- 目标：可靠性兜底 + 遥控。
- 依据：neko_roast `safety_guard` / 五层兜底；D-B4 抢占。
- 产出：`core/safety_guard.py`、`ui/panel.tsx`、`i18n/*`。
- 步骤：① safety_guard 照搬(限流/队列/连续失败自动急停/手动急停/dry_run) + 与 arbiter 的 critical 抢占对接；② 面板：总开关 / dry_run / 安全状态灯 / 一键急停；③ 8 locale。
- 验收：急停即停、dry_run 开关生效、状态可见；轮询循环异常不拖垮插件。

### L8 数据层并入 + 运行编排
- 目标：一个插件文件夹装下两层；运行可启。
- 依据：计划"目标打包"。
- 产出：`data_layer/`（合作者整包，内容不改）+ `__init__.py` 编排。
- 步骤：① 把合作者文件夹整包搬入 `data_layer/`（不改内容）；② 插件启动时**尽力**拉起 `:8112` 子进程（路径含空格要加引号）或检测已在运行，连不上则降级 + 面板提示；③ 文档说明"用户也可手动先开数据层"。
- 验收：数据层在跑→端到端通；不在跑→插件不崩、面板提示。

### L9 真机调参 + 实装
- 目标：阈值/节奏在真机 RB 空战调到舒服。
- 依据：D-B2/D-B4 参数；G3/G4。
- 步骤：① dry_run 真机灌数据，看决策链路调 cooldown/grace/rate_limit/priority；② 接合作者补齐的 overspeed/kill/death，去桩；③ 关 dry_run 终验。
- 验收：真机 9 事件正确播报、不刷屏、危急能抢占、生死有安慰。

---

## 4. 测试策略

- **契约测试**：`tests/test_contract.py`（合成样本，验解析）+ `tests/test_real_sample.py`（真实 `contract/telemetry_sample.json`，无则跳过；含 flag 名比对报告）。
- **Detector 单测**：给每个 detector 喂合成信号序列，断言边沿/去重/迟滞/re-arm（参照 neko_roast `test_live_events`）。
- **Arbiter 序列测试**：多事件同窗序列 → 断言择优/抢占/门控/≤1 条。
- **Scenario 测试**：状态转移用例 + grace。
- **语料回归**：真机抓包当 G2/G3 回归样本。
- **CLI check**：`uv run python -m plugin.neko_plugin_cli.cli check plugin/plugins/neko_warthunder`（0 error）。
- **无依赖逻辑自检**：`uv run python plugin/plugins/neko_warthunder/tests/run_logic_tests.py`（不需 NEKO 环境；当前 **29/29 过**）。
- **离线回放/仿真**：`uv run python plugin/plugins/neko_warthunder/tools/replay.py`（内置合成场景或真机帧序列 → 打印 scenario/候选/决策链路/猫娘 prompt）。

## 5. 推进顺序（里程碑）

1. **M1 框架可跑(dry_run)** ✅：L0→L1→L2→L6→L7（链路通）。
2. **M2 非阻塞事件** ✅：L3→L4(stall/overheat/low_fuel/low_alt + spawn/death/battle_end)→L5；逻辑单测 29/29 过。
3. **Hosted UI 接入与最小面板** ✅：T1A/T1B 已完成，surface/context/action smoke 已通过。
4. **接缝验证** ⏳（需真机/数据层/真实开口）：按 `docs/真机验证-checklist.md` 敲定 ①加载 ②字段/flag ③push 开口。
5. **M3 接阻塞事件** ⏳：合作者补 overspeed flag + hudmsg/击杀 + player_name 后去桩。
6. **M4 终装** ⏳：L8 子进程编排 + L9 真机调参 + 关 dry_run 终验。

> M1/M2 已在当前契约下完成（阻塞事件打桩）；正式去桩 + 终验需合作者补齐 + 真机验证。

---

## 6. 给 Codex 的下一步（按可做性排序）

### Codex 现在就能做（不阻塞）

- **T1A Hosted UI Integration / T1B Minimal Panel ✅ 已完成**：`plugin.toml` surface、`dashboard` context、`set_dry_run`/`pause`/`resume`/`test_say` action、`ui/panel.tsx` 最小面板已接入；surface/context/action smoke 已通过。
- **T4 补测试（下一步）**：`DetectorEngine.feed` 全链路 integration、`NekoDispatcher.build_prompt` 各事件、scenario 多 tick 序列。
- **T2 recovery 事件**：把生死级 detector 的 `wants_recovery=True`（在 `detectors/condition/flight_safety.py` 给 `stall_risk`/`low_alt_danger`）。recovery 走限流通道、低优先级、可被丢（D-B4）；intent 已在 `neko_dispatcher._RECOVERY_INTENT`。
- **T3 L8 子进程编排**：插件 `startup` 尽力 `subprocess` 拉起 `data_layer/data process/wt_server.py`（**路径含空格要加引号**，带 `--player-name`），或检测 `:8112` 已在跑；连不上降级 + `status` 提示。**只当外部进程，绝不 import 数据层。**

### 需要人/真机（Codex 做不了，等）

- **T5 三接缝验证**：见 `docs/真机验证-checklist.md`（①加载 ②字段/flag ③push 开口）。失败按 checklist 改对应单文件（`plugin.toml`/`__init__.py` · `core/flag_codes.py`/`adapters/telemetry_client.py` · `adapters/neko_dispatcher.py`）。
- **T6 M3 去桩**：等数据层补 `overspeed_warn/critical` flag + hudmsg/击杀解析 + `player_name` 注入。届时 overspeed / you_killed **无需改逻辑自动生效**（已写好），只需确认 flag 名/字段对得上。
- **T7 真机调参**：`tools/replay.py` 灌真机帧 + dry_run 决策链路，调 `plugin.toml` 阈值/冷却/grace 与 `core/flag_codes.py`。

## 7. 已知坑 / 不要重新引入（Bugbot 已修，勿回退）

逻辑（每条都有对应单测守着）：
1. **窗口 flush 必须按当前 scenario 重新门控**（`core/arbiter.py`）——缓冲期场景可能切到 DEAD/结束。
2. **COMBAT_STRESS 受创判定按"新 damage id"增量**（`core/scenario.py` 的 `_last_hud_id`）——hud_events 累积，否则永久卡死。
3. **warning→critical 升级要重发一条 critical enter**（`detectors/_base.py` ConditionDetector ACTIVE 分支）——否则收不到可抢占事件。
4. **spawn 要求 `prev.connected`**（`detectors/discrete/lifecycle.py`）——否则遥测瞬断恢复误报重生。
5. **配置重载仅 `player_name` 变才重建引擎**（`__init__._apply_config`）——否则切 dry_run 会重放 `combat.feed` 历史击杀。
6. **击杀去重用单调 `_last_id`**（`KillDetector`）——勿用 set 裁剪（非确定、可能重复）。

工程：
- 测试**不要**走 `plugin.*` 包链导入（会拉宿主重依赖如 ormsgpack）：用 `tests/conftest.py` 的 `neko_warthunder` 桩 + pytest `--import-mode=importlib`，或无依赖 `tests/run_logic_tests.py`。
- `push_message` 是**同步**的（从轮询 timer 线程直接调）；读配置用 `await self.config.dump()` 取 `["neko_warthunder"]` 段。
- **`data_layer/` 一字不改**；其 `data process` 目录带空格，**绝不当 Python 模块 import**。
- `dry_run` 默认开；真投前才关。共享态 `self.state` 用 `self._state_lock`。
