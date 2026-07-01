"""Integration options."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry

from .const import (
    BLE_SESSION_KEEPALIVE_INTERVAL_SEC,
    OPT_BLE_KEEPALIVE_SEC,
    OPT_STATE_POLL_SEC,
    STATE_POLL_INTERVAL_SEC,
)


def get_integration_options(entry: ConfigEntry) -> dict[str, int]:
    data = entry.options
    return {
        OPT_BLE_KEEPALIVE_SEC: int(
            data.get(OPT_BLE_KEEPALIVE_SEC, BLE_SESSION_KEEPALIVE_INTERVAL_SEC)
        ),
        OPT_STATE_POLL_SEC: int(
            data.get(OPT_STATE_POLL_SEC, STATE_POLL_INTERVAL_SEC)
        ),
    }
