# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-08-05

### Changed (breaking)

- Distribution moved from HACS's "Package" category (removed by HACS) to
  a real `custom_components/smart_ev_charging` Integration. See README
  "Upgrading from 1.x".
- Entity configuration moved from 8 manually-filled `input_text.ev_*_entity`
  helpers to the integration's config flow (Settings > Devices & Services
  > + Add Integration > Smart EV Charging), with an options flow to
  change entities later.
- The blueprint automation now has 4 inputs instead of 11 — vehicle,
  charger, and price entities are read directly from the integration's
  stable mirror entities instead of being re-selected per installation.

### Added

- `custom_components/smart_ev_charging/`: config flow + options flow,
  and sensor/binary_sensor platforms mirroring the configured entities
  onto stable IDs (`binary_sensor.ev_vehicle_connected`,
  `binary_sensor.ev_charging_active`, `binary_sensor.ev_price_cheap`,
  `sensor.ev_charging_price`, `sensor.ev_battery_percentage`,
  `sensor.ev_charging_power`, `sensor.ev_energy_meter`), plus a
  diagnostic `sensor.ev_smart_charging_config`.

### Removed

- The `input_text.ev_vehicle_connected_entity`, `ev_charging_active_entity`,
  `ev_price_entity`, `ev_cheap_price_entity`, `ev_battery_entity`,
  `ev_power_entity`, `ev_energy_entity`, and `ev_departure_calendar_entity`
  helpers, and their corresponding template sensors, from the package.

## [1.0.0] - 2026-08-04

### Added

- Initial release of the Smart EV Charging package.
- Core smart charging logic: wait for cheap electricity, start/stop automatically.
- Generic blueprint automation compatible with any EV / charger integration.
- Actionable, updating, tag-based mobile notifications (Android + iOS safe).
- Template sensors for charging duration, session energy, session cost, mode,
  state, current price, estimated cost, and average price.
- Ready-to-import Lovelace dashboards (native Sections + Mushroom/ApexCharts).
- Nice-to-have features: target battery %, resume on price drop, one-session
  manual override, calendar departure time, maximum acceptable price, low
  battery emergency charging, quiet hours, session statistics, debug logging.
- README with installation, configuration, FAQ, and troubleshooting guides.
