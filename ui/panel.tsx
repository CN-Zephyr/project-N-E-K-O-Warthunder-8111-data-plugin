import {
  Page,
  Card,
  Grid,
  Stack,
  StatusBadge,
  StatCard,
  KeyValue,
  Toolbar,
  ToolbarGroup,
  Button,
  Field,
  Input,
  Switch,
  ActionButton,
  RefreshButton,
  Alert,
  useState,
} from "@neko/plugin-ui"
import type { HostedAction, PluginSurfaceProps } from "@neko/plugin-ui"

type SafetyState = {
  status?: string
  manual_paused?: boolean
  auto_paused?: boolean
  failures?: number
}

type IdentityState = {
  player_name?: string | null
  self?: {
    name?: string | null
    source?: string | null
    confidence?: number | null
  } | null
  requested?: string | null
  active_players_count?: number
  active_players?: Array<{
    display_name?: string
    name?: string
    selectable?: boolean
  }>
}

type DataLayerState = {
  mode?: string
  url?: string
  pid?: number | null
  started_by_plugin?: boolean
  auto_start?: boolean
  health?: boolean
  last_error?: string | null
}

type DashboardState = {
  enabled?: boolean
  dry_run?: boolean
  connected?: boolean
  conn_state?: string
  in_battle?: boolean
  dead?: boolean
  domain?: string
  domain_label?: string | null
  vehicle_type?: string | null
  profile_matched?: boolean | null
  profile_source?: string | null
  profile_family?: string | null
  scenario?: string
  level?: string
  identity?: IdentityState
  data_layer?: DataLayerState
  safety?: SafetyState
}

function actionById(actions: HostedAction[], id: string): HostedAction | undefined {
  return actions.find((action) => action.id === id || action.entry_id === id)
}

function text(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-"
  if (typeof value === "boolean") return value ? "是" : "否"
  return String(value)
}

function badge(value: boolean | undefined, yes = "是", no = "否") {
  return <StatusBadge tone={value ? "success" : "warning"} label={value ? yes : no} />
}

function mappedText(value: unknown, labels: Record<string, string> = {}): string {
  const raw = text(value)
  return labels[raw] || raw
}

const CONN_STATE_LABELS: Record<string, string> = {
  offline: "离线",
  not_in_battle: "未进战斗",
  in_battle: "战斗中",
}

const SCENARIO_LABELS: Record<string, string> = {
  OUT_OF_BATTLE: "战斗外",
  SPAWNING: "出生/进场",
  IN_FLIGHT: "飞行中",
  COMBAT_STRESS: "交战压力",
  CRITICAL_RISK: "危急风险",
  DEAD: "已阵亡",
  BATTLE_ENDED: "战斗结束",
}

const LEVEL_LABELS: Record<string, string> = {
  info: "正常",
  warning: "警告",
  critical: "危急",
  danger: "危险",
}

const SAFETY_LABELS: Record<string, string> = {
  running: "运行中",
  paused: "已暂停",
  auto_paused: "自动暂停",
}

const DOMAIN_LABELS: Record<string, string> = {
  air: "空战",
  heli: "直升机",
  ground: "陆战",
  naval: "海战",
  menu: "菜单",
  unknown: "未知",
}

const DATA_LAYER_LABELS: Record<string, string> = {
  managed: "插件托管",
  external: "外部运行",
  disabled: "未启用",
  unknown: "未知",
}

const IDENTITY_SOURCE_LABELS: Record<string, string> = {
  manual: "手动设置",
  auto: "自动识别",
}

function safetyTone(status: string | undefined) {
  if (status === "running") return "success"
  if (status === "paused") return "danger"
  return "warning"
}

function levelTone(level: string | undefined) {
  if (level === "critical" || level === "danger") return "danger"
  if (level === "warning") return "warning"
  return "info"
}

function unwrapActionResult(envelope: any): Record<string, any> {
  if (envelope && typeof envelope === "object") {
    if (envelope.result && typeof envelope.result === "object") return envelope.result
    return envelope
  }
  return {}
}

export default function NekoWarthunderPanel(props: PluginSurfaceProps<DashboardState>) {
  const state = props.state || {}
  const safety = state.safety || {}
  const identity = state.identity || {}
  const dataLayer = state.data_layer || {}
  const actions = Array.isArray(props.actions) ? props.actions : []
  const setDryRunAction = actionById(actions, "set_dry_run")
  const setIdentityAction = actionById(actions, "set_identity")
  const pauseAction = actionById(actions, "pause")
  const resumeAction = actionById(actions, "resume")
  const testSayAction = actionById(actions, "test_say")
  const [dryRunError, setDryRunError] = useState("")
  const [identityName, setIdentityName] = useState("")
  const [identityError, setIdentityError] = useState("")

  async function setDryRun(value: boolean) {
    if (!setDryRunAction) {
      setDryRunError("安全试运行开关不可用")
      return
    }
    try {
      setDryRunError("")
      await props.api.call("set_dry_run", { value })
      await props.api.refresh()
    } catch (error) {
      setDryRunError(error instanceof Error ? error.message : String(error))
    }
  }

  async function submitIdentity(clear = false) {
    await submitIdentityName(identityName, clear)
  }

  async function submitIdentityName(name: string, clear = false) {
    if (!setIdentityAction) {
      setIdentityError("玩家名设置不可用")
      return
    }
    try {
      setIdentityError("")
      const result = unwrapActionResult(await props.api.call("set_identity", { name, clear }))
      const identityResult = result.identity && typeof result.identity === "object" ? result.identity : result
      if (identityResult.ok === false) {
        setIdentityError(String(identityResult.error || "玩家名设置失败"))
        return
      }
      setIdentityName(clear ? "" : name)
      await props.api.refresh()
    } catch (error) {
      setIdentityError(error instanceof Error ? error.message : String(error))
    }
  }

  const activePlayers = Array.isArray(identity.active_players) ? identity.active_players : []
  const selectablePlayers = activePlayers.filter((player) => player?.selectable && player.name)

  return (
    <Page title="战雷猫娘副驾驶" subtitle="战场态势状态面板">
      <Toolbar>
        <ToolbarGroup>
          <StatusBadge tone={state.connected ? "success" : "warning"} label={state.connected ? "已连接" : "未连接"} />
          <StatusBadge tone={safetyTone(safety.status)} label={mappedText(safety.status, SAFETY_LABELS)} />
          <StatusBadge tone={levelTone(state.level)} label={mappedText(state.level, LEVEL_LABELS)} />
        </ToolbarGroup>
        <ToolbarGroup>
          <RefreshButton label="刷新状态" />
        </ToolbarGroup>
      </Toolbar>

      <Grid cols={4}>
        <StatCard label="插件启用" value={text(state.enabled)} />
        <StatCard label="安全试运行" value={text(state.dry_run)} />
        <StatCard label="连接状态" value={mappedText(state.conn_state, CONN_STATE_LABELS)} />
        <StatCard label="当前场景" value={mappedText(state.scenario, SCENARIO_LABELS)} />
        <StatCard label="数据层" value={mappedText(dataLayer.mode, DATA_LAYER_LABELS)} />
      </Grid>

      <Grid cols={2}>
        <Card title="运行状态">
          <KeyValue
            items={[
              { key: "enabled", label: "插件启用", value: badge(state.enabled) },
              { key: "dry_run", label: "安全试运行", value: badge(state.dry_run, "开启", "关闭") },
              { key: "connected", label: "数据连接", value: badge(state.connected, "已连接", "离线") },
              { key: "conn_state", label: "连接状态", value: mappedText(state.conn_state, CONN_STATE_LABELS) },
              { key: "in_battle", label: "战斗内", value: badge(state.in_battle) },
              { key: "dead", label: "阵亡状态", value: badge(state.dead) },
              { key: "domain", label: "模式", value: mappedText(state.domain, DOMAIN_LABELS) },
              { key: "domain_label", label: "模式说明", value: text(state.domain_label) },
              { key: "vehicle_type", label: "载具", value: text(state.vehicle_type) },
              { key: "profile_source", label: "数据库来源", value: text(state.profile_source) },
              { key: "profile_family", label: "载具族", value: text(state.profile_family) },
              { key: "profile_matched", label: "数据库匹配", value: badge(state.profile_matched ?? undefined) },
              { key: "scenario", label: "当前场景", value: mappedText(state.scenario, SCENARIO_LABELS) },
              { key: "level", label: "风险等级", value: <StatusBadge tone={levelTone(state.level)} label={mappedText(state.level, LEVEL_LABELS)} /> },
              { key: "data_layer.mode", label: "数据层模式", value: mappedText(dataLayer.mode, DATA_LAYER_LABELS) },
              { key: "data_layer.health", label: "数据层健康", value: badge(dataLayer.health) },
              { key: "data_layer.pid", label: "数据层 PID", value: text(dataLayer.pid) },
              { key: "data_layer.started_by_plugin", label: "由插件启动", value: badge(dataLayer.started_by_plugin) },
              { key: "data_layer.last_error", label: "最近错误", value: text(dataLayer.last_error) },
            ]}
          />
        </Card>

        <Card title="安全状态">
          <KeyValue
            items={[
              { key: "safety.status", label: "安全门状态", value: <StatusBadge tone={safetyTone(safety.status)} label={mappedText(safety.status, SAFETY_LABELS)} /> },
              { key: "safety.manual_paused", label: "手动暂停", value: badge(safety.manual_paused) },
              { key: "safety.auto_paused", label: "自动暂停", value: badge(safety.auto_paused) },
              { key: "safety.failures", label: "失败计数", value: text(safety.failures) },
            ]}
          />
        </Card>
      </Grid>

      <Card title="身份识别">
        <Stack>
          <KeyValue
            items={[
              { key: "identity.player_name", label: "手动玩家名", value: text(identity.player_name) },
              { key: "identity.self.name", label: "当前识别", value: text(identity.self?.name) },
              { key: "identity.self.source", label: "识别来源", value: mappedText(identity.self?.source, IDENTITY_SOURCE_LABELS) },
              { key: "identity.self.confidence", label: "置信度", value: text(identity.self?.confidence) },
              { key: "identity.active_players_count", label: "候选玩家数", value: text(identity.active_players_count) },
            ]}
          />
          <Field label="玩家名">
            <Input value={identityName} placeholder="输入你的游戏昵称" onChange={setIdentityName} />
          </Field>
          {selectablePlayers.length ? (
            <Grid cols={3}>
              {selectablePlayers.map((player) => (
                <Button key={player.name} onClick={() => submitIdentityName(String(player.name))}>
                  {text(player.display_name || player.name)}
                </Button>
              ))}
            </Grid>
          ) : null}
          {identityError ? <Alert tone="danger">{identityError}</Alert> : null}
          <Grid cols={2}>
            <Button tone="primary" onClick={() => submitIdentity(false)}>设置玩家名</Button>
            <Button tone="warning" onClick={() => submitIdentity(true)}>清除玩家名</Button>
          </Grid>
        </Stack>
      </Card>

      <Card title="操作">
        <Stack>
          <Switch checked={!!state.dry_run} label="安全试运行 dry_run" onChange={setDryRun} />
          {dryRunError ? <Alert tone="danger">{dryRunError}</Alert> : null}
          <Grid cols={3}>
            <ActionButton action={pauseAction} actionId="pause" tone="danger">急停</ActionButton>
            <ActionButton action={resumeAction} actionId="resume" tone="success">恢复</ActionButton>
            <ActionButton action={testSayAction} actionId="test_say" values={{ text: "副驾驶面板测试开口" }} refresh={false}>测试开口</ActionButton>
          </Grid>
        </Stack>
      </Card>
    </Page>
  )
}
