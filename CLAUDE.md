# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant add-on for price-aware smart EV charging: wait for cheap
electricity, charge, stop when price rises or a target battery % is
reached, with actionable Android/iOS mobile notifications. It's a hybrid
repo: a real Python integration (`custom_components/smart_ev_charging/`,
HACS category **Integration**) that owns entity configuration via a config
flow, plus a Home Assistant **package** (YAML) that owns all the derived
sensors, statistics, and helpers, plus a **blueprint** that owns the
  plug/price decision logic. There is no build system — "development"
  means authoring/editing Python and YAML, validating each parses and is
  internally consistent (see "Validating changes" below), and running the
  self-contained `tests/` suite (`python -m pytest tests -q`). The Python
  side has never been exercised against a running Home Assistant instance
  (no `homeassistant` package available in this environment — see the
  Integration section below); live validation happens on the Dockerized
  HA instance.

An earlier iteration of this project was pure YAML (no Python), installed
via HACS's "Package" category. That category was removed from HACS
entirely, which is *why* the integration exists — a real Integration is
now the only viable HACS distribution path for this kind of project.
Don't assume the old all-YAML, no-Python design from git history's early
commits is still current; `CHANGELOG.md` and this file describe the
current, integration-based architecture only.

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

For `custom_components/smart_ev_charging/*.py`, at minimum
`python -m py_compile custom_components/smart_ev_charging/*.py` to catch
syntax errors, and `json.load()` each `.json` file. There is no
`homeassistant` package installed in this environment, so imports from
`homeassistant.*` cannot be resolved or type-checked here — API misuse
(wrong signatures, renamed helpers, etc.) will not be caught until someone
runs this against a real Home Assistant instance. Flag this limitation
rather than claiming the integration is verified.

There's no automated test suite beyond `tests/`, which is stub-module
based (Home Assistant packages mocked out in `tests/conftest.py`; it does
*not* use `pytest-homeassistant-custom-component`) and runs anywhere with
just pytest:

```bash
python -m pytest tests -q
```

When making entity-touching changes,
manually trace call sites across files (see "Entity naming and cross-file
coupling" below) — that coupling is the main source of bugs in this repo,
not syntax.

## Architecture

Five pieces cooperate and none is self-sufficient:

1. **`custom_components/smart_ev_charging/`** — the only piece HACS
   auto-installs (Integration category; version comes from its
   `manifest.json`, not `hacs.json`). Owns entity *configuration*:
   `config_flow.py` collects the user's vehicle/charger/price entities
   (required: vehicle_connected, charging_active, price, cheap_price;
   optional: battery, power, energy, departure_calendar) through a config
   entry + options flow, single-instance-only. `sensor.py`/`binary_sensor.py`
   mirror those chosen entities' state onto fixed, well-known entity IDs
   (`binary_sensor.ev_vehicle_connected`, `binary_sensor.ev_charging_active`,
   `binary_sensor.ev_price_cheap`, `sensor.ev_charging_price`,
   `sensor.ev_battery_percentage`, `sensor.ev_charging_power`,
   `sensor.ev_energy_meter`) by directly setting `self.entity_id` in each
   entity's constructor — a deliberate departure from the usual
   "let HA derive entity_id from name" pattern, because the package,
   scripts, blueprint, and dashboards all hardcode these exact IDs.
   `sensor.py` also exposes a diagnostic `sensor.ev_smart_charging_config`
   whose attributes hold the full configured entity map (used by the
   blueprint's departure-calendar lookup and the dashboards' Debug section).
    `__init__.py` also owns **best-effort auto-install**: on
    `async_setup_entry`, it copies the bundled
    `custom_components/smart_ev_charging/blueprint/smart_ev_charging.yaml`,
    `packages/smart_ev_charging.yaml` and
    `scripts/smart_ev_charging_scripts.yaml` into the user's config
    directory. These use *different* overwrite policies, deliberately — see
    `_install_bundled_assets`'s docstring: the blueprint is re-synced
    (overwritten) whenever its bundled content differs from what's on
    disk, on every setup/restart, because that's the only way a blueprint
    bugfix in a new release reaches someone who already installed an
    earlier version — blueprints are customized via the automation's
    inputs, not by hand-editing the blueprint file. The package and
    scripts are copied once and never touched again (they're commonly
    hand-tweaked after install). The dashboard is *not* copied as a YAML
    file at all — it's handled separately by `dashboard.py`, which
    registers it with Lovelace storage (see below) and refreshes it on
    every HA start while it stays installed. Don't change the blueprint to
    "only if missing" — that was the actual bug
    that shipped in 1.3.0 (an `action` selector input spliced under an
    `action:` key instead of as a bare sequence item, caught by a user
    error report, fixed in 1.3.1) and had no way to reach existing
    installs until this sync-on-diff behavior was added.
   `_async_notify_setup_complete` then posts one `persistent_notification`
   summarizing what was
   installed and what's still manual. It owns zero charging *decision*
   logic — that's the package/blueprint's job.
2. **`custom_components/smart_ev_charging/packages/smart_ev_charging.yaml`**
    — `input_boolean` / `input_number`
    / `input_datetime` / `input_text` helpers, `counter`, `utility_meter`,
    `template:` sensors/binary_sensors derived from the integration's
    mirror entities (charging mode/state/duration/session cost/statistics),
    and one static automation (`ev_smart_charging_notification_actions`)
    that listens for `mobile_app_notification_action` events and dispatches
    to scripts. Reads the integration's entities; never reads the user's
    raw vehicle/charger entities directly. Auto-copied to the user's
    `config/packages/` on setup (copy-if-missing), but HA won't load it
    without the `packages: !include_dir_named packages` include in
    `configuration.yaml` plus a full restart — `__init__.py` detects the
    include and tells the user exactly what to add rather than
    auto-editing their config file.
3. **`custom_components/smart_ev_charging/blueprint/smart_ev_charging.yaml`**
   — the actual plug/price/charging state machine, and the **single
   canonical copy** (do not recreate a second copy at a repo-root
   `blueprints/` path — that duplication existed in earlier versions and
   was deliberately removed; `__init__.py`'s auto-install is what puts a
   *runtime* copy in the user's config, not a second copy in this repo).
   User-instantiated once via the HA UI. Only 4 inputs remain
   (`start_charging_action`, `stop_charging_action`, `notify_targets`,
   `deadline_lead_time_minutes`) — the vehicle/charger/price entities are
   *not* blueprint inputs; the blueprint reads the integration's fixed
   mirror entity IDs directly, the same way it already hardcodes
   `input_boolean.ev_follow_price`. Do not re-add those as `!input`
   selectors — that would resurrect the double-configuration problem the
   integration exists to remove. Uses trigger IDs + `choose:` blocks,
   `mode: queued` to serialize concurrent trigger firings and avoid race
   conditions.

   `start_charging_action`/`stop_charging_action` use `selector: {action: {}}`,
   which resolves to a **list** of action steps, not a service-name
   string. Each call site splices it via the empty-choose trick —
   `- choose: []` / `default: !input start_charging_action` — never as
   `- action: !input start_charging_action`, which fails at
   automation-creation time with "value should be a string for dictionary
   value" (HA then tries to put a list where a string belongs). This
   shipped broken in 1.3.0 and was fixed in 1.3.1 — if you ever add
   another `action`-selector input, use the same pattern, and keep every
   start/stop call site dry-run guarded (`if not dry_run`).
4. **`custom_components/smart_ev_charging/scripts/smart_ev_charging_scripts.yaml`**
    — all reusable logic
    (notification building, session bookkeeping, dashboard button targets).
    Flat mapping of `script_id: {...}`, merged in via
    `script: !include_dir_merge_named scripts` — do not wrap it in a `script:`
    key. Reads `sensor.ev_battery_percentage` / `sensor.ev_charging_power` /
    `sensor.ev_energy_meter` directly rather than receiving them as script
    fields — only `notify_targets` (genuinely per-installation) is passed
    in. `script.ev_send_notification` is the one place that actually calls
   `notify.send_message`; every notify-sending script routes through it
   instead of calling a notify action directly.
5. **`custom_components/smart_ev_charging/dashboards/dashboard.yaml`**
   (native, canonical copy — same "don't duplicate at repo root" rule as
   the blueprint) and **`dashboards/mushroom_dashboard.yaml`** (enhanced,
   needs Mushroom + ApexCharts, repo-root only, *not* auto-installed —
   requires HACS frontend resources the integration can't detect or
   install). Same information architecture in both. Keep them in sync
   when adding a new sensor/section.

### Why the dashboard is auto-installed via Lovelace storage, while the blueprint is just a file copy

The blueprint is a YAML file dropped into `blueprints/automation/` — HA
reads blueprints from disk on demand, so the file copy in `__init__.py` is
all it takes. A sidebar dashboard can't be created that way: it must be
registered with Lovelace. `dashboard.py` installs it directly into the
storage-mode Lovelace store (`lovelace_dashboards`), registers the sidebar
panel, and saves the bundled config, so the user gets the dashboard in the
sidebar without pasting YAML. Install / update / uninstall are exposed
both from the integration's Options menu (`install_dashboard` /
`uninstall_dashboard` steps) and as the
`smart_ev_charging.install_dashboard` / `smart_ev_charging.uninstall_dashboard`
services.

Two deliberate trade-offs, both documented in `dashboard.py`:

1. The install writes the `lovelace_dashboards` store directly rather than
   going through Lovelace's `DashboardsCollection`. That collection API is
   an undocumented internal with a known data-loss bug
   (home-assistant/core#165767) if called before Lovelace's lazy-load
   completes; the direct write is how this code avoids depending on it —
   at the cost of the in-memory collection not being told about the new
   item until restart. Don't rewrite this without re-verifying that bug
   is resolved.
2. `rebuild_installed_dashboard` re-saves the bundled config on every
   `async_setup_entry`, so an installed dashboard is refreshed on each HA
   start — but only if it's already installed; it never auto-creates for
   users who didn't opt in. Hand-edited dashboard customizations are
   therefore overwritten on restart; that's the documented price of
   shipping card updates automatically. README says the same thing — keep
   them in agreement. Known limitation, deliberately not "fixed": the
   rebuild reads `hass.data["lovelace"]` and silently no-ops if Lovelace
   hasn't loaded yet at `async_setup_entry` time (startup race). The user
   can always re-run Options > Install Dashboard to force it; wiring this
   to wait for Lovelace would couple the integration to frontend-internal
   event ordering for marginal benefit.

### v1.7.0 architecture notes

- **Package is copy-if-missing — upgrades don't re-apply it.** The user's
  `config/packages/smart_ev_charging.yaml` is only written when absent
  (`_copy_if_missing`), so on every upgrade most installs keep the old
  file. This is deliberate (the file is commonly hand-tweaked), but it
  means any package-only change — v1.7.0's re-sourced meters, new
  `sensor.ev_charging_power_cost`, Riemann `sensor.ev_charging_cost_accumulated`,
  `unique_id`s — requires the user to manually replace the file and
  restart. The README Troubleshooting row states this; don't "fix" it by
  making the package overwrite blindly.
- **Energy meters read the live charger meter; cost meters read a Riemann
  integral.** `sensor.ev_energy_*` are sourced from `sensor.ev_energy_meter`
  (monotonically increasing) so "today" moves during a session.
  `sensor.ev_charging_cost_accumulated` is a `platform: integration` sensor
  (Riemann, `unit_time: h`, `max_sub_interval: 5 min`, `round: 2`) of
  `sensor.ev_charging_power_cost` (EUR/h = power × live tariff), and the
  `sensor.ev_charging_cost_*` meters source *it*. Both flux sensors carry
  accurate units and the meters set `periodically_resetting: false` so
  HA 2025.12+ long-term statistics aren't suppressed. Changing a meter's
  source resets its reading once (documented in CHANGELOG/README).
- **Auto-start pause is intentional "start then stop", not "prevent".** HA
  cannot beat the charger to the first watt — `should_stop_charging` (a
  variable whose fragments cover price-uncheap, battery-target reached,
  and manual override) runs in the `connected`, `charging_started` (before
  the notify/session-seeding steps), `periodic_check` (new pause
  sub-branch), `price_cheap`/`price_expensive`, and `manual_stop_requested`
  branches and calls `!input stop_charging_action` (dry-run guarded) to
  pause the ~5–30 s burst. Don't rename it to "should_not_start" — the
  stop decision is what makes manual/emergency paths unconditional while
  the paused auto-start is still possible.
- **Legacy blueprint copy cleanup.** The legacy root-level
  `blueprints/smart_ev_charging.yaml` copy is removed on setup when it's
  byte-identical to the bundled blueprint (it was written by an old
  `_copy_if_missing` style that duplicated the canonical copy); a
  user-modified copy is left alone.
- **The "smart charging disabled" repair issue** (`issue_registry`
  `smart_charging_disabled`) is created whenever
  `input_boolean.ev_follow_price` is `off` and cleaned up automatically
  when the helper isn't loaded yet (no-op) or turns `on`. It's the
  v1.7.0 answer to F2 ("we never knew the system was in Manual mode").

### Why the integration's mirror entities exist

Lovelace cards need a fixed `entity_id` at dashboard-authoring time — they
cannot resolve "whatever entity was picked in a config entry" themselves,
and the blueprint's price/plug triggers need real entity IDs too. Rather
than making users pick entities twice (once in the integration, again as
blueprint `!input`s — the v1.0.0 design), the integration is the single
place configuration happens, and it re-exposes the chosen entities under
fixed IDs everything else can hardcode. Don't remove the mirror sensors
thinking they're redundant with the config entry's raw data — dashboards
and package templates depend on the mirrors' entity IDs directly, not on
`entry.data`/`entry.options`.

### Session tracking: use the boolean, not datetime emptiness

`input_boolean.ev_session_tracking` is the single source of truth for
"is a charging session currently being tracked." Do **not** infer this from
`input_datetime.ev_charge_start_time` being empty/unknown — HA's
`input_datetime.set_datetime` cannot clear a value back to unknown once
set, so a stale start_time survives after a session ends. Any new logic
that needs to know "did we already seed this session" must check
`ev_session_tracking`, matching:
- `custom_components/smart_ev_charging/scripts/smart_ev_charging_scripts.yaml`:
  `ev_seed_session_helpers` turns
  it on, `ev_log_charging_session` turns it off.
- `blueprints/automation/smart_ev_charging.yaml`'s `ha_restart` branch
  checks it's off before backfilling.

### Debug logging is centralized

Every decision point in the blueprint calls `script.ev_debug_log` (never
`input_text.set_value` on `ev_last_charging_decision` directly) — it writes
the debug helper and conditionally mirrors to the Logbook when
`input_boolean.ev_debug_logging` is on. Add new decision points through
this script, not by duplicating the two-step pattern inline.

### Notify targeting: device-based, not a typed service string

The blueprint's `notify_targets` input is a `device` selector
(`multiple: true`, filtered to the `mobile_app` integration) — the user
picks phones/tablets by name instead of typing a `notify.mobile_app_...`
service string. `script.ev_send_notification` (in
`custom_components/smart_ev_charging/scripts/smart_ev_charging_scripts.yaml`)
is the single place that
actually sends. `notify.send_message` with `target: {device_id: [...]}`
is the modern fan-out call but rejects the nested `data` payload (tag,
actions, channel) this package needs, so the script instead resolves each
device to its legacy `notify.mobile_app_*` service and loops. Resolution
goes through the entity registry (`integration_entities('mobile_app')` ∩
`device_entities(device_id)`), and every resolved service is validated
with `has_service`, so a device whose notify entity was renamed or a
wrong guess degrades to the `notify.send_message` fallback (message/title
only, no actions/tag) rather than failing the run. Every other
notify-sending script
(`ev_notify_plugged_in`, `ev_notify_charging_started`,
`ev_notify_charging_finished`) must go through this shared script rather
than calling a notify action directly, both to avoid duplicating the
multi-device fan-out and to keep the tag-based dismiss/replace behavior
consistent across all targets.

This is a deliberate compatibility tradeoff, made explicitly at the
user's request for a "friendly, not typed" field: the device selector and
the legacy service resolution only work on **Home Assistant 2026.5+**
(mobile_app notify entities didn't exist before that release) — see
`hacs.json`'s `homeassistant` field and README's Installation section,
which must stay in sync with this constraint. Don't "restore" a typed
service-string field without re-raising this tradeoff — it was the whole
point of the change.

### Manual charge-now / stop-charging use pulse booleans, not direct actions

`script.ev_charge_now` / `script.ev_stop_charging` (called from dashboard
buttons and the notification-action listener) cannot call the user's
charger-specific start/stop action directly — that action is only known to
the blueprint automation, as its `start_charging_action`/`stop_charging_action`
`!input`s (the two blueprint inputs that genuinely can't be centralized in
the integration, since "how to start your charger" isn't an entity to
mirror). Instead the scripts toggle
`input_boolean.ev_charge_now_override` / `input_boolean.ev_stop_charging_requested`,
and the blueprint has dedicated triggers (`manual_charge_now`,
`manual_stop_requested`) that react and call the real action. Preserve this
indirection when touching either script or the blueprint.

## Entity naming and cross-file coupling

Everything package/integration-defined is prefixed `ev_` (`input_boolean.ev_follow_price`,
`sensor.ev_charging_state`, `script.ev_charge_now`, `binary_sensor.ev_vehicle_connected`, …).
When renaming or removing any entity — whether it originates in the
integration's `sensor.py`/`binary_sensor.py` or in the package's `template:`
block — grep across all of `custom_components/`, `blueprints/`,
`custom_components/smart_ev_charging/scripts/`, and both `dashboards/*.yaml`
files. There is no schema or
compiler to catch a stale reference; the dashboard files in particular
silently degrade to "entity not found" cards, and a Jinja template
referencing a removed entity just silently evaluates to `unknown`. The
`automation.smart_ev_charging` entity ID referenced in both dashboards is
not package/integration-defined — it's whatever the user named their
blueprint-created automation; README calls this out as the one manual-edit
point.

## Versioning and releases

See `AGENTS.md`'s release checklist — it is the authoritative, step-by-step
process (README updates, the four places version must move together
consistently, then tag + GitHub release) and applies regardless of which
agent or tool is making the change. Follow it for every user-facing
change without waiting to be asked; HACS installs from tags/releases, not
raw commits, so an untagged change is invisible to users.
