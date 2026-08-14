# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.7.0] - 2026-08-14

### Breaking changes

- The energy and cost utility meters are re-sourced. `sensor.ev_energy_*`
  daily/weekly/monthly meters now read the live charger meter
  (`sensor.ev_energy_meter`) instead of the session-closing
  `sensor.ev_charging_lifetime_energy`, so they move **during** a session
  instead of only when a session closes, and discontinued
  midnight-reset meters no longer drift. Cost meters
  (`sensor.ev_charging_cost_*`) now read a new Riemann integral
  `sensor.ev_charging_cost_accumulated` of the live power draw against the
  live tariff. Because a meter's reading resets when its source changes,
  every meter value — and the cost/energy dashboard tiles — reset to zero
  **once** on upgrade; values rebuild from the new sources going forward.
- Every package helper sensor now carries a `unique_id`, so the entity
  identities (and their long-term-statistics history) differ from v1.6.x.
  Merge or remove the stale v1.6.x entities in Developer Tools > Entities
  once after upgrading.
- The package YAML is copied into `config/packages/` only if it's missing
  (`copy_if_missing`), so an existing install keeps the old file on
  upgrade. Apply this release — including the re-sourced meters — by
  manually replacing `config/packages/smart_ev_charging.yaml` and
  restarting (see README Troubleshooting).

### Added

- The automation now pauses a charger that auto-starts the moment the car
  is plugged in: a `should_stop_charging` decision runs on connect, at
  charging start, in the periodic check, and at cost thresholds, so the
  car only keeps drawing after plug-in when the tariff is actually cheap.
  The manual/emergency paths still charge immediately and unconditionally
  turn the follow-price override off (as before). The emergency deadline
  and battery-target routes start charging with the same guarantees as the
  manual path, now that the charging-started stop check runs before the
  notification/session-tracking bookkeeping.
- A Home Assistant repair issue ("Smart charging is installed but
  disabled") is raised while `input_boolean.ev_follow_price` is off, so a
  disabled system can't be mistaken for a broken one. It resolves itself
  the moment the toggle is turned on.
- `sensor.ev_charging_power_cost` (EUR/h) and the flux-state cost integral
  `sensor.ev_charging_cost_accumulated` with correct `EUR/h`/`EUR`
  units, `periodically_resetting: false` and a 5-minute Riemann sampling
  cap, so the cost sensors produce clean long-term statistics instead of
  being suppressed by Home Assistant 2025.12+ unit handling.
- The price-cheap/price-expensive automation triggers now pin both `from`
  and `to` punctuation (`off`→`on` / `on`→`off`), so the rules listen for
  the exact crossing instead of the default `on`/`off` semantics, which
  could leave the automation edge-triggered in a stale state after a
  restart mid-trigger. The connect/disconnect triggers gained a 10-second
  debounce so a charger that flaps its status sensor at plug-in won't fire
  the automation twice.
- The config flow now auto-unions recorder state options (`binary sensors
  combined`, etc.) with the config flow's own suggestions, so existing
  installs whose "connected" states only live in the YAML package keep
  working without re-ticking states after an upgrade (the union is
  applied whenever an entry is saved, so it heals automatically).

### Fixed

- Mirror binary sensors (`ev_vehicle_connected`, `ev_price_cheap`, and
  the new implied-charging mirror) treat `unavailable`/`unknown` source
  states as *not* a match instead of bouncing between on/off, so the
  dashboard no longer shows a flickering "connected" during a source gap.
- `ev_charging_active`'s mirror now stays "on" whenever the implied
  charging source is on, even if the explicitly configured source flips;
  the mirror ordering also changed so `charging_active` registers before
  `price_cheap`, matching the documented entity order.
- The Blueprint + legacy-sync copy of the blueprint are no longer both
  written on every helper state; the legacy root path is removed when it
  matches the bundled file. F13's corrupted README text ("Vehicle Weekend
  charging active") is fixed.

### Documentation

- README: version badge → 1.7.0; new FAQ entries for instant-start on
  plug-in, the normal 5–30 s auto-start pause burst, and the one-time
  meter reset; Troubleshooting rows for the new repair notice, the stale
  package file after upgrade, and the long-term-statistics unit fix.
  CLAUDE.md notes updated for the new entities.

### Tests

- Blueprint dry-run guard assertions now count 12 action sites; new checks
  for `should_stop_charging` variable fragments, `from`/`to` trigger
  punctuation, and the disconnect debounce. `binary_sensor` tests cover
  `implied_on_by` and unavailable/unknown handling; config-flow tests
  cover the auto-union of recorder "binary sensors combined" options.
  88 tests (was 59).

## [1.6.6] - 2026-08-12

### Fixed

- The session-duration fix in 1.6.5 reintroduced the v1.5.2 timezone bug:
  `ev_notify_charging_finished` subtracted a timezone-naive `strptime`
  result from `now()`, raising `TypeError` inside the `variables:` step.
  Because that step is first, the script aborted before dismissing the
  charging notification, sending the summary, or logging the session —
  leaving `ev_session_tracking` stuck on so lifetime statistics stopped
  updating permanently. Elapsed time is now computed via `timestamp()`,
  which compares naive and aware datetimes safely.
- Notification delivery was silently dead for every install: the 1.6.5
  rewrite used `has_service()`, which is **not** a Home Assistant template
  function (`UndefinedError`), and it required notify entity IDs to already
  carry the `mobile_app_` prefix. On this and typical installs the entities
  are `notify.<phone>` and only the legacy *services* are
  `notify.mobile_app_<phone>`, so nothing resolved and every notification
  fell back to `notify.send_message`, losing the tag/action `data` payload
  that the Charge now / Stop charging buttons depend on. Resolution now
  derives the legacy service name from the registry-found entity (handling
  both ID shapes) and drops the unavailable `has_service` check.
- Stop-at-target-battery was dead: the 1.6.5 `battery_update` change made
  it a *template* trigger, which fires only on a falsy→truthy boolean
  transition — and a numeric battery percentage isn't a valid boolean, so
  it never fired. It is a state trigger again (`not_to: unknown,
  unavailable`), which still suppresses attribute-only changes.
- The "cleared optional entity" fix was only half-finished: the mirror
  readers preferred options, but the config-flow **writer** still rebuilt
  `captured` from the whole stored dict, so a cleared optional entity
  picker (key omitted by the frontend) was restored from its old value on
  save. The configure step now carries across only the `*_states` keys, so
  cleared entities genuinely stay cleared.
- The dashboard install/uninstall services were removed *before* platform
  unload; if unload failed the entry stayed loaded with its services gone.
  They are now removed only after a successful unload.

### Documentation

- CLAUDE.md: the Lovelace storage install bypass and the
  overwrite-on-restart behavior were already recorded as deliberate
  trade-offs; the startup race (rebuild silently no-ops if Lovelace isn't
  loaded during `async_setup_entry`) is now also documented as a known,
  deliberately unfixed limitation.

### Tests

- `sensor.py` and `binary_sensor.py` now have coverage locking in the
  "options win wholesale over data" reader contract (a cleared field stays
  cleared, an options value wins over data, empty options falls back).
  Test suite is 59 tests (was 54).

## [1.6.5] - 2026-08-12

### Fixed

- Session duration was always recorded as 0: `ev_notify_charging_finished`
  read `sensor.ev_charging_duration`, which resets to 0 the moment charging
  stops — and the script runs exactly then. The "✅ Charging finished"
  notification showed `0h 0m`, `input_number.ev_lifetime_duration_minutes`
  never grew, and `sensor.ev_average_session_duration` stayed at 0. The
  script now computes elapsed time from the seeded `ev_charge_start_time`
  instead.
- The duration sensor template applied `round()` to the literal `60`
  instead of the quotient (Jinja filter precedence) — it emitted full
  float precision. The division is now wrapped before the filter.
- Options flow silently wiped stored options: the "Install/uninstall
  dashboard" steps ended with `async_create_entry(data={})`, replacing
  `entry.options` with `{}` and reverting any entity re-selection made via
  Options > Configure. Both steps now re-emit the existing options
  unchanged.
- Clearing an optional entity in Options > Configure did nothing: the
  cleaned config was written to *options*, but the mirror sensors still
  fell back to `entry.data` (which still held the old value) for any key
  missing from options. The readers now prefer `entry.options` wholesale
  once options exist, so a cleared field stays cleared.
- Plugging in during an already-cheap price window never started charging:
  the automation was purely edge-triggered (`price_cheap` only fires on a
  transition). The start decision is now a single shared condition set
  used by the `price_cheap` trigger, a new "cheap at plug-in" check in the
  `connected` branch, and a backstop in the 10-minute `periodic_check` —
  so a vehicle plugged in mid-cheap-window starts within seconds (or the
  next periodic check), instead of waiting for the next price transition.
- `ev_charge_now` / `ev_stop_charging` were no-ops on a second press while
  the pulse boolean was already on. They now pulse (off, then on) so every
  press produces a state edge.
- Negative electricity prices (below −1 €/kWh) aborted the session-seed
  sequence with an out-of-range error, leaving session tracking off
  mid-session. `ev_charge_start_price` and `ev_max_acceptable_price` now
  accept prices down to −5 €/kWh.
- Monetary sensors were missing units: `EV Charging Lifetime Cost` and
  `EV Estimated Session Cost` had `device_class: monetary` with no
  `unit_of_measurement`, and lifetime cost used `state_class:
  total_increasing` (monetary pairs with `total`). Both now carry
  `EUR` and lifetime cost uses `state_class: total`. (Existing installs:
  a utility meter copies its source's unit event-driven, so cost meters
  that were created unitless restore `unit=None` and only show `EUR`
  once the lifetime-cost source next updates — i.e. at the first logged
  session after the upgrade. Home Assistant may also raise a
  "units changed" / "state class changed" repair notification for
  `sensor.ev_charging_lifetime_cost` on the first start after the
  upgrade; that's expected, not a bug.)
- Notification service resolution in `ev_send_notification` reconstructed
  `notify.mobile_app_*` service names by string surgery on entity IDs. It
  now resolves through the entity registry
  (`integration_entities('mobile_app')` ∩ device entities), filters to
  genuine mobile_app notify entities, and validates each service with
  `has_service`, so a wrong guess falls back to `notify.send_message`
  (message/title only) instead of failing the run. `service_template:` was
  replaced by a templated `action:`.
- `ev_notify_charging_started` is driven by both the `charging_started`
  trigger and a 5-minute refresh; it was `mode: single` and logged
  "already running" warnings. It is now `mode: queued`.
- The blueprint's `battery_update` trigger fired on attribute-only changes
  (no `to:`). It is now a template trigger that only fires when the
  battery percentage value actually changes.
- The dashboard install/uninstall services are now removed on config-entry
  unload instead of leaking.
- The dashboard's "Current Session" card displayed the session-start helper
  entities (`input_datetime.ev_charge_start_time`,
  `input_number.ev_charge_start_price`) as editable controls — and editing
  them skewed the duration/cost calculations. They're now shown read-only
  (or "No active session" when nothing is charging); the editable helpers
  remain in the Debug section, where they belong.

### Documentation

- CLAUDE.md reconciled with the code: the dashboard is installed into
  Lovelace storage (not copied as a YAML file) and refreshed on every HA
  start while installed; `ev_send_notification` resolves legacy
  `notify.mobile_app_*` services rather than calling `notify.send_message`
  directly; blueprint action inputs use the `- choose: [] / default:
  !input` splice; the `tests/` suite and its command are documented.
- README corrected: the bundled dashboard is registered into Lovelace via
  the integration's Options menu (it is not copied to
  `config/dashboards/`), and the manual-paste fallback now points at the
  bundled `custom_components/smart_ev_charging/dashboards/dashboard.yaml`.

## [1.6.4] - 2026-08-11

### Added

- README: worked example for the Easee Oprit (official Easee integration),
  showing the `sensor.oprit_status` status states to mark for "Vehicle
  connected" / "Charging active" (lower-case underscore values like
  `ready_to_charge`, `awaiting_start`, `charging`) and the Oprit's own
  `sensor.oprit_power` / `sensor.oprit_lifetime_energy` for the optional
  power/energy fields.

## [1.6.3] - 2026-08-11

### Fixed

- The lifetime statistics sensors were named "EV Lifetime Energy"/"EV
  Lifetime Cost", so Home Assistant registered them as
  `sensor.ev_lifetime_energy`/`sensor.ev_lifetime_cost` — but the
  dashboards' "Total energy charged" tile and the `utility_meter`
  sources (today/week/month energy and cost) all referenced
  `sensor.ev_charging_lifetime_energy`/`sensor.ev_charging_lifetime_cost`,
  which never existed. The tiles showed an unknown entity and the meters
  sat at `unknown`/0. The sensors are now named "EV Charging Lifetime
  Energy"/"EV Charging Lifetime Cost" so their entity IDs match every
  reference. Existing installs: re-run the integration's Options >
  Install Dashboard (or rename the entities in the Entity registry) to
  apply the corrected IDs.

## [1.6.2] - 2026-08-11

### Fixed

- Notifications sent via `script.ev_send_notification` failed with
  "Template rendered invalid service" when the blueprint's "Notify Devices"
  field used device IDs. The script's service-name template used Jinja's
  literal `replace` (not a regex) to strip the `notify.` prefix, producing
  malformed services like `notify.mobile_app_notify.iphone_cansu`. It now
  uses `regex_replace`, so each target resolves to its real
  `notify.mobile_app_*` service and notifications (including the "extra
  keys not allowed @ data['data']" era) are delivered correctly.
- `binary_sensor.ev_vehicle_connected`/`ev_charging_active` mirrors now
  normalize configured matching states (lowercase + trim) before
  comparing, so legacy configs that saved values like "Awaiting start" or
  "Waiting for autorization" match the source sensor's actual states
  (e.g. `awaiting_start`, `awaiting_authorization`) instead of silently
  staying off. Also confirmed the full connected-state set including
  `charging`, `ready_to_charge` and `completed` is recognized — re-running
  Configure and marking those states keeps the connected mirror on for the
  whole session.
- Session bookkeeping survived notification failures: `ev_notify_charging_finished`
  called the notification script *before* `ev_log_charging_session`, so when a
  notify call failed the script aborted and the session was never logged — leaving
  `ev_session_tracking` stuck on and every later `charging_started` skipping the
  re-seed, which made the dashboard's "Current Session" show stale start
  time/energy/cost (e.g. a 4-day, 100-hour session) forever. The notify steps now
  use `continue_on_error: true` so the session is always logged and reset
  correctly.

## [1.6.1] - 2026-08-10

### Fixed

- `sensor.ev_charging_session_cost` used a Jinja template in its
  `unit_of_measurement`. Home Assistant stores that field verbatim for
  template sensors (it is not rendered), so the dashboard tile showed the
  raw template text after the value (e.g. "2.18 {{ ... }}"). The unit is
  now a literal `EUR` (matching the plugin's existing EUR price units), so
  the tile displays "2.18 EUR".

## [1.6.0] - 2026-08-10

### Added

- New **Dry Run** blueprint input (default off). When enabled, the
  automation evaluates every decision and writes it to the EV debug log
  but does NOT actually start or stop the charger. Useful for verifying
  triggers/conditions safely before letting the automation touch real
  hardware. All seven start/stop action call sites are guarded.

## [1.5.2] - 2026-08-07

### Fixed

- The `sensor.ev_charging_duration` template returned a TypeError
  ("can't subtract offset-naive and offset-aware datetimes") because it
  subtracted a timezone-naive `strptime` result from `now()`. It now
  compares naive/aware values via `timestamp()`, so the sensor renders
  correctly while charging.
- The `input_number.ev_charge_start_energy` helper had `max: 1000 kWh`,
  but the EV energy meter commonly reads far higher (e.g. 4600+ kWh), so
  seeding the start-energy helper during a charge raised
  "Invalid value ... (range 0.0 - 1000.0)" and halted the automation.
  Raised the max to 100000 kWh.
- `sensor.ev_charging_session_energy` used `state_class: measurement`
  with `device_class: energy`, which Home Assistant rejects (expects a
  `total_increasing`/`total` class). Changed to `total_increasing`.
- The integration registered dashboard services but shipped no
  `services.yaml`, producing "Failed to load services.yaml for
  integration: smart_ev_charging". Added `services.yaml`.
- `dashboard.load_dashboard_config()` did blocking file I/O
  (`Path.read_text`) inside the event loop. It now reads the bundled YAML
  in the executor.

## [1.5.1] - 2026-08-07

### Fixed

- The bundled `scripts/smart_ev_charging_scripts.yaml` used non-scalar
  values for some `example:` fields (`notify_targets` as a list and
  `notification_data` as a mapping). Home Assistant's script schema
  requires `example` to be a string, so `script.ev_send_notification`
  (and the notify scripts referencing it) failed to load with
  "value should be a string for dictionary value". These are now scalar
  strings, so all scripts load and the automation's notification actions
  work again.

## [1.5.0] - 2026-08-07

### Added

- The helper package and scripts are now auto-installed. The canonical
  `packages/smart_ev_charging.yaml` and
  `scripts/smart_ev_charging_scripts.yaml` moved into
  `custom_components/smart_ev_charging/` so they ship via HACS, and the
  integration copies them to `config/packages/` and `config/scripts/` on
  setup — no more manual file copying. On setup it also detects whether
  `configuration.yaml` contains the two include lines and, if not, the
  setup notification tells you exactly which two lines to add (HA still
  requires those plus a full restart to load packages/scripts; that can't
  be automated).

## [1.4.9] - 2026-08-06

### Fixed

- The bundled dashboard's sections layout is no longer misaligned. All
  sections used the default 1-column span, and the "Graphs" section held
  four stacked history-graphs, so it became a long, skinny column that
  stretched its row and pushed the other controls down with a blank gap in
  the middle. Every section now spans 2 columns and the graphs are split
  into two side-by-side sections ("Graphs" and "Battery & Energy"), so the
  layout forms balanced pairs across the width with no empty area.

## [1.4.8] - 2026-08-06

### Fixed

- The integration's **Options** menu now shows its three action labels
  ("Change the configured entities", "Install or update the dashboard",
  "Uninstall the dashboard"). The labels were translated under a wrong
  backend key (`menu` instead of `menu_options`), so only the heading and
  hint text appeared and the three buttons were blank.
- The automation blueprint no longer errors with *"unknown action:
  script.ev_debug_log"* when the companion scripts aren't loaded (e.g. the
  `script: !include_dir_merge_named scripts` include is missing). Each
  debug-log line is now guarded by `has_value('script.ev_debug_log')` and
  is simply skipped when the script isn't available.

## [1.4.7] - 2026-08-05

### Added

- The bundled dashboard can now be installed/updated and uninstalled from
  the integration's **Options** menu (Settings > Devices & Services >
  Smart EV Charging > Options), instead of only by pasting YAML. A running
  dashboard is automatically refreshed on every Home Assistant start.
  Also exposed as `smart_ev_charging.install_dashboard` and
  `smart_ev_charging.uninstall_dashboard` services.

## [1.4.6] - 2026-08-05

### Fixed

- The integration's logo is now visible in Home Assistant's store and the
  Devices & Services integration list. The `brand/` folder only shipped
  `logo.png`/`logo@2x.png`, but the storefront and integration list render
  the square **icon** image — which was missing — so nothing appeared.
  Added `icon.png` (256x256) and `icon@2x.png` (512x512), rasterized from
  the same square source art. Works with HA 2026.3+ (local brand images).

## [1.4.5] - 2026-08-05

### Fixed

- Reconfiguring the integration no longer forgets the states you selected
  in the "Status sensor states" step. The options flow only re-collects
  the entity pickers on its first step, so the previously saved
  matching-states values were dropped from the schema defaults — they are
  now carried over and stay pre-selected.

## [1.4.4] - 2026-08-05

### Fixed

- The "Status sensor states" picker now lists every state the source
  sensor has ever recorded (from its Home Assistant history), instead of
  only its current value. For a plain text status sensor — which exposes
  no `options` attribute — this previously meant the picker showed a
  single (current) value. History is gathered best-effort; if the recorder
  is unavailable or the entity is unrecorded, the picker falls back to the
  current state and still allows typing any value.

## [1.4.3] - 2026-08-05

### Added

- Automated `pytest` unit tests for the config-flow "matching states"
  pickers and binary-sensor state parsing (see the README *Testing*
  section; run with `python -m pytest`).

### Changed

- Added verbose `debug` logging to the "Status sensor states" config-flow
  pickers (source entity, resolved possible states, and which fields make
  it into the schema). Turn on debug logging for
  `custom_components.smart_ev_charging` while re-running the config flow
  to diagnose why the matching-states picker isn't showing.

## [1.4.2] - 2026-08-05

### Fixed

- The config flow's "Status sensor states" pickers were built with Home
  Assistant's `state` selector, which only shows a list of choices for
  `device_class: enum` sensors. For a plain text status sensor (e.g.
  Easee's charger status) HA knows no possible states, so the picker
  rendered as an empty/blank control — it looked like the "matching
  states" field had vanished entirely. The pickers now use a `select`
  selector (`multiple` + `custom_value`) pre-filled with the source
  entity's known states (its `options` attribute if present, plus its
  current state), and still let any unlisted state be typed. Existing
  comma-separated or list values remain fully supported.

## [1.4.1] - 2026-08-05

### Fixed

- The blueprint's action-splice workaround (empty `choose` whose `default`
  holds `start_charging_action`/`stop_charging_action`) placed `default`
  *inside* `choose`, so "Create Automation from blueprint" failed with
  `Message malformed: extra keys not allowed @ data['actions'][0]
  ['choose'][2]['sequence'][1]['choose'][0]['default']`. `choose` is a
  list and `default` must be a sibling key, i.e. `- choose: []` followed
  by `default: !input ...`. Corrected in all 7 splice points.

## [1.4.0] - 2026-08-05

### Changed

- The config flow's "matching states" fields for the `Vehicle connected`
  and `Charging active` sources are now a proper picker instead of a
  free-text comma-separated box. When you pick a status sensor (anything
  that isn't a plain `binary_sensor`), the flow continues to a new
  "Status sensor states" screen whose multi-select pickers list the states
  that source sensor can actually report — just tick the ones that count
  as active. No more hand-typing (or mistyping) state strings. Existing
  comma-separated values remain fully supported (stored data is unchanged,
  and `_parse_on_states` still accepts the legacy format), so no
  reconfiguration is needed for already-configured installs.

## [1.3.2] - 2026-08-05

### Fixed

- The blueprint's inline `start_charging_action`/`stop_charging_action`
  steps were written as `- !input start_charging_action` directly inside a
  `sequence`. An `action`-selector input resolves to a *list* of action
  steps, so splicing it in as a list element produced a nested list, and
  "Create Automation from blueprint" failed with `Message malformed:
  expected dictionary @ data['actions'][0]['choose'][...]['sequence'][1]`.
  The input is now expanded through an empty `choose` whose `default` is the
  input (e.g. `- choose:` / `  default: !input start_charging_action`),
  which flattens the action list back into the surrounding sequence.

## [1.3.1] - 2026-08-05

### Fixed

- The blueprint's `start_charging_action`/`stop_charging_action` steps
  were written as `- action: !input start_charging_action`, but an
  `action`-selector input resolves to a *list* of action steps, not a
  service-name string — this made "Create Automation" from the blueprint
  fail with `Message malformed: value should be a string for dictionary
  value @ ...['action']`. Fixed to splice the input in as a bare sequence
  item (`- !input start_charging_action`) everywhere it's used.
- The integration's auto-install now re-syncs the blueprint file on every
  setup/restart whenever its bundled content differs from what's on disk
  (previously "only if missing," like the dashboard) — otherwise a fix
  like this one would never reach anyone who'd already installed the
  broken 1.3.0 blueprint. The dashboard keeps the old, install-once
  behavior, since dashboards are commonly hand-customized after import.

## [1.3.0] - 2026-08-05

### Added

- The integration now auto-installs the blueprint and native dashboard
  on setup: `async_setup_entry` copies the bundled
  `custom_components/smart_ev_charging/blueprint/smart_ev_charging.yaml`
  and `.../dashboards/dashboard.yaml` into
  `<config>/blueprints/automation/smart_ev_charging/` and
  `<config>/dashboards/`, only if not already present (never overwrites),
  then posts a persistent notification listing what was installed and
  what's still manual (packages/scripts copy, `configuration.yaml`
  includes, restart).
- The dashboard is *not* auto-registered in the sidebar — Home Assistant
  has no stable, documented API for that from a custom integration (the
  internal Lovelace mechanism that exists has a known data-destroying
  bug), so the one remaining manual step is adding it via **Settings >
  Dashboards > + Add Dashboard > New dashboard from YAML**.

### Changed

- Moved the blueprint and native dashboard's canonical source into
  `custom_components/smart_ev_charging/` (no longer duplicated at a
  repo-root `blueprints/`/`dashboards/dashboard.yaml` path) so the
  bundled copy used for auto-install can't drift out of sync with a
  second copy. `dashboards/mushroom_dashboard.yaml` (not auto-installed)
  stays at the repo root.

## [1.2.0] - 2026-08-05

### Changed (requires reconfiguration)

- The blueprint's "Notify Service" text field (`notify_service`, typed
  service names like `notify.mobile_app_pixel_7`) is replaced by "Notify
  Devices" (`notify_targets`), a device picker supporting multiple
  devices — no typing required, and notifications now go to every
  selected device instead of just one. Existing automations built from
  the blueprint need this field re-selected after updating.
- **Minimum Home Assistant version raised to 2026.5.0** (was 2024.12.0):
  the device-picker notify dispatch (`notify.send_message` +
  `target: device_id`) depends on mobile_app notify entities, only added
  in that release. Installs on older Home Assistant versions cannot use
  this blueprint version.

### Added

- `script.ev_send_notification`: shared notification dispatch used by
  every notify-sending script, fanning a message out to all selected
  devices in one call.

## [1.1.1] - 2026-08-05

### Added

- README: FAQ entry and Troubleshooting row for status-sensor chargers
  (matching-states misconfiguration).
- `AGENTS.md`: process checklist for AI coding agents working in this
  repo — every user-facing change must update `README.md` and ship a
  version bump + git tag + GitHub release, proactively, not only when
  asked. `CLAUDE.md`'s versioning section now points to it instead of
  duplicating it.

## [1.1.0] - 2026-08-05

### Added

- "Vehicle connected" and "Charging active" now accept a text/enum status
  sensor (e.g. Easee's charger status, which reports `Charging`,
  `Completed`, `Car disconnected`, etc. instead of a boolean) in addition
  to a proper `binary_sensor`. Two new optional config flow fields,
  `vehicle_connected_states` and `charging_active_states`, take a
  comma-separated list of which raw state values count as "on" for that
  concept. Leaving them empty preserves the previous plain on/off
  behavior for binary_sensor sources — fully backward compatible.
- Tooltips (`data_description`) added to every config/options flow field,
  explaining what it's for and how it affects charging behavior.

## [1.0.0] - 2026-08-05

### Added

- Initial release of Smart EV Charging.
- `custom_components/smart_ev_charging/`: a real Home Assistant
  Integration (HACS category: Integration) with a config flow + options
  flow for picking your vehicle/charger/price entities once. Mirrors
  them onto stable entity IDs (`binary_sensor.ev_vehicle_connected`,
  `binary_sensor.ev_charging_active`, `binary_sensor.ev_price_cheap`,
  `sensor.ev_charging_price`, `sensor.ev_battery_percentage`,
  `sensor.ev_charging_power`, `sensor.ev_energy_meter`), plus a
  diagnostic `sensor.ev_smart_charging_config`. Ships its own brand logo.
- Core smart charging logic: wait for cheap electricity, start/stop
  automatically, resume automatically if price becomes cheap again.
- Generic blueprint automation compatible with any EV/charger
  integration — reads the integration's entities directly, so it only
  needs 4 inputs (start action, stop action, notify service, departure
  deadline lead time).
- Actionable, updating, tag-based mobile notifications (Android + iOS
  safe).
- Template sensors for charging duration, session energy, session cost,
  mode, state, estimated cost, and average price; lifetime statistics
  via `utility_meter` (today/week/month cost and energy, session count,
  average price/duration).
- Ready-to-import Lovelace dashboards (native Sections + Mushroom/
  ApexCharts).
- Nice-to-have features: target battery %, one-session manual override,
  calendar or fixed-time departure deadline, maximum acceptable price,
  low battery emergency charging, quiet hours, debug logging.
- README with installation, configuration, FAQ, and troubleshooting
  guides.
