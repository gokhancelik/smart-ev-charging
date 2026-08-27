"""Test fixtures.

The integration imports ``homeassistant`` packages that aren't installed in
this repo. Rather than depend on the full `pytest-homeassistant-custom-component`
harness, we install minimal stub modules for exactly the names the
integration imports, so the pure logic (config-flow schema building, state
list parsing) can be unit tested with plain pytest.
"""

from __future__ import annotations

import enum
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _module(name: str) -> types.ModuleType:
    mod = types.ModuleType(name)
    mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = mod
    return mod


class State:
    """Minimal stand-in for homeassistant.core.State."""

    def __init__(self, state, attributes=None):
        self.state = state
        self.attributes = attributes or {}


class _FakeStates:
    def __init__(self):
        self._entities: dict[str, State] = {}

    def get(self, entity_id):
        return self._entities.get(entity_id)

    def is_state(self, entity_id, state):
        obj = self.get(entity_id)
        return obj is not None and obj.state == state


class HomeAssistant:
    def __init__(self):
        self.states = _FakeStates()


class ConfigEntry:
    def __init__(self, data=None, options=None, entry_id="test-entry"):
        self.data = data or {}
        self.options = options or {}
        self.entry_id = entry_id


class Selector:
    """Stub for homeassistant.helpers.selector.Selector."""

    def __init__(self, config):
        self.config = config

    def __repr__(self):
        return f"Selector({self.config!r})"

    def __voluptuous_compile__(self, schema):
        """Make the selector usable as a voluptuous schema value, like real HA."""

        def _validate(v):
            return v

        return _validate


class ConfigFlow:
    domain = None

    def __init_subclass__(cls, domain=None, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.domain = domain

    def __init__(self, hass=None):
        self.hass = hass
        self._async_current_entries_calls = 0
        self._captured = None

    def _async_current_entries(self):
        self._async_current_entries_calls += 1
        return []

    def async_show_form(self, step_id, data_schema=None):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}

    def async_abort(self, reason):
        return {"type": "abort", "reason": reason}


class OptionsFlow:
    def __init__(self, hass=None, config_entry=None):
        self.hass = hass
        self.config_entry = config_entry
        self._captured = None

    def async_show_form(self, step_id, data_schema=None):
        return {"type": "form", "step_id": step_id, "data_schema": data_schema}

    def async_show_menu(self, step_id, menu_options):
        return {"type": "menu", "step_id": step_id, "menu_options": menu_options}

    def async_create_entry(self, title, data):
        return {"type": "create_entry", "title": title, "data": data}


def _install_ha_stubs() -> None:
    """Register stub `homeassistant.*` modules before the integration imports them."""

    def callback(func):
        return func

    class Platform(enum.Enum):
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"

    # --- homeassistant package tree ---
    ha = _module("homeassistant")
    ha_const = _module("homeassistant.const")
    ha_const.Platform = Platform

    ha_core = _module("homeassistant.core")
    ha_core.HomeAssistant = HomeAssistant
    ha_core.State = State
    ha_core.callback = callback
    ha_core.Event = type("Event", (), {})
    ha_core.EventStateChangedData = type("EventStateChangedData", (), {})
    ha_core.ServiceCall = type("ServiceCall", (), {})

    ha_ce = _module("homeassistant.config_entries")
    ha_ce.ConfigEntry = ConfigEntry
    ha_ce.ConfigFlow = ConfigFlow
    ha_ce.OptionsFlow = OptionsFlow
    ha_ce.ConfigFlowResult = dict

    ha_helpers = _module("homeassistant.helpers")
    ha_sel = _module("homeassistant.helpers.selector")
    ha_sel.Selector = Selector
    ha_sel.selector = Selector

    ha_helpers.entity_platform = _module("homeassistant.helpers.entity_platform")
    ha_helpers.entity_platform.AddEntitiesCallback = object
    ha_helpers.event = _module("homeassistant.helpers.event")

    async def async_track_state_change_event(*_args, **_kwargs):
        return lambda: None

    ha_helpers.event.async_track_state_change_event = async_track_state_change_event

    ha_components = _module("homeassistant.components")
    ha_bs = _module("homeassistant.components.binary_sensor")
    ha_bs.BinarySensorDeviceClass = enum.Enum(
        "BinarySensorDeviceClass", "ON OFF PLUG BATTERY_CHARGING"
    )
    ha_bs.BinarySensorEntity = type("BinarySensorEntity", (), {})
    ha_bs.SensorDeviceClass = enum.Enum("SensorDeviceClass", "ENUM")

    ha_sensor = _module("homeassistant.components.sensor")
    ha_sensor.SensorEntity = type("SensorEntity", (), {})
    ha_sensor.SensorDeviceClass = enum.Enum(
        "SensorDeviceClass",
        "BATTERY ENERGY MONETARY POWER",
    )
    ha_sensor.SensorStateClass = enum.Enum(
        "SensorStateClass",
        "MEASUREMENT TOTAL TOTAL_INCREASING",
    )

    ha_helpers_entity = _module("homeassistant.helpers.entity")
    ha_helpers_entity.EntityCategory = enum.Enum("EntityCategory", "DIAGNOSTIC")

    ha_issue = _module("homeassistant.helpers.issue_registry")
    ha_issue.IssueSeverity = enum.Enum("IssueSeverity", "ERROR WARNING CRITICAL")

    # Deliberately SYNCHRONOUS, matching real Home Assistant: despite the
    # async_ prefix, both are @callback functions returning None. Stubbing
    # them as coroutines lets `await async_create_issue(...)` pass here and
    # then blow up with TypeError on a real instance — which is exactly what
    # happened once. Keep these sync so the tests hold the real contract.
    def async_create_issue(*_args, **_kwargs):
        return None

    def async_delete_issue(*_args, **_kwargs):
        return None

    ha_issue.async_create_issue = async_create_issue
    ha_issue.async_delete_issue = async_delete_issue


_install_ha_stubs()


@pytest.fixture
def hass():
    """A fake HomeAssistant with an empty (mutable) states registry."""
    return HomeAssistant()


@pytest.fixture
def add_state(hass):
    """Populate the fake states registry; returns the added State."""

    def _add(entity_id, state, attributes=None):
        st = State(state, attributes)
        hass.states._entities[entity_id] = st
        return st

    return _add
