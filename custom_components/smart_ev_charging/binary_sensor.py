"""Binary sensor platform for Smart EV Charging.

Mirrors the configured source entities chosen in the config flow onto
stable, well-known entity IDs used throughout the package, blueprint, and
dashboards.

vehicle_connected and charging_active support two source shapes:
  - A proper binary_sensor: on/off is used as-is (the default when no
    "matching states" list is configured).
  - A text/enum status sensor (e.g. Easee's charger status, which reports
    "Charging" / "Completed" / "Car disconnected" / ... instead of a
    boolean): the paired *_states config value lists which raw states
    count as "on" for that concept, e.g. "Charging,Completed,Awaiting
    Start" for vehicle_connected, "Charging" for charging_active.
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

from .const import (
    CONF_CHARGING_ACTIVE,
    CONF_CHARGING_ACTIVE_STATES,
    CONF_CHEAP_PRICE,
    CONF_VEHICLE_CONNECTED,
    CONF_VEHICLE_CONNECTED_STATES,
)

UNAVAILABLE_STATES = ("unknown", "unavailable")


def _parse_on_states(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [part.strip().lower() for part in raw.split(",") if part.strip()]


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
                on_states=_parse_on_states(config.get(CONF_VEHICLE_CONNECTED_STATES)),
            ),
            SmartEvChargingMirrorBinarySensor(
                entry,
                config[CONF_CHARGING_ACTIVE],
                name="EV Charging Active",
                object_id="ev_charging_active",
                device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
                on_states=_parse_on_states(config.get(CONF_CHARGING_ACTIVE_STATES)),
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
    """Mirrors the on/off state of a configured source entity.

    With no on_states configured, treats the source as a plain
    binary_sensor (state == "on"). With on_states configured, treats the
    source as a status/enum sensor and is "on" whenever its state
    case-insensitively matches one of on_states.
    """

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
        on_states: list[str] | None = None,
    ) -> None:
        self._source_entity_id = source_entity_id
        self._on_states = on_states or []
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
        if self._on_states:
            self._attr_is_on = state.state.strip().lower() in self._on_states
        else:
            self._attr_is_on = state.state == "on"
