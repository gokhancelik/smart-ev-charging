# 🔌 Smart EV Charging for Home Assistant

Price-aware EV charging that waits for cheap electricity, notifies you along
the way, and stops automatically when price rises or your target battery
level is reached. Works with *any* EV/charger integration — you point it at
your existing vehicle/charger/price entities once, through a normal
Home Assistant config flow; a package and blueprint do the rest.

![version](https://img.shields.io/badge/version-1.4.6-blue)
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
│       ├── blueprint/
│       │   └── smart_ev_charging.yaml   # canonical blueprint, auto-installed on setup
│       └── dashboards/
│           └── dashboard.yaml           # canonical native dashboard, auto-installed on setup
├── packages/
│   └── smart_ev_charging.yaml     # helpers, template sensors, statistics
├── scripts/
│   └── smart_ev_charging_scripts.yaml
├── dashboards/
│   └── mushroom_dashboard.yaml    # enhanced (Mushroom + ApexCharts) — manual install only
├── images/                        # dashboard screenshots
├── hacs.json
├── README.md
├── LICENSE
└── CHANGELOG.md
```

The blueprint and native dashboard live inside `custom_components/smart_ev_charging/` — not duplicated at the repo root — because the integration copies them into your config directory automatically on setup (see [Configuration](#configuration)).

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

Requires **Home Assistant 2026.5 or newer** — the blueprint's "Notify
Devices" picker depends on mobile_app notify entities, which were only
added in that release.

### Via HACS (custom repository)

1. HACS > ⋮ > Custom repositories > add this repository URL, category
   **Integration**.
2. Install "Smart EV Charging" and restart Home Assistant. HACS copies
   `custom_components/smart_ev_charging/` into your config.
3. Manually copy the following from this repository into your Home
   Assistant config directory (HACS's Integration category only copies
   `custom_components/`):
   - `packages/smart_ev_charging.yaml` → `config/packages/`
   - `scripts/smart_ev_charging_scripts.yaml` → `config/scripts/`

   You do **not** need to copy the blueprint or dashboard — setting up
   the integration (next section) installs those automatically.

### Manual installation

1. Copy `custom_components/`, `packages/`, and `scripts/` into your Home
   Assistant config directory, merging with any existing folders.
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
| Charging active | ✅ | `binary_sensor.charger_charging` |
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
Weekend charging active" at that same status sensor. Whenever you
pick a status sensor (i.e. anything that isn't a plain `binary_sensor`),
the flow moves on to a **"Status sensor states"** screen with a picker for
each one — tick which raw states count as on for that concept (you can
select several, and a box is offered to type any state that isn't listed):

- Vehicle connected — matching states: `Charging`, `Completed`, `Awaiting Start`, `Ready to Charge`
  (anything that isn't `Car disconnected`/`Disconnected`)
- Charging active — matching states: `Charging`

The picker is pre-filled with the states your status sensor can actually
report, so you don't need to type (or mistype) them by hand. Leave it empty
if your source is a real binary_sensor — the integration then falls back to
plain on/off, unchanged from before.

The integration exposes what you picked under stable entity IDs
(`binary_sensor.ev_vehicle_connected`, `binary_sensor.ev_charging_active`,
`binary_sensor.ev_price_cheap`, `sensor.ev_charging_price`,
`sensor.ev_battery_percentage`, `sensor.ev_charging_power`,
`sensor.ev_energy_meter`, plus diagnostic `sensor.ev_smart_charging_config`)
— the package, scripts, blueprint, and dashboards all read from these, not
from your raw integration entities directly.

Finishing this step also copies the blueprint and native dashboard YAML
into your config directory automatically — check the "Smart EV Charging:
setup" notification (Settings > Notifications) for exactly what was
installed and what's still left to do.

### 2. Create the automation from the blueprint

**Settings > Automations & Scenes > Blueprints.** "Smart EV Charging"
should already be listed (it was copied into
`blueprints/automation/smart_ev_charging/` in step 1) — click **Create
Automation**. If it isn't listed yet, reload the Blueprints page or
restart Home Assistant once, or import it manually by pasting this URL
via **Import Blueprint**:

```
https://github.com/gokhancelik/smart-ev-charging/blob/master/custom_components/smart_ev_charging/blueprint/smart_ev_charging.yaml
```

Name the automation **Smart EV Charging** (the dashboards assume
`automation.smart_ev_charging` — rename the one reference in the
dashboard YAML if you use a different name). The blueprint doesn't ask
you to re-pick your vehicle/charger/price entities — it already reads
them from step 1. It only needs:

- **Start Charging Action** / **Stop Charging Action** — whatever action
  actually starts/stops your charger (a `switch.turn_on`, a charger
  integration's `start`/`stop` service, a script, …)
- **Notify Devices** — pick one or more phones/tablets running the
  Companion App from the device list (search by device name, no typing
  required). Add more than one to notify multiple people/devices —
  tapping Charge now / Stop charging on any of them works the same way.
  Requires **Home Assistant 2026.5 or newer** (mobile_app notify
  entities).
- **Departure Deadline Lead Time** — how many minutes before departure to
  force-start if price still isn't cheap (default 120)

### 3. Add the dashboard

Home Assistant doesn't give integrations a safe way to add a dashboard to
your sidebar automatically (it'd require touching undocumented Lovelace
internals with a known history of silently destroying dashboard data —
not a risk worth taking), so this one step stays manual: **Settings >
Dashboards > + Add Dashboard > New dashboard from YAML**, then paste the
contents of the file step 1 already copied to
`config/dashboards/smart_ev_charging_dashboard.yaml`.

Prefer the enhanced version instead? Copy `dashboards/mushroom_dashboard.yaml`
from this repository (not auto-installed) if you have
[Mushroom](https://github.com/piitaya/lovelace-mushroom) and
[ApexCharts Card](https://github.com/RomRider/apexcharts-card) installed
via HACS.

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
sensor; the config flow then shows a "Status sensor states" screen where
you tick which raw values count as on for that concept (see
[Configuration](#configuration)). No template YAML needed.

**Can I send notifications to more than one phone?**
Yes — the blueprint's "Notify Devices" field accepts multiple devices.
Every device gets the same actionable notifications (plugged in,
charging, finished), and pressing Charge now / Stop charging on any one
of them works the same way, since the button-press listener isn't tied
to a specific device.

**What happens if Home Assistant restarts mid-charge?**
All helpers restore their last state automatically. If charging was
already active before the restart, the blueprint backfills session
tracking on startup so duration/energy/cost stay accurate.

**Does the "Charge now" button disable smart charging permanently?**
No — it only overrides the current session. It resets automatically when
you unplug.

**Why doesn't the dashboard just appear in my sidebar automatically, like the blueprint does?**
Home Assistant has no officially supported, stable API for an integration
to register a Lovelace dashboard on your behalf — the mechanism that
exists is an undocumented internal of the `lovelace` component with a
known bug that can silently wipe existing dashboard data if used
incorrectly. Rather than risk that, the integration copies the dashboard
YAML into your config directory for you and leaves the one-click "Add
Dashboard from YAML" step to you. Blueprints don't have this problem —
they're just files Home Assistant reads from disk, so copying the file
*is* the whole installation.

---

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Smart EV Charging" doesn't appear in + Add Integration | `custom_components/smart_ev_charging/` is missing or HA wasn't restarted after install |
| Blueprint not listed under Settings > Blueprints after adding the integration | Check the "Smart EV Charging: setup" notification confirmed it was synced; verify `blueprints/automation/smart_ev_charging/smart_ev_charging.yaml` directly |
| Creating the automation from the blueprint fails with "Message malformed: value should be a string for dictionary value @ ...['action']" | You have a pre-1.3.1 copy of the blueprint. Restart Home Assistant once (the integration re-syncs the blueprint file on every restart, unlike the dashboard) or delete `blueprints/automation/smart_ev_charging/smart_ev_charging.yaml` and restart to force a fresh copy |
| Helpers/sensors from the package don't exist | `configuration.yaml` is missing the `packages:` include, or HA wasn't restarted |
| Scripts fail with "not found" | `configuration.yaml` is missing the `script: !include_dir_merge_named scripts` include |
| `sensor.ev_battery_percentage` / `sensor.ev_charging_power` / `sensor.ev_energy_meter` don't exist | That field was left empty in the integration's config flow — expected, it's optional |
| `binary_sensor.ev_vehicle_connected` etc. show "unavailable" | The source entity picked in the integration's config flow is itself unavailable — check it directly |
| `binary_sensor.ev_vehicle_connected`/`ev_charging_active` never turn on, even though the source status sensor changes | No "matching states" were marked for that source in the config flow's "Status sensor states" screen, or the ticked values don't match your source sensor's actual ones — re-open Configure and pick the exact states (matching is case-insensitive, but must otherwise match exactly) |
| Notifications never arrive | Confirm the device is still listed under Settings > Devices & Services > Mobile App, and that it's actually selected in the blueprint's "Notify Devices" field |
| Blueprint's "Notify Devices" field is empty or missing | Your Home Assistant version is older than 2026.5 — this field needs mobile_app notify entities, which didn't exist before that release |
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
- [x] Automated tests (`pytest`) — unit tests for the config-flow
      state-picker and binary-sensor state parsing; run with
      `python -m pytest` (see the *Testing* section below). A
      `pytest-homeassistant-custom-component` harness / CI YAML is still
      not in place, so the tests exercise the pure logic against stubbed
      Home Assistant modules rather than a running instance

---

## Testing

The integration ships a self-contained `pytest` suite for its pure logic —
the config-flow "matching states" pickers and the binary-sensor state
parsing. It depends only on `pytest` (Home Assistant packages are stubbed
out), so it runs anywhere without an HA install:

```
python -m pytest
```

The tests cover: which entity sources get a matching-states picker, how
possible state options are collected and de-duplicated, the structure of
the resulting `select`-selector schema, and how comma-separated/list
"on states" are normalised.

## Contributing

Issues and pull requests are welcome. Please keep YAML changes consistent
with the existing style (comments explaining *why*, not *what*; shared
logic in `scripts/`, not duplicated across the blueprint).

## License

[MIT](LICENSE)
