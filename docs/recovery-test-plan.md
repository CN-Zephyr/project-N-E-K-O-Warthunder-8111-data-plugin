# Recovery 测试方案（暂缓实现）

> 状态：只记录未来实现前的测试清单。当前不实现 recovery，不打开 `wants_recovery`，不新增 BattleEvent / Detector / Arbiter 功能。

## 0. 目标与边界

目标：如果未来加入 recovery，先用测试锁住 Detector / Arbiter / Scenario / Dispatcher 的语义，避免 recovery 破坏现有 Battle Awareness 主链路。

建议事件形状：

```text
BattleEvent(event_id="stall_risk", edge="recovery")
BattleEvent(event_id="low_alt_danger", edge="recovery")
```

不建议新增 `stall_risk_recovered` / `low_alt_danger_recovered` 这类独立 event_id。recovery 应该是同一事件的 `edge`，但 Arbiter 必须给 recovery 单独的低优先级、非抢占、可丢弃策略。

当前结论：

- v1 可考虑 `stall_risk` recovery。
- v1 可考虑 `low_alt_danger` recovery。
- v1 不建议 `overheat` recovery。
- v1 不建议 `overspeed` recovery。
- v1 不建议 `low_fuel` recovery。
- recovery 实现应等真机 flag 退出稳定性样本回来后再做。

## 1. Detector 层测试

### 1.1 `stall_risk` enter 后满足 `confirm_exit` 产 recovery

前置：未来实现时仅对 `stall_risk` detector 打开 `wants_recovery=True`。

输入序列：

```text
tick1 flags={"stall_warning": true}
tick2 flags={"stall_warning": true}
tick3 flags={"stall_warning": true}
tick4 flags={}
tick5 flags={}
tick6 flags={}
```

期望输出：

```text
tick1: None
tick2: BattleEvent(event_id="stall_risk", edge="enter", level="warning")
tick3: None
tick4: None
tick5: None
tick6: BattleEvent(event_id="stall_risk", edge="recovery", level="warning")
```

覆盖点：

- enter 仍由 `confirm_enter=2` 控制。
- active 期间不重复 enter。
- exit 需要连续满足 `confirm_exit=3`。
- recovery 只在回到 ARMED 时产生一次。

### 1.2 `low_alt_danger` enter 后满足 `confirm_exit` 产 recovery

前置：未来实现时仅对 `low_alt_danger` detector 打开 `wants_recovery=True`。

输入序列：

```text
tick1 flags={"altitude_critical": true}
tick2 flags={"altitude_critical": true}
tick3 flags={}
tick4 flags={}
```

期望输出：

```text
tick1: None
tick2: BattleEvent(event_id="low_alt_danger", edge="enter", level="critical")
tick3: None
tick4: BattleEvent(event_id="low_alt_danger", edge="recovery", level="warning")
```

覆盖点：

- enter level 仍反映进入时的 critical。
- recovery level 固定为 warning。
- `confirm_exit=2` 满足前不产 recovery。

### 1.3 flag 抖动时不频繁产 recovery

输入序列：

```text
tick1 flags={"stall_warning": true}
tick2 flags={"stall_warning": true}    -> enter
tick3 flags={}
tick4 flags={"stall_warning": true}
tick5 flags={}
tick6 flags={"stall_warning": true}
tick7 flags={}
tick8 flags={}
tick9 flags={}
```

期望输出：

```text
tick2: BattleEvent(event_id="stall_risk", edge="enter")
tick3-tick8: None
tick9: BattleEvent(event_id="stall_risk", edge="recovery")
```

覆盖点：

- false tick 被 true tick 打断时，退出确认计数重置。
- 抖动期间不应反复 recovery。
- 一次持续危险解除最多产一个 recovery。

### 1.4 `overheat` 不产 recovery

输入序列：

```text
tick1 flags={"engine_overheat": true}
tick2 flags={"engine_overheat": true}
tick3 flags={"engine_overheat": true}  -> enter
tick4 flags={}
tick5 flags={}
tick6 flags={}
tick7 flags={}
```

期望输出：

```text
tick3: BattleEvent(event_id="overheat", edge="enter")
tick4-tick7: None
```

覆盖点：

- overheat 退出只 re-arm。
- 不产生 `BattleEvent(event_id="overheat", edge="recovery")`。

### 1.5 `overspeed` 不产 recovery

输入序列：

```text
tick1 flags={"overspeed_warning": true} 或 {"overspeed_critical": true}
tick2 flags={"overspeed_warning": true} 或 {"overspeed_critical": true}
tick3 flags={}
tick4 flags={}
tick5 flags={}
```

期望输出：

```text
enter 是否产出取决于未来数据层 flag 是否到位。
exit 阶段不产 BattleEvent(event_id="overspeed", edge="recovery")。
```

覆盖点：

- overspeed 仍是数据层 blocker。
- 即使未来 flag 到位，v1 recovery 默认不开。

### 1.6 `low_fuel` 不产 recovery

输入序列：

```text
tick1 flags={"fuel_low": true}          -> enter
tick2 flags={}
tick3 flags={}
```

期望输出：

```text
tick1: BattleEvent(event_id="low_fuel", edge="enter")
tick2-tick3: None
```

覆盖点：

- 低油恢复不是 v1 语义事件。
- 不因 fuel flag 消失触发安抚。

## 2. Arbiter 层测试

### 2.1 recovery 不允许抢占 critical enter

输入：

```text
scenario=CRITICAL_RISK
candidates=[
  BattleEvent(event_id="stall_risk", edge="recovery"),
  BattleEvent(event_id="low_alt_danger", edge="enter", level="critical"),
]
```

期望：

- 输出 `low_alt_danger enter`。
- `stall_risk recovery` 被丢弃或输给 preempt。
- recovery 不进入 critical preempt 通道。

### 2.2 recovery priority 低于新的 warning / critical

输入：

```text
scenario=IN_FLIGHT
candidates=[
  BattleEvent(event_id="stall_risk", edge="recovery"),
  BattleEvent(event_id="overheat", edge="enter", level="warning"),
]
```

期望：

- `overheat enter` 优先于 recovery。
- 如果处于 rate limit 窗口，窗口里保留 `overheat enter`，而不是 recovery。

### 2.3 recovery 不继承 enter 的高 priority

输入：

```text
scenario=IN_FLIGHT
candidates=[
  BattleEvent(event_id="low_alt_danger", edge="recovery"),
  BattleEvent(event_id="low_fuel", edge="enter", level="warning"),
]
```

期望：

- `low_fuel enter` 优先于 `low_alt_danger recovery`。
- 该测试应防止 recovery 继承 `low_alt_danger` 的 priority 9。

### 2.4 recovery 使用独立 cooldown key

建议 cooldown key：

```text
f"{event_id}:{edge}"
```

输入序列：

```text
t=1000 output BattleEvent(event_id="stall_risk", edge="enter")
t=1005 candidate BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- recovery 不被 `stall_risk enter` 的 cooldown 直接丢弃。
- 是否最终输出由 scenario / rate limit / priority 决定。

### 2.5 enter 和 recovery 不互相 cooldown 影响

输入序列：

```text
t=1000 output BattleEvent(event_id="stall_risk", edge="recovery")
t=1003 candidate BattleEvent(event_id="stall_risk", edge="enter", level="critical")
```

期望：

- 新的 `stall_risk enter critical` 不被 recovery cooldown 影响。
- 如果 scenario 允许且 critical cooldown 允许，应可进入 preempt。

### 2.6 多个 recovery 同窗最多一条

输入：

```text
scenario=IN_FLIGHT
candidates=[
  BattleEvent(event_id="stall_risk", edge="recovery"),
  BattleEvent(event_id="low_alt_danger", edge="recovery"),
]
```

期望：

- 至多输出或缓存一条 recovery。
- 另一条被窗口择优丢弃。
- 决策链路必须记录丢弃原因。

### 2.7 recovery 在 warning 单槽窗口中排队或丢弃

输入序列：

```text
t=1000 output BattleEvent(event_id="overheat", edge="enter")
t=1003 candidate BattleEvent(event_id="stall_risk", edge="recovery")       -> rate limited
t=1004 candidate BattleEvent(event_id="you_killed", edge="enter")          -> higher priority
t=1013 flush window
```

期望：

- recovery 可进入普通限流窗口，但必须可被更高优先级 warning / combat / lifecycle 替换。
- flush 时仍要按当前 scenario 重新门控。
- 输出最多一条。

## 3. Scenario 门控测试

### 3.1 `IN_FLIGHT` 允许 recovery

输入：

```text
scenario=IN_FLIGHT
candidate=BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- 通过 scenario gate。
- 是否输出由 Arbiter 的 cooldown / rate limit / priority 决定。

### 3.2 `COMBAT_STRESS` 允许但降低优先级

输入：

```text
scenario=COMBAT_STRESS
candidates=[
  BattleEvent(event_id="stall_risk", edge="recovery"),
  BattleEvent(event_id="you_killed", edge="enter"),
]
```

期望：

- recovery 可通过 scenario gate。
- `you_killed enter` 优先于 recovery。
- 如果 recovery 在真机里噪音偏大，可改为 COMBAT_STRESS 下直接抑制。

### 3.3 `CRITICAL_RISK` 下被新的 critical enter 压掉

输入：

```text
scenario=CRITICAL_RISK
candidates=[
  BattleEvent(event_id="stall_risk", edge="recovery"),
  BattleEvent(event_id="low_alt_danger", edge="enter", level="critical"),
]
```

期望：

- 输出 critical enter。
- recovery 不抢占、不补播。

### 3.4 `SPAWNING` 抑制 recovery

输入：

```text
scenario=SPAWNING
candidate=BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- 被 `scenario_gated(SPAWNING)` 丢弃。

### 3.5 `DEAD` 抑制 recovery

输入：

```text
scenario=DEAD
candidate=BattleEvent(event_id="low_alt_danger", edge="recovery")
```

期望：

- 被 `scenario_gated(DEAD)` 丢弃。
- 死亡安慰不应被危险解除提示打断。

### 3.6 `BATTLE_ENDED` 抑制 recovery

输入：

```text
scenario=BATTLE_ENDED
candidate=BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- 被 `scenario_gated(BATTLE_ENDED)` 丢弃。

### 3.7 `OUT_OF_BATTLE` 抑制 recovery

输入：

```text
scenario=OUT_OF_BATTLE
candidate=BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- 被 `scenario_gated(OUT_OF_BATTLE)` 丢弃。

## 4. Dispatcher 测试

### 4.1 recovery prompt 使用 `_RECOVERY_INTENT`

输入：

```text
BattleEvent(event_id="stall_risk", edge="recovery")
```

期望：

- prompt 使用 recovery 安抚语义。
- prompt 包含 `{MASTER_NAME}` 占位。

### 4.2 recovery 不复用危险进入提示

输入：

```text
BattleEvent(event_id="low_alt_danger", edge="recovery")
```

期望：

- 不出现“立刻拉起”“濒临失速”“收油门改出”等 enter 提示。
- 不把 recovery 写成新的危险告警。

### 4.3 recovery payload 只包含必要事实

输入：

```text
BattleEvent(
  event_id="stall_risk",
  edge="recovery",
  payload={"ias_kmh": 260, "aoa_deg": 8, "altitude_m": 1200},
)
```

期望：

- prompt 可以带少量事实，但不应重复播报大量数字。
- 推荐只表达“刚才危险解除 / 稳住了”。

### 4.4 dry_run 下能记录 recovery 决策链路

输入：

```text
BattleEvent(event_id="stall_risk", edge="recovery")
dry_run=True
```

期望：

- dry_run 摘要或决策链路中出现 `edge=recovery`。
- 能看到 scenario gate / cooldown / window / dropped / spoken 原因。

## 5. Integration 测试

### 5.1 完整 recovery 序列

输入序列：

```text
t=1000 flags={}
t=1001 flags={"stall_warning": true}
t=1002 flags={"stall_warning": true}
t=1003 flags={"stall_warning": true}
t=1004 flags={}
t=1005 flags={}
t=1006 flags={}
```

期望链路：

```text
t=1001 Detector: None
t=1002 Detector: stall_risk enter
t=1002 Arbiter: scenario/cooldown/priority 决定 spoken 或 dropped
t=1003 Detector: None
t=1004 Detector: None
t=1005 Detector: None
t=1006 Detector: stall_risk recovery
t=1006 Arbiter: scenario/cooldown/priority/window 决定 spoken / buffered / dropped
```

dry_run 期望：

- enter 为什么说或没说可解释。
- active 为什么不重复可解释。
- recovery 为什么说或没说可解释。
- 如果 recovery 被 cooldown、scenario、priority、window 丢弃，原因必须可见。

### 5.2 recovery 与新危险同窗

输入：

```text
same tick:
  BattleEvent(event_id="stall_risk", edge="recovery")
  BattleEvent(event_id="low_alt_danger", edge="enter", level="critical")
```

期望：

- 输出或保留新的危险 enter。
- recovery 被丢弃。
- 单次仲裁仍最多一条输出。

### 5.3 recovery 在场景切换后 flush 被重新门控

输入序列：

```text
t=1000 output warning event，占用 rate limit
t=1003 recovery 进入窗口
t=1013 scenario=DEAD 时 flush
```

期望：

- recovery flush 时被 `scenario_gated_on_flush(DEAD)` 丢弃。
- 不在 DEAD 状态补播“好险”。

## 6. 真机样本验证

未来需要采集以下 `/api/telemetry` 样本：

### 6.1 stall flag 进入 / 退出

需要样本：

- `stall_warning` 或 `stall_critical` 从 false 到 true。
- 危险解除后稳定回 false。

用途：

- 校准 `confirm_enter` / `confirm_exit`。
- 判断 recovery 是否会太晚或太早。

### 6.2 altitude critical 进入 / 退出

需要样本：

- `altitude_low` / `altitude_critical` 进入。
- 拉起后 flag 稳定退出。

用途：

- 判断低空解除是否足够稳定。
- 避免贴地飞行时 recovery 抖动。

### 6.3 flag 抖动样本

需要样本：

- stall / altitude 在临界点附近 true/false 来回跳。

用途：

- 验证 `confirm_exit` 是否能过滤抖动。
- 决定 recovery 是否需要更长 exit 确认窗口。

### 6.4 死亡前后 flag 退出样本

需要样本：

- 死亡前 active flag。
- 死亡后 telemetry flag 变 false 或断开。

用途：

- 确认 DEAD 下 recovery 必须抑制。
- 防止死亡后播“好险拉回来了”。

### 6.5 出生 grace 期间 flag 变化样本

需要样本：

- 刚出生 / 刚进场时 stall / altitude flag 的变化。

用途：

- 确认 SPAWNING 下 recovery 被抑制。
- 避免出生瞬间噪音。

## 7. 实现前测试优先级

必须先写：

- Detector: `stall_risk` recovery 产出。
- Detector: `low_alt_danger` recovery 产出。
- Detector: flag 抖动不重复 recovery。
- Detector: `overheat` / `overspeed` / `low_fuel` 不产 recovery。
- Arbiter: recovery 不抢占。
- Arbiter: recovery 不继承 enter 高 priority。
- Arbiter: enter 与 recovery 不互相 cooldown。
- Scenario: SPAWNING / DEAD / BATTLE_ENDED / OUT_OF_BATTLE 抑制 recovery。
- Dispatcher: recovery prompt 使用 `_RECOVERY_INTENT`，不复用 enter 危险提示。

可以实现后补：

- 多个 recovery 同窗择优细节。
- COMBAT_STRESS 下 recovery 是否允许的节奏校准。
- 真机样本回归。
- dry_run 文案细节断言。

## 8. 当前决策

- 当前只记录 TODO。
- 暂不实现 recovery。
- 暂不打开 `wants_recovery`。
- 暂不新增 BattleEvent / Detector / Arbiter 功能。
- 等真机 / 数据层 flag 退出稳定性样本回来后，再决定是否进入 recovery 实现。
