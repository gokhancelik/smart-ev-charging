"""Config flow for Smart EV Charging.

Replaces the old approach of manually filling input_text helpers with the
raw entity IDs of your vehicle/charger integration. The package
(packages/smart_ev_charging.yaml) and blueprint still do all the price/plug
decision logic; this integration's only job is to let you pick those
entities through a normal HA form, and expose them under stable,
well-known entity IDs (sensor.ev_charging_price, binary_sensor.ev_vehicle_connected,
etc.) that the package's templates, the scripts, and the dashboards rely on.

vehicle_connected and charging_active accept either a proper binary_sensor
(the common case) or a text/enum status sensor (e.g. Easee's charger
status, which reports strings like "Charging", "Completed", "Car
disconnected" instead of a boolean) paired with a "which states count as
on" picker — see vehicle_connected_states / charging_active_states.

Single-vehicle by design, matching the rest of the package (see README FAQ):
only one config entry is allowed.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY,
    CONF_CHARGING_ACTIVE,
    CONF_CHARGING_ACTIVE_STATES,
    CONF_CHEAP_PRICE,
    CONF_DEPARTURE_CALENDAR,
    CONF_ENERGY,
    CONF_POWER,
    CONF_PRICE,
    CONF_VEHICLE_CONNECTED,
    CONF_VEHICLE_CONNECTED_STATES,
    DOMAIN,
)

# (matching-states config key, source entity config key) pairings that need a
# state picker whenever their source isn't a plain binary_sensor.
STATUS_SOURCE_FIELDS = (
    (CONF_VEHICLE_CONNECTED_STATES, CONF_VEHICLE_CONNECTED),
    (CONF_CHARGING_ACTIVE_STATES, CONF_CHARGING_ACTIVE),
)


def _entity_selector(domain: str | list[str]) -> selector.Selector:
    return selector.selector({"entity": {"domain": domain}})


def _build_entity_schema(current: dict) -> vol.Schema:
    """Entity pickers only — the status matching-states fields come later."""
    fields: dict = {}

    def required_entity(key: str, domain: str | list[str]) -> None:
        kwargs = {"default": current[key]} if current.get(key) else {}
        fields[vol.Required(key, **kwargs)] = _entity_selector(domain)

    def optional_entity(key: str, domain: str | list[str]) -> None:
        fields[
            vol.Optional(key, description={"suggested_value": current.get(key)})
        ] = _entity_selector(domain)

    required_entity(CONF_VEHICLE_CONNECTED, ["binary_sensor", "sensor"])
    required_entity(CONF_CHARGING_ACTIVE, ["binary_sensor", "sensor"])
    required_entity(CONF_PRICE, "sensor")
    required_entity(CONF_CHEAP_PRICE, "binary_sensor")
    optional_entity(CONF_BATTERY, "sensor")
    optional_entity(CONF_POWER, "sensor")
    optional_entity(CONF_ENERGY, "sensor")
    optional_entity(CONF_DEPARTURE_CALENDAR, "calendar")

    return vol.Schema(fields)


def _is_non_binary_source(entity_id: str) -> bool:
    """Only sources that aren't plain binary_sensors need a matching-states list."""
    return bool(entity_id) and entity_id.split(".", 1)[0] != "binary_sensor"


def _current_states_list(current: dict, key: str) -> list[str] | None:
    """Normalise a stored comma-string/list states value to a list for the picker."""
    value = current.get(key)
    if not value:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [part.strip() for part in str(value).split(",") if part.strip()] or None


def _entity_state_options(hass: HomeAssistant, entity_id: str) -> list[str]:
    """Best-effort list of the source entity's possible state values.

    Only enum device-class sensors expose a real ``options`` list; for a
    plain text status sensor the best guesses are its ``options``/state
    attributes (from a `select` helper or template) plus its current
    state. Empty is fine — `custom_value` on the selector still lets the
    user type any state.
    """
    state_obj = hass.states.get(entity_id)
    if state_obj is None:
        return []

    candidates: list[str] = []
    for attr_name in ("options", "current_option"):
        value = state_obj.attributes.get(attr_name)
        if isinstance(value, list):
            candidates.extend(str(item) for item in value if str(item))
        elif isinstance(value, str) and value:
            candidates.append(value)

    current = state_obj.state
    if current and current not in ("unknown", "unavailable"):
        candidates.append(current)

    seen: set[str] = set()
    unique: list[str] = []
    for value in candidates:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def _build_states_schema(
    hass: HomeAssistant, captured: dict
) -> vol.Schema | None:
    """Build a schema of multi-select state pickers for non-binary status sources.

    Uses a `select` selector (rather than the ``state`` selector) because
    the ``state`` selector can't show a list for a plain text sensor that
    isn't `device_class: enum`. `custom_value` lets unrecognised states be
    typed as well as picked from the source's known values.

    Returns None when neither source entity needs a picker.
    """
    fields: dict = {}
    for field_key, source_key in STATUS_SOURCE_FIELDS:
        source = captured.get(source_key)
        if not _is_non_binary_source(source):
            continue
        fields[
            vol.Optional(
                field_key,
                default=_current_states_list(captured, field_key),
            )
        ] = selector.selector(
            {
                "select": {
                    "multiple": True,
                    "custom_value": True,
                    "mode": "dropdown",
                    "options": _entity_state_options(hass, source),
                }
            }
        )
    return vol.Schema(fields) if fields else None


def _clean(user_input: dict) -> dict:
    """Drop empty/cleared optional selections instead of storing them as '' or []."""
    return {k: v for k, v in user_input.items() if v}


class SmartEvChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            if schema := _build_states_schema(self.hass, user_input):
                self._captured = user_input
                return self.async_show_form(step_id="states", data_schema=schema)
            return self.async_create_entry(
                title="Smart EV Charging", data=_clean(user_input)
            )

        return self.async_show_form(
            step_id="user", data_schema=_build_entity_schema({})
        )

    async def async_step_states(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        captured = dict(self._captured)
        if user_input is not None:
            merged = _clean({**captured, **user_input})
            return self.async_create_entry(title="Smart EV Charging", data=merged)

        return self.async_show_form(
            step_id="states", data_schema=_build_states_schema(self.hass, captured)
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartEvChargingOptionsFlow:
        return SmartEvChargingOptionsFlow()


class SmartEvChargingOptionsFlow(config_entries.OptionsFlow):
    """Let the user change the configured entities after setup."""

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            if schema := _build_states_schema(self.hass, user_input):
                self._captured = user_input
                return self.async_show_form(step_id="states", data_schema=schema)
            return self.async_create_entry(title="", data=_clean(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="init", data_schema=_build_entity_schema(current)
        )

    async def async_step_states(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        captured = dict(self._captured)
        if user_input is not None:
            merged = _clean({**captured, **user_input})
            return self.async_create_entry(title="", data=merged)

        return self.async_show_form(
            step_id="states", data_schema=_build_states_schema(self.hass, captured)
        )
