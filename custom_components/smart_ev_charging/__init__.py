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

    blueprint_synced, dashboard_installed = await hass.async_add_executor_job(
        _install_bundled_assets, hass
    )
    if blueprint_synced or dashboard_installed:
        await _async_notify_setup_complete(hass, blueprint_synced, dashboard_installed)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _install_bundled_assets(hass: HomeAssistant) -> tuple[bool, bool]:
    """Install the bundled blueprint/dashboard into the config dir.

    Runs in the executor (blocking file I/O). Two different policies:

    - The blueprint is kept in sync on every setup/restart (overwritten
      whenever its content differs from the bundled copy). Blueprints are
      templates you customize by changing the *automation's* inputs, not
      by hand-editing the blueprint file, so re-syncing it is how bugfixes
      actually reach an already-installed automation. Without this, a
      fixed blueprint shipped in a new release would never reach anyone
      who installed an earlier, broken version.
    - The dashboard is written once and never touched again — dashboards
      are commonly hand-customized (card layout, added sections) after
      import, and overwriting that would destroy real user work.

    Returns (blueprint_synced, dashboard_installed) — True only when this
    call actually wrote something.
    """
    blueprint_synced = _sync_file(hass, _BLUEPRINT_SOURCE, _BLUEPRINT_DEST_PARTS)
    dashboard_installed = _copy_if_missing(
        hass, _DASHBOARD_SOURCE, _DASHBOARD_DEST_PARTS
    )
    return blueprint_synced, dashboard_installed


def _sync_file(hass: HomeAssistant, source: Path, dest_parts: tuple[str, ...]) -> bool:
    """Write source to dest whenever their contents differ. Returns True if written."""
    dest = Path(hass.config.path(*dest_parts))
    if dest.exists() and dest.read_bytes() == source.read_bytes():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dest)
    _LOGGER.info("Smart EV Charging: synced %s", dest)
    return True


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
    hass: HomeAssistant, blueprint_synced: bool, dashboard_installed: bool
) -> None:
    lines = ["Smart EV Charging installed what it safely can on its own:", ""]
    if blueprint_synced:
        lines.append(
            "- ✅ Blueprint synced to `blueprints/automation/smart_ev_charging/` "
            "— go to **Settings > Automations & Scenes > Blueprints** to create "
            "the automation from it. Already have one? Restart Home Assistant "
            "(or reload Automations) to pick up this update."
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
