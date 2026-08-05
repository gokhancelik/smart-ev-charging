# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
