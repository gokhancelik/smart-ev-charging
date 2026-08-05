"""Tests for dashboard installation (storage-mode Lovelace)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.smart_ev_charging import dashboard as dash
from custom_components.smart_ev_charging.const import (
    DASHBOARD_ICON,
    DASHBOARD_TITLE,
    DASHBOARD_URL_PATH,
)


def _run(coro):
    return asyncio.run(coro)


def _lovelace_hass(existing=None) -> MagicMock:
    lovelace = MagicMock()
    lovelace.dashboards = {} if existing is None else {DASHBOARD_URL_PATH: existing}
    hass = MagicMock()
    hass.data = {"lovelace": lovelace}
    return hass


def test_load_dashboard_config_returns_yaml_dict():
    d = dash.load_dashboard_config()
    assert isinstance(d, dict)
    assert d.get("title") == "Smart EV Charging"
    assert isinstance(d.get("views"), list)


def test_is_dashboard_installed_true_when_present():
    assert dash.is_dashboard_installed(_lovelace_hass(existing=MagicMock())) is True


def test_is_dashboard_installed_false_when_missing():
    assert dash.is_dashboard_installed(_lovelace_hass()) is False


def test_is_dashboard_installed_false_without_lovelace():
    hass = MagicMock()
    hass.data = {}
    assert dash.is_dashboard_installed(hass) is False


class TestSaveDashboard:
    def test_updates_existing_dashboard(self):
        config = {"title": "Smart EV Charging", "views": []}
        existing = MagicMock()
        existing.async_save = AsyncMock()
        hass = _lovelace_hass(existing=existing)

        ok = _run(dash.save_dashboard(hass, config))

        assert ok is True
        existing.async_save.assert_awaited_once_with(config)

    def test_creates_storage_dashboard(self):
        config = {"title": "Smart EV Charging", "views": []}
        new_dashboard = MagicMock()
        new_dashboard.async_save = AsyncMock()

        fake_store = MagicMock()
        fake_store.async_load = AsyncMock(return_value={"items": []})
        fake_store.async_save = AsyncMock()
        store_cls = MagicMock(return_value=fake_store)

        fake_const = MagicMock()
        fake_const.CONF_REQUIRE_ADMIN = "require_admin"
        fake_const.CONF_ICON = "icon"
        fake_const.CONF_TITLE = "title"
        fake_const.CONF_SHOW_IN_SIDEBAR = "show_in_sidebar"
        fake_const.CONF_MODE = "mode"
        fake_const.CONF_URL_PATH = "url_path"
        fake_const.MODE_STORAGE = "storage"
        fake_const.DOMAIN = "lovelace"

        fake_dashboard_mod = MagicMock()
        fake_dashboard_mod.LovelaceStorage = MagicMock(return_value=new_dashboard)

        lovelace = MagicMock()
        lovelace.dashboards = {}
        hass = MagicMock()
        hass.data = {"lovelace": lovelace}
        ll_frontend = MagicMock()

        with (
            patch.object(dash, "_INTERNAL_IMPORTS_OK", True),
            patch.object(dash, "_ll_const", fake_const),
            patch.object(dash, "_ll_dashboard", fake_dashboard_mod),
            patch.object(dash, "_ll_frontend", ll_frontend),
            patch.object(dash, "_ll_storage", type("S", (), {"Store": store_cls})),
        ):
            ok = _run(dash.save_dashboard(hass, config))

        assert ok is True
        store_cls.assert_called()
        fake_store.async_save.assert_awaited_once()
        fake_dashboard_mod.LovelaceStorage.assert_called_once()
        new_dashboard.async_save.assert_awaited_once_with(config)
        assert DASHBOARD_URL_PATH in lovelace.dashboards
        ll_frontend.async_register_built_in_panel.assert_called_once()
        panel_kwargs = ll_frontend.async_register_built_in_panel.call_args.kwargs
        assert panel_kwargs["frontend_url_path"] == DASHBOARD_URL_PATH
        assert panel_kwargs["show_in_sidebar"] is True
        assert panel_kwargs["sidebar_title"] == DASHBOARD_TITLE
        assert panel_kwargs["sidebar_icon"] == DASHBOARD_ICON

    def test_without_lovelace_returns_false(self):
        hass = MagicMock()
        hass.data = {"lovelace": MagicMock()}
        hass.data["lovelace"].dashboards = None
        assert _run(dash.save_dashboard(hass, {"title": "x"})) is False

    def test_internals_unavailable_returns_false(self):
        hass = _lovelace_hass()
        with (
            patch.object(dash, "_INTERNAL_IMPORTS_OK", False),
            patch.object(dash, "_ll_dashboard", None),
        ):
            assert _run(dash.save_dashboard(hass, {"title": "x"})) is False


class TestInstallDashboard:
    def test_installs_bundled_config(self):
        existing = MagicMock()
        existing.async_save = AsyncMock()
        hass = _lovelace_hass(existing=existing)

        with patch.object(
            dash, "load_dashboard_config", return_value={"title": "Smart EV Charging"}
        ):
            ok = _run(dash.install_dashboard(hass))

        assert ok is True
        existing.async_save.assert_awaited_once_with({"title": "Smart EV Charging"})

    def test_install_failure_returns_false(self):
        hass = _lovelace_hass()
        with (
            patch.object(
                dash, "load_dashboard_config", side_effect=RuntimeError("boom")
            ),
            patch.object(dash, "_LOGGER"),
        ):
            assert _run(dash.install_dashboard(hass)) is False


class TestRebuildDashboard:
    def test_rebuild_only_when_installed(self):
        hass = _lovelace_hass(existing=MagicMock())
        with patch.object(
            dash, "install_dashboard", AsyncMock(return_value=True)
        ) as mock_install:
            assert _run(dash.rebuild_installed_dashboard(hass)) is True
            mock_install.assert_awaited_once_with(hass)

    def test_rebuild_skips_when_not_installed(self):
        hass = _lovelace_hass()
        with patch.object(dash, "install_dashboard", AsyncMock()) as mock_install:
            assert _run(dash.rebuild_installed_dashboard(hass)) is False
        mock_install.assert_not_awaited()


class TestUninstallDashboard:
    def test_uninstalls_existing_dashboard(self):
        existing = MagicMock()
        existing.async_delete = AsyncMock()
        lovelace = MagicMock()
        lovelace.dashboards = {DASHBOARD_URL_PATH: existing}

        fake_store = MagicMock()
        fake_store.async_load = AsyncMock(
            return_value={"items": [{"url_path": DASHBOARD_URL_PATH}]}
        )
        fake_store.async_save = AsyncMock()
        store_cls = MagicMock(return_value=fake_store)

        ll_frontend = MagicMock()

        hass = MagicMock()
        hass.data = {"lovelace": lovelace}

        with (
            patch.object(dash, "_INTERNAL_IMPORTS_OK", True),
            patch.object(dash, "_ll_frontend", ll_frontend),
            patch.object(dash, "_ll_storage", type("S", (), {"Store": store_cls})),
        ):
            ok = _run(dash.uninstall_dashboard(hass))

        assert ok is True
        ll_frontend.async_remove_panel.assert_called_once_with(hass, DASHBOARD_URL_PATH)
        fake_store.async_save.assert_awaited_once()
        assert DASHBOARD_URL_PATH not in lovelace.dashboards
        existing.async_delete.assert_awaited_once()

    def test_not_installed_returns_false(self):
        assert _run(dash.uninstall_dashboard(_lovelace_hass())) is False

    def test_missing_lovelace_returns_false(self):
        hass = MagicMock()
        hass.data = {}
        assert _run(dash.uninstall_dashboard(hass)) is False