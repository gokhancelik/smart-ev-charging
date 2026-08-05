"""Constants for the Smart EV Charging integration."""

from homeassistant.const import Platform

DOMAIN = "smart_ev_charging"

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_VEHICLE_CONNECTED = "vehicle_connected"
CONF_VEHICLE_CONNECTED_STATES = "vehicle_connected_states"
CONF_CHARGING_ACTIVE = "charging_active"
CONF_CHARGING_ACTIVE_STATES = "charging_active_states"
CONF_PRICE = "price"
CONF_CHEAP_PRICE = "cheap_price"
CONF_BATTERY = "battery"
CONF_POWER = "power"
CONF_ENERGY = "energy"
CONF_DEPARTURE_CALENDAR = "departure_calendar"

# Required entity-pointer fields (must resolve to a real entity)
REQUIRED_FIELDS = (
    CONF_VEHICLE_CONNECTED,
    CONF_CHARGING_ACTIVE,
    CONF_PRICE,
    CONF_CHEAP_PRICE,
)

# Optional entity-pointer fields
OPTIONAL_FIELDS = (
    CONF_BATTERY,
    CONF_POWER,
    CONF_ENERGY,
    CONF_DEPARTURE_CALENDAR,
)
