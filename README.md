# 🔌 Smart EV Charging for Home Assistant

Price-aware EV charging that waits for cheap electricity, notifies you along
the way, and stops automatically when price rises or your target battery
level is reached. Built as a Home Assistant **package** + **blueprint**, so
it works with *any* EV/charger integration — no custom component required.

![version](https://img.shields.io/badge/version-1.0.0-blue)
![license](https://img.shields.io/badge/license-MIT-green)

---

## Features

- ⚡ Waits for cheap electricity before charging, resumes automatically if
  price drops again
- 🔔 Actionable, tag-based mobile notifications that **update in place**
  instead of stacking up — works on Android **and** iOS
- 🎯 Optional stop-at-target-battery-%
- 💶 Optional maximum acceptable price cap
- 🔋 Optional low-battery emergency override
- 🕑 Optional calendar or fixed-time departure deadline (forces a charge if
  the cheap window hasn't arrived in time)
- 🌙 Optional quiet hours (suppresses non-critical notifications)
- 📊 Session and lifetime statistics (today/week/month cost & energy,
  session count, average price/duration) via `utility_meter`
- 📈 Ready-to-import dashboards — native Sections view, plus an enhanced
  Mushroom + ApexCharts version
- 🧩 No hardcoded entity IDs — one blueprint, any vehicle/charger

---

## Project structure

```
smart-ev-charging/
├── packages/
│   └── smart_ev_charging.yaml     # helpers, template sensors, statistics
├── blueprints/
│   └── automation/
│       └── smart_ev_charging.yaml # the price/plug automation logic
├── scripts/
│   └── smart_ev_charging_scripts.yaml
├── dashboards/
│   ├── dashboard.yaml             # native Sections dashboard
│   └── mushroom_dashboard.yaml    # enhanced (Mushroom + ApexCharts)
├── images/                        # dashboard screenshots
├── hacs.json
├── README.md
├── LICENSE
└── CHANGELOG.md
```

---

## How it works

1. You plug in your EV. If smart charging is enabled, you get a
   **🔌 EV plugged in** notification with a **⚡ Charge now** button.
   Ignore it and the package waits for a cheap price; tap it to charge
   immediately for this session only.
2. When your price sensor reports "cheap", charging starts automatically.
3. A single **⚡ Charging** notification appears, showing battery %,
   price, duration, power and energy delivered — it refreshes in place
   every 5 minutes rather than spamming new notifications.
4. When price becomes expensive (or your target battery % is reached),
   charging stops automatically and the notification is dismissed.
5. You optionally get a **✅ Charging finished** summary, and the session
   is logged into the statistics sensors.

---

## Installation

### Via HACS (custom repository)

1. HACS > ⋮ > Custom repositories > add this repository URL, category
   **Package**.
2. Install "Smart EV Charging". HACS copies `smart_ev_charging.yaml` into
   `config/packages/`.
3. Manually copy the following two folders from this repository into your
   Home Assistant config directory (HACS's "Package" category only copies
   the package file itself):
   - `blueprints/automation/smart_ev_charging.yaml` →
     `config/blueprints/automation/smart_ev_charging/smart_ev_charging.yaml`
   - `scripts/smart_ev_charging_scripts.yaml` → `config/scripts/`

### Manual installation

1. Copy `packages/`, `blueprints/`, and `scripts/` into your Home
   Assistant config directory, merging with any existing folders.
2. Make sure `configuration.yaml` includes:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages

   script: !include_dir_merge_named scripts
   ```

3. Restart Home Assistant (or reload YAML configuration: packages require
   a full restart).

---

## Configuration

### 1. Point the package at your real entities

Go to **Settings > Devices & Services > Helpers** and fill in the
following text helpers with the entity IDs from your vehicle/charger
integration (Easee, OCPP, Zaptec, Tesla, a generic smart plug, …):

| Helper | Required | Example |
|---|---|---|
| `input_text.ev_vehicle_connected_entity` | ✅ | `binary_sensor.charger_cable_connected` |
| `input_text.ev_charging_active_entity` | ✅ | `binary_sensor.charger_charging` |
| `input_text.ev_price_entity` | ✅ | `sensor.nordpool_kwh_price` |
| `input_text.ev_cheap_price_entity` | ✅ | `binary_sensor.price_is_cheap` |
| `input_text.ev_battery_entity` | optional | `sensor.car_battery_level` |
| `input_text.ev_power_entity` | optional | `sensor.charger_power` |
| `input_text.ev_energy_entity` | optional | `sensor.charger_energy_total` |
| `input_text.ev_departure_calendar_entity` | optional | `calendar.work_schedule` |

`cheap_price` is normally produced by your energy-price integration
(Nordpool, Tibber, ENTSO-E …) or a small template/threshold helper you
already have; this package only *reacts* to it.

### 2. Import and configure the blueprint

**Settings > Automations & Scenes > Blueprints > Import Blueprint**, paste:

```
https://github.com/gokhancelik/smart-ev-charging/blob/master/blueprints/automation/smart_ev_charging.yaml
```

Create a new automation from the blueprint, name it **Smart EV Charging**
(the dashboards assume `automation.smart_ev_charging` — rename the one
reference in the dashboard YAML if you use a different name), and fill in:

- **Vehicle Connected** / **Charging Active** — the same entities as above
- **Battery Percentage / Charging Power / Energy Meter** — optional, same
  as above
- **Current Electricity Price** / **Cheap Electricity** — same as above
- **Start Charging Action** / **Stop Charging Action** — whatever action
  actually starts/stops your charger (a `switch.turn_on`, a charger
  integration's `start`/`stop` service, a script, …)
- **Notify Service** — e.g. `notify.mobile_app_pixel_7`
- **Departure Deadline Lead Time** — how many minutes before departure to
  force-start if price still isn't cheap (default 120)

### 3. Add the dashboard

**Settings > Dashboards > + Add Dashboard > New dashboard from YAML**,
paste the contents of `dashboards/dashboard.yaml` (or
`dashboards/mushroom_dashboard.yaml` if you have
[Mushroom](https://github.com/piitaya/lovelace-mushroom) and
[ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed
via HACS).

### 4. Tune optional features

All optional behavior is off by default except where noted, controlled by
helpers under **Settings > Devices & Services > Helpers**:

- `input_boolean.ev_target_battery_enabled` + `input_number.ev_target_battery_percentage`
- `input_boolean.ev_max_price_enabled` + `input_number.ev_max_acceptable_price`
- `input_boolean.ev_quiet_hours_enabled` + `input_datetime.ev_quiet_hours_start` / `_end`
- `input_boolean.ev_low_battery_emergency_enabled` + `input_number.ev_low_battery_threshold`
- `input_datetime.ev_departure_time` (used when no calendar entity is set)
- `input_number.ev_battery_capacity_kwh` (only needed for the *estimated
  total session cost* projection)
- `input_boolean.ev_debug_logging` (mirrors decisions into the Logbook)

---

## Supported integrations

Any integration that exposes the entities below works — the package never
assumes a specific brand:

- **Charger / EV state**: Easee, OCPP, Zaptec, go-eCharger, Tesla, Wallbox,
  or a plain `binary_sensor`/`switch` you template yourself
- **Electricity price**: Nordpool, Tibber, ENTSO-E, Energi Data Service, or
  a custom template sensor
- **Notifications**: the official Home Assistant Companion App on Android
  and iOS (actionable notifications required)

---

## Notification examples

**Plugged in**

> 🔌 **EV plugged in**
> Charging is scheduled for the next cheap electricity period.
> `[⚡ Charge now]`

**Charging (persistent, updates in place)**

> ⚡ **Charging**
> 🔋 Battery: 58%
> 💶 Price: €0.18/kWh
> 🕒 Started: 22:46
> ⏱ Duration: 00:18
> ⚡ Power: 11 kW
> 🔌 Energy added: 5.2 kWh
> `[⏹ Stop charging]`

**Finished**

> ✅ **Charging finished**
> 🔋 Added 18.4 kWh
> ⏱ Duration 2h 35m
> 💶 Average charging price €0.17/kWh

---

## Screenshots

_Add your own screenshots to `images/` and reference them here — e.g.:_

```markdown
![Overview](images/overview.png)
![Debug section](images/debug.png)
```

---

## FAQ

**Does this support multiple vehicles?**
Not out of the box in v1.0.0 — the package's helpers are single-vehicle.
For a second car, duplicate `packages/smart_ev_charging.yaml` and every
entity ID inside it with a different prefix (e.g. `ev2_`), and import a
second blueprint instance pointing at the new helpers. True multi-vehicle
support is on the [roadmap](#roadmap).

**Why is there no "charging efficiency" sensor?**
Efficiency (AC energy drawn vs. DC energy stored) needs two separate
meters. Most integrations only expose one energy sensor, so a computed
"efficiency" would be misleading. If you have both readings, it's a
one-line addition to the `template:` section.

**Can I use a fixed price threshold instead of a "cheap" binary sensor?**
Yes — create a small template `binary_sensor` that compares your price
sensor to a threshold, and point `ev_cheap_price_entity` at it.

**What happens if Home Assistant restarts mid-charge?**
All helpers restore their last state automatically. If charging was
already active before the restart, the blueprint backfills session
tracking on startup so duration/energy/cost stay accurate.

**Does the "Charge now" button disable smart charging permanently?**
No — it only overrides the current session. It resets automatically when
you unplug.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Helpers/sensors don't exist after install | `configuration.yaml` is missing the `packages:` include, or HA wasn't restarted |
| Scripts fail with "not found" | `configuration.yaml` is missing the `script: !include_dir_merge_named scripts` include |
| Sensors show "unavailable" | The matching `input_text.ev_*_entity` config helper is empty or points at a nonexistent entity |
| Notifications never arrive | Check `notify_service` in the blueprint matches Settings > Devices & Services > your mobile device exactly (`notify.mobile_app_...`) |
| "Charge now"/"Stop charging" notification buttons do nothing | Confirm the Companion App has notification permissions and background access; check `input_text.ev_last_notification_action` in the Debug dashboard section to see if the event even arrived |
| Dashboard shows "entity not found" for `automation.smart_ev_charging` | You renamed the automation created from the blueprint — update that one reference in the dashboard YAML |
| Duration/cost sensors look wrong after a restart | Confirm `input_boolean.ev_session_tracking` reflects the actual charging state — toggle `charging_active` off/on once to resync |

Turn on `input_boolean.ev_debug_logging` and watch the Logbook, or check
the "🐞 Debug" dashboard section — it surfaces every raw helper, every
template sensor, and the automation's last decision in one place.

---

## Roadmap

- [ ] Native `custom_components` integration with a UI config flow
      (multi-vehicle, no manual helper editing)
- [ ] Direct Energy Dashboard cost integration
- [ ] Built-in fixed-price-threshold helper (no separate template needed)
- [ ] Additional language translations for notifications
- [ ] Home Assistant Energy Dashboard "EV charging" native card support
- [ ] Automated tests / CI YAML linting

---

## Contributing

Issues and pull requests are welcome. Please keep YAML changes consistent
with the existing style (comments explaining *why*, not *what*; shared
logic in `scripts/`, not duplicated across the blueprint).

## License

[MIT](LICENSE)
