"""Unit tests for the Smart EV Charging config-flow state-picker logic.

These cover the "matching states" feature: deciding which sources need a
state picker (only non-binary_sensor sources), how possible states are
collected, and the structure of the resulting `select`-selector schema.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.smart_ev_charging.config_flow import (
    CONF_CHARGING_ACTIVE_STATES,
    CONF_VEHICLE_CONNECTED_STATES,
    SmartEvChargingConfigFlow,
    _build_states_schema,
    _clean,
    _current_states_list,
    _entity_state_options,
    _is_non_binary_source,
)
from homeassistant.helpers import selector as selector_mod


def _run(coro):
    return asyncio.run(coro)


def _flow(hass):
    flow = SmartEvChargingConfigFlow()
    flow.hass = hass
    return flow


def _full_user_input():
    return {
        "vehicle_connected": "sensor.charger_status",
        "charging_active": "binary_sensor.charging_active",
        "price": "sensor.energy_price",
        "cheap_price": "binary_sensor.cheap_price",
    }


# ---------------------------------------------------------------- _is_non_binary_source


@pytest.mark.parametrize(
    "entity_id,expected",
    [
        ("sensor.easee_charger_status", True),
        ("select.charger_mode", True),
        ("binary_sensor.vehicle_connected", False),
        (None, False),
        ("", False),
    ],
)
def test_is_non_binary_source(entity_id, expected):
    assert _is_non_binary_source(entity_id) is expected


# ----------------------------------------------------------------- _current_states_list


def test_current_states_list_handles_list():
    assert _current_states_list({"k": ["Charging", "Completed"]}, "k") == [
        "Charging",
        "Completed",
    ]


def test_current_states_list_handles_comma_string():
    assert _current_states_list({"k": "Charging, Completed,  Idle"}, "k") == [
        "Charging",
        "Completed",
        "Idle",
    ]


def test_current_states_list_empty_returns_none():
    assert _current_states_list({"k": ""}, "k") is None
    assert _current_states_list({"k": None}, "k") is None
    assert _current_states_list({}, "k") is None


def test_current_states_list_blank_string_returns_none():
    assert _current_states_list({"k": " , , "}, "k") is None


# ------------------------------------------------------------------ _entity_state_options


def test_entity_state_options_missing_entity(hass):
    assert _entity_state_options(hass, "sensor.missing") == []


def test_entity_state_options_uses_options_attr(hass, add_state):
    add_state("sensor.charger", "Charging", {"options": ["Charging", "Idle"]})
    assert _entity_state_options(hass, "sensor.charger") == ["Charging", "Idle"]


def test_entity_state_options_uses_current_option(hass, add_state):
    add_state("select.charger", "Idle", {"current_option": "Idle", "options": ["A", "B"]})
    assert _entity_state_options(hass, "select.charger") == ["A", "B", "Idle"]


def test_entity_state_options_appends_current_state(hass, add_state):
    add_state("sensor.charger", "Charging")
    assert _entity_state_options(hass, "sensor.charger") == ["Charging"]


def test_entity_state_options_dedupes(hass, add_state):
    add_state(
        "sensor.charger", "Charging", {"options": ["Charging", "Charging", "Idle"]}
    )
    assert _entity_state_options(hass, "sensor.charger") == ["Charging", "Idle"]


def test_entity_state_options_ignores_unknown_state(hass, add_state):
    add_state("sensor.charger", "unknown", {"options": ["Charging", "Idle"]})
    assert _entity_state_options(hass, "sensor.charger") == ["Charging", "Idle"]


def test_entity_state_options_merges_history_after_current(hass, add_state):
    add_state("sensor.charger", "Disconnected")
    history = ["Disconnected", "Charging", "Completed", "Disconnected"]
    assert _entity_state_options(hass, "sensor.charger", history) == [
        "Disconnected",
        "Charging",
        "Completed",
    ]


def test_entity_state_options_history_when_no_state(hass):
    assert _entity_state_options(hass, "sensor.charger", ["A", "B"]) == ["A", "B"]


# ------------------------------------------------------------------ _build_states_schema


def test_build_states_schema_none_for_binary_sources(hass):
    captured = {
        "vehicle_connected": "binary_sensor.vehicle_connected",
        "charging_active": "binary_sensor.charging_active",
    }
    assert _build_states_schema(hass, captured) is None


def test_build_states_schema_includes_sensor_sources(hass):
    captured = {
        "vehicle_connected": "sensor.charger_status",
        "charging_active": "binary_sensor.charging_active",
    }
    result = _build_states_schema(hass, captured)
    assert result is not None
    field_keys = [k.schema for k in result.schema]
    assert CONF_VEHICLE_CONNECTED_STATES in field_keys
    assert CONF_CHARGING_ACTIVE_STATES not in field_keys


def test_build_states_schema_uses_select_selector(hass):
    captured = {
        "vehicle_connected": "sensor.charger_status",
        "charging_active": "sensor.charger_active",
    }
    result = _build_states_schema(hass, captured)
    assert result is not None
    for validator in result.schema.values():
        assert isinstance(validator, selector_mod.Selector)
        assert validator.config["select"]["multiple"] is True
        assert validator.config["select"]["custom_value"] is True


def test_build_states_schema_options_filled(hass, add_state):
    add_state("sensor.charger_status", "Charging", {"options": ["Charging", "Idle"]})
    captured = {
        "vehicle_connected": "sensor.charger_status",
        "charging_active": "binary_sensor.charging_active",
    }
    result = _build_states_schema(hass, captured)
    validator = result.schema[CONF_VEHICLE_CONNECTED_STATES]
    assert validator.config["select"]["options"] == ["Charging", "Idle"]


def test_build_states_schema_includes_history_options(hass, add_state):
    add_state("sensor.charger_status", "Idle")
    captured = {
        "vehicle_connected": "sensor.charger_status",
        "charging_active": "binary_sensor.charging_active",
    }
    result = _build_states_schema(
        hass, captured, {"sensor.charger_status": ["Charging", "Completed"]}
    )
    validator = result.schema[CONF_VEHICLE_CONNECTED_STATES]
    # current state + history, de-duplicated, current first
    assert validator.config["select"]["options"] == ["Idle", "Charging", "Completed"]


# ----------------------------------------------------------------- flow integration


def test_async_step_user_binary_sources_creates_entry(hass):
    flow = _flow(hass)
    input_ = _full_user_input()
    input_["vehicle_connected"] = "binary_sensor.vehicle_connected"
    result = _run(flow.async_step_user(input_))
    assert result["type"] == "create_entry"


def test_async_step_user_sensor_source_leads_to_states_step(hass):
    flow = _flow(hass)
    result = _run(flow.async_step_user(_full_user_input()))
    assert result["type"] == "form"
    assert result["step_id"] == "states"


def test_clean_drops_empty_values():
    assert _clean({"a": "x", "b": "", "c": [], "d": None}) == {"a": "x"}


def test_options_flow_preserves_stored_states_as_defaults(hass):
    """Reconfiguring keeps previously-selected states pre-filled in the states schema."""
    from custom_components.smart_ev_charging.config_flow import (
        SmartEvChargingOptionsFlow,
    )
    from homeassistant.config_entries import ConfigEntry

    flow = SmartEvChargingOptionsFlow()
    flow.hass = hass
    flow.config_entry = ConfigEntry(
        data={
            "vehicle_connected": "sensor.charger_status",
            "charging_active": "binary_sensor.charging_active",
        },
        options={"vehicle_connected_states": ["Charging", "Completed"]},
    )
    result = _run(
        flow.async_step_init(
            {
                "vehicle_connected": "sensor.charger_status",
                "charging_active": "binary_sensor.charging_active",
            }
        )
    )
    assert result["type"] == "form"
    assert result["step_id"] == "states"
    field_keys = [k.schema for k in result["data_schema"].schema]
    assert CONF_VEHICLE_CONNECTED_STATES in field_keys
    assert CONF_CHARGING_ACTIVE_STATES not in field_keys
    # previously saved values survive as the picker defaults
    for key, _ in result["data_schema"].schema.items():
        if key.schema == CONF_VEHICLE_CONNECTED_STATES:
            default = key.default() if callable(key.default) else key.default
            assert default == ["Charging", "Completed"]