# D-B5｜事件 → 输入字段需求清单（v1 · RB 空战）

> 状态：v0.2（汇合后已重画边界）· 范围：v1 RB 空战，不含陆战/海战，不碰 map/PNG
> 用途：① 事件 → 数据层来源(flag/字段) 映射；② DTO 直接采用数据层接口文档
> 关联：数据层 `../data_layer/data process/后端接口文档.md`（插件内 vendored）

## v0.2 边界更新（汇合后 · 权威，取代下方 v0.1 原始字段假设）

合作者数据层已自带"逐机阈值 → 告警 flags"（`/api/processed`，端口 `:8112`）。据此重画边界（已拍板）：

- **数据层负责**：原始事实（`/api/state`、`/api/indicators`）+ 逐机阈值判定（`/api/processed.flags`/`alerts`/`level`，两级 warning/critical）。
- **我们负责**：消费其 flags 作为"条件已成立"信号，只做 边沿 / debounce / 迟滞 / re-arm / cooldown / Scenario 门控 / 仲裁 / 提示意图。
- **DTO 不再自定义**：直接采用数据层 `/api/telemetry` 结构（见其 `后端接口文档.md`）。下方 §1~§7 的"原始字段需求"**降级为参考**（仅用于校验数据层字段是否齐全）。

### 事件 → 数据层来源 映射（v1，9 个事件）

| 我们的事件 | 数据层来源 | 我们做什么 | payload 取值 |
|---|---|---|---|
| `stall_risk` | flags `stall_warning`/`stall_critical`（OR `aoa_high`/`aoa_critical`） | 边沿+debounce+迟滞+cooldown | ias_kmh, aoa_deg, altitude_m |
| `overspeed` | flags `overspeed_warn` / `overspeed_critical`（数据层 v1.6 已提供，插件侧待验证） | 同上 | ias_kmh, mach |
| `overheat` | flags `engine_overheat`/`engine_overheat_critical`（OR `oil_overheat*`） | 同上（不抢占） | water/head/turbine/oil temp_c |
| `low_fuel` | flags `fuel_low`/`fuel_critical` | 同上（仅 IN_FLIGHT） | fuel_fraction, fuel_remaining_sec |
| `low_alt_danger` | flags `altitude_low`/`altitude_critical`（MSL 非 AGL） | 同上 | altitude_m, climb_ms |
| `spawn` | `state` not_in_battle→in_battle / 新 `vehicle_type` | 边沿一次 | vehicle_type |
| `you_died` | `hud_events`(damage 关于我) + `state` 跳变 + `mission_status` | 双路合一去重 | cause |
| `you_killed` | `combat.feed`(is_kill, killer==player_name) | 新 id + 多杀合并 | victim, victim_vehicle |
| `battle_end` | `mission_status` / `state` | 边沿一次 | result, my{kills,deaths} |

### 本次拍板
- **overspeed → 合作者补进 `vehicle_profiles`**（never-exceed 逐机），我们消费其 flag。
- **steep_dive → v1 删除**（与 low_alt/overspeed 重叠、最弱、数据层也没做；留 v2）。

### 给合作者的 TODO（汇合产出）
- `overspeed_warn` / `overspeed_critical` 已由数据层 v1.6 提供；插件侧下一步是验证字段名、触发节奏和 Arbiter 优先级。
- 完成 hudmsg/击杀解析（其待办：击杀/起火/重创/油温/非对称襟翼），保证 `combat.feed` 与 damage 流稳定——我们的 `you_killed/you_died` 依赖它。
- 确认 `player_name` 注入方式（我们靠它判"关于我"）。

### 待你确认
- **两级 severity**：数据层已给 warning/critical 两级。建议顺势采用两级（critical→高 severity+可抢占；warning→中 severity），**推翻早期"v1 单级"暂定**。待你点头。

---

## v1 核心原则

v1 的核心**不是“敌情感知”**，而是先做 **飞行安全 + 发动机状态 + 生命周期 + hudmsg 离散事件**。

v1 事件范围（10 个）：低速/失速、超速、过热、低油、低空危险、高速俯冲、出生、死亡、击杀、战斗结束。

“敌机接近”“被敌机尾随”留到 v2，等决定是否纳入 map 数据后再做。

## 0. 关键决策（已确认）

1. **“敌机接近 / 被敌机尾随”从 v1 砍掉，标记 v2。** 二者依赖 `/map_obj.json` + `/map_info.json`，而 v1 不碰 map；`/state`、`/indicators`、`/hudmsg` 无替代字段。硬做只会得到高误判的假功能。见第 5 节。
2. **`/mission.json` 纳入必需采集集合。** 生命周期事件只靠 `/state.valid` 翻转太不稳，battle_end / spawn / death 需要 mission 作为交叉确认。

## 1. 字段来源约定（键名均待抓包确认）

- 运动学（高度/空速/马赫/迎角/G/垂速）：以 `/state` 为准（键带单位、语义清晰）。
- 载具身份/航向：`/indicators`（`type` / `army` / `compass`）。
- 姿态（俯仰/横滚）：`/indicators`（`tangage` / `bank`）。
- 发动机温度/油量/油门：`/state`（`water temp 1, C` 等）。
- 战斗文本事件：`/hudmsg`（`damage[]` / `events[]`）。
- 生命周期：`/state.valid` + `/indicators.type` + `/mission.json`。
- `/state` 与 `/indicators` 字段重叠（都有速度/高度/温度）：D-A5 反推时须为每个信号指定**唯一权威端点**，不要两头取。

---

## 2. A 组 · 连续派生事件（StateEvaluator 产出）

### A1 低速 / 接近失速 `stall_risk`
- 类型：连续派生
- 必须字段：`IAS, km/h`、`AoA, deg`（均 `/state`）
- 推荐字段：`H, m`、`Vy, m/s`、`Ny`、`flaps, %`、`gear, %`、`throttle 1, %`
- 缺字段降级：无 `AoA` → 用 `IAS`+`Vy`（下沉）+高油门粗判（误判↑）；无 `IAS` → 砍
- 抓包要求：“接近失速”持续若干秒多帧采样，记录进入瞬间；同时采降落进近样本作为反例；标注载具
- 误判风险：高——失速速度逐机不同；`AoA` 单帧抖动需 debounce；降落低速属正常

### A2 超速 `overspeed`
- 类型：连续派生
- 必须字段：`IAS, km/h`（`/state`）
- 推荐字段：`M`、`TAS, km/h`、`H, m`、`flaps, %`、`gear, %`（放襟翼/起落架时超速更易撕裂）
- 缺字段降级：有 `IAS` 即可粗做；无 `IAS` → 砍
- 抓包要求：高速平飞 + 俯冲增速样本各采；标注是否喷气
- 误判风险：中——never-exceed 逐机不同，喷气/螺旋桨阈值差异大

### A3 发动机过热 `overheat`
- 类型：连续派生
- 必须字段：`water temp 1, C` 或 `oil temp 1, C`（`/state`；喷气可能是 `head temp, C`）
- 推荐字段：`throttle 1, %`、`RPM 1`、多发各缸温度、温度时间趋势（持续 N 秒）
- 缺字段降级：有任一温度即可；全无 → 砍
- 抓包要求：分别采液冷/气冷/喷气三类样本，确认温度字段名与数量（多发有 ` 1`/` 2` 后缀）
- 误判风险：中——红线逐机不同；不同发动机看不同温度字段

### A4 低油 `low_fuel`
- 类型：连续派生
- 必须字段：`Mfuel, kg` + `Mfuel0, kg`（`/state`，算 fuel_frac）
- 推荐字段：耗油速率（历史差分）、滞空时间
- 缺字段降级：有 `Mfuel` 无 `Mfuel0` → 只能用绝对值粗判（差）；两者齐备最好
- 抓包要求：记录满油与低油两帧，确认两个字段都在
- 误判风险：低——量较确定；“多少算低”是产品口味，非数据问题

### A5 低空危险 `low_alt_danger`
- 类型：连续派生
- 必须字段：`H, m`、`Vy, m/s`（`/state`，负=下降）
- 推荐字段：`IAS, km/h`、`tangage`（俯仰）、`AoA, deg`、`gear, %`（降落低空属正常）
- 缺字段降级：有 `H`+`Vy` 即可；只有 `H` → 用历史差分算下降率（更糙）
- 抓包要求：低空掠地 + 正常降落进近样本各采
- 误判风险：高且结构性——`/state.H` 是**海拔高度，不是离地高度（AGL）**；地形起伏会致误判，8111 不提供 AGL。D-B2 须限定它只在“高 + 大下沉率”组合下触发，并接受山区误判

### A6 高速俯冲 `steep_dive`
- 类型：连续派生
- 必须字段：`Vy, m/s`（大负值）、`IAS, km/h`（上升中）（`/state`）
- 推荐字段：`tangage`（俯仰）、`M`、`H, m`
- 缺字段降级：有 `Vy`+`IAS` 即可
- 抓包要求：采一段完整俯冲（进入→拉起）多帧
- 误判风险：中 + 重叠——俯冲是战术常态，不该次次报；与 A2 超速 / A5 低空高度重叠。D-B2 须决定“合并成一个‘危险俯冲’事件，还是三者分立 + 去重”，否则一次俯冲会同时炸出三条

---

## 3. B 组 · hudmsg 离散事件

> 共同最大难点：**“这条消息是不是关于我”**。8111 不直接给玩家自己的昵称，只能靠玩家配置的名字 + 文本匹配。这是 B 组所有事件的头号误判源，必须作为 D-A4 的核心交付。

### B1 击杀 `you_killed`
- 类型：hudmsg 离散
- 必须字段：`/hudmsg` `damage[].msg`（含 "shot down" / "destroyed"）+ 玩家自我身份（名字）
- 推荐字段：`damage[].sender`/`enemy`/`mode`/`time`、被击杀方载具名
- 缺字段降级：不可降级——无 hudmsg 即无此事件
- 抓包要求：采多条真实击杀文本（含助攻 assist、多语言客户端各一份），记录玩家自己昵称；实测 `lastDmg` 增量游标 + 新对局 id 是否归零
- 误判风险：高——文本解析 + 身份匹配 + 击杀/助攻区分 + 重名 + 多语言

### B2 被击落 / 死亡 `you_died`（hudmsg 路径）
- 类型：hudmsg 离散（与 C 组交叉）
- 必须字段：`/hudmsg` `damage[].msg`（你被 "shot down" / "has crashed"）+ 自我身份
- 推荐字段：与 `/state.valid` 翻转、`/mission.json` 交叉确认（多路确认降误判）
- 缺字段降级：hudmsg 不可靠时 → 用 `valid` true→false 兜底（valid 翻转原因多，见 C3）
- 抓包要求：采“被击落”和“自己坠机”两类文本
- 误判风险：中-高——身份匹配 + 与“离场/切观战”混淆

---

## 4. C 组 · 生命周期事件

### C1 出生 / 进入战斗 `spawn`
- 类型：生命周期
- 必须字段：`/state.valid` false→true、`/indicators.type`（载具出现/变化）、`/mission.json` 状态
- 推荐字段：`/indicators.army`
- 缺字段降级：无 mission 时仅用 `valid` 翻转可粗做（区分能力下降）
- 抓包要求：采“加载完成入场”“死亡后重生”“中途换载具”三种过渡的连续帧 + 对应 mission.json
- 误判风险：中——加载/换机/重生都触发 valid 或 type 变化，需组合 mission 区分

### C2 战斗结束 `battle_end`
- 类型：生命周期 / hudmsg events
- 必须字段：`/mission.json` status（win/fail/left）或 `/hudmsg` `events[]`（对局结束）
- 推荐字段：结算/胜负信息
- 缺字段降级：无 mission → 用 `valid` 长时间 false + 无在战 兜底（糙）
- 抓包要求：采一局完整结束（胜/负各一）的 mission.json 与 hudmsg events
- 误判风险：中——区分“这局结束”vs“我死了但局还在”

### C3 死亡（valid 路径）`you_died_state`
- 类型：生命周期（与 B2 互为备份）
- 必须字段：`/state.valid` true→false
- 推荐字段：hudmsg 交叉确认、`/mission.json`（是否仍在对局）
- 缺字段降级：本身就是降级路径
- 抓包要求：采“被击落瞬间”“主动离场”“切观战”三种 valid 翻转，确认能否区分
- 误判风险：高——valid 变 false 的原因不止死亡，须靠 mission/hudmsg 交叉确认

---

## 5. D 组 · v2 延后（依赖已排除的 map 数据，v1 不做）

### D1 敌机接近 `enemy_nearby` — v2
- 需要：`/map_obj.json`（敌我归一化坐标）+ `/map_info.json`（距离换算）。`/state`/`/indicators`/`/hudmsg` 无替代字段。
- 结论：与 v1“不碰 map”范围冲突 → 延后 v2。

### D2 被敌机尾随 `being_tailed` — v2
- 需要：敌我相对位置 + 速度矢量 + 持续性 → map 数据。即便有 map，误判率也极高，本就 v2+。
- 结论：延后 v2。

---

## 6. 给合作者的采集清单（字段并集 = 直接照此抓）

- `/state` 必采键（待确认）：`valid`、`H, m`、`IAS, km/h`、`TAS, km/h`、`M`、`AoA, deg`、`Ny`、`Vy, m/s`、`Mfuel, kg`、`Mfuel0, kg`、`water temp 1, C`、`oil temp 1, C`、`head temp, C`、`throttle 1, %`、`RPM 1`、`flaps, %`、`gear, %`（多发注意 ` 2`/` 3` 后缀）
- `/indicators` 必采键：`valid`、`type`、`army`、`compass`、`tangage`、`bank`、`speed`（与 state 对比取舍）
- `/hudmsg`：`damage[]`（全字段 `id/msg/sender/enemy/mode/time`）、`events[]`；实测 `lastEvt/lastDmg` 增量 + 新对局归零
- `/mission.json`：必采（C 组生命周期交叉确认）
- 玩家自我身份：务必记录“如何拿到玩家自己昵称”（D-A4 核心）
- 分载具类型各采一套：液冷螺旋桨 / 气冷螺旋桨 / 喷气（温度与发动机字段差异大）

## 7. 反推 DTO 的提示

- 上述“必须字段”的并集 = `TelemetrySnapshot` 的最小事实字段集候选。
- A 组全部是派生，**不进** `TelemetrySnapshot`（只进 BattleState / BattleEvent）。
- 待 D-A5 解决：① `/state` vs `/indicators` 重叠信号指定唯一权威端点；② 多发/机型字段差异 → snapshot 用“发动机数组”还是“固定 ` 1`”要定型。
