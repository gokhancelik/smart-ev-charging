"""Tests for the automation blueprint's dry-run wiring."""

from __future__ import annotations

from pathlib import Path

import yaml

_BLUEPRINT = Path(__file__).resolve().parents[1] / (
    "custom_components"
    "/smart_ev_charging"
    "/blueprint"
    "/smart_ev_charging.yaml"
)


class _Loader(yaml.SafeLoader):
    pass


def _flatten_input(loader, node):
    return loader.construct_scalar(node)


_Loader.add_constructor("!input", _flatten_input)


def _load_blueprint() -> dict:
    return yaml.load(_BLUEPRINT.read_text(encoding="utf-8"), Loader=_Loader)


def test_dry_run_input_and_variable_wired():
    bp = _load_blueprint()
    assert "dry_run" in bp["blueprint"]["input"]
    assert bp["blueprint"]["input"]["dry_run"]["default"] is False
    assert bp["blueprint"]["input"]["dry_run"]["selector"] == {"boolean": {}}
    assert bp["variables"]["dry_run"] == "dry_run"


def test_all_action_calls_are_dry_run_guarded():
    text = _BLUEPRINT.read_text(encoding="utf-8")
    action_defaults = text.count("default: !input start_charging_action") + text.count(
        "default: !input stop_charging_action"
    )
    guards = text.count("'{{ not dry_run }}'") + text.count('"{{ not dry_run }}"')
    # 6 start sites (price_cheap, connected-during-cheap-window, low-battery
    # emergency, cheap-wait backstop, departure deadline, manual_charge_now)
    # + 6 stop sites (price_expensive, battery reached target,
    # manual_stop_requested, connected-branch should_stop pause,
    # charging_started pause, reconcile pause).
    assert action_defaults == 12
    assert guards == action_defaults, (
        "every start/stop action call must be guarded by a dry-run branch"
    )


_START_FRAGMENTS = (
    "is_state('binary_sensor.ev_vehicle_connected', 'on')",
    "is_state('input_boolean.ev_follow_price', 'on')",
    "is_state('input_boolean.ev_charge_now_override', 'off')",
    "is_state('binary_sensor.ev_charging_active', 'off')",
    "is_state('input_boolean.ev_max_price_enabled', 'off')",
    "(states('sensor.ev_charging_price') | float(0)) <= (states('input_number.ev_max_acceptable_price') | float(1000))",
    "is_state('input_boolean.ev_target_battery_enabled', 'off')",
    "states('sensor.ev_battery_percentage') in ['unknown', 'unavailable']",
    "(states('sensor.ev_battery_percentage') | float(0)) < (states('input_number.ev_target_battery_percentage') | float(100))",
)

_STOP_FRAGMENTS = (
    # The auto-stop decision: connected + smart on + no override + charging
    # active + price explicitly not cheap.
    "is_state('binary_sensor.ev_vehicle_connected', 'on')",
    "is_state('input_boolean.ev_follow_price', 'on')",
    "is_state('input_boolean.ev_charge_now_override', 'off')",
    "is_state('binary_sensor.ev_charging_active', 'on')",
    "is_state('binary_sensor.ev_price_cheap', 'off')",
    "not is_state('binary_sensor.ev_price_cheap', 'unavailable')",
    "not is_state('binary_sensor.ev_price_cheap', 'unknown')",
)

_EMERGENCY_DEADLINE_FRAGMENTS = (
    "is_state('input_boolean.ev_low_battery_emergency_enabled', 'on')",
    "states('sensor.ev_battery_percentage') not in ['unknown', 'unavailable']",
    "(states('sensor.ev_battery_percentage') | float(100)) <= (states('input_number.ev_low_battery_threshold') | float(0))",
    "state_attr('sensor.ev_smart_charging_config', 'departure_calendar_entity')",
    "as_local(strptime(state_attr(cal, 'start_time'), '%Y-%m-%d %H:%M:%S'))",
    "today_at(states('input_datetime.ev_departure_time'))",
    "reconcile_lead_minutes | float(120)",
)


def test_should_stop_charging_variable_defined():
    bp = _load_blueprint()
    stop_expr = bp["variables"]["should_stop_charging"]
    for fragment in _STOP_FRAGMENTS:
        assert fragment in stop_expr, f"should_stop_charging missing: {fragment}"


def test_should_start_charging_variable_defined():
    bp = _load_blueprint()
    start_expr = bp["variables"]["should_start_charging"]
    for fragment in _START_FRAGMENTS:
        assert fragment in start_expr, f"should_start_charging missing: {fragment}"


def test_price_triggers_use_from_and_to():
    """`from`/`to` together skip transitions through unknown/unavailable,
    so the nightly price-source gap can't fake a cheap/expensive change."""
    bp = _load_blueprint()
    triggers = {t["id"]: t for t in bp["triggers"]}
    assert triggers["price_cheap"]["from"] == "off"
    assert triggers["price_cheap"]["to"] == "on"
    assert triggers["price_expensive"]["from"] == "on"
    assert triggers["price_expensive"]["to"] == "off"


def test_plug_triggers_are_debounced():
    """Connected/disconnected must wait 10s of stable state so transient
    charger ramp states and unavailable-blip storms can't fire them."""
    bp = _load_blueprint()
    triggers = {t["id"]: t for t in bp["triggers"]}
    assert triggers["connected"]["for"] == "00:00:10"
    assert triggers["disconnected"]["for"] == "00:00:10"


def test_reconcile_trigger_is_event_driven():
    """The decision path must not poll: the old `periodic_check` time_pattern
    is replaced by a template trigger on the predicate union, with a 30 s
    `for:` that de-duplicates the immediate event triggers."""
    bp = _load_blueprint()
    triggers = {t["id"]: t for t in bp["triggers"]}
    assert "periodic_check" not in triggers
    reconcile = triggers["reconcile"]
    assert reconcile["trigger"] == "template"
    assert reconcile["for"] == "00:00:30"
    # The only remaining time_pattern is the cosmetic charging-notification
    # refresh — never part of start/stop decision making.
    assert [t["id"] for t in bp["triggers"] if t["trigger"] == "time_pattern"] == [
        "notification_refresh"
    ]


def _iter_trigger_conditions(node):
    """Yield every {condition: trigger, id: ...} mapping in an action tree."""
    if isinstance(node, dict):
        if node.get("condition") == "trigger" and "id" in node:
            yield node
        for value in node.values():
            yield from _iter_trigger_conditions(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_trigger_conditions(item)


def test_reconcile_branch_also_runs_on_ha_restart():
    """A template trigger does not fire for already-true state at startup,
    so the reconcile branch must also accept the `ha_restart` trigger."""
    bp = _load_blueprint()
    ids = [condition["id"] for condition in _iter_trigger_conditions(bp["actions"])]
    assert ids.count(["reconcile", "ha_restart"]) == 1
    assert "periodic_check" not in _BLUEPRINT.read_text(encoding="utf-8")


def test_reconcile_input_wired_via_trigger_variables():
    """Trigger templates cannot see action-level `variables`; the lead-time
    blueprint input must be exposed as a trigger variable instead."""
    bp = _load_blueprint()
    assert bp["trigger_variables"]["reconcile_lead_minutes"] == (
        "deadline_lead_time_minutes"
    )


def test_reconcile_template_fragments_match_decision_variables():
    """Triggers cannot reference action-level variables, so the reconcile
    template inlines the start/stop predicates. Guard against the inlined
    copy diverging from the single-source `variables`."""
    bp = _load_blueprint()
    triggers = {t["id"]: t for t in bp["triggers"]}
    template = triggers["reconcile"]["value_template"]
    for fragment in _START_FRAGMENTS + _STOP_FRAGMENTS + _EMERGENCY_DEADLINE_FRAGMENTS:
        assert fragment in template, f"reconcile template missing: {fragment}"


def _walk_for_empty_action_bodies(node, path, problems):
    """Collect every then/else/sequence/default key with a null or empty body."""
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path}.{key}"
            if key in ("then", "else", "sequence", "default"):
                if value is None:
                    problems.append(f"null `{key}:` at {here}")
                elif isinstance(value, list) and not value:
                    problems.append(f"empty `{key}: []` at {here}")
            _walk_for_empty_action_bodies(value, here, problems)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _walk_for_empty_action_bodies(item, f"{path}[{index}]", problems)


def test_no_null_or_empty_action_bodies():
    """A dedented step under `then:` silently produces `then: null`.

    Home Assistant rejects that at automation-creation time, and it is easy
    to introduce (and invisible in review) because the orphaned step still
    parses as a sibling list item. This has now bitten twice, so assert the
    whole tree structurally rather than eyeballing indentation.

    `choose: []` is the deliberate empty-choose splice trick for action
    selectors, so `choose` is not in the checked key set — but the
    `default:` that carries the spliced action list must never be empty.
    """
    problems: list[str] = []
    _walk_for_empty_action_bodies(_load_blueprint(), "<root>", problems)
    assert not problems, "empty action bodies in blueprint:\n  " + "\n  ".join(problems)
