# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
