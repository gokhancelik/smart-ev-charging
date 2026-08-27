"""The Smart EV Charging integration.

Owns entity configuration (see config_flow.py) plus best-effort
auto-install of the bundled blueprint, package, scripts and dashboard on
setup (see _install_bundled_assets below). All charging decision logic
lives in the companion HA package and blueprint — see
packages/smart_ev_charging.yaml and
blueprint/smart_ev_charging.yaml inside this component directory.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import (
    DOMAIN,
    PLATFORMS,
    SERVICE_INSTALL_DASHBOARD,
    SERVICE_UNINSTALL_DASHBOARD,
)
from .dashboard import install_dashboard, rebuild_installed_dashboard, uninstall_dashboard

_LOGGER = logging.getLogger(__name__)

_INTEGRATION_DIR = Path(__file__).parent
_BLUEPRINT_SOURCE = _INTEGRATION_DIR / "blueprint" / "smart_ev_charging.yaml"
_BLUEPRINT_DEST_PARTS = (
    "blueprints",
    "automation",
    "smart_ev_charging",
    "smart_ev_charging.yaml",
)
_PACKAGE_SOURCE = _INTEGRATION_DIR / "packages" / "smart_ev_charging.yaml"
_PACKAGE_DEST_PARTS = ("packages", "smart_ev_charging.yaml")
_SCRIPTS_SOURCE = _INTEGRATION_DIR / "scripts" / "smart_ev_charging_scripts.yaml"
_SCRIPTS_DEST_PARTS = ("scripts", "smart_ev_charging_scripts.yaml")
_NOTIFICATION_ID = "smart_ev_charging_setup"
_ISSUE_SMART_CHARGING_DISABLED = "smart_charging_disabled"
_FOLLOW_PRICE_ENTITY = "input_boolean.ev_follow_price"


async def _async_install_dashboard_service(call: ServiceCall) -> None:
    """Install or update the Smart EV Charging dashboard."""
    await install_dashboard(call.hass)


async def _async_uninstall_dashboard_service(call: ServiceCall) -> None:
    """Remove the Smart EV Charging dashboard."""
    await uninstall_dashboard(call.hass)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    blueprint_synced, package_installed, scripts_installed, inc = (
        await hass.async_add_executor_job(_install_bundled_assets, hass)
    )
    if blueprint_synced or package_installed or scripts_installed or not inc:
        await _async_notify_setup_complete(
            hass, blueprint_synced, package_installed, scripts_installed, inc
        )

    await rebuild_installed_dashboard(hass)

    hass.services.async_register(
        DOMAIN,
        SERVICE_INSTALL_DASHBOARD,
        _async_install_dashboard_service,
        schema=vol.Schema({}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_UNINSTALL_DASHBOARD,
        _async_uninstall_dashboard_service,
        schema=vol.Schema({}),
    )

    # Raise (or clear) the "smart charging is installed but disabled"
    # repair issue, and keep it in sync live when the toggle flips. The
    # listener also fires the moment the package's helper appears, so a
    # package that loads after this integration is still covered.
    entry.async_on_unload(
        async_track_state_change_event(
            hass,
            [_FOLLOW_PRICE_ENTITY],
            _build_follow_price_change_handler(hass),
        )
    )
    _update_smart_charging_disabled_issue(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.services.async_remove(DOMAIN, SERVICE_INSTALL_DASHBOARD)
        hass.services.async_remove(DOMAIN, SERVICE_UNINSTALL_DASHBOARD)
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _install_bundled_assets(hass: HomeAssistant) -> tuple[bool, bool, bool, bool]:
    """Install bundled assets into the config dir.

    Runs in the executor (blocking file I/O). Three different policies:

    - The blueprint is kept in sync on every setup/restart (overwritten
      whenever its content differs from the bundled copy). Blueprints are
      templates you customize by changing the *automation's* inputs, not
      by hand-editing the blueprint file, so re-syncing it is how bugfixes
      actually reach an already-installed automation. Without this, a
      fixed blueprint shipped in a new release would never reach anyone
      who installed an earlier, broken version.
    - The dashboard, package and scripts are written once and never
      touched again — they're commonly hand-customized (card layout,
      notification wording, helper tweaks) after install, and overwriting
      them would destroy real user work.

    Returns (blueprint_synced, package_installed, scripts_installed,
    config_includes_present) — True for the *_installed flags only when
    this call actually wrote something; the last is True when
    configuration.yaml already carries both include lines.
    """
    blueprint_synced = _sync_file(hass, _BLUEPRINT_SOURCE, _BLUEPRINT_DEST_PARTS)
    _remove_legacy_blueprint(hass)
    package_installed = _copy_if_missing(hass, _PACKAGE_SOURCE, _PACKAGE_DEST_PARTS)
    scripts_installed = _copy_if_missing(hass, _SCRIPTS_SOURCE, _SCRIPTS_DEST_PARTS)
    inc = _config_has_includes(hass)
    return blueprint_synced, package_installed, scripts_installed, inc


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


def _remove_legacy_blueprint(hass: HomeAssistant) -> bool:
    """Remove the pre-1.4 root-level blueprint file if it mirrors ours.

    Up to v1.4 the blueprint lived at ``blueprints/automation/
    smart_ev_charging.yaml`` (no subfolder). That path is never touched by
    the subfolder sync, so it silently drifts out of date and shows up as a
    second (broken) entry in the Blueprints UI. Delete only when its content
    is byte-identical to the bundled copy — a hand-authored or customized
    file keeps the user's work.
    """
    legacy = Path(
        hass.config.path("blueprints", "automation", "smart_ev_charging.yaml")
    )
    if not legacy.exists():
        return False
    if legacy.read_bytes() != _BLUEPRINT_SOURCE.read_bytes():
        _LOGGER.info(
            "Smart EV Charging: legacy blueprint %s differs from the bundled copy; leaving it in place",
            legacy,
        )
        return False
    legacy.unlink()
    _LOGGER.info("Smart EV Charging: removed legacy blueprint %s", legacy)
    return True


@callback
def _update_smart_charging_disabled_issue(hass: HomeAssistant) -> None:
    """Raise or clear the "smart charging is installed but disabled" issue.

    The feature this integration exists to provide is a no-op while
    ``input_boolean.ev_follow_price`` is off and the charger auto-starts on
    plug-in — an easy onboarding trap diagnosed on a live install. No-ops
    (rather than raising) if the package's helper isn't loaded yet; the
    state-change listener covers that case.

    Synchronous on purpose: despite the ``async_`` prefix,
    ``issue_registry.async_create_issue`` / ``async_delete_issue`` are
    ``@callback`` functions returning ``None``, not coroutines. Awaiting
    them raises ``TypeError: object NoneType can't be used in 'await'
    expression`` and takes ``async_setup_entry`` down with it.
    """
    state = hass.states.get(_FOLLOW_PRICE_ENTITY)
    if state is None:
        _LOGGER.debug(
            "Smart EV Charging: %s not loaded yet; skipping repair-issue update",
            _FOLLOW_PRICE_ENTITY,
        )
        return
    if state.state == "off":
        async_create_issue(
            hass,
            DOMAIN,
            _ISSUE_SMART_CHARGING_DISABLED,
            is_fixable=False,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key=_ISSUE_SMART_CHARGING_DISABLED,
        )
    else:
        async_delete_issue(hass, DOMAIN, _ISSUE_SMART_CHARGING_DISABLED)


def _build_follow_price_change_handler(hass: HomeAssistant):
    """Return the toggle-watcher that re-syncs the disabled-toggle repair issue."""

    @callback
    def _handler(event: Event[EventStateChangedData]) -> None:
        _update_smart_charging_disabled_issue(hass)

    return _handler


def _config_has_includes(hass: HomeAssistant) -> bool:
    """Return True when configuration.yaml carries both include lines.

    The package and scripts are plain YAML files that Home Assistant only
    loads if they're referenced from configuration.yaml. We can't edit
    that file for the user, but we can detect whether the two lines are
    present so the setup notification can tell them exactly what's left.
    """
    config_yaml = Path(hass.config.path("configuration.yaml"))
    if not config_yaml.exists():
        return False
    try:
        text = config_yaml.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return (
        "!include_dir_named packages" in text
        and "!include_dir_merge_named scripts" in text
    )


async def _async_notify_setup_complete(
    hass: HomeAssistant,
    blueprint_synced: bool,
    package_installed: bool,
    scripts_installed: bool,
    config_includes_present: bool,
) -> None:
    lines = ["Smart EV Charging installed what it safely can on its own:", ""]
    if blueprint_synced:
        lines.append(
            "- ✅ Blueprint synced to `blueprints/automation/smart_ev_charging/` "
            "— go to **Settings > Automations & Scenes > Blueprints** to create "
            "the automation from it. Already have one? Restart Home Assistant "
            "(or reload Automations) to pick up this update."
        )
    if package_installed:
        lines.append(
            "- ✅ Helper package written to `packages/smart_ev_charging.yaml`."
        )
    if scripts_installed:
        lines.append(
            "- ✅ Scripts written to `scripts/smart_ev_charging_scripts.yaml`."
        )
    lines.append("")
    lines.append(
        "Still needed (can't be automated — Home Assistant only loads the "
        "package and scripts if `configuration.yaml` points at them, and "
        "that requires a full restart):"
    )
    if config_includes_present:
        lines.append("- Both include lines are present — just **Restart Home Assistant**.")
    else:
        lines.append(
            "- Add these two lines to `configuration.yaml`, then restart:"
        )
        lines.append("  ```yaml")
        lines.append("  homeassistant:")
        lines.append("    packages: !include_dir_named packages")
        lines.append("")
        lines.append("  script: !include_dir_merge_named scripts")
        lines.append("  ```")

    await hass.services.async_call(
        "persistent_notification",
        "create",
        {
            "title": "Smart EV Charging: setup",
            "message": "\n".join(lines),
            "notification_id": _NOTIFICATION_ID,
        },
    )
