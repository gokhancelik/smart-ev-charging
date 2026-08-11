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
    # + 3 stop sites (price_expensive, battery reached target,
    # manual_stop_requested).
    assert action_defaults == 9
    assert guards == action_defaults, (
        "every start/stop action call must be guarded by a dry-run branch"
    )