# Project Status

## Current State

- M1 scaffold and M2 understanding/decision logic are implemented.
- Battle Awareness main chain is implemented.
- Hosted UI Integration is complete.
- Minimal Panel is complete.
- T4 integration tests are complete.
- Logic self-check currently passes: `32/32`.
- Default runtime mode is `dry_run = true`; the plugin runs the decision chain but does not push real catgirl speech until dry run is disabled.
- The plugin boundary is HTTP `:8112` (`/api/telemetry`) only. It consumes the vendored data layer and must not import or modify `data_layer/` code.
- Vendored data layer contract `v1.6` is merged. It includes `overspeed_warn` / `overspeed_critical`, enhanced `combat.feed`, `is_my_kill` / `is_my_death`, `/api/identity`, `replay: true` degrade mode, `hud_notices`, and `awards`.

## Ready to Hand Off

- Core contracts, scenario machine, detectors, arbiter, safety guard, dispatcher, tests, replay tool, and Hosted UI panel are present.
- Hosted UI surface, dashboard context, actions, and minimal panel have passed smoke validation.
- Design docs are complete for the current v1 scope: D-B1 through D-B5, implementation plan, data-layer TODOs, recovery test plan, and real-machine validation checklist.
- Data-layer blockers are no longer "waiting for fields"; the current work is plugin-side v1.6 DTO adaptation and real-machine seam validation.

## Not Done Yet

- Real-machine/data-layer/real-speech seams still need validation.
- Plugin-side M3 adaptation to data-layer `v1.6` DTO is not implemented yet.
- `you_killed` and `you_died` should be adapted to `combat.feed[].is_my_kill` and `combat.feed[].is_my_death`; the old `vehicle_valid` death path is not reliable enough as the main source.
- `overspeed` is no longer a data-layer gap, but still needs plugin-side verification against `overspeed_warn` / `overspeed_critical`.
- `replay: true` still needs a plugin degrade or silence policy.
- `/api/identity` still needs a player-name seam through UI/config/runtime orchestration.
- `T-Safety: output text sanitizer` is planned but not implemented yet.
- T-Safety blocks formal kill/death/hudmsg/combat.feed/awards speech. It does not block numeric flight-safety events such as stall, low altitude, overheat, low fuel, or overspeed.
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

- `tests/run_logic_tests.py` is the no-host logic self-check and should report `32/32 passed`.
- If an older handoff note still shows the pre-T4 test count, treat it as stale unless it explicitly refers to an older test entry point.
- The real-machine checklist is in `docs/真机验证-checklist.md`.

## Next Recommended Work

1. Keep code frozen until the docs-only status sync is committed.
2. Implement `T-Safety: output text sanitizer` before formal kill/death/hudmsg/combat.feed/awards speech.
3. Adapt M3 to data-layer `v1.6` DTO: `overspeed_warn` / `overspeed_critical`, `combat.feed[].is_my_kill`, `combat.feed[].is_my_death`, `/api/identity`, and `replay: true`.
4. Run the remaining real-machine/data-layer/real-speech seams from `docs/真机验证-checklist.md`.
5. Capture `contract/telemetry_sample.json` from a real `/api/telemetry` response.
6. Keep T3/L8 data-layer subprocess orchestration for a later runtime pass.
