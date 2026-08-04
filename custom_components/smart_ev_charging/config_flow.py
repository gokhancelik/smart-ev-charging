"""Config flow for Smart EV Charging.

Replaces the old approach of manually filling input_text helpers with the
raw entity IDs of your vehicle/charger integration. The package
(packages/smart_ev_charging.yaml) and blueprint still do all the price/plug
decision logic; this integration's only job is to let you pick those
entities through a normal HA form, and expose them under stable,
well-known entity IDs (sensor.ev_charging_price, binary_sensor.ev_vehicle_connected,
etc.) that the package's templates, the scripts, and the dashboards rely on.

Single-vehicle by design, matching the rest of the package (see README FAQ):
only one config entry is allowed.
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BATTERY,
    CONF_CHARGING_ACTIVE,
    CONF_CHEAP_PRICE,
    CONF_DEPARTURE_CALENDAR,
    CONF_ENERGY,
    CONF_POWER,
    CONF_PRICE,
    CONF_VEHICLE_CONNECTED,
    DOMAIN,
)


def _entity_selector(domain: str) -> selector.Selector:
    return selector.selector({"entity": {"domain": domain}})


def _build_schema(current: dict) -> vol.Schema:
    fields: dict = {}

    def required(key: str, domain: str) -> None:
        kwargs = {"default": current[key]} if current.get(key) else {}
        fields[vol.Required(key, **kwargs)] = _entity_selector(domain)

    def optional(key: str, domain: str) -> None:
        fields[
            vol.Optional(key, description={"suggested_value": current.get(key)})
        ] = _entity_selector(domain)

    required(CONF_VEHICLE_CONNECTED, "binary_sensor")
    required(CONF_CHARGING_ACTIVE, "binary_sensor")
    required(CONF_PRICE, "sensor")
    required(CONF_CHEAP_PRICE, "binary_sensor")
    optional(CONF_BATTERY, "sensor")
    optional(CONF_POWER, "sensor")
    optional(CONF_ENERGY, "sensor")
    optional(CONF_DEPARTURE_CALENDAR, "calendar")

    return vol.Schema(fields)


def _clean(user_input: dict) -> dict:
    """Drop empty/cleared optional selections instead of storing them as ''."""
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
            return self.async_create_entry(
                title="Smart EV Charging", data=_clean(user_input)
            )

        return self.async_show_form(step_id="user", data_schema=_build_schema({}))

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
            return self.async_create_entry(title="", data=_clean(user_input))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=_build_schema(current))
