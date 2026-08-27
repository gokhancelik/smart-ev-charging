"""Tests for __init__ repair-issue and blueprint-cleanup logic.

The conftest stubs let ``custom_components.smart_ev_charging.__init__`` be
imported in-process; these tests exercise the "smart charging disabled"
repair-issue sync and the legacy blueprint removal decisions.
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import homeassistant.helpers.issue_registry as issue_registry

import custom_components.smart_ev_charging.__init__ as init

FOLLOW_PRICE = init._FOLLOW_PRICE_ENTITY


@pytest.fixture
def issue_log(monkeypatch):
    """Record create/delete calls instead of the stub no-ops."""
    calls = {"create": [], "delete": []}

    def _create(hass, domain, issue_id, **kwargs):
        calls["create"].append((domain, issue_id, kwargs))

    def _delete(hass, domain, issue_id):
        calls["delete"].append((domain, issue_id))

    monkeypatch.setattr(init, "async_create_issue", _create)
    monkeypatch.setattr(init, "async_delete_issue", _delete)
    return calls


def test_issue_noop_when_helper_not_loaded_yet(hass, issue_log):
    """The package helper may load after the integration — must not raise."""
    assert hass.states.get(FOLLOW_PRICE) is None
    init._update_smart_charging_disabled_issue(hass)
    assert issue_log["create"] == []
    assert issue_log["delete"] == []


def test_issue_created_when_follow_price_off(hass, add_state, issue_log):
    add_state(FOLLOW_PRICE, "off")
    init._update_smart_charging_disabled_issue(hass)
    assert len(issue_log["create"]) == 1
    domain, issue_id, kwargs = issue_log["create"][0]
    assert domain == init.DOMAIN
    assert issue_id == init._ISSUE_SMART_CHARGING_DISABLED
    assert kwargs["severity"] == issue_registry.IssueSeverity.WARNING
    assert issue_log["delete"] == []


def test_issue_deleted_when_follow_price_on(hass, add_state, issue_log):
    add_state(FOLLOW_PRICE, "on")
    init._update_smart_charging_disabled_issue(hass)
    assert issue_log["delete"] == [(init.DOMAIN, init._ISSUE_SMART_CHARGING_DISABLED)]
    assert issue_log["create"] == []


def test_follow_price_change_handler_is_callable(hass):
    handler = init._build_follow_price_change_handler(hass)
    assert callable(handler)


def test_issue_translation_key_matches_strings(hass, add_state):
    """The translation_key must exist in strings.json, or the UI shows a raw key."""
    import json

    root = REPO_ROOT / "custom_components" / "smart_ev_charging"
    strings = json.loads((root / "strings.json").read_text(encoding="utf-8"))
    assert init._ISSUE_SMART_CHARGING_DISABLED in strings["issues"]

    en = json.loads((root / "translations" / "en.json").read_text(encoding="utf-8"))
    assert init._ISSUE_SMART_CHARGING_DISABLED in en["issues"]


def test_legacy_blueprint_removed_only_when_identical(tmp_path, monkeypatch):
    """A byte-identical legacy copy is deleted; a customized copy is kept."""
    bundled = (REPO_ROOT / "custom_components" / "smart_ev_charging" / "blueprint" / "smart_ev_charging.yaml").read_bytes()
    legacy_dir = tmp_path / "blueprints" / "automation"
    legacy_dir.mkdir(parents=True)
    legacy = legacy_dir / "smart_ev_charging.yaml"

    class FakeHassConfig:
        def path(self, *parts):
            return str(tmp_path.joinpath(*parts))

    class FakeHass:
        config = FakeHassConfig()

    # Identical copy -> removed.
    legacy.write_bytes(bundled)
    assert init._remove_legacy_blueprint(FakeHass()) is True
    assert not legacy.exists()

    # Customized copy -> kept.
    legacy.write_text("my custom blueprint\n", encoding="utf-8")
    assert init._remove_legacy_blueprint(FakeHass()) is False
    assert legacy.exists()