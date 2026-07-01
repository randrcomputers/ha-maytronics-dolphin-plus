"""BLE device resolution for Plus robots (Nordic UART / alternate GATT)."""

from __future__ import annotations

import logging

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_process_advertisements,
    async_rediscover_address,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from .const import (
    BLE_ADVERTISEMENT_WAIT_SECONDS,
    IOT_NOTIFY_UUID,
    IOT_SERVICE_UUID,
    IOT_WRITE_UUID,
    NUS_NOTIFY_UUID,
    NUS_SERVICE_UUID,
    NUS_WRITE_UUID,
    POP_NOTIFY_UUID,
    POP_SERVICE_UUID,
    POP_WRITE_UUID,
    TRANSPORT_IOT_GATT,
    TRANSPORT_NUS,
    TRANSPORT_POP,
)

_LOGGER = logging.getLogger(__name__)

_PLUS_SERVICE_UUIDS = {
    NUS_SERVICE_UUID.lower(),
    IOT_SERVICE_UUID.lower(),
    POP_SERVICE_UUID.lower(),
}


def transport_uuids(transport: str) -> tuple[str, str, str]:
    """Return (service, write, notify) UUIDs for the selected transport."""
    if transport == TRANSPORT_POP:
        return POP_SERVICE_UUID, POP_WRITE_UUID, POP_NOTIFY_UUID
    if transport == TRANSPORT_IOT_GATT:
        return IOT_SERVICE_UUID, IOT_WRITE_UUID, IOT_NOTIFY_UUID
    return NUS_SERVICE_UUID, NUS_WRITE_UUID, NUS_NOTIFY_UUID


def _addr_hex_digits(value: str) -> str:
    return "".join(c for c in value if c in "0123456789abcdefABCDEF").lower()


def _service_uuids_lower(si: BluetoothServiceInfoBleak) -> set[str]:
    return {u.lower() for u in si.service_uuids}


def _has_plus_service(si: BluetoothServiceInfoBleak) -> bool:
    advertised = _service_uuids_lower(si)
    return bool(advertised & _PLUS_SERVICE_UUIDS)


def _ble_device_from_scanners(hass: HomeAssistant, addr: str) -> BLEDevice | None:
    best: tuple[int, BLEDevice] | None = None
    for connectable in (True, False):
        entries = bluetooth.async_scanner_devices_by_address(hass, addr, connectable)
        for entry in entries:
            try:
                r = int(entry.advertisement.rssi)
            except (TypeError, ValueError):
                r = -999
            cand = entry.ble_device
            if best is None or r > best[0]:
                best = (r, cand)
    return best[1] if best else None


def _ble_device_from_discovered_identity(hass: HomeAssistant, addr: str) -> BLEDevice | None:
    want = _addr_hex_digits(addr)
    if len(want) != 12:
        return None

    candidates: list[tuple[int, BluetoothServiceInfoBleak]] = []
    for si in bluetooth.async_discovered_service_info(hass, connectable=True):
        name_d = _addr_hex_digits(si.name or "")
        addr_d = _addr_hex_digits(si.address)
        if want != name_d and want != addr_d:
            continue
        if not _has_plus_service(si):
            continue
        try:
            rssi = int(si.rssi) if si.rssi is not None else -999
        except (TypeError, ValueError):
            rssi = -999
        candidates.append((rssi, si))

    if not candidates:
        return None

    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1].device


async def async_resolve_ble_device(hass: HomeAssistant, address: str) -> BLEDevice:
    """Resolve a Bleak BLEDevice from HA Bluetooth data."""
    addr = dr.format_mac(address.strip())

    ble_device = bluetooth.async_ble_device_from_address(hass, addr, connectable=True)
    if ble_device is None:
        ble_device = bluetooth.async_ble_device_from_address(
            hass, addr, connectable=False
        )
    if ble_device is None:
        ble_device = _ble_device_from_scanners(hass, addr)
    if ble_device is None:
        ble_device = _ble_device_from_discovered_identity(hass, addr)

    if ble_device is None:
        async_rediscover_address(hass, addr)
        _LOGGER.debug(
            "Dolphin Plus %s not in Bluetooth cache; waiting up to %ss",
            addr,
            BLE_ADVERTISEMENT_WAIT_SECONDS,
        )
        try:
            service_info = await async_process_advertisements(
                hass,
                lambda _si: True,
                {"address": addr},
                BluetoothScanningMode.ACTIVE,
                BLE_ADVERTISEMENT_WAIT_SECONDS,
            )
        except TimeoutError:
            raise HomeAssistantError(
                f"Dolphin Plus ({addr}) did not advertise within "
                f"{BLE_ADVERTISEMENT_WAIT_SECONDS}s. Close the MyDolphin Plus app, "
                "ensure the robot is in range, and confirm the MAC in "
                "Settings → Devices & services → Bluetooth."
            ) from None
        ble_device = service_info.device

    return ble_device
