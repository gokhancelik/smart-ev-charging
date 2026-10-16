"""Offline truth-table tests for the blueprint's `reconcile` template trigger.

Tier-0 verification (see CLAUDE.md > "Verifying changes without releasing"):
this renders the blueprint's reconcile `value_template` with plain Jinja2
against synthetic entity states, mimicking the Home Assistant template
environment closely enough that the decision logic can be exercised without
a running HA instance. The template must be a pure predicate over entity
states plus `now()` — if you find yourself needing HA services or live
listeners here, the template is doing too much and that is a design bug.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import jinja2
import yaml

_BLUEPRINT = Path(__file__).resolve().parents[1] / (
    "custom_components"
    "/smart_ev_charging"
    "/blueprint"
    "/smart_ev_charging.yaml"
)

# Fixed "current time" for every render: 2026-08-14 12:00 UTC. The default
# departure time (07:30) has then already passed today, so the input_datetime
# branch rolls over to tomorrow morning and the deadline is far away.
_NOW = dt.datetime(2026, 8, 14, 12, 0, tzinfo=dt.timezone.utc)


class _Loader(yaml.SafeLoader):
    pass


def _flatten_input(loader, node):
    return loader.construct_scalar(node)


_Loader.add_constructor("!input", _flatten_input)


def _load_reconcile_template() -> str:
    bp = yaml.load(_BLUEPRINT.read_text(encoding="utf-8"), Loader=_Loader)
    triggers = {t["id"]: t for t in bp["triggers"]}
    return triggers["reconcile"]["value_template"]


_TEMPLATE = _load_reconcile_template()


class _FakeHA:
    """Minimal stand-ins for the HA template functions used by the template."""

    def __init__(self, states, attributes, now):
        self._states = states
        self._attributes = attributes
        self._now = now

    def states(self, entity_id):
        return self._states.get(entity_id, "unavailable")

    def is_state(self, entity_id, state):
        return self.states(entity_id) == state

    def state_attr(self, entity_id, attribute):
        return self._attributes.get(entity_id, {}).get(attribute)

    def now(self):
        return self._now

    def today_at(self, value):
        parsed = dt.time.fromisoformat(value)
        return dt.datetime.combine(self._now.date(), parsed).replace(
            tzinfo=self._now.tzinfo
        )

    def strptime(self, value, fmt):
        # HA's strptime returns a NAIVE datetime (verified against
        # homeassistant/helpers/template/extensions/datetime.py) — the
        # template must attach a timezone itself before comparing to now().
        return dt.datetime.strptime(value, fmt)

    def as_local(self, value):
        # dt_util.as_local assumes the default timezone for naive datetimes.
        return value.replace(tzinfo=self._now.tzinfo)


def _render(overrides=None, attributes=None, lead_minutes=120) -> bool:
    states = _base_states()
    if overrides:
        states.update(overrides)
    ha = _FakeHA(states, attributes or {}, _NOW)
    env = jinja2.Environment()
    template = env.from_string(_TEMPLATE)
    rendered = template.render(
        is_state=ha.is_state,
        states=ha.states,
        state_attr=ha.state_attr,
        now=ha.now,
        today_at=ha.today_at,
        strptime=ha.strptime,
        as_local=ha.as_local,
        timedelta=dt.timedelta,
        reconcile_lead_minutes=lead_minutes,
    )
    return rendered.strip() == "True"


def _base_states(**overrides: str) -> dict[str, str]:
    states = {
        "binary_sensor.ev_vehicle_connected": "off",
        "binary_sensor.ev_charging_active": "off",
        "binary_sensor.ev_price_cheap": "off",
        "sensor.ev_charging_price": "1.50",
        "sensor.ev_battery_percentage": "50",
        "input_boolean.ev_follow_price": "on",
        "input_boolean.ev_charge_now_override": "off",
        "input_boolean.ev_max_price_enabled": "off",
        "input_boolean.ev_target_battery_enabled": "off",
        "input_boolean.ev_low_battery_emergency_enabled": "on",
        "input_number.ev_max_acceptable_price": "2.00",
        "input_number.ev_target_battery_percentage": "80",
        "input_number.ev_low_battery_threshold": "20",
        "input_datetime.ev_departure_time": "07:30:00",
    }
    states.update(overrides)
    return states


# ---------------------------------------------------------------------------
# Idle / no-op states
# ---------------------------------------------------------------------------


def test_idle_connected_at_expensive_price_does_nothing():
    assert _render({"binary_sensor.ev_vehicle_connected": "on"}) is False


def test_nothing_happens_when_not_connected():
    assert _render({"binary_sensor.ev_price_cheap": "on"}) is False


# ---------------------------------------------------------------------------
# Cheap-window backstop start
# ---------------------------------------------------------------------------


def test_cheap_window_while_connected_fires():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "binary_sensor.ev_price_cheap": "on",
            }
        )
        is True
    )


def test_max_price_gate_blocks_expensive_cheap_flag():
    base = {
        "binary_sensor.ev_vehicle_connected": "on",
        "binary_sensor.ev_price_cheap": "on",
        "input_boolean.ev_max_price_enabled": "on",
    }
    assert _render({**base, "sensor.ev_charging_price": "3.00"}) is False
    assert _render({**base, "sensor.ev_charging_price": "1.00"}) is True


def test_target_battery_gate_blocks_start_when_reached():
    base = {
        "binary_sensor.ev_vehicle_connected": "on",
        "binary_sensor.ev_price_cheap": "on",
        "input_boolean.ev_target_battery_enabled": "on",
    }
    assert _render({**base, "sensor.ev_battery_percentage": "80"}) is False
    assert _render({**base, "sensor.ev_battery_percentage": "50"}) is True


def test_manual_override_blocks_backstop_start():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "binary_sensor.ev_price_cheap": "on",
                "input_boolean.ev_charge_now_override": "on",
            }
        )
        is False
    )


# ---------------------------------------------------------------------------
# Low-battery emergency
# ---------------------------------------------------------------------------


def test_low_battery_emergency_fires_regardless_of_price():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "sensor.ev_battery_percentage": "10",
            }
        )
        is True
    )


def test_low_battery_emergency_respects_enable_and_threshold():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "sensor.ev_battery_percentage": "10",
                "input_boolean.ev_low_battery_emergency_enabled": "off",
            }
        )
        is False
    )
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "sensor.ev_battery_percentage": "30",
            }
        )
        is False
    )


# ---------------------------------------------------------------------------
# Departure deadline — input_datetime fallback path
# ---------------------------------------------------------------------------


def test_departure_deadline_within_lead_time_fires():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "input_datetime.ev_departure_time": "12:45:00",  # 45 min away
            }
        )
        is True
    )


def test_departure_deadline_outside_lead_time_does_not_fire():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "input_datetime.ev_departure_time": "18:00:00",  # 6 h away
            }
        )
        is False
    )


def test_departure_deadline_honours_lead_minutes_input():
    states = {
        "binary_sensor.ev_vehicle_connected": "on",
        "input_datetime.ev_departure_time": "13:00:00",  # 60 min away
    }
    assert _render(states, lead_minutes=30) is False
    assert _render(states, lead_minutes=120) is True


def test_departure_deadline_requires_smart_mode():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "input_datetime.ev_departure_time": "12:45:00",
                "input_boolean.ev_follow_price": "off",
            }
        )
        is False
    )


# ---------------------------------------------------------------------------
# Departure deadline — calendar path (regression: tz-naive strptime)
# ---------------------------------------------------------------------------


def _calendar_attributes(start_time):
    return {
        "sensor.ev_smart_charging_config": {
            "departure_calendar_entity": "calendar.work"
        },
        "calendar.work": {"start_time": start_time},
    }


def test_departure_deadline_from_calendar_event():
    states = {"binary_sensor.ev_vehicle_connected": "on"}
    # HA's strptime is tz-naive while now() is tz-aware; if the template ever
    # drops its as_local() wrapping this render raises TypeError and fails.
    assert (
        _render(states, attributes=_calendar_attributes("2026-08-14 13:00:00"))
        is True
    )
    assert (
        _render(states, attributes=_calendar_attributes("2026-08-15 13:00:00"))
        is False
    )


# ---------------------------------------------------------------------------
# Auto-start pause backstop
# ---------------------------------------------------------------------------


def test_pause_backstop_fires_for_unmanaged_charge():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "binary_sensor.ev_charging_active": "on",
            }
        )
        is True
    )


def test_pause_backstop_ignores_manual_override_and_smart_mode_off():
    base = {
        "binary_sensor.ev_vehicle_connected": "on",
        "binary_sensor.ev_charging_active": "on",
    }
    assert _render({**base, "input_boolean.ev_charge_now_override": "on"}) is False
    assert _render({**base, "input_boolean.ev_follow_price": "off"}) is False


def test_pause_backstop_needs_price_explicitly_not_cheap():
    base = {
        "binary_sensor.ev_vehicle_connected": "on",
        "binary_sensor.ev_charging_active": "on",
    }
    assert _render({**base, "binary_sensor.ev_price_cheap": "on"}) is False
    assert (
        _render({**base, "binary_sensor.ev_price_cheap": "unavailable"}) is False
    )
    assert _render({**base, "binary_sensor.ev_price_cheap": "unknown"}) is False


# ---------------------------------------------------------------------------
# Transition semantics the `for: 30s` de-duplication relies on
# ---------------------------------------------------------------------------


def test_convergence_clears_the_predicate():
    waiting = {
        "binary_sensor.ev_vehicle_connected": "on",
        "binary_sensor.ev_price_cheap": "on",
    }
    assert _render(waiting) is True
    # Once the immediate event trigger has started the charge, the backstop
    # predicate must drop back to false so the 30 s `for:` never fires.
    assert _render({**waiting, "binary_sensor.ev_charging_active": "on"}) is False


def test_nightly_price_gap_renders_quietly():
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "binary_sensor.ev_price_cheap": "unavailable",
            }
        )
        is False
    )
    assert (
        _render(
            {
                "binary_sensor.ev_vehicle_connected": "on",
                "binary_sensor.ev_charging_active": "on",
                "binary_sensor.ev_price_cheap": "unavailable",
            }
        )
        is False
    )
