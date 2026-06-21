# Project Status

## Current State

- M1 scaffold and M2 understanding/decision logic are implemented.
- Battle Awareness main chain is implemented.
- Hosted UI Integration is complete.
- Minimal Panel is complete.
- T4 integration tests are complete.
- `T-Safety: output text sanitizer` is complete.
- Logic self-check currently passes: `62/62`.
- Real-machine `dry_run` smoke passed on 2026-06-21 for Hosted UI context/actions, safety pause/resume, stall/low-altitude decision flow, and dry-run dispatcher output.
- Default runtime mode is `dry_run = true`; the plugin runs the decision chain but does not push real catgirl speech until dry run is disabled.
- The plugin boundary is HTTP `:8112` (`/api/telemetry`) only. It consumes the vendored data layer and must not import or modify `data_layer/` code.
- Vendored data layer contract `v1.6` is merged. It includes `overspeed_warn` / `overspeed_critical`, enhanced `combat.feed`, `is_my_kill` / `is_my_death`, `/api/identity`, `replay: true` degrade mode, `hud_notices`, and `awards`.

## Ready to Hand Off

- Core contracts, scenario machine, detectors, arbiter, safety guard, dispatcher, tests, replay tool, and Hosted UI panel are present.
- Hosted UI surface, dashboard context, actions, and minimal panel have passed smoke validation.
- Design docs are complete for the current v1 scope: D-B1 through D-B5, implementation plan, data-layer TODOs, recovery test plan, and real-machine validation checklist.
- Data-layer blockers are no longer "waiting for fields"; the current work is plugin-side v1.6 DTO adaptation and real-machine seam validation.

## Not Done Yet

- Real-machine `dry_run` seams are partially validated; real-speech `dry_run=false` seams still need validation.
- Plugin-side M3 adaptation to data-layer `v1.6` DTO is partially implemented and awaiting real-machine validation.
- `you_killed` and `you_died` now consume `combat.feed[].is_my_kill` and `combat.feed[].is_my_death`; the old `vehicle_valid` death path is not used as the main death source.
- `overspeed` is no longer a data-layer gap; plugin-side dry-run validation has observed the event path, but DTO mapping should still be kept under M3 regression coverage.
- Overheat HUD-notice seam is implemented for `hud_notices.feed[].code` values `engine_overheat` and `oil_overheat`, mapped to the existing `overheat` event with safe code-only payload. It still needs real-machine dry-run revalidation; `powertrain_failure` is intentionally not promoted to a speech event yet.
- `replay: true` telemetry is silenced at `DetectorEngine`: detectors reset and no battle events are emitted. Real replay samples still need validation.
- `/api/identity` still needs a player-name seam through UI/config/runtime orchestration.
- T-Safety is now in place at the NekoDispatcher / prompt-builder boundary. Formal kill/death/hudmsg/combat.feed/awards speech still needs real-machine dry-run validation before dry_run=false rollout.
- Numeric flight-safety events such as stall, low altitude, overheat, low fuel, and overspeed are not blocked by T-Safety.
- Data-layer subprocess orchestration is not implemented.
- `contract/telemetry_sample.json` is still waiting for a real `/api/telemetry` capture.
- recovery remains deferred; do not open `wants_recovery` until real-machine samples justify it.
- i18n currently has only a `zh-CN` placeholder; full 8-locale coverage is expected when future panel copy expands.

## Verification

Run from the standalone plugin repository root:

```powershell
uv run python tests/run_logic_tests.py
uv run pytest tests -q
```

Notes:

- `tests/run_logic_tests.py` is the no-host logic self-check and should report `62/62 passed`.
- If an older handoff note still shows the pre-T4 test count, treat it as stale unless it explicitly refers to an older test entry point.
- The real-machine checklist is in `docs/真机验证-checklist.md`; it now includes the 2026-06-21 dry-run smoke result.

## Next Recommended Work

1. Continue M3 seams that still need runtime integration or samples: `/api/identity`, replay real-sample validation, awards/free-text dry_run validation, and the remaining failure-field strategy.
2. Run the remaining real-machine/data-layer/dry_run seams from `docs/真机验证-checklist.md`, focusing on overheat HUD notice revalidation, identity, replay, kill/death, and free-text event paths.
3. Capture `contract/telemetry_sample.json` from a real `/api/telemetry` response.
4. Only after M3 + real-machine dry_run pass, consider formal kill/death/hudmsg/combat.feed/awards speech through T-Safety.
5. Keep T3/L8 data-layer subprocess orchestration for a later runtime pass.
