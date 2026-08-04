"""Binary sensor platform for Smart EV Charging.

Mirrors the required binary_sensor entities chosen in the config flow onto
stable, well-known entity IDs used throughout the package, blueprint, and
dashboards.
"""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_CHARGING_ACTIVE, CONF_CHEAP_PRICE, CONF_VEHICLE_CONNECTED

UNAVAILABLE_STATES = ("unknown", "unavailable")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    config = {**entry.data, **entry.options}

    async_add_entities(
        [
            SmartEvChargingMirrorBinarySensor(
                entry,
                config[CONF_VEHICLE_CONNECTED],
                name="EV Vehicle Connected",
                object_id="ev_vehicle_connected",
                device_class=BinarySensorDeviceClass.PLUG,
            ),
            SmartEvChargingMirrorBinarySensor(
                entry,
                config[CONF_CHARGING_ACTIVE],
                name="EV Charging Active",
                object_id="ev_charging_active",
                device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
            ),
            SmartEvChargingMirrorBinarySensor(
                entry,
                config[CONF_CHEAP_PRICE],
                name="EV Price Cheap",
                object_id="ev_price_cheap",
                icon="mdi:cash-check",
            ),
        ]
    )


class SmartEvChargingMirrorBinarySensor(BinarySensorEntity):
    """Mirrors the on/off state of a configured source binary_sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        source_entity_id: str,
        *,
        name: str,
        object_id: str,
        device_class: BinarySensorDeviceClass | None = None,
        icon: str | None = None,
    ) -> None:
        self._source_entity_id = source_entity_id
        self._attr_name = name
        self._attr_icon = icon
        self._attr_unique_id = f"{entry.entry_id}_{object_id}"
        self._attr_device_class = device_class
        self._attr_available = False
        self.entity_id = f"binary_sensor.{object_id}"

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
        if state is None or state.state in UNAVAILABLE_STATES:
            self._attr_available = False
            self._attr_is_on = None
            return
        self._attr_available = True
        self._attr_is_on = state.state == "on"
