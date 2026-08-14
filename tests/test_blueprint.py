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
    # charging_started pause, periodic_check pause).
    assert action_defaults == 12
    assert guards == action_defaults, (
        "every start/stop action call must be guarded by a dry-run branch"
    )


def test_should_stop_charging_variable_defined():
    bp = _load_blueprint()
    stop_expr = bp["variables"]["should_stop_charging"]
    # The auto-stop decision: connected + smart on + no override + charging
    # active + price explicitly not cheap.
    for fragment in (
        "is_state('binary_sensor.ev_vehicle_connected', 'on')",
        "is_state('input_boolean.ev_follow_price', 'on')",
        "is_state('input_boolean.ev_charge_now_override', 'off')",
        "is_state('binary_sensor.ev_charging_active', 'on')",
        "is_state('binary_sensor.ev_price_cheap', 'off')",
        "not is_state('binary_sensor.ev_price_cheap', 'unavailable')",
        "not is_state('binary_sensor.ev_price_cheap', 'unknown')",
    ):
        assert fragment in stop_expr, f"should_stop_charging missing: {fragment}"


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
