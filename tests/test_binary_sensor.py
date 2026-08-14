"""Unit tests for the binary-sensor platform's state parsing and config."""

from __future__ import annotations

import pytest

from custom_components.smart_ev_charging.binary_sensor import (
    SmartEvChargingMirrorBinarySensor,
    _is_unavailable,
    _parse_on_states,
    async_setup_entry,
)
from custom_components.smart_ev_charging.const import (
    CONF_CHARGING_ACTIVE,
    CONF_CHEAP_PRICE,
    CONF_VEHICLE_CONNECTED,
)

from conftest import ConfigEntry, State


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("unknown", True),
        ("unknown 0", True),
        ("unknown  0", True),
        ("unavailable", True),
        ("Unavailable", True),
        ("UNKNOWN 0", True),
        ("charging", False),
        ("awaiting_start", False),
        ("  Charging  ", False),
        ("disconnected", False),
    ],
)
def test_is_unavailable(raw, expected):
    assert _is_unavailable(raw) is expected


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


def test_charging_mirror_added_before_connected():
    """ev_charging_active must be added (and readable via hass.states)
    before ev_vehicle_connected, which consults it through implied_on_by."""
    data = {
        CONF_VEHICLE_CONNECTED: "sensor.status",
        CONF_CHARGING_ACTIVE: "sensor.status",
        CONF_CHEAP_PRICE: "binary_sensor.cheap",
    }
    entry = ConfigEntry(data=data, options={})
    added: list = []
    import asyncio

    asyncio.run(async_setup_entry(_hass(), entry, added.extend))
    assert [e.entity_id for e in added] == [
        "binary_sensor.ev_charging_active",
        "binary_sensor.ev_vehicle_connected",
        "binary_sensor.ev_price_cheap",
    ]
    connected = added[1]
    assert connected._implied_on_by == "binary_sensor.ev_charging_active"


def test_implied_on_by_keeps_connected_on_while_charging(hass, add_state):
    """Charging implies plugged in: even a source state not in the (possibly
    misconfigured) on_states list stays 'on' while charging is active."""
    add_state("binary_sensor.ev_charging_active", "on")
    mirror = SmartEvChargingMirrorBinarySensor(
        ConfigEntry(data={}, options={}),
        "sensor.status",
        name="EV Vehicle Connected",
        object_id="ev_vehicle_connected",
        on_states=["awaiting_authorization", "awaiting_start"],
        implied_on_by="binary_sensor.ev_charging_active",
    )
    mirror.hass = hass
    mirror._apply_source_state(State("charging"))
    assert mirror._attr_available is True
    assert mirror._attr_is_on is True
    # Without charging active, a non-matching state is off again.
    add_state("binary_sensor.ev_charging_active", "off")
    mirror._apply_source_state(State("disconnected"))
    assert mirror._attr_is_on is False


def test_implied_on_by_tracks_charging_flip(hass, add_state):
    add_state("binary_sensor.ev_charging_active", "off")
    mirror = SmartEvChargingMirrorBinarySensor(
        ConfigEntry(data={}, options={}),
        "sensor.status",
        name="EV Vehicle Connected",
        object_id="ev_vehicle_connected",
        on_states=["awaiting_authorization", "awaiting_start", "charging"],
        implied_on_by="binary_sensor.ev_charging_active",
    )
    mirror.hass = hass
    mirror._apply_source_state(State("charging"))
    assert mirror._attr_is_on is True

