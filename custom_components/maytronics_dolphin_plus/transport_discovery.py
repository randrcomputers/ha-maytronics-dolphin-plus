"""Discover Plus BLE write/notify characteristics after GATT connect."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from bleak import BleakClient

from .const import (
    IOT_NOTIFY_UUID,
    IOT_SERVICE_UUID,
    IOT_WRITE_UUID,
    NUS_NOTIFY_UUID,
    NUS_SERVICE_UUID,
    NUS_WRITE_UUID,
    POP_NOTIFY_UUID,
    POP_SERVICE_UUID,
    POP_WRITE_UUID,
    TRANSPORT_AUTO,
    TRANSPORT_IOT_GATT,
    TRANSPORT_NUS,
    TRANSPORT_POP,
)

_LOGGER = logging.getLogger(__name__)

_PROP_NOTIFY = frozenset({"notify", "indicate"})
_PROP_WRITE = frozenset({"write", "write-without-response"})


@dataclass(frozen=True, slots=True)
class ResolvedTransport:
    transport: str
    service_uuid: str
    write_uuid: str
    notify_uuid: str


def _uuid_lower(value: str) -> str:
    return value.lower()


def _find_service(client: BleakClient, service_uuid: str):
    want = _uuid_lower(service_uuid)
    for service in client.services:
        if _uuid_lower(service.uuid) == want:
            return service
    return None


def _char_by_uuid(service, char_uuid: str):
    want = _uuid_lower(char_uuid)
    for char in service.characteristics:
        if _uuid_lower(char.uuid) == want:
            return char
    return None


def _char_props(char) -> set[str]:
    return set(char.properties)


def _pick_write_notify(service) -> tuple[str | None, str | None]:
    """Pick write + notify UUIDs on a service (may be the same characteristic)."""
    write_uuid: str | None = None
    notify_uuid: str | None = None
    combined: str | None = None

    for char in service.characteristics:
        props = _char_props(char)
        if props & _PROP_WRITE and props & _PROP_NOTIFY:
            combined = char.uuid
        if props & _PROP_WRITE and write_uuid is None:
            write_uuid = char.uuid
        if props & _PROP_NOTIFY and notify_uuid is None:
            notify_uuid = char.uuid

    if combined:
        return combined, combined
    if write_uuid and notify_uuid:
        return write_uuid, notify_uuid
    if write_uuid and notify_uuid is None:
        char = _char_by_uuid(service, write_uuid)
        if char and _char_props(char) & _PROP_NOTIFY:
            return write_uuid, write_uuid
    return write_uuid, notify_uuid


def _try_fixed_profile(
    client: BleakClient,
    *,
    transport: str,
    service_uuid: str,
    write_uuid: str,
    notify_uuid: str,
) -> ResolvedTransport | None:
    service = _find_service(client, service_uuid)
    if service is None:
        return None

    write_char = _char_by_uuid(service, write_uuid)
    notify_char = _char_by_uuid(service, notify_uuid)
    if write_char is None or notify_char is None:
        # Fixed UUIDs missing — infer from properties (E35i / IoT230 PSU pattern).
        inferred_write, inferred_notify = _pick_write_notify(service)
        if inferred_write is None or inferred_notify is None:
            return None
        write_uuid = inferred_write
        notify_uuid = inferred_notify
    else:
        w_props = _char_props(write_char)
        n_props = _char_props(notify_char)
        if not (w_props & _PROP_WRITE):
            return None
        if not (n_props & _PROP_NOTIFY):
            return None

    return ResolvedTransport(transport, service_uuid, write_uuid, notify_uuid)


def _transport_candidates(preferred: str) -> list[tuple[str, str, str, str]]:
    profiles = [
        (TRANSPORT_IOT_GATT, IOT_SERVICE_UUID, IOT_WRITE_UUID, IOT_NOTIFY_UUID),
        (TRANSPORT_NUS, NUS_SERVICE_UUID, NUS_WRITE_UUID, NUS_NOTIFY_UUID),
        (TRANSPORT_POP, POP_SERVICE_UUID, POP_WRITE_UUID, POP_NOTIFY_UUID),
    ]
    if preferred == TRANSPORT_AUTO:
        return profiles
    if preferred in {p[0] for p in profiles}:
        profiles.sort(key=lambda row: 0 if row[0] == preferred else 1)
    return profiles


def discover_transport(
    client: BleakClient, preferred: str
) -> ResolvedTransport | None:
    """Resolve service/write/notify UUIDs present on this robot."""
    for transport, service_uuid, write_uuid, notify_uuid in _transport_candidates(
        preferred
    ):
        resolved = _try_fixed_profile(
            client,
            transport=transport,
            service_uuid=service_uuid,
            write_uuid=write_uuid,
            notify_uuid=notify_uuid,
        )
        if resolved is not None:
            if transport != preferred:
                _LOGGER.info(
                    "Dolphin Plus: using %s transport (configured %s) "
                    "write=%s notify=%s",
                    resolved.transport,
                    preferred,
                    resolved.write_uuid,
                    resolved.notify_uuid,
                )
            else:
                _LOGGER.debug(
                    "Dolphin Plus: transport %s write=%s notify=%s",
                    resolved.transport,
                    resolved.write_uuid,
                    resolved.notify_uuid,
                )
            return resolved

    _LOGGER.warning(
        "Dolphin Plus: no supported BLE transport found (preferred=%s). "
        "GATT services: %s",
        preferred,
        ", ".join(sorted({s.uuid for s in client.services})),
    )
    return None


def log_gatt_services(client: BleakClient) -> None:
    """Debug helper when notify setup fails."""
    for service in client.services:
        chars = []
        for char in service.characteristics:
            chars.append(f"{char.uuid} [{','.join(char.properties)}]")
        _LOGGER.debug(
            "Dolphin Plus GATT service %s → %s",
            service.uuid,
            "; ".join(chars) if chars else "(no characteristics)",
        )
