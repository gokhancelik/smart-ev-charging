"""Unit tests for the binary-sensor platform's state parsing and config."""

from __future__ import annotations

import pytest

from custom_components.smart_ev_charging.binary_sensor import (
    _parse_on_states,
    async_setup_entry,
)
from custom_components.smart_ev_charging.const import (
    CONF_CHARGING_ACTIVE,
    CONF_CHEAP_PRICE,
    CONF_VEHICLE_CONNECTED,
)

from conftest import ConfigEntry


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, []),
        ("", []),
        ("Charging", ["charging"]),
        ("Charging,Completed", ["charging", "completed"]),
        ("Charging, Completed,  Idle", ["charging", "completed", "idle"]),
        (["Charging", "Completed"], ["charging", "completed"]),
        (["Charging"], ["charging"]),
        ("a,b c", ["a", "b c"]),
    ],
)
def test_parse_on_states(raw, expected):
    assert _parse_on_states(raw) == expected


def _mirror_ids(entry: ConfigEntry) -> dict[str, str]:
    """Run async_setup_entry, returning object_id -> source entity."""
    added: list = []

    def _add(entities) -> None:
        added.extend(entities)

    import asyncio

    asyncio.run(async_setup_entry(_hass(), entry, _add))
    return {e.entity_id: e._source_entity_id for e in added}


class _States:
    def get(self, entity_id):
        return None


class _Hass:
    def __init__(self):
        self.states = _States()


def _hass():
    return _Hass()


def test_options_value_wins_over_data():
    data = {
        CONF_VEHICLE_CONNECTED: "sensor.old_vc",
        CONF_CHARGING_ACTIVE: "sensor.old_ca",
        CONF_CHEAP_PRICE: "binary_sensor.old_cp",
    }
    options = {
        CONF_VEHICLE_CONNECTED: "sensor.new_vc",
        CONF_CHARGING_ACTIVE: "sensor.new_ca",
        CONF_CHEAP_PRICE: "binary_sensor.new_cp",
    }
    entry = ConfigEntry(data=data, options=options)
    mirrors = _mirror_ids(entry)
    assert mirrors["binary_sensor.ev_vehicle_connected"] == "sensor.new_vc"
    assert mirrors["binary_sensor.ev_charging_active"] == "sensor.new_ca"
    assert mirrors["binary_sensor.ev_price_cheap"] == "binary_sensor.new_cp"


def test_empty_options_falls_back_to_data():
    data = {
        CONF_VEHICLE_CONNECTED: "sensor.old_vc",
        CONF_CHARGING_ACTIVE: "sensor.old_ca",
        CONF_CHEAP_PRICE: "binary_sensor.old_cp",
    }
    entry = ConfigEntry(data=data, options={})
    mirrors = _mirror_ids(entry)
    assert mirrors["binary_sensor.ev_vehicle_connected"] == "sensor.old_vc"

