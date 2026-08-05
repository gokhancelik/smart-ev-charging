"""The Smart EV Charging integration.

Owns entity configuration (see config_flow.py) plus best-effort
auto-install of the bundled blueprint and dashboard on setup (see
_install_bundled_assets below). All charging decision logic lives in the
companion HA package and blueprint — see packages/smart_ev_charging.yaml
and custom_components/smart_ev_charging/blueprint/smart_ev_charging.yaml
in this repository.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import PLATFORMS

_LOGGER = logging.getLogger(__name__)

_INTEGRATION_DIR = Path(__file__).parent
_BLUEPRINT_SOURCE = _INTEGRATION_DIR / "blueprint" / "smart_ev_charging.yaml"
_BLUEPRINT_DEST_PARTS = (
    "blueprints",
    "automation",
    "smart_ev_charging",
    "smart_ev_charging.yaml",
)
_DASHBOARD_SOURCE = _INTEGRATION_DIR / "dashboards" / "dashboard.yaml"
_DASHBOARD_DEST_PARTS = ("dashboards", "smart_ev_charging_dashboard.yaml")
_NOTIFICATION_ID = "smart_ev_charging_setup"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    blueprint_installed, dashboard_installed = await hass.async_add_executor_job(
        _install_bundled_assets, hass
    )
    if blueprint_installed or dashboard_installed:
        await _async_notify_setup_complete(hass, blueprint_installed, dashboard_installed)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _install_bundled_assets(hass: HomeAssistant) -> tuple[bool, bool]:
    """Copy the bundled blueprint/dashboard into the config dir if missing.

    Runs in the executor (blocking file I/O). Never overwrites an
    existing file, so a user's own edits (or a deliberate removal) are
    left alone on subsequent restarts. Returns (blueprint_installed,
    dashboard_installed) — True only for files actually written just now.
    """
    blueprint_installed = _copy_if_missing(
        hass, _BLUEPRINT_SOURCE, _BLUEPRINT_DEST_PARTS
    )
    dashboard_installed = _copy_if_missing(
        hass, _DASHBOARD_SOURCE, _DASHBOARD_DEST_PARTS
    )
    return blueprint_installed, dashboard_installed


def _copy_if_missing(
    hass: HomeAssistant, source: Path, dest_parts: tuple[str, ...]
) -> bool:
    dest = Path(hass.config.path(*dest_parts))
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    _LOGGER.info("Smart EV Charging: installed %s", dest)
    return True


async def _async_notify_setup_complete(
    hass: HomeAssistant, blueprint_installed: bool, dashboard_installed: bool
) -> None:
    lines = ["Smart EV Charging installed what it safely can on its own:", ""]
    if blueprint_installed:
        lines.append(
            "- ✅ Blueprint copied to `blueprints/automation/smart_ev_charging/` "
            "— go to **Settings > Automations & Scenes > Blueprints** to create "
            "the automation from it."
        )
    if dashboard_installed:
        lines.append(
            "- ✅ Dashboard YAML copied to "
            "`dashboards/smart_ev_charging_dashboard.yaml` — Home Assistant "
            "doesn't offer a safe way for an integration to add a dashboard to "
            "your sidebar automatically, so add it yourself: **Settings > "
            "Dashboards > + Add Dashboard > New dashboard from YAML**, then "
            "paste that file's contents."
        )
    lines.append("")
    lines.append(
        "Still needed (can't be automated — see the "
        "[README](https://github.com/gokhancelik/smart-ev-charging#installation)):"
    )
    lines.append(
        "- Copy `packages/smart_ev_charging.yaml` and "
        "`scripts/smart_ev_charging_scripts.yaml` into your config"
    )
    lines.append(
        "- Add `packages: !include_dir_named packages` and "
        "`script: !include_dir_merge_named scripts` to `configuration.yaml`"
    )
    lines.append("- Restart Home Assistant")

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Smart EV Charging: setup",
            "message": "\n".join(lines),
            "notification_id": _NOTIFICATION_ID,
        },
    )
