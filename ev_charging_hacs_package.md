# Build a Production-Quality Home Assistant Smart EV Charging Package

I want you to build a complete Home Assistant package that provides smart EV charging based on dynamic electricity prices.

The goal is to create something that feels like a polished feature of Home Assistant, not a collection of random automations.

The package should be modular, well documented, easy to configure, and suitable for publishing on GitHub.

---

# Project structure

Create something similar to:

```
smart-ev-charging/
├── custom_components/          (optional later)
├── packages/
│   └── smart_ev_charging.yaml
├── blueprints/
├── dashboards/
│   ├── dashboard.yaml
│   └── mushroom_dashboard.yaml
├── scripts/
├── images/
├── README.md
├── hacs.json
├── LICENSE
└── CHANGELOG.md
```

Everything should be commented.

---

# Features

## Smart charging

Default behaviour:

When the charging cable is connected:

* Send a mobile notification.
* Do NOT immediately start charging.
* Wait until electricity price becomes cheap.

Notification:

Title

🔌 EV plugged in

Message

Charging is scheduled for the next cheap electricity period.

Button

⚡ Charge now

If the user presses the button:

* disable smart charging for this charging session
* immediately start charging

If the notification is ignored:

continue waiting until electricity becomes cheap.

---

## Start charging automatically

Trigger:

Price becomes cheap.

Conditions:

* vehicle connected
* smart charging enabled
* vehicle not already charging

Action:

Start charging.

---

## Stop charging automatically

Trigger:

Price becomes expensive.

Conditions:

* smart charging enabled
* charging active

Action:

Stop charging.

---

## Charging notification

When charging starts:

Replace the previous notification instead of creating another notification.

Use notification tags.

Notification should be persistent.

Example:

⚡ Charging

🔋 Battery: 58%

💶 Price: €0.18/kWh

🕒 Started: 22:46

⏱ Duration: 00:18

⚡ Power: 11 kW

🔌 Energy added: 5.2 kWh

Button:

⏹ Stop charging

The notification should update while charging.

---

## Charging finished

When charging stops:

Dismiss the persistent notification.

Optionally send:

✅ Charging finished

🔋 Added 18.4 kWh

⏱ Duration 2h 35m

💶 Average charging price €0.17/kWh

---

# Helpers

Create helpers for:

* follow_price
* charge_start_time
* charge_start_energy
* charge_start_price

Use helpers only where necessary.

Prefer Template Sensors whenever possible.

---

# Template sensors

Create sensors for:

Charging duration

Charging session energy

Charging session cost

Current charging mode

Current charging state

Current charging price

Estimated session cost

Any other useful derived values.

---

# Blueprint inputs

The blueprint should work with ANY EV or charger.

Inputs:

Vehicle connected binary sensor

Charging binary sensor

Current battery percentage sensor (optional)

Charging power sensor (optional)

Energy meter sensor (optional)

Current electricity price sensor

Cheap electricity binary sensor

Start charging action

Stop charging action

Notify service

Everything should be configurable.

No hardcoded entity IDs.

---

# Notification actions

Support actionable notifications.

Charge now

Stop charging

Dismiss notifications correctly.

Use notification tags so only one charging notification exists.

---

# Dashboard compatibility

Template sensors should work nicely with:

Mushroom cards

Bubble cards

Sections dashboard

Energy dashboard

---

## Dashboard

Create a ready-to-import Lovelace dashboard named **Smart EV Charging**.

The dashboard should work with Home Assistant's built-in Sections dashboard and use native cards where possible. If Mushroom cards are installed, provide an optional enhanced version.

### Overview section

Display:

* 🔋 Current battery percentage
* ⚡ Charging status
* 🔌 Plugged in / Unplugged
* 💶 Current electricity price
* 📈 Price status (Cheap / Expensive)
* 🚗 Charging mode (Smart / Manual)
* ⏱ Charging duration
* ⚡ Current charging power
* 🔌 Energy delivered during this session
* 💰 Estimated charging cost

### Session section

Show:

* Start time
* Start price
* Current price
* Average charging price
* Energy added
* Total session cost
* Charging efficiency (optional)

### Controls

Provide buttons for:

* ▶️ Charge now
* ⏹ Stop charging
* 📈 Enable Smart Charging
* ⏸ Disable Smart Charging

Buttons should call scripts instead of directly invoking services.

### Graphs

Include:

* Electricity price history
* Charging power history
* Battery percentage history
* Energy delivered history

If ApexCharts is installed, provide an enhanced dashboard version that uses it. Otherwise, use native History Graph cards.

### Statistics

Include cards showing:

* Today's charging cost
* This week's charging cost
* This month's charging cost
* Total energy charged
* Number of charging sessions
* Average charging price
* Average session duration

### Notification status

Display:

* Current notification state
* Current automation state
* Last charging session summary

### Debug section (collapsible)

Include:

* All helper entity values
* Template sensor values
* Automation last triggered
* Current charging decision
* Last notification action received

This section should make troubleshooting easy.

### Theme

Use a clean layout with consistent emojis that render well on Android and iOS.

Use colors naturally through Home Assistant state colors rather than hardcoding them.

The dashboard should require little or no manual editing after importing

---

# Android and iOS compatibility

Notifications MUST work on BOTH Android and iOS.

Only use notification features supported by both platforms whenever possible.

If platform-specific features are required, isolate them cleanly.

---

# Emoji / icons

Use emojis throughout the notifications because they improve readability.

Only use emojis that render correctly on both Android and Apple devices.

Examples:

🔌 Plugged in

⚡ Charging

⏹ Stop charging

▶️ Charge now

💶 Electricity price

🔋 Battery

🕒 Start time

⏱ Duration

📈 Smart charging

✅ Finished

❌ Error

⚠️ Warning

Do NOT use obscure or platform-specific emojis.

---

# Code quality

Requirements:

* YAML should be clean and readable.
* No duplicated logic.
* Use scripts where logic is reused.
* Use variables.
* Comment complex sections.
* Follow Home Assistant best practices.
* Use modern syntax.
* Support parallel execution safely.
* Handle race conditions.
* Handle Home Assistant restart gracefully.
* Restore helper state when appropriate.
* Validate missing optional entities.

---

# Documentation

Create a professional README containing:

Installation

Configuration

Blueprint setup

Supported integrations

Screenshots (placeholder)

Notification examples

FAQ

Troubleshooting

Roadmap

---

# Nice-to-have features

If feasible, also implement:

* Stop charging at target battery percentage.
* Resume charging automatically if price becomes cheap again.
* Manual override for one charging session only.
* Calendar departure time.
* Maximum acceptable price.
* Low battery emergency charging.
* Optional quiet hours.
* Statistics for previous charging sessions.
* Debug logging.
* Version number.

The final result should feel like a polished open-source Home Assistant project that could realistically become a HACS package in the future.
