# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
