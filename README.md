# 🔌 Smart EV Charging for Home Assistant

Price-aware EV charging that waits for cheap electricity, notifies you along
the way, and stops automatically when price rises or your target battery
level is reached. Works with *any* EV/charger integration — you point it at
your existing vehicle/charger/price entities once, through a normal
Home Assistant config flow; a package and blueprint do the rest.

![version](https://img.shields.io/badge/version-1.1.1-blue)
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
- 🧩 No hardcoded entity IDs — configure your vehicle/charger/price
  entities once, through a UI config flow

---

## Project structure

```
smart-ev-charging/
├── custom_components/
│   └── smart_ev_charging/         # HACS Integration: config flow + entity mirrors
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
   **Integration**.
2. Install "Smart EV Charging" and restart Home Assistant. HACS copies
   `custom_components/smart_ev_charging/` into your config.
3. Manually copy the following two items from this repository into your
   Home Assistant config directory (HACS's Integration category only
   copies `custom_components/`, not the package/blueprint/scripts/
   dashboards that round out the feature):
   - `packages/smart_ev_charging.yaml` → `config/packages/`
   - `blueprints/automation/smart_ev_charging.yaml` →
     `config/blueprints/automation/smart_ev_charging/smart_ev_charging.yaml`
   - `scripts/smart_ev_charging_scripts.yaml` → `config/scripts/`

### Manual installation

1. Copy `custom_components/`, `packages/`, `blueprints/`, and `scripts/`
   into your Home Assistant config directory, merging with any existing
   folders.
2. Make sure `configuration.yaml` includes:

   ```yaml
   homeassistant:
     packages: !include_dir_named packages

   script: !include_dir_merge_named scripts
   ```

3. Restart Home Assistant (packages and custom integrations both require
   a full restart, not just a YAML reload).

---

## Configuration

### 1. Set up the integration

**Settings > Devices & Services > + Add Integration > Smart EV Charging.**
A form asks for the entities from your vehicle/charger and price
integration (Easee, OCPP, Zaptec, Tesla, a generic smart plug, Nordpool,
Tibber, …):

| Field | Required | Example |
|---|---|---|
| Vehicle connected | ✅ | `binary_sensor.charger_cable_connected` |
| Vehicle connected — matching states | optional | `Charging, Completed, Awaiting Start` |
| Charging active | ✅ | `binary_sensor.charger_charging` |
| Charging active — matching states | optional | `Charging` |
| Current electricity price | ✅ | `sensor.nordpool_kwh_price` |
| Cheap electricity | ✅ | `binary_sensor.price_is_cheap` |
| Battery percentage | optional | `sensor.car_battery_level` |
| Charging power | optional | `sensor.charger_power` |
| Energy meter | optional | `sensor.charger_energy_total` |
| Departure calendar | optional | `calendar.work_schedule` |

"Cheap electricity" is normally produced by your energy-price integration
or a small template/threshold binary_sensor you already have — this
package only *reacts* to it. Only one instance of the integration is
allowed (single-vehicle for now — see [FAQ](#faq)). To change any of
these entities later, open the integration's **Configure** option instead
of re-adding it.

**Chargers without separate connected/charging binary sensors** (Easee,
some OCPP/go-eCharger/Wallbox setups) commonly expose a single text status
sensor instead — e.g. Easee's charger status reports `Charging`,
`Completed`, `Car disconnected`, `Awaiting Start`, etc. Point "Vehicle
connected" and "Charging active" at that same status sensor, then fill in
the matching "matching states" field with a comma-separated list of which
raw values count as on for that concept:

- Vehicle connected — matching states: `Charging, Completed, Awaiting Start, Ready to Charge`
  (anything that isn't `Car disconnected`/`Disconnected`)
- Charging active — matching states: `Charging`

Leave both "matching states" fields empty if your source is a real
binary_sensor — the integration then falls back to plain on/off, unchanged
from before.

The integration exposes what you picked under stable entity IDs
(`binary_sensor.ev_vehicle_connected`, `binary_sensor.ev_charging_active`,
`binary_sensor.ev_price_cheap`, `sensor.ev_charging_price`,
`sensor.ev_battery_percentage`, `sensor.ev_charging_power`,
`sensor.ev_energy_meter`, plus diagnostic `sensor.ev_smart_charging_config`)
— the package, scripts, blueprint, and dashboards all read from these, not
from your raw integration entities directly.

### 2. Import and configure the blueprint

**Settings > Automations & Scenes > Blueprints > Import Blueprint**, paste:

```
https://github.com/gokhancelik/smart-ev-charging/blob/master/blueprints/automation/smart_ev_charging.yaml
```

Create a new automation from the blueprint, name it **Smart EV Charging**
(the dashboards assume `automation.smart_ev_charging` — rename the one
reference in the dashboard YAML if you use a different name). The
blueprint no longer asks you to re-pick your vehicle/charger/price
entities — it already reads them from step 1. It only needs:

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

Any integration that exposes the entities below works — the integration's
config flow and the package never assume a specific brand:

- **Charger / EV state**: Easee, OCPP, Zaptec, go-eCharger, Tesla, Wallbox,
  or a plain `binary_sensor`/`switch` you template yourself. Both proper
  binary sensors and single text-status sensors (Easee-style) are
  supported natively — see [Configuration](#configuration).
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
Not out of the box — the integration only allows a single config entry,
and the package's helpers are single-vehicle. For a second car, duplicate
`packages/smart_ev_charging.yaml` and every entity ID inside it with a
different prefix (e.g. `ev2_`), duplicate `custom_components/smart_ev_charging`
under a new domain, and import a second blueprint instance pointing at the
new helpers/entities. True multi-vehicle support is on the
[roadmap](#roadmap).

**Why is there no "charging efficiency" sensor?**
Efficiency (AC energy drawn vs. DC energy stored) needs two separate
meters. Most integrations only expose one energy sensor, so a computed
"efficiency" would be misleading. If you have both readings, it's a
small addition to `custom_components/smart_ev_charging/sensor.py`.

**Can I use a fixed price threshold instead of a "cheap" binary sensor?**
Yes — create a small template `binary_sensor` that compares your price
sensor to a threshold, and point the integration's "Cheap electricity"
field at it (Settings > Devices & Services > Smart EV Charging >
Configure).

**My charger (e.g. Easee) only exposes one status sensor, not separate
"connected"/"charging" binary sensors — do I need to write a template?**
No. Point "Vehicle connected" and "Charging active" at that same status
sensor and fill in the matching "matching states" field (comma-separated
raw values that count as on for that concept) — see
[Configuration](#configuration). No template YAML needed.

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
| "Smart EV Charging" doesn't appear in + Add Integration | `custom_components/smart_ev_charging/` is missing or HA wasn't restarted after install |
| Helpers/sensors from the package don't exist | `configuration.yaml` is missing the `packages:` include, or HA wasn't restarted |
| Scripts fail with "not found" | `configuration.yaml` is missing the `script: !include_dir_merge_named scripts` include |
| `sensor.ev_battery_percentage` / `sensor.ev_charging_power` / `sensor.ev_energy_meter` don't exist | That field was left empty in the integration's config flow — expected, it's optional |
| `binary_sensor.ev_vehicle_connected` etc. show "unavailable" | The source entity picked in the integration's config flow is itself unavailable — check it directly |
| `binary_sensor.ev_vehicle_connected`/`ev_charging_active` never turn on, even though the source status sensor changes | The "matching states" field doesn't match your source sensor's actual values — open the source entity's state history and copy the exact text (matching is case-insensitive, but must otherwise match exactly) |
| Notifications never arrive | Check `notify_service` in the blueprint matches Settings > Devices & Services > your mobile device exactly (`notify.mobile_app_...`) |
| "Charge now"/"Stop charging" notification buttons do nothing | Confirm the Companion App has notification permissions and background access; check `input_text.ev_last_notification_action` in the Debug dashboard section to see if the event even arrived |
| Dashboard shows "entity not found" for `automation.smart_ev_charging` | You renamed the automation created from the blueprint — update that one reference in the dashboard YAML |
| Duration/cost sensors look wrong after a restart | Confirm `input_boolean.ev_session_tracking` reflects the actual charging state — toggle `charging_active` off/on once to resync |

Turn on `input_boolean.ev_debug_logging` and watch the Logbook, or check
the "🐞 Debug" dashboard section — it surfaces every raw helper, every
template sensor, and the automation's last decision in one place.

---

## Roadmap

- [x] Native `custom_components` integration with a UI config flow
      (no manual helper editing)
- [ ] Multi-vehicle support (multiple config entries, prefixed entities)
- [ ] Direct Energy Dashboard cost integration
- [ ] Built-in fixed-price-threshold helper (no separate template needed)
- [ ] Additional language translations for notifications and the config
      flow (currently English only)
- [ ] Home Assistant Energy Dashboard "EV charging" native card support
- [ ] Automated tests (`pytest-homeassistant-custom-component`) / CI YAML
      linting — the integration is currently validated only for Python
      syntax and JSON well-formedness, not against a running Home
      Assistant instance

---

## Contributing

Issues and pull requests are welcome. Please keep YAML changes consistent
with the existing style (comments explaining *why*, not *what*; shared
logic in `scripts/`, not duplicated across the blueprint).

## License

[MIT](LICENSE)
