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

import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector

try:
    from homeassistant.components import recorder as recorder_component
    from homeassistant.components.recorder import get_instance as get_recorder
except ImportError:  # pragma: no cover - older HA where recorder isn't importable
    recorder_component = None
    get_recorder = None

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
    DASHBOARD_TITLE,
    DOMAIN,
)
from .dashboard import install_dashboard, uninstall_dashboard

_LOGGER = logging.getLogger(__name__)

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


def _entity_state_options(
    hass: HomeAssistant, entity_id: str, history: list[str] | None = None
) -> list[str]:
    """Best-effort list of the source entity's possible state values.

    Sources, in priority order: the ``options`` or ``current_option`` attributes
    (from a `select` helper or enum sensor), the current state, then any recorded
    history values (from the recorder). Distinct values are de-duplicated,
    preserving first-seen order. Empty is fine — `custom_value` on the
    selector still lets the user type any state.
    """
    state_obj = hass.states.get(entity_id)
    _LOGGER.debug(
        "status states: source=%s state=%r attrs=%r",
        entity_id,
        state_obj.state if state_obj else None,
        state_obj.attributes if state_obj else None,
    )

    candidates: list[str] = []
    if state_obj is not None:
        for attr_name in ("options", "current_option"):
            value = state_obj.attributes.get(attr_name)
            if isinstance(value, list):
                candidates.extend(str(item) for item in value if str(item))
            elif isinstance(value, str) and value:
                candidates.append(value)

        current = state_obj.state
        if current not in ("unknown", "unavailable"):
            candidates.append(current)

    for value in history or []:
        if value:
            candidates.append(value)

    seen: set[str] = set()
    unique: list[str] = []
    for value in candidates:
        if value not in seen:
            seen.add(value)
            unique.append(value)
    _LOGGER.debug("status states: options for %s = %s", entity_id, unique)
    return unique


def _build_states_schema(
    hass: HomeAssistant, captured: dict, history: dict[str, list[str]] | None = None
) -> vol.Schema | None:
    """Build a schema of multi-select state pickers for non-binary status sources.

    Uses a `select` selector (rather than the ``state`` selector) because
    the ``state`` selector can't show a list for a plain text sensor that
    isn't `device_class: enum`. `custom_value` lets unrecognised states be
    typed as well as picked from the source's known values.

    ``history`` maps a source entity id to values taken from its recorded
    history, so the picker can offer every state the sensor has ever shown
    (not just the current one).

    Returns None when neither source entity needs a picker.
    """
    fields: dict = {}
    state_keys: list[str] = []
    for field_key, source_key in STATUS_SOURCE_FIELDS:
        source = captured.get(source_key)
        _LOGGER.debug(
            "status states: field=%s source=%s non_binary=%s",
            field_key, source, _is_non_binary_source(source),
        )
        if not _is_non_binary_source(source):
            continue
        state_keys.append(field_key)
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
                    "options": _entity_state_options(
                        hass, source, (history or {}).get(source)
                    ),
                }
            }
        )
    _LOGGER.debug("status states: schema fields = %s", state_keys)
    return vol.Schema(fields) if fields else None


async def _async_entity_state_history(
    hass: HomeAssistant, entity_id: str, days: int = 30
) -> list[str]:
    """Distinct recorded state values for an entity from the recorder.

    Best effort: returns [] if the recorder isn't available, the entity has
    no history, or recording is disabled for it. Never raises.
    """
    if get_recorder is None or recorder_component is None:
        return []
    try:
        instance = get_recorder(hass)
        # get_significant_states is blocking; run it on the recorder's own
        # executor so we never stall the event loop.
        from homeassistant.components.recorder import history as recorder_history

        start = _utc_now() - timedelta(days=days)
        rows = await instance.async_add_executor_job(
            recorder_history.get_significant_states,
            hass,
            start,
            None,
            [entity_id],
        )
    except Exception as exc:  # noqa: BLE001 - degrade, don't break the flow
        _LOGGER.debug("status states: no history for %s (%s)", entity_id, exc)
        return []

    values: list[str] = []
    seen: set[str] = set()
    for lazy_state in rows.get(entity_id, []):
        value = getattr(lazy_state, "state", None)
        if value and value not in ("unknown", "unavailable") and value not in seen:
            seen.add(value)
            values.append(value)
    return values


def _utc_now():
    from homeassistant.util.dt import utcnow

    return utcnow()


def _clean(user_input: dict) -> dict:
    """Drop empty/cleared optional selections instead of storing them as '' or []."""
    return {k: v for k, v in user_input.items() if v}


async def _analyze_state_history(
    hass: HomeAssistant, captured: dict
) -> dict[str, list[str]]:
    """Gather recorded state history for every non-binary status source."""
    history: dict[str, list[str]] = {}
    for _field_key, source_key in STATUS_SOURCE_FIELDS:
        source = captured.get(source_key)
        if source and _is_non_binary_source(source):
            history[source] = await _async_entity_state_history(hass, source)
    return history


class SmartEvChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial setup flow."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        _LOGGER.debug("Smart EV Charging config flow starting")

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            if _build_states_schema(self.hass, user_input):
                self._captured = user_input
                self._history = await _analyze_state_history(self.hass, user_input)
                return self.async_show_form(
                    step_id="states",
                    data_schema=_build_states_schema(
                        self.hass, user_input, self._history
                    ),
                )
            return self.async_create_entry(
                title="Smart EV Charging", data=_clean(user_input)
            )

        self._history = {}
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

        history = self._history or await _analyze_state_history(self.hass, captured)
        return self.async_show_form(
            step_id="states",
            data_schema=_build_states_schema(self.hass, captured, history),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SmartEvChargingOptionsFlow:
        return SmartEvChargingOptionsFlow()


class SmartEvChargingOptionsFlow(config_entries.OptionsFlow):
    """Options flow: menu-driven configure / install / uninstall dashboard."""

    def __init__(self) -> None:
        super().__init__()
        self._captured: dict | None = None
        self._history: dict[str, list[str]] = {}

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Show the main options menu."""
        menu = ["configure", "install_dashboard", "uninstall_dashboard"]
        return self.async_show_menu(
            step_id="init",
            menu_options=menu,
        )

    async def async_step_configure(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        self._history = {}
        if user_input is not None:
            # The init schema only contains entity pickers, so the submitted
            # user_input has no *_states keys. Carry the stored ones across so
            # the previously selected values stay pre-filled on reconfigure.
            stored = {**self.config_entry.data, **self.config_entry.options}
            captured = {**stored, **user_input}
            if _build_states_schema(self.hass, captured):
                self._captured = captured
                self._history = await _analyze_state_history(self.hass, captured)
                return self.async_show_form(
                    step_id="states",
                    data_schema=_build_states_schema(
                        self.hass, captured, self._history
                    ),
                )
            return self.async_create_entry(title="", data=_clean(captured))

        current = {**self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(
            step_id="configure", data_schema=_build_entity_schema(current)
        )

    async def async_step_install_dashboard(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Install or update the bundled dashboard, then return to the menu."""
        ok = await install_dashboard(self.hass)
        _LOGGER.info(
            "Smart EV Charging dashboard install %s", "succeeded" if ok else "failed"
        )
        return self.async_create_entry(title="", data={})

    async def async_step_uninstall_dashboard(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove the dashboard, then return to the menu."""
        ok = await uninstall_dashboard(self.hass)
        _LOGGER.info(
            "Smart EV Charging dashboard uninstall %s",
            "succeeded" if ok else "failed",
        )
        return self.async_create_entry(title="", data={})

    async def async_step_states(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        captured = dict(self._captured)
        if user_input is not None:
            merged = _clean({**captured, **user_input})
            return self.async_create_entry(title="", data=merged)

        history = self._history or await _analyze_state_history(self.hass, captured)
        return self.async_show_form(
            step_id="states",
            data_schema=_build_states_schema(self.hass, captured, history),
        )

