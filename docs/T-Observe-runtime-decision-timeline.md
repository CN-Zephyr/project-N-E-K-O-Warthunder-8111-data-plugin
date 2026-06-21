# T-Observe: runtime decision timeline

> 状态：设计计划 / TODO。当前不实现代码。等 M3 v1.6 DTO 适配提交后，再决定是否进入实现。

## 目标

T-Observe 用来回答真机调试时最难定位的问题：

- 为什么没播？
- 为什么晚播？
- 是 Arbiter 压住了，还是 cooldown / scenario gate / safety？
- 是 dry_run，还是 Dispatcher / push_message 失败？
- 是宿主 TTS / Realtime 链路慢，还是插件侧没有发出？

它不是新功能，不改变 Battle Awareness 语义，也不接入 kill / death / hudmsg / awards 去桩。

## 分层设计

T-Observe 分为两层：

1. Always-on minimal observability
2. Debug timeline observability

### 1. Always-on minimal observability

默认开启，极低成本。只保存最新状态，不保存高频历史。

保留内容：

- 当前状态
- 最近一次事件摘要
- 最近一次决策摘要
- 最近一次输出状态

建议结构：

```yaml
last_decision:
  ts: "2026-06-21T00:00:00Z"
  event_id: "stall_risk"
  stage: "arbiter_cooldown"
  outcome: "dropped"
  reason: "cooldown_active"
  scenario: "IN_FLIGHT"
  safety_status: "ok"
  dry_run: true
```

硬性要求：

- 只保存最新一次。
- 不记录 telemetry tick 历史。
- 不记录完整 prompt。
- 不记录 raw payload。
- 不写同步磁盘日志。
- 不做重序列化。
- 记录失败不能影响主链路。

### 2. Debug timeline observability

默认关闭，由配置控制：

```toml
observability_enabled = false
observability_max_events = 100
observability_include_prompt_preview = false
```

开启后使用内存 ring buffer，记录 runtime decision timeline。

记录范围：

- telemetry tick 摘要
- BattleEvent candidate
- Arbiter allow / drop / window / preempt / cooldown / scenario_gated
- safety block
- Dispatcher dry_run / pushed / failed
- push_message 耗时

硬性要求：

- ring buffer 只存在内存。
- 不写同步磁盘日志。
- 不记录 unsafe raw 文本。
- 不记录完整 prompt。
- `observability_include_prompt_preview=true` 时，也只能记录 safe summary 或截断后的安全预览。
- 记录失败不能影响 telemetry -> detector -> arbiter -> dispatcher 主链路。

## Timeline stage

建议使用固定 stage，方便 Hosted UI、测试和日志对齐：

| stage | 含义 |
| --- | --- |
| `telemetry_received` | 收到 telemetry tick |
| `telemetry_parsed` | 转成 BattleState |
| `detector_candidate` | Detector 产生 BattleEvent candidate |
| `detector_suppressed` | Detector 因 replay / out_of_battle / reset 等没有产出 |
| `arbiter_allowed` | Arbiter 允许事件进入输出 |
| `arbiter_dropped` | Arbiter 丢弃事件 |
| `arbiter_cooldown` | cooldown 压制 |
| `arbiter_scenario_gated` | scenario gate 压制 |
| `arbiter_preempted` | 被更高优先级事件抢占 |
| `safety_blocked` | manual pause / auto pause / safety 阻止 |
| `dispatcher_dry_run` | Dispatcher dry_run 决策完成 |
| `dispatcher_pushed` | 已调用 push_message |
| `dispatcher_failed` | Dispatcher / push_message 报错 |
| `tts_pending` | 已交给宿主或 TTS 链路，等待外部完成 |
| `tts_failed` | 可观测到 TTS / Realtime 失败时记录 |
| `completed` | 链路结束 |

## Record 字段

建议每条 timeline record 只包含 metadata：

```yaml
trace_id: "evt:123:stall_risk:enter:0"
seq: 123
ts: "2026-06-21T00:00:00Z"
stage: "arbiter_allowed"
outcome: "allowed"
reason: "selected"
event_id: "stall_risk"
edge: "enter"
scenario: "IN_FLIGHT"
priority: 8
level: "critical"
dry_run: true
in_battle: true
replay: false
cooldown_key: "stall_risk:enter"
window: "critical"
safety_status: "ok"
dispatcher_status: "pending"
message: "stall_risk enter allowed"
```

不允许记录：

- raw 玩家名
- raw hudmsg
- raw combat.feed
- raw awards
- 完整 BattleState
- 完整 prompt
- 完整 `push_message` body
- 大型 payload

## trace_id / event_id 串联

建议两层 ID：

```text
tick_trace_id = "tick:<monotonic_seq>"
event_trace_id = "evt:<tick_seq>:<event_id>:<edge>:<candidate_seq>"
```

规则：

- telemetry parse 阶段使用 `tick_trace_id`。
- 一个 tick 内产生多个 BattleEvent candidate 时，每个 candidate 派生自己的 `event_trace_id`。
- Arbiter / safety / Dispatcher / push_message 使用同一个 `event_trace_id`。
- Hosted UI 可按 `trace_id` 聚合展示一条事件链路。

## Arbiter 观测

不改变 Arbiter 决策，只在现有决策点旁路记录。

需要记录：

- allow：`arbiter_allowed`, reason=`selected`
- cooldown drop：`arbiter_cooldown`, reason=`cooldown_active`
- scenario gate：`arbiter_scenario_gated`, reason=`scenario_<name>_blocked`
- priority/window drop：`arbiter_dropped`, reason=`lower_priority` / `warning_slot_occupied` / `window_limit`
- preempt：`arbiter_preempted`, reason=`preempted_by_critical`

不允许为了观测修改 cooldown、priority、window、Scenario gate 语义。

## Dispatcher 观测

需要记录输出边界：

- dry_run：`dispatcher_dry_run`, outcome=`dry_run`, reason=`dry_run_enabled`
- push 成功：`dispatcher_pushed`, outcome=`pushed`, reason=`push_message_accepted`
- push 失败：`dispatcher_failed`, outcome=`failed`, reason=异常类型或宿主错误摘要

dry_run 和非 dry_run 应记录相同决策粒度，只在输出尾部 stage 不同。

## Hosted UI context

普通面板默认只显示：

- `connected`
- `conn_state`
- `in_battle`
- `scenario`
- `safety`
- `last_event`
- `last_decision`
- `last_output_status`

debug timeline 只在 `observability_enabled=true` 时展示。

关闭时显示：

```text
Observability disabled
```

或最近一次轻量决策摘要。

建议 context 结构：

```yaml
observe:
  enabled: false
  last_tick_at: "2026-06-21T00:00:00Z"
  last_event:
    event_id: "stall_risk"
    edge: "enter"
    level: "critical"
  last_decision:
    ts: "2026-06-21T00:00:00Z"
    event_id: "stall_risk"
    stage: "arbiter_allowed"
    outcome: "allowed"
    reason: "selected"
    scenario: "IN_FLIGHT"
    safety_status: "ok"
    dry_run: true
  last_output_status:
    stage: "dispatcher_dry_run"
    outcome: "dry_run"
    reason: "dry_run_enabled"
  recent_timeline: []
```

`recent_timeline` 只有在 debug timeline 开启时返回最近 N 条轻量记录。

## 日志策略

默认不把每个 stage 写入普通日志，避免刷屏和延迟。

允许写日志的情况：

- dispatcher failed
- push_message failed
- safety 状态切换
- observability 自身异常计数

不允许：

- 每个 telemetry tick 写日志
- 每个 timeline record 写同步文件
- 每次 record 都 JSON 序列化后落盘

## 性能约束

实现时必须满足：

- `record()` 为 O(1)。
- `record()` 不做同步磁盘 IO。
- `record()` 不做网络 IO。
- `record()` 不抛异常到主链路。
- `record()` 不保存大对象。
- `snapshot()` 返回轻量拷贝。
- Hosted UI 只读快照。
- 默认最多保存最近 N 条。

建议默认：

```text
observability_max_events = 100
```

## 测试计划

实现前先写 RED 测试。

必须覆盖：

1. Always-on minimal observability
   - 只保留最新 `last_decision`。
   - 不保存 tick 历史。
   - 不包含完整 prompt / raw payload。

2. Ring buffer
   - 超过 `observability_max_events` 后只保留最近 N 条。
   - snapshot 不暴露内部可变列表。
   - record 失败不影响主链路。

3. Detector 观测
   - 正常 flag enter 记录 `detector_candidate`。
   - `replay=true` 记录 `detector_suppressed` 或更新 last decision reason。

4. Arbiter 观测
   - allow 记录 `arbiter_allowed`。
   - cooldown drop 记录 `arbiter_cooldown`。
   - scenario gate 记录 `arbiter_scenario_gated`。
   - preempt 记录 `arbiter_preempted`。
   - window / priority drop 记录 `arbiter_dropped`。

5. Dispatcher 观测
   - dry_run 记录 `dispatcher_dry_run`。
   - push 成功记录 `dispatcher_pushed`。
   - push 失败记录 `dispatcher_failed`。

6. Hosted UI context
   - 普通模式返回最小 observe 状态。
   - debug 关闭时 `recent_timeline` 为空或不返回详细历史。
   - debug 开启时返回最近 N 条 timeline。
   - context 不包含 unsafe raw 文本。

7. T-Safety 合同
   - timeline message 不包含 raw 玩家名 / hudmsg / combat.feed / awards。
   - prompt preview 即使开启，也只能包含 safe summary。

8. 回归
   - 不影响现有逻辑测试基线。
   - M3 合并后的测试数量应在新增 T-Observe 测试后全部通过。

## 边界

- 不照搬 `neko_roast` module registry。
- 不扩 Battle Awareness 功能。
- 不改 `data_layer/`。
- 不做 recovery。
- 不做 kill / death / hudmsg / awards 去桩。
- 不做复杂 UI。
- 不写同步磁盘日志。
- 不记录 raw 玩家名 / hudmsg / combat.feed / awards 原文。

## 推荐顺序

1. 先提交 M3 v1.6 DTO 适配。
2. 再进入 T-Observe RED 测试。
3. 实现 Always-on minimal observability。
4. 实现默认关闭的 Debug timeline ring buffer。
5. 将最小 observe 状态暴露给 Hosted UI context。
6. 真机 dry_run 验证链路解释能力。
