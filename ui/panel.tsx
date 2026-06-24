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
      setDryRunError("dry_run action 不可用")
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
    if (!setIdentityAction) {
      setIdentityError("set_identity action 不可用")
      return
    }
    try {
      setIdentityError("")
      const result = unwrapActionResult(await props.api.call("set_identity", { name: identityName, clear }))
      const identityResult = result.identity && typeof result.identity === "object" ? result.identity : result
      if (identityResult.ok === false) {
        setIdentityError(String(identityResult.error || "identity request failed"))
        return
      }
      if (clear) setIdentityName("")
      await props.api.refresh()
    } catch (error) {
      setIdentityError(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <Page title="战雷猫娘副驾驶" subtitle="Battle Awareness 状态面板">
      <Toolbar>
        <ToolbarGroup>
          <StatusBadge tone={state.connected ? "success" : "warning"} label={state.connected ? "已连接" : "未连接"} />
          <StatusBadge tone={safetyTone(safety.status)} label={text(safety.status)} />
          <StatusBadge tone={levelTone(state.level)} label={text(state.level)} />
        </ToolbarGroup>
        <ToolbarGroup>
          <RefreshButton label="刷新状态" />
        </ToolbarGroup>
      </Toolbar>

      <Grid cols={4}>
        <StatCard label="enabled" value={text(state.enabled)} />
        <StatCard label="dry_run" value={text(state.dry_run)} />
        <StatCard label="conn_state" value={text(state.conn_state)} />
        <StatCard label="scenario" value={text(state.scenario)} />
      </Grid>

      <Grid cols={2}>
        <Card title="运行状态">
          <KeyValue
            items={[
              { key: "enabled", label: "enabled", value: badge(state.enabled) },
              { key: "dry_run", label: "dry_run", value: badge(state.dry_run) },
              { key: "connected", label: "connected", value: badge(state.connected, "connected", "offline") },
              { key: "conn_state", label: "conn_state", value: text(state.conn_state) },
              { key: "in_battle", label: "in_battle", value: badge(state.in_battle) },
              { key: "dead", label: "dead", value: badge(state.dead) },
              { key: "domain", label: "domain", value: text(state.domain) },
              { key: "domain_label", label: "domain_label", value: text(state.domain_label) },
              { key: "vehicle_type", label: "vehicle_type", value: text(state.vehicle_type) },
              { key: "profile_source", label: "profile_source", value: text(state.profile_source) },
              { key: "profile_family", label: "profile_family", value: text(state.profile_family) },
              { key: "profile_matched", label: "profile_matched", value: badge(state.profile_matched ?? undefined) },
              { key: "scenario", label: "scenario", value: text(state.scenario) },
              { key: "level", label: "level", value: <StatusBadge tone={levelTone(state.level)} label={text(state.level)} /> },
            ]}
          />
        </Card>

        <Card title="安全状态">
          <KeyValue
            items={[
              { key: "safety.status", label: "safety.status", value: <StatusBadge tone={safetyTone(safety.status)} label={text(safety.status)} /> },
              { key: "safety.manual_paused", label: "safety.manual_paused", value: badge(safety.manual_paused) },
              { key: "safety.auto_paused", label: "safety.auto_paused", value: badge(safety.auto_paused) },
              { key: "safety.failures", label: "safety.failures", value: text(safety.failures) },
            ]}
          />
        </Card>
      </Grid>

      <Card title="身份识别">
        <Stack>
          <KeyValue
            items={[
              { key: "identity.player_name", label: "player_name", value: text(identity.player_name) },
              { key: "identity.self.name", label: "self.name", value: text(identity.self?.name) },
              { key: "identity.self.source", label: "self.source", value: text(identity.self?.source) },
              { key: "identity.self.confidence", label: "self.confidence", value: text(identity.self?.confidence) },
              { key: "identity.active_players_count", label: "active_players", value: text(identity.active_players_count) },
            ]}
          />
          <Field label="玩家名">
            <Input value={identityName} placeholder="输入你的游戏昵称" onChange={setIdentityName} />
          </Field>
          {identityError ? <Alert tone="danger">{identityError}</Alert> : null}
          <Grid cols={2}>
            <Button tone="primary" onClick={() => submitIdentity(false)}>设置玩家名</Button>
            <Button tone="warning" onClick={() => submitIdentity(true)}>清除玩家名</Button>
          </Grid>
        </Stack>
      </Card>

      <Card title="操作">
        <Stack>
          <Switch checked={!!state.dry_run} label="dry_run" onChange={setDryRun} />
          {dryRunError ? <Alert tone="danger">{dryRunError}</Alert> : null}
          <Grid cols={3}>
            <ActionButton action={pauseAction} actionId="pause" tone="danger">急停</ActionButton>
            <ActionButton action={resumeAction} actionId="resume" tone="success">恢复</ActionButton>
            <ActionButton action={testSayAction} actionId="test_say" values={{ text: "T1B 面板测试开口" }} refresh={false}>测试开口</ActionButton>
          </Grid>
        </Stack>
      </Card>
    </Page>
  )
}
