# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant **package** (YAML, no Python/custom component) that adds
price-aware smart EV charging: wait for cheap electricity, charge, stop when
price rises or a target battery % is reached, with actionable Android/iOS
mobile notifications. Distributed as a HACS "Package" category repo. There
is no build system, no tests, no runtime here — this repo *is* the
configuration that Home Assistant loads directly. "Development" means
authoring/editing YAML and validating it parses and is internally
consistent.

`ev_charging_hacs_package.md` is the original spec this project was built
from — consult it to check a proposed change against the original intent
before deviating from established patterns.

## Validating changes

There's no HA instance to run here. Before committing, at minimum check
every YAML file still parses:

```bash
python -c "
import yaml, glob, sys
ok = True
for f in sorted(glob.glob('**/*.yaml', recursive=True)):
    try:
        with open(f, encoding='utf-8') as fh:
            list(yaml.safe_load_all(fh))
        print('OK  ', f)
    except Exception as e:
        ok = False
        print('FAIL', f, '->', repr(e))
sys.exit(0 if ok else 1)
"
```

`blueprints/automation/smart_ev_charging.yaml` will fail plain `yaml.safe_load`
because of the Home Assistant-specific `!input` tag — that's expected. To
validate it structurally, register a permissive multi-constructor for `!`
tags before loading (see git history for the exact snippet), then confirm
`blueprint.input`, `triggers`, and `actions[0].choose` come out with the
expected keys/counts.

There's no automated test suite. When making entity-touching changes,
manually trace call sites across files (see "Entity naming and cross-file
coupling" below) — that coupling is the main source of bugs in this repo,
not YAML syntax.

## Architecture

Four files cooperate and none of them is self-sufficient:

1. **`packages/smart_ev_charging.yaml`** — the only file HACS actually
   auto-installs (per `hacs.json`'s `filename`). Defines all `input_text`
   / `input_boolean` / `input_number` / `input_datetime` helpers, `counter`,
   `utility_meter`, `template:` sensors/binary_sensors, and one static
   automation (`ev_smart_charging_notification_actions`) that listens for
   `mobile_app_notification_action` events and dispatches to scripts.
2. **`blueprints/automation/smart_ev_charging.yaml`** — the actual
   plug/price/charging state machine. User-instantiated per vehicle via the
   HA UI, with entity/action selectors (`!input ...`) so no real entity ID
   is ever hardcoded here. Uses trigger IDs + `choose:` blocks, `mode: queued`
   to serialize concurrent trigger firings and avoid race conditions.
3. **`scripts/smart_ev_charging_scripts.yaml`** — all reusable logic
   (notification building, session bookkeeping, dashboard button targets).
   Flat mapping of `script_id: {...}`, merged in via
   `script: !include_dir_merge_named scripts` — do not wrap it in a `script:`
   key.
4. **`dashboards/dashboard.yaml`** (native) and
   **`dashboards/mushroom_dashboard.yaml`** (enhanced, needs Mushroom +
   ApexCharts) — same information architecture in both, native cards vs.
   `custom:mushroom-*`/`custom:apexcharts-card`. Keep them in sync when
   adding a new sensor/section.

### Why there's a config layer (`input_text` entity pointers)

Lovelace cards need a fixed `entity_id` at dashboard-authoring time — they
cannot resolve "whatever entity is named inside this helper" themselves.
Blueprint `!input` selectors *can* be picked per-installation, but template
sensors in the static package file cannot take blueprint inputs. The
resolution is a two-layer indirection:

- `input_text.ev_*_entity` helpers (in the package) store the user's real
  entity IDs (e.g. `sensor.nordpool_kwh_price`).
- Template sensors resolve them dynamically via `states(states('input_text.ev_..._entity'))`.
- Because dashboards need *stable* entity IDs, several sensors exist purely
  as passthrough mirrors with fixed entity_ids (`sensor.ev_battery_percentage`,
  `sensor.ev_charging_power`, `binary_sensor.ev_vehicle_connected`,
  `binary_sensor.ev_charging_active`, `binary_sensor.ev_price_cheap`,
  `sensor.ev_charging_price`) — don't remove these thinking they're
  redundant with the input_text config; dashboards depend on them directly.
- The blueprint's own `!input` selectors are a *separate* configuration
  step from the `input_text` helpers (users set both, pointing at the same
  entities) — this intentional duplication is the tradeoff for supporting
  "any EV/charger" without a custom component. Documented in README FAQ.

### Session tracking: use the boolean, not datetime emptiness

`input_boolean.ev_session_tracking` is the single source of truth for
"is a charging session currently being tracked." Do **not** infer this from
`input_datetime.ev_charge_start_time` being empty/unknown — HA's
`input_datetime.set_datetime` cannot clear a value back to unknown once
set, so a stale start_time survives after a session ends. Any new logic
that needs to know "did we already seed this session" must check
`ev_session_tracking`, matching:
- `scripts/smart_ev_charging_scripts.yaml`: `ev_seed_session_helpers` turns
  it on, `ev_log_charging_session` turns it off.
- `blueprints/automation/smart_ev_charging.yaml`'s `ha_restart` branch
  checks it's off before backfilling.

### Debug logging is centralized

Every decision point in the blueprint calls `script.ev_debug_log` (never
`input_text.set_value` on `ev_last_charging_decision` directly) — it writes
the debug helper and conditionally mirrors to the Logbook when
`input_boolean.ev_debug_logging` is on. Add new decision points through
this script, not by duplicating the two-step pattern inline.

### Notify service calls

Scripts call the notify service dynamically — `action: "{{ notify_service }}"`
with a plain literal service name string (e.g. `notify.mobile_app_pixel_7`),
not the newer `notify.send_message` + `target: entity_id:` pattern. This is
intentional for broader compatibility across notify integrations, not an
oversight — don't "modernize" it without checking README's stated minimum
HA version and the blueprint's `notify_service` input description.

### Manual charge-now / stop-charging use pulse booleans, not direct actions

`script.ev_charge_now` / `script.ev_stop_charging` (called from dashboard
buttons and the notification-action listener) cannot call the user's
charger-specific start/stop action directly — that action only exists as a
per-blueprint-instance `!input`. Instead they toggle
`input_boolean.ev_charge_now_override` / `input_boolean.ev_stop_charging_requested`,
and the blueprint has dedicated triggers (`manual_charge_now`,
`manual_stop_requested`) that react and call the real action. Preserve this
indirection when touching either script or the blueprint.

## Entity naming and cross-file coupling

Everything package-defined is prefixed `ev_` (`input_boolean.ev_follow_price`,
`sensor.ev_charging_state`, `script.ev_charge_now`, …). When renaming or
removing any package/script entity, grep across all of
`packages/`, `blueprints/`, `scripts/`, and both `dashboards/*.yaml` files —
there is no schema or compiler to catch a stale reference, and the dashboard
files in particular silently degrade to "entity not found" cards. The
`automation.smart_ev_charging` entity ID referenced in both dashboards is
not package-defined — it's whatever the user named their blueprint-created
automation; README calls this out as the one manual-edit point.

## Versioning and releases

Version is tracked in three places that must move together: `hacs.json`
(no explicit version field currently — HACS derives it from git
tags/releases), `CHANGELOG.md`, and the hardcoded
`sensor.ev_smart_charging_version` state in
`packages/smart_ev_charging.yaml`. HACS resolves installable versions from
GitHub releases (falls back to the default branch if none exist), so a
version bump is: update `CHANGELOG.md` and the version sensor, commit, then
`git tag -a vX.Y.Z -m "..."`, `git push origin vX.Y.Z`, and
`gh release create vX.Y.Z --title vX.Y.Z --notes "..."`.
