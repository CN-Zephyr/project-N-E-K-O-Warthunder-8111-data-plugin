# Project Status

## Current State

- M1 scaffold and M2 understanding/decision logic are implemented.
- Battle Awareness main chain is implemented.
- Hosted UI Integration is complete.
- Minimal Panel is complete.
- T4 integration tests are complete.
- `T-Safety: output text sanitizer` is complete.
- `T-Observe: runtime decision timeline` is implemented in lightweight form: always-on last summaries plus an opt-in in-memory debug ring buffer.
- `T-Live: live monitor summary tool` is complete for safe, read-only runtime summaries during real-machine tests.
- Logic self-check currently passes: `108/108`.
- Real-machine smoke passed on 2026-06-21 and 2026-06-23 for Hosted UI context/actions, safety pause/resume, spawn, overspeed warning/critical, low_fuel warning/critical, low-altitude warning/critical, stall warning/critical, overheat warning/critical, identity manual seam, owned kill/death ownership, you_killed / you_died Arbiter decisions, dry-run dispatcher output, and `dry_run=false` push output.
- 2026-06-23: plugin status reporting was deduped and throttled to avoid host-side `report_status` / ZMQ backpressure spam while still reporting immediately on real state changes.
- Default runtime mode is `dry_run = true`; the plugin runs the decision chain but does not push real catgirl speech until dry run is disabled.
- The plugin boundary is HTTP `:8112` (`/api/telemetry`) only. It consumes the vendored data layer and must not import or modify `data_layer/` code.
- Vendored data layer contract `v1.6` is merged. It includes `overspeed_warn` / `overspeed_critical`, enhanced `combat.feed`, `is_my_kill` / `is_my_death`, `/api/identity`, `replay: true` degrade mode, `hud_notices`, and `awards`.

## Ready to Hand Off

- Core contracts, scenario machine, detectors, arbiter, safety guard, dispatcher, runtime observability, tests, replay tool, and Hosted UI panel are present.
- The offline replay tool's synthetic scenario now covers v1.6 `combat.feed[].is_my_kill` / `is_my_death` kill and death events.
- `tools/sample_replay.py` now includes a safe `session_summary`, validation-check verdicts, P1/P2 `live_test_plan`, safe event display labels, and `--json` output for offline/sample review. `tools/offline_report.py` renders the same safe verdicts as Markdown with a Team brief and Next live-test plan, or as compact JSON for tooling. `tools/live_test_plan.py` expands the plan into concrete live-test operation steps with operation / monitor / pass / fail / data-layer-gap criteria. `tools/live_monitor.py` prints a top-line `Summary` plus safe health/context/telemetry/log summaries, explicit free-text dry_run-only status with per-source blocked detail, and replay degrade status for live validation without raw player/HUD/combat/award text. `tools/preflight.py --run --report-output <path>` can save the offline readiness report and print the operation plan during the full offline gate. These paths avoid raw player/HUD/combat/award text.
- Hosted UI surface, dashboard context, actions, and minimal panel have passed smoke validation.
- Design docs are complete for the current v1 scope: D-B1 through D-B5, implementation plan, data-layer TODOs, recovery test plan, and real-machine validation checklist.
- Data-layer blockers are no longer "waiting for fields"; plugin-side v1.6 DTO seams are wired, and the current work is real-machine / sample validation.

## Not Done Yet

- Real-machine `dry_run` seams are validated for numeric flight-safety basics and owned kill/death. `dry_run=false` push output is validated for `test_say`, `you_killed`, and `you_died`; additional hudmsg / awards free-text paths still need dry-run safety validation before real output.
- The later 2026-06-23 air dry-run monitor independently confirmed the `:8111` native telemetry -> `:8112` data layer -> plugin log chain for `spawn`, `stall_risk`, `low_alt_danger`, `overspeed`, owned `you_killed`, and crash-style owned `you_died`. In that boot the Hosted UI HTTP ports were not listening, so the result is counted as runtime chain evidence rather than a fresh Hosted UI smoke.
- Plugin-side M3 adaptation to data-layer `v1.6` DTO is implemented for the current v1 scope. Owned kill/death, identity, overspeed, overheat, low altitude, stall, and low_fuel have real-machine evidence; replay samples, awards/free-text paths, and oil/engine profile calibration remain open.
- `you_killed` and `you_died` now consume `combat.feed[].is_my_kill` and `combat.feed[].is_my_death`; the old `vehicle_valid` death path is not used as the main death source.
- `overspeed` is no longer a data-layer gap; 2026-06-23 real-machine dry-run observed `overspeed_warn` and `overspeed_critical` flowing through Detector -> Arbiter -> Dispatcher dry_run. DTO mapping should still be kept under M3 regression coverage.
- Overheat HUD-notice seam is implemented for `hud_notices.feed[].code` values `engine_overheat` and `oil_overheat`, mapped to the existing `overheat` event with safe code-only payload. 2026-06-23 real-machine dry-run observed the `overheat` event path. Oil/engine-temperature threshold precision still waits for the data-layer database/profile calibration; `powertrain_failure` is intentionally not promoted to a speech event yet.
- `replay: true` telemetry is silenced at `DetectorEngine`: detectors reset, no battle events are emitted, and T-Observe records `detector_suppressed/replay` as the latest decision. `tools/live_monitor.py` now reports `replay_degrade.status`, `decision_stage` / `decision_reason`, and whether output was blocked. Real replay samples still need validation.
- `/api/identity` now has a plugin-side player-name seam through Hosted UI context/action and the minimal panel. 2026-06-23 real-machine testing verified the manual identity seam against `combat.self.source=manual`, observed owned `combat.feed[].is_my_kill` / `combat.feed[].is_my_death` paths in air/ground contexts, and confirmed post-fix `you_killed` plus `you_died` reach Arbiter and Dispatcher.
- T-Observe exposes `observe.last_event`, `observe.last_decision`, `observe.last_output_status`, and debug-only `recent_timeline` through Hosted UI context. 2026-06-23 real-machine dry-run confirmed the always-on summaries explain allowed, preempted, cooldown-dropped, and dry-run dispatcher outcomes.
- T-Safety is now in place at the NekoDispatcher / prompt-builder boundary. It blocks common hudmsg / combat.feed / awards free-text field families before prompt construction. Generic kill/death speech has passed real-machine `dry_run=false` smoke; hudmsg / awards / other free-text speech still needs real-machine dry-run validation before rollout.
- Numeric flight-safety events such as stall, low altitude, overheat, overspeed, and low_fuel are not blocked by T-Safety. 2026-06-23 air dry-run observed low_fuel warning and critical output; later low_fuel repeats could be scenario-gated under combat stress as expected.
- The 2026-06-23 live monitor exposed a data-layer map/profile polling regression where `wt_proximity` still called the old `_merge_profile()` signature. The code path is fixed with regression coverage; the next live data-layer restart should confirm the log no longer repeats.
- Data-layer subprocess orchestration is not implemented.
- `contract/telemetry_sample.json` now contains a sanitized v1.6-shaped telemetry sample derived from real capture structure. It intentionally excludes raw free text; live testing should place raw captures under ignored `local_samples/` and only update `contract/telemetry_sample.json` with sanitized data.
- recovery remains deferred; do not open `wants_recovery` until real-machine samples justify it.
- i18n currently has only a `zh-CN` placeholder; full 8-locale coverage is expected when future panel copy expands.

## Verification

Run the full offline gate from the standalone plugin repository root:

```powershell
uv run python tools\preflight.py --run
```

For single-check reruns or troubleshooting:

```powershell
uv run python tests/run_logic_tests.py
uv run pytest -c tests\pytest.ini tests -q
```

Notes:

- `tools/preflight.py --run` also runs plugin check, synthetic replay, local sample replay, the offline readiness report, and the live test plan when the relevant local paths exist. Use `--report-output <path>` to save the Markdown report; parent directories are created automatically. The printed preflight plan points local sample replay users to `session_summary`, the Markdown / JSON report, and the live operation plan as review entries.
- `tests/run_logic_tests.py` is the no-host logic self-check and should report `108/108 passed`.
- The standalone pytest entry uses `tests/pytest.ini` so pytest does not import the host SDK-dependent plugin entrypoint while collecting tests.
- If an older handoff note still shows the pre-T4 test count, treat it as stale unless it explicitly refers to an older test entry point.
- The real-machine checklist is in `docs/真机验证-checklist.md`; it now includes the 2026-06-21 dry-run smoke result, the next unified live-test order, and links to the 2026-06-20 offline sample replay report in `docs/样本回放-20260620.md`.
- After each live test, record the sanitized result summary with `docs/真机测试结果-template.md`; do not commit raw player names, HUD text, combat feed text, or awards text.
- Before the next unified live test, run the offline gate in `docs/统一测试前-离线检查.md`.

## Next Recommended Work

1. Continue M3 seams that still need real-machine validation or samples: replay real-sample validation with the `live_monitor` `Summary` / replay degrade status, awards/free-text dry_run validation with `free_text_safety.source_details` / `FreeText detail`, and the remaining failure-field strategy.
2. Run the remaining real-machine/data-layer/dry_run seams from `docs/真机验证-checklist.md`, using T-Observe to inspect `last_decision` / `last_output_status` while focusing on replay, awards/free-text paths, and oil/engine failure details after the data-layer database/profile calibration.
3. During live validation, capture a fresh real `/api/telemetry` response under ignored `local_samples/` for comparison with the sanitized `contract/telemetry_sample.json`, then summarize the result with `docs/真机测试结果-template.md`.
4. Keep kill/death generic speech enabled only through T-Safety-safe prompts; consider hudmsg/combat.feed/awards speech only after their own dry-run safety checks pass.
5. Keep T3/L8 data-layer subprocess orchestration for a later runtime pass.
