# Project Status

## Current State

- M1 scaffold and M2 understanding/decision logic are implemented.
- Battle Awareness main chain is implemented.
- Hosted UI Integration is complete.
- Minimal Panel is complete.
- T4 integration tests are complete.
- `T-Safety: output text sanitizer` is complete.
- `T-FreeText-Gate: free-text release gate` is complete. `tools/free_text_gate.py` is now part of offline preflight and proves synthetic hudmsg / combat.feed / awards / player-name payloads do not leak raw text into prompts or `push_message.parts[].text`; those paths remain dry-run-only until live safety validation passes.
- `T-Replay-Gate: replay degrade release gate` is complete. `tools/replay_gate.py` is now part of offline preflight and proves synthetic `replay=true` frames with critical flags, owned combat.feed, HUD notices, and awards do not emit Detector candidates, prompts, or `push_message` output.
- `V2 Proximity / Objective Awareness` is implemented for the non-live scope. The plugin now consumes data-layer `proximity.events` / `situation`, emits safe generic `enemy_nearby`, `air_threat_nearby`, `enemy_on_six`, and `ground_target_nearby` events, gates them below critical safety events, exposes a safe Hosted UI awareness summary, and validates the path with `tools/proximity_gate.py`.
- `T-Release-Readiness: v1 RC offline gate aggregator` is complete. `tools/release_readiness.py` runs deterministic no-host checks and reports whether the branch is ready for the final live smoke.
- `T-Observe: runtime decision timeline` is implemented in lightweight form: always-on last summaries plus an opt-in in-memory debug ring buffer.
- `T-Live: live monitor summary tool` is complete for safe, read-only runtime summaries during real-machine tests.
- `T-Output: output backpressure guard` is complete for real `push_message` calls. It suppresses same-or-lower-priority real pushes during `output_backpressure_seconds` while allowing higher-priority events through. Real battle-event pushes also use `coalesce_key=neko_warthunder:battle_event` so the host proactive queue can replace stale unreleased battle cues with the newest event. Events older than `output_event_max_age_seconds` are dropped before real push with `event_expired`.
- `T-Kill-Coalesce: you_killed multi-kill coalescing` is complete in lightweight form. Owned kill events are buffered for `kill_coalesce_window_seconds`, merged into one `kill_count` event, and cleared by critical preempt.
- L8 data-layer subprocess orchestration is implemented and locally verified. The plugin can auto-start vendored `wt_server.py` when `:8112` is missing, marks an already-running `:8112` as external, and only stops processes it started itself.
- L9 takeoff tuning is implemented with radio-altitude-first semantics. `radio_altitude_m` is the preferred AGL source for low-altitude/takeoff decisions; `altitude_m` is treated as MSL/field-elevation context when AGL is available.
- Takeoff/rollout protection keeps the original `takeoff_low_alt_grace_seconds=45` window and adds `takeoff_radio_altitude_enter_m=10` / `takeoff_radio_altitude_exit_m=40` hysteresis. It suppresses `low_alt_danger` during takeoff grace and also suppresses runway-roll `overspeed` while radio-altitude protection is active. Stall, overheat, low_fuel, and death events are not suppressed by this guard.
- Hosted UI panel has completed a first information-architecture pass: connection status, battle status, safety controls, latest decision, and latest output are grouped in Chinese.
- Logic self-check currently passes: `197/197`.
- Real-machine smoke passed on 2026-06-21 and 2026-06-23 for Hosted UI context/actions, safety pause/resume, spawn, overspeed warning/critical, low_fuel warning/critical, low-altitude warning/critical, stall warning/critical, overheat warning/critical, identity manual seam, owned kill/death ownership, you_killed / you_died Arbiter decisions, dry-run dispatcher output, and `dry_run=false` push output.
- 2026-06-23: plugin status reporting was deduped and throttled to avoid host-side `report_status` / ZMQ backpressure spam while still reporting immediately on real state changes.
- 2026-06-24 live `dry_run=false` testing showed the plugin can push events quickly while the host reply may arrive late and mix older event context. Mitigations now include plugin-side real-output backpressure, host proactive-queue coalescing via `coalesce_key`, and real-push TTL expiry; the next live test should verify they reduce stale queued replies without blocking critical interrupts.
- Default runtime mode is `dry_run = true`; the plugin runs the decision chain but does not push real catgirl speech until dry run is disabled.
- The plugin data boundary is HTTP `:8112` (`/api/telemetry`) only. L8 lifecycle code may start/stop the vendored data-layer process, but it still must not import or modify `data_layer/` code.
- Vendored data layer contract `v1.6` is merged. It includes `overspeed_warn` / `overspeed_critical`, enhanced `combat.feed`, `is_my_kill` / `is_my_death`, `/api/identity`, `replay: true` degrade mode, `hud_notices`, and `awards`.

## Ready to Hand Off

- Core contracts, scenario machine, detectors, arbiter, safety guard, dispatcher, runtime observability, tests, replay tool, and Hosted UI panel are present.
- The offline replay tool's synthetic scenario now covers v1.6 `combat.feed[].is_my_kill` / `is_my_death` kill and death events.
- `tools/sample_replay.py` now includes a safe `session_summary`, validation-check verdicts, P1/P2 `live_test_plan`, safe event display labels, `--json` output, free-text source details, V2 proximity/situation/ground-target coverage, and an offline replay contract that marks `replay=true` samples as suppressed only when candidate/chosen/output counts stay zero. `tools/offline_report.py` renders the same safe verdicts as Markdown with a Team brief, Next test focus, Operator quick checklist, and Next live-test plan, or as compact JSON for tooling. The sample, offline-report, and live-test-plan exits all include runtime output follow-ups for T-Output backpressure and T-Kill-Coalesce; `next_steps` also names those two live actions while the summary status remains based on sample/data gaps. `tools/live_test_plan.py` expands the plan into an Operator quick checklist plus concrete live-test operation steps with operation / monitor / pass / fail / data-layer-gap criteria, including `capture_ground_target_sample` when situation data exists without objective targets. `tools/live_monitor.py` prints a top-line `Summary` plus safe health/context/telemetry/log summaries, explicit free-text dry_run-only status with per-source blocked detail, replay degrade status, and Chinese actionable observe/output reasons such as `selected`, `dry_run_enabled`, `kill_coalesced`, `output_backpressure`, and `event_expired` for live validation without raw player/HUD/combat/award text. `tools/free_text_gate.py` provides a synthetic no-host release gate for free-text unstubbing. `tools/replay_gate.py` provides a synthetic no-host release gate for replay degrade safety. `tools/proximity_gate.py` provides a synthetic no-host V2 proximity/objective awareness gate. `tools/release_readiness.py` aggregates deterministic offline checks. `tools/preflight.py` dry-run output includes a Quick read for operators, and `--run --report-output <path>` can run the free-text, replay, and proximity release gates, runtime smoke, save the offline readiness report, print the operation plan, and clearly say whether to proceed with dry-run live validation or stop before real-machine testing. These paths avoid raw player/HUD/combat/award/proximity/objective text.
- Hosted UI surface, dashboard context, actions, and minimal panel have passed smoke validation.
- Design docs are complete for the current v1 scope: D-B1 through D-B5, implementation plan, data-layer TODOs, recovery test plan, and real-machine validation checklist.
- Data-layer blockers are no longer "waiting for fields"; plugin-side v1.6 DTO seams are wired, and the current work is real-machine / sample validation.

## Not Done Yet

- Real-machine `dry_run` seams are validated for numeric flight-safety basics and owned kill/death. `dry_run=false` push output is validated for `test_say`, `you_killed`, and `you_died`; additional hudmsg / awards free-text paths still need dry-run safety validation before real output.
- The later 2026-06-23 air dry-run monitor independently confirmed the `:8111` native telemetry -> `:8112` data layer -> plugin log chain for `spawn`, `stall_risk`, `low_alt_danger`, `overspeed`, owned `you_killed`, and crash-style owned `you_died`. In that boot the Hosted UI HTTP ports were not listening, so the result is counted as runtime chain evidence rather than a fresh Hosted UI smoke.
- Plugin-side M3 adaptation to data-layer `v1.6` DTO is implemented for the current v1 scope. Owned kill/death, identity, overspeed, overheat, low altitude, stall, and low_fuel have real-machine evidence; replay samples, awards/free-text paths, and oil/engine profile calibration remain open.
- `you_killed` and `you_died` now consume `combat.feed[].is_my_kill` and `combat.feed[].is_my_death`; the old `vehicle_valid` death path is not used as the main death source.
- Combat output wording is now domain-aware for generic kill/death prompts: air/heli kills use air-target wording, ground kills use ground-target destruction wording, crash/death prompts use `cause` + `domain`, and prompt facts do not repeat raw victim player names.
- `overspeed` is no longer a data-layer gap; 2026-06-23 real-machine dry-run observed `overspeed_warn` and `overspeed_critical` flowing through Detector -> Arbiter -> Dispatcher dry_run. DTO mapping should still be kept under M3 regression coverage.
- Overheat HUD-notice seam is implemented for `hud_notices.feed[].code` values `engine_overheat` and `oil_overheat`, mapped to the existing `overheat` event with safe code-only payload. 2026-06-23 real-machine dry-run observed the `overheat` event path. Oil/engine-temperature threshold precision still waits for the data-layer database/profile calibration; `powertrain_failure` is intentionally not promoted to a speech event yet, but it is now recorded as `detector_suppressed/deferred_hud_notice` in T-Observe / live monitor.
- `replay: true` telemetry is silenced at `DetectorEngine`: detectors reset, no battle events are emitted, and T-Observe records `detector_suppressed/replay` as the latest decision. `tools/live_monitor.py` now reports `replay_degrade.status`, `decision_stage` / `decision_reason`, and whether output was blocked. Real replay samples still need validation.
- `/api/identity` now has a plugin-side player-name seam through Hosted UI context/action and the minimal panel. The dashboard can show safe, selectable `combat.active_players` candidates for one-click identity selection while redacting unsafe names. 2026-06-23 real-machine testing verified the manual identity seam against `combat.self.source=manual`, observed owned `combat.feed[].is_my_kill` / `combat.feed[].is_my_death` paths in air/ground contexts, and confirmed post-fix `you_killed` plus `you_died` reach Arbiter and Dispatcher.
- T-Observe exposes `observe.last_event`, `observe.last_decision`, `observe.last_output_status`, and debug-only `recent_timeline` through Hosted UI context. 2026-06-23 real-machine dry-run confirmed the always-on summaries explain allowed, preempted, cooldown-dropped, and dry-run dispatcher outcomes.
- T-Output adds a final dispatcher-side guard before real `push_message`: same-or-lower-priority events inside `output_backpressure_seconds` are recorded as `dispatcher_suppressed / output_backpressure`; higher-priority events can still be pushed. Pushed battle events share `coalesce_key=neko_warthunder:battle_event` so the host can collapse unreleased stale cues. Events older than `output_event_max_age_seconds` are recorded as `dispatcher_suppressed / event_expired` and are not pushed. `tools/live_monitor.py` now surfaces output backpressure and expired stale-event drops directly in the short output summary.
- Multi-kill coalescing is implemented in Arbiter for `you_killed`: short-window kills become one generic `kill_count` prompt, reducing repeated kill chatter without exposing raw player names.
- T-Safety is now in place at the NekoDispatcher / prompt-builder boundary. It blocks common hudmsg / combat.feed / awards free-text field families before prompt construction. Generic kill/death speech has passed real-machine `dry_run=false` smoke; hudmsg / awards / other free-text speech still needs real-machine dry-run validation before rollout.
- Numeric flight-safety events such as stall, low altitude, overheat, overspeed, and low_fuel are not blocked by T-Safety. 2026-06-23 air dry-run observed low_fuel warning and critical output; later low_fuel repeats could be scenario-gated under combat stress as expected.
- The 2026-06-23 live monitor exposed a data-layer map/profile polling regression where `wt_proximity` still called the old `_merge_profile()` signature. The code path is fixed with regression coverage; the next live data-layer restart should confirm the log no longer repeats.
- Data-layer subprocess orchestration is implemented for the minimal ownership contract. 2026-06-26 local self-validation confirmed managed processes are stopped on plugin shutdown, external `:8112` services are not killed, and Hosted UI/status expose `data_layer.mode`, `pid`, `started_by_plugin`, `health`, and `last_error`.
- `contract/telemetry_sample.json` now contains a sanitized v1.6-shaped telemetry sample derived from real capture structure. It intentionally excludes raw free text; live testing should place raw captures under ignored `local_samples/` and only update `contract/telemetry_sample.json` with sanitized data.
- recovery remains deferred; do not open `wants_recovery` until real-machine samples justify it.
- i18n currently has only a `zh-CN` placeholder; the current Hosted UI panel copy is Chinese-first, and full 8-locale coverage is expected if future panel copy expands beyond this plugin-local surface.

## Verification

Run the full offline gate from the standalone plugin repository root:

```powershell
uv run python tools\preflight.py --run
uv run python tools\release_readiness.py --run
```

For single-check reruns or troubleshooting:

```powershell
uv run python tests/run_logic_tests.py
uv run pytest -c tests\pytest.ini tests -q
```

Notes:

- `tools/release_readiness.py --run` is the no-host gate aggregator. It runs deterministic checks and returns `ready_for_final_live_smoke` only when the branch is ready for the final focused live smoke.
- `tools/preflight.py --run` also runs the free-text, replay, and proximity release gates, plugin check, synthetic replay, local sample replay, the offline readiness report, and the live test plan when the relevant local paths exist. Use `--report-output <path>` to save the Markdown report; parent directories are created automatically. The printed preflight plan points local sample replay users to `session_summary`, the Markdown / JSON report, and the live operation plan as review entries.
- `tests/run_logic_tests.py` is the no-host logic self-check and should report `197/197 passed`.
- The standalone pytest entry uses `tests/pytest.ini` so pytest does not import the host SDK-dependent plugin entrypoint while collecting tests.
- If an older handoff note still shows the pre-T4 test count, treat it as stale unless it explicitly refers to an older test entry point.
- The real-machine checklist is in `docs/真机验证-checklist.md`; it now includes the 2026-06-21 dry-run smoke result, the next unified live-test order, and links to the 2026-06-20 offline sample replay report in `docs/样本回放-20260620.md`.
- After each live test, record the sanitized result summary with `docs/真机测试结果-template.md`; do not commit raw player names, HUD text, combat feed text, or awards text.
- Before the next unified live test, run the offline gate in `docs/统一测试前-离线检查.md`.

## Next Recommended Work

1. In the next unified live pass, verify V2 proximity/objective awareness on real data: confirm `proximity.events` are visible, `air_threat_nearby` can be produced from air proximity, a rear / six-o'clock sample can be captured for `enemy_on_six`, and approaching an objective can produce `ground_target_nearby`. The 2026-06-20 local sample already contains 4615 proximity air events, 9970 situation frames, and 3253 ground-target items, but no rear-threat sample and no close-objective trigger sample.
2. Continue M3 seams that still need real-machine validation or samples: replay real-sample validation with the `live_monitor` `Summary` / replay degrade status, awards/free-text dry_run validation with `free_text_safety.source_details` / `FreeText detail`, oil/engine profile calibration, and the remaining failure-field strategy.
3. Run the remaining real-machine/data-layer/dry_run seams from `docs/真机验证-checklist.md`, using T-Observe to inspect `last_decision` / `last_output_status` while focusing on V2 proximity/objective awareness, replay, awards/free-text paths, oil/engine failure details after the data-layer database/profile calibration, and whether T-Output reduces stale real replies.
4. During live validation, capture a fresh real `/api/telemetry` response under ignored `local_samples/` for comparison with the sanitized `contract/telemetry_sample.json`, then summarize the result with `docs/真机测试结果-template.md`.
5. Keep kill/death generic speech enabled only through T-Safety-safe prompts; consider hudmsg/combat.feed/awards speech only after their own dry-run safety checks pass.
