"""Offline truth-table tests for the package's session-energy template.

Tier-0 verification (see CLAUDE.md > "Verifying changes without releasing"):
renders the package's `sensor.ev_charging_session_energy` state template
with plain Jinja2 against synthetic entity states. The template takes the
max of the live session-energy source and the energy-meter delta so a slow
meter (Easee refreshes lifetime energy roughly hourly) never under-reports
and a stale live sensor near session close never wins over the final meter
delta. It must stay a pure predicate over `states()` so it renders offline.
"""

from __future__ import annotations

from pathlib import Path

import jinja2
import yaml

_PACKAGE = Path(__file__).resolve().parents[1] / (
    "custom_components"
    "/smart_ev_charging"
    "/packages"
    "/smart_ev_charging.yaml"
)


def _load_sensor() -> dict:
    pkg = yaml.safe_load(_PACKAGE.read_text(encoding="utf-8"))
    for block in pkg["template"]:
        for sensor in block.get("sensor", []):
            if sensor.get("unique_id") == "ev_charging_session_energy":
                return sensor
    raise AssertionError("ev_charging_session_energy sensor not found in package")


_SENSOR = _load_sensor()


def _render(template: str, states: dict[str, str]) -> str:
    env = jinja2.Environment()
    return env.from_string(template).render(
        states=lambda entity_id: states.get(entity_id, "unknown"),
    ).strip()


def _value(states: dict[str, str]) -> float | None:
    rendered = _render(_SENSOR["state"], states)
    if rendered.lower() in ("none", "unknown", "unavailable"):
        return None
    return float(rendered)


_BASE = {
    "sensor.ev_energy_meter": "5208.03",
    "input_number.ev_charge_start_energy": "5200.00",
}


def test_falls_back_to_meter_delta_without_live_sensor():
    assert _value(_BASE) == 8.03


def test_live_sensor_covers_stale_meter_mid_session():
    # Easee's meter hasn't ticked since session start; the live sensor has.
    states = {**_BASE, "sensor.ev_session_energy_live": "8.5"}
    assert _value(states) == 8.5


def test_meter_delta_wins_once_refreshed_at_close():
    # Meter's final refresh is ahead of the live sensor's last update.
    states = {**_BASE, "sensor.ev_energy_meter": "5209.50", "sensor.ev_session_energy_live": "8.5"}
    assert _value(states) == 9.5


def test_live_sensor_works_without_meter_configured():
    assert _value({"sensor.ev_session_energy_live": "3.25"}) == 3.25


def test_unavailable_when_neither_source_exists():
    assert _value({}) is None


def test_unavailable_when_both_sources_report_unknown():
    states = {
        "sensor.ev_energy_meter": "unavailable",
        "sensor.ev_session_energy_live": "unavailable",
    }
    assert _value(states) is None


def test_never_negative_when_meter_below_start():
    states = {
        "sensor.ev_energy_meter": "5199.00",
        "input_number.ev_charge_start_energy": "5200.00",
    }
    assert _value(states) == 0.0


def test_availability_true_when_only_live_sensor_available():
    rendered = _render(_SENSOR["availability"], {"sensor.ev_session_energy_live": "3.25"})
    assert rendered == "True"


def test_availability_false_when_no_source_available():
    assert _render(_SENSOR["availability"], {}) == "False"
