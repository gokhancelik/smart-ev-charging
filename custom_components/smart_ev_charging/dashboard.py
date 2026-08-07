"""Dashboard installation for Smart EV Charging.

Builds the Lovelace dashboard from the bundled ``dashboards/dashboard.yaml``
(a static JSON-compatible YAML document) and installs it into Home
Assistant's storage-mode Lovelace at runtime, so the user gets it in the
sidebar without pasting YAML manually.

Ported from the ``dynamic_energy_prices`` integration's ``dashboard.py``:
the install/update/uninstall logic and the ``install_dashboard`` /
``uninstall_dashboard`` services are the same; only the config source
differs (static bundled YAML here, entity-registry-built config there).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from homeassistant.core import HomeAssistant

from .const import DASHBOARD_ICON, DASHBOARD_TITLE, DASHBOARD_URL_PATH, DOMAIN

_LOGGER = logging.getLogger(__name__)

_INTEGRATION_DIR = Path(__file__).parent

try:
    from homeassistant.components import frontend as _ll_frontend
    from homeassistant.components.lovelace import const as _ll_const
    from homeassistant.components.lovelace import dashboard as _ll_dashboard
    from homeassistant.helpers import storage as _ll_storage

    _INTERNAL_IMPORTS_OK = True
except ImportError:  # pragma: no cover - mocked/test environments
    _ll_frontend = None
    _ll_const = None
    _ll_dashboard = None
    _ll_storage = None
    _INTERNAL_IMPORTS_OK = False


async def load_dashboard_config(hass: HomeAssistant) -> dict[str, Any]:
    """Load the bundled dashboard YAML into a Lovelace config dict."""
    path = _INTEGRATION_DIR / "dashboards" / "dashboard.yaml"

    def _load() -> dict[str, Any]:
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    return await hass.async_add_executor_job(_load)


def is_dashboard_installed(hass: HomeAssistant) -> bool:
    """Return True when the dashboard is present in Lovelace."""
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if not isinstance(dashboards, dict):
        return False
    return DASHBOARD_URL_PATH in dashboards


async def save_dashboard(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Persist the dashboard config into Home Assistant's Lovelace.

    ``hass.data["lovelace"].dashboards`` is a ``dict`` mapping ``url_path``
    to a Lovelace config object. If our dashboard already exists we save
    straight into it; otherwise we create a storage-mode dashboard (mirroring
    how the Lovelace component creates dashboards) and then save.

    Returns True on success, or False when Lovelace is unavailable so callers
    can fall back to the raw YAML file.
    """
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if not isinstance(dashboards, dict):
        _LOGGER.warning(
            "Lovelace is not available; the dashboard could not be installed "
            "automatically. Use Settings > Dashboards > 'Add dashboard from "
            "YAML' and paste dashboards/dashboard.yaml instead."
        )
        return False

    existing = dashboards.get(DASHBOARD_URL_PATH)
    if existing is not None:
        try:
            await existing.async_save(config)
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to save the %s dashboard.", DASHBOARD_TITLE)
            return False
        _LOGGER.info("Updated the %s dashboard.", DASHBOARD_TITLE)
        return True

    return await _create_storage_dashboard(hass, lovelace, dashboards, config)


async def _create_storage_dashboard(
    hass: HomeAssistant,
    lovelace: Any,
    dashboards: dict,
    config: dict[str, Any],
) -> bool:
    """Create a storage-mode dashboard, register its panel, and save."""

    if not _INTERNAL_IMPORTS_OK or _ll_dashboard is None:
        _LOGGER.warning(
            "Could not load Lovelace internals to auto-install the dashboard; "
            "use the bundled YAML instead."
        )
        return False

    url_path = DASHBOARD_URL_PATH
    item: dict[str, Any] = {
        _ll_const.CONF_REQUIRE_ADMIN: False,
        _ll_const.CONF_ICON: DASHBOARD_ICON,
        _ll_const.CONF_TITLE: DASHBOARD_TITLE,
        _ll_const.CONF_SHOW_IN_SIDEBAR: True,
        _ll_const.CONF_MODE: _ll_const.MODE_STORAGE,
        _ll_const.CONF_URL_PATH: url_path,
        "id": url_path,
    }
    try:
        # Persist the dashboard entry so it survives a restart.
        store = _ll_storage.Store(hass, 1, "lovelace_dashboards")
        data = await store.async_load()
        data = data or {"items": []}
        data.setdefault("items", [])
        if not any(i.get("url_path") == url_path for i in data["items"]):
            data["items"].append(item)
            await store.async_save(data)

        new_dashboard = _ll_dashboard.LovelaceStorage(hass, item)
        dashboards[url_path] = new_dashboard
        _ll_frontend.async_register_built_in_panel(
            hass,
            _ll_const.DOMAIN,
            frontend_url_path=url_path,
            require_admin=False,
            show_in_sidebar=True,
            sidebar_title=DASHBOARD_TITLE,
            sidebar_icon=DASHBOARD_ICON,
            config={"mode": _ll_const.MODE_STORAGE},
            update=False,
        )
        await new_dashboard.async_save(config)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to create the %s dashboard.", DASHBOARD_TITLE)
        return False

    _LOGGER.info("Installed the %s dashboard.", DASHBOARD_TITLE)
    return True


async def install_dashboard(hass: HomeAssistant) -> bool:
    """Load the bundled config and install/update the dashboard."""
    try:
        config = await load_dashboard_config(hass)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to load the bundled dashboard config.")
        return False
    return await save_dashboard(hass, config)


async def rebuild_installed_dashboard(hass: HomeAssistant) -> bool:
    """Rebuild the dashboard after an upgrade, but only if it exists.

    Keeps an already-installed dashboard current with new cards on every
    Home Assistant start, while never creating a dashboard for users who
    didn't opt in.
    """
    if not is_dashboard_installed(hass):
        return False
    return await install_dashboard(hass)


async def uninstall_dashboard(hass: HomeAssistant) -> bool:
    """Remove the dashboard entry, panel, and its config."""
    lovelace = hass.data.get("lovelace")
    dashboards = getattr(lovelace, "dashboards", None)
    if not isinstance(dashboards, dict):
        _LOGGER.warning("Lovelace is not available; cannot uninstall the dashboard.")
        return False

    if DASHBOARD_URL_PATH not in dashboards:
        _LOGGER.info("The %s dashboard is not installed.", DASHBOARD_TITLE)
        return False

    if not _INTERNAL_IMPORTS_OK or _ll_frontend is None or _ll_storage is None:
        _LOGGER.warning("Could not load Lovelace internals to uninstall the dashboard.")
        return False

    try:
        _ll_frontend.async_remove_panel(hass, DASHBOARD_URL_PATH)

        store = _ll_storage.Store(hass, 1, "lovelace_dashboards")
        data = await store.async_load() or {"items": []}
        data.setdefault("items", [])
        data["items"] = [
            item
            for item in data["items"]
            if item.get("url_path") != DASHBOARD_URL_PATH
        ]
        await store.async_save(data)

        dashboard = dashboards.pop(DASHBOARD_URL_PATH, None)
        if dashboard is not None and hasattr(dashboard, "async_delete"):
            await dashboard.async_delete()
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Failed to uninstall the %s dashboard.", DASHBOARD_TITLE)
        return False

    _LOGGER.info("Uninstalled the %s dashboard.", DASHBOARD_TITLE)
    return True