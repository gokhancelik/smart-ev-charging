"""Sensor platform for Smart EV Charging.

Provides stable, well-known passthrough sensors for the entities chosen in
the config flow, plus one diagnostic sensor exposing the full configured
entity map. Lovelace cards and the package's Jinja templates cannot resolve
"whatever entity was picked in a config entry" themselves, so these mirrors
give them a fixed entity_id to point at instead.
"""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

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

UNAVAILABLE_STATES = ("unknown", "unavailable")


def _is_unavailable(raw: str | None) -> bool:
    """Whether a raw state should be treated as unavailable.

    Same policy as binary_sensor.py: some integrations (e.g. Easee) emit
    decorated variants such as ``"unknown 0"``; treat any state whose first
    word is an unavailable marker as unavailable rather than leaking it
    through as a real measurement.
    """
    stripped = (raw or "").strip()
    if not stripped:
        return True
    return stripped.lower().split()[0] in UNAVAILABLE_STATES


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    # Once options exist they hold the full merged config (the options flow
    # always re-emits every stored field), so prefer them over entry.data —
    # falling back to data here would resurrect fields the user cleared.
    config = dict(entry.options) or dict(entry.data)
    entities: list[SensorEntity] = [SmartEvChargingConfigSensor(entry, config)]

    if config.get(CONF_PRICE):
        entities.append(
            SmartEvChargingMirrorSensor(
                entry,
                config[CONF_PRICE],
                name="EV Charging Price",
                object_id="ev_charging_price",
                icon="mdi:currency-eur",
                state_class=SensorStateClass.MEASUREMENT,
                mirror_unit=True,
            )
        )
    if config.get(CONF_BATTERY):
        entities.append(
            SmartEvChargingMirrorSensor(
                entry,
                config[CONF_BATTERY],
                name="EV Battery Percentage",
                object_id="ev_battery_percentage",
                icon="mdi:battery-high",
                device_class=SensorDeviceClass.BATTERY,
                state_class=SensorStateClass.MEASUREMENT,
                unit="%",
            )
        )
    if config.get(CONF_POWER):
        entities.append(
            SmartEvChargingMirrorSensor(
                entry,
                config[CONF_POWER],
                name="EV Charging Power",
                object_id="ev_charging_power",
                icon="mdi:flash",
                device_class=SensorDeviceClass.POWER,
                state_class=SensorStateClass.MEASUREMENT,
                mirror_unit=True,
            )
        )
    if config.get(CONF_ENERGY):
        entities.append(
            SmartEvChargingMirrorSensor(
                entry,
                config[CONF_ENERGY],
                name="EV Energy Meter",
                object_id="ev_energy_meter",
                icon="mdi:counter",
                device_class=SensorDeviceClass.ENERGY,
                state_class=SensorStateClass.TOTAL_INCREASING,
                mirror_unit=True,
            )
        )

    async_add_entities(entities)


class SmartEvChargingMirrorSensor(SensorEntity):
    """Mirrors the state (and optionally unit) of a configured source sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        source_entity_id: str,
        *,
        name: str,
        object_id: str,
        icon: str,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        unit: str | None = None,
        mirror_unit: bool = False,
    ) -> None:
        self._source_entity_id = source_entity_id
        self._mirror_unit = mirror_unit
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{object_id}"
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_native_unit_of_measurement = unit
        self._attr_available = False
        self.entity_id = f"sensor.{object_id}"

    async def async_added_to_hass(self) -> None:
        self._apply_source_state(self.hass.states.get(self._source_entity_id))
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity_id], self._handle_source_event
            )
        )

    @callback
    def _handle_source_event(self, event: Event[EventStateChangedData]) -> None:
        self._apply_source_state(event.data["new_state"])
        self.async_write_ha_state()

    def _apply_source_state(self, state) -> None:
        if state is None or _is_unavailable(getattr(state, "state", None)):
            self._attr_available = False
            self._attr_native_value = None
            return
        self._attr_available = True
        self._attr_native_value = state.state
        if self._mirror_unit:
            self._attr_native_unit_of_measurement = state.attributes.get(
                "unit_of_measurement"
            )


class SmartEvChargingConfigSensor(SensorEntity):
    """Diagnostic sensor exposing the full configured entity map as attributes.

    Read by the blueprint's departure-deadline logic (for the optional
    calendar entity) and shown in the dashboards' Debug section.
    """

    _attr_should_poll = False
    _attr_name = "EV Smart Charging Config"
    _attr_icon = "mdi:cog"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, config: dict) -> None:
        self._attr_unique_id = f"{entry.entry_id}_config"
        self.entity_id = "sensor.ev_smart_charging_config"
        self._config = config

    @property
    def native_value(self) -> str:
        return "configured"

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "vehicle_connected_entity": self._config.get(CONF_VEHICLE_CONNECTED),
            "charging_active_entity": self._config.get(CONF_CHARGING_ACTIVE),
            "price_entity": self._config.get(CONF_PRICE),
            "cheap_price_entity": self._config.get(CONF_CHEAP_PRICE),
            "battery_entity": self._config.get(CONF_BATTERY),
            "power_entity": self._config.get(CONF_POWER),
            "energy_entity": self._config.get(CONF_ENERGY),
            "departure_calendar_entity": self._config.get(CONF_DEPARTURE_CALENDAR),
        }
