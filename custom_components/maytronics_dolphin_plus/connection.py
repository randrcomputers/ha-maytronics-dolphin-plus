"""BLE client for Dolphin Plus — short sessions over Nordic UART."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .ble import async_resolve_ble_device, transport_uuids
from .const import (
    DATA_BLE_SESSION,
    DOMAIN,
    OPT_BLE_KEEPALIVE_SEC,
    PROFILE_IOT,
)
from .options import get_integration_options
from .protocol import (
    build_shutdown,
    build_startup,
    build_system_status_request,
    iter_iot_frames,
    load_protocol_spec,
    parse_iot_frame_payload,
    parse_system_status,
)

_LOGGER = logging.getLogger(__name__)

_BLE_CONNECT_TIMEOUT = 35.0
_NOTIFY_TIMEOUT = 4.0
_POST_WRITE_DELAY = 0.35


class DolphinPlusBleConnection:
    """Connect per operation, then disconnect (same pattern as legacy integration)."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        entry_id: str,
        *,
        profile: str,
        transport: str,
    ) -> None:
        self.hass = hass
        self.address = address
        self._entry_id = entry_id
        self._profile = profile
        self._transport = transport
        self._spec = load_protocol_spec(profile)
        self._service_uuid, self._write_uuid, self._notify_uuid = transport_uuids(
            transport
        )
        self._lock = asyncio.Lock()
        self._command_waiters = 0
        self._client: BleakClientWithServiceCache | None = None
        self._shutting_down = False

    @property
    def command_active(self) -> bool:
        return self._command_waiters > 0

    def mark_shutting_down(self) -> None:
        self._shutting_down = True

    @property
    def is_connected(self) -> bool:
        c = self._client
        return c is not None and c.is_connected

    def _options(self) -> dict[str, int | bool]:
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            return {}
        return get_integration_options(entry)

    async def async_disconnect(self) -> None:
        self._shutting_down = True
        async with self._lock:
            await self._disconnect_locked()

    async def _disconnect_locked(self) -> None:
        if self._client is None:
            return
        try:
            if self._client.is_connected:
                await self._client.disconnect()
                _LOGGER.debug("Dolphin Plus: BLE released")
        except BleakError:
            _LOGGER.debug("disconnect BleakError (ignored)", exc_info=True)
        self._client = None

    async def _ensure_connected_locked(self) -> BleakClientWithServiceCache:
        if self._shutting_down:
            raise HomeAssistantError("Dolphin Plus BLE is shutting down")
        if self._client is not None and self._client.is_connected:
            return self._client

        await self._disconnect_locked()
        ble_device = await async_resolve_ble_device(self.hass, self.address)
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name=ble_device.name or self.address,
            timeout=_BLE_CONNECT_TIMEOUT,
        )
        if not client.is_connected:
            raise HomeAssistantError("Failed to connect over BLE")
        self._client = client
        _LOGGER.debug(
            "Dolphin Plus: BLE connected (%s, profile=%s transport=%s)",
            ble_device.address,
            self._profile,
            self._transport,
        )
        return self._client

    async def _release_after_operation_locked(self) -> None:
        await self._disconnect_locked()

    async def _exchange_locked(
        self,
        payload: bytes,
        *,
        expect_opcode: int | None = None,
        timeout: float = _NOTIFY_TIMEOUT,
    ) -> bytes | None:
        if self._profile != PROFILE_IOT:
            raise HomeAssistantError(
                f"Profile {self._profile!r} is not supported yet — use IoT (PS Plus)"
            )

        acc = bytearray()
        loop = asyncio.get_running_loop()
        fut: asyncio.Future[bytes | None] = loop.create_future()

        def _handler(_sender: Any, data: bytearray) -> None:
            acc.extend(data)
            frames, remainder = iter_iot_frames(bytes(acc))
            acc.clear()
            acc.extend(remainder)
            for frame in frames:
                opcode, _data_len, body = parse_iot_frame_payload(frame)
                if expect_opcode is not None and opcode != expect_opcode:
                    continue
                if not fut.done():
                    fut.set_result(body if expect_opcode is not None else b"")

        client = await self._ensure_connected_locked()
        try:
            await client.start_notify(self._notify_uuid, _handler)
        except BleakError as err:
            await self._release_after_operation_locked()
            raise HomeAssistantError(f"BLE notify setup failed: {err}") from err

        try:
            await asyncio.sleep(0.15)
            await client.write_gatt_char(
                self._write_uuid, payload, response=True
            )
            await asyncio.sleep(_POST_WRITE_DELAY)
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        except BleakError as err:
            await self._release_after_operation_locked()
            raise HomeAssistantError(f"BLE error: {err}") from err
        finally:
            try:
                await client.stop_notify(self._notify_uuid)
            except BleakError:
                _LOGGER.debug("stop_notify ignored", exc_info=True)
            await self._release_after_operation_locked()

    async def async_send_command(self, payload: bytes, *, expect_opcode: int | None) -> None:
        self._command_waiters += 1
        try:
            async with self._lock:
                await self._exchange_locked(payload, expect_opcode=expect_opcode)
        finally:
            self._command_waiters = max(0, self._command_waiters - 1)

    async def async_startup(self) -> None:
        payload = build_startup(self._spec)
        _LOGGER.info("Dolphin Plus STARTUP → %s", payload.hex())
        await self.async_send_command(payload, expect_opcode=None)

    async def async_shutdown(self) -> None:
        payload = build_shutdown(self._spec)
        _LOGGER.info("Dolphin Plus SHUTDOWN → %s", payload.hex())
        await self.async_send_command(payload, expect_opcode=None)

    async def async_read_system_status(self) -> dict[str, int | None] | None:
        if self._command_waiters > 0:
            return None
        payload = build_system_status_request(self._spec)
        self._command_waiters += 1
        try:
            async with self._lock:
                body = await self._exchange_locked(
                    payload, expect_opcode=0x07, timeout=5.0
                )
        finally:
            self._command_waiters = max(0, self._command_waiters - 1)
        if body is None:
            return None
        return parse_system_status(body)

    async def async_release_ble_link(self) -> None:
        if self._shutting_down:
            return
        try:
            async with self._lock:
                await self._disconnect_locked()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("release BLE: %s", err)


async def async_ble_periodic_release(hass: HomeAssistant, entry_id: str) -> None:
    """Periodically disconnect so HA never holds the robot hostage."""
    try:
        while True:
            entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
            session: DolphinPlusBleConnection | None = (
                entry_data.get(DATA_BLE_SESSION) if entry_data else None
            )
            if session is None or session._shutting_down:
                return
            entry = hass.config_entries.async_get_entry(entry_id)
            opts = get_integration_options(entry) if entry else {}
            interval = int(opts.get(OPT_BLE_KEEPALIVE_SEC, 0))
            if interval <= 0:
                await asyncio.sleep(60)
                continue
            await asyncio.sleep(interval)
            await session.async_release_ble_link()
    except asyncio.CancelledError:
        raise
