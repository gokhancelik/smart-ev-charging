"""Unit tests for the sensor platform's config resolution.

Locks in the reader-side contract behind §3.2 of HANDOFF-2.md: once
entry.options exist they win wholesale over entry.data, so a field the
user cleared (key absent from options but still present in data) stays
cleared instead of being resurrected.
"""

from __future__ import annotations

from custom_components.smart_ev_charging.const import (
    CONF_BATTERY,
    CONF_CHARGING_ACTIVE,
    CONF_CHEAP_PRICE,
    CONF_PRICE,
    CONF_VEHICLE_CONNECTED,
)
from custom_components.smart_ev_charging.sensor import async_setup_entry

from conftest import ConfigEntry


def _full_config(entity: str) -> dict:
    """A complete, valid config sharing one entity across the mirror sensors."""
    return {
        CONF_VEHICLE_CONNECTED: entity,
        CONF_CHARGING_ACTIVE: entity,
        CONF_PRICE: entity,
        CONF_CHEAP_PRICE: "binary_sensor.cheap",
        CONF_BATTERY: entity,
    }


def _mirror_ids(hass, entry: ConfigEntry) -> set[str]:
    added: list = []

    def _add(entities) -> None:
        added.extend(entities)

    import asyncio

    asyncio.run(async_setup_entry(hass, entry, _add))
    return {e.entity_id for e in added}


def test_empty_options_falls_back_to_data(hass):
    data = _full_config("sensor.data_battery")
    entry = ConfigEntry(data=data, options={})
    ids = _mirror_ids(hass, entry)
    # With no options the battery mirror is created from data.
    assert "sensor.ev_battery_percentage" in ids
    assert "sensor.ev_smart_charging_config" in ids


def test_options_missing_cleared_field_does_not_resurrect_from_data(hass):
    data = _full_config("sensor.old_battery")
    # User cleared the battery picker, so options omits CONF_BATTERY while
    # still holding the other kept fields (a non-empty dict).
    options = {k: v for k, v in data.items() if k != CONF_BATTERY}
    entry = ConfigEntry(data=data, options=options)
    ids = _mirror_ids(hass, entry)
    assert "sensor.ev_battery_percentage" not in ids


def test_options_value_wins_over_data(hass):
    data = _full_config("sensor.data_value")
    options = {**data, CONF_BATTERY: "sensor.options_value"}
    entry = ConfigEntry(data=data, options=options)
    ids = _mirror_ids(hass, entry)
    assert "sensor.ev_battery_percentage" in ids
