"""Plus app IoT BLE frame builder (from ``ble_iot_protocol.json`` + APK 3.4).

IoT checksum: 16-bit unsigned sum of all preceding bytes, big-endian (``Lq/f.a``).
"""

from __future__ import annotations

import json
import logging
from enum import IntEnum
from functools import lru_cache
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

SOP_IOT = 0xAB
SRC_IOT = 0x03
IOT_HEADER_LEN = 7  # sop + src + dest(2) + opcode + data_len(2)
IOT_CHECKSUM_LEN = 2

CMD_START_UP = "start_up_dolphin"
CMD_SHUTDOWN = "shutdown_dolphin"
CMD_SYSTEM_STATUS = "system_status"


class PowerState(IntEnum):
    """Inferred from ``system_status.sm_state`` (0 = off, non-zero = on)."""

    OFF = 0
    ON = 1
    UNKNOWN = -1


def _protocol_json_path(profile: str) -> Path:
    base = Path(__file__).resolve().parent / "protocols"
    name = {
        "iot": "ble_iot_protocol.json",
        "pop": "ble_pop_protocol.json",
        "buoy": "ble_buoy_protocol.json",
    }.get(profile, "ble_iot_protocol.json")
    return base / name


@lru_cache(maxsize=4)
def load_protocol_spec(profile: str) -> dict[str, Any]:
    path = _protocol_json_path(profile)
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


async def async_load_protocol_spec(
    hass: HomeAssistant, profile: str
) -> dict[str, Any]:
    """Load protocol JSON off the event loop (avoids blocking-call warnings)."""
    return await hass.async_add_executor_job(load_protocol_spec, profile)


def iot_checksum(data: bytes) -> bytes:
    total = sum(b & 0xFF for b in data) & 0xFFFF
    return bytes([(total >> 8) & 0xFF, total & 0xFF])


def _hex_to_bytes(value: str) -> bytes:
    cleaned = value.strip().replace(" ", "")
    if len(cleaned) % 2:
        cleaned = "0" + cleaned
    return bytes.fromhex(cleaned)


def build_iot_command(
    spec: dict[str, Any],
    command_name: str,
    payload: bytes = b"",
) -> bytes:
    """Build a single IoT-protocol request frame."""
    commands = spec.get("commands") or {}
    if command_name not in commands:
        raise ValueError(f"Unknown command: {command_name}")
    cmd = commands[command_name]
    dest = _hex_to_bytes(str(cmd["destination"]))
    opcode = _hex_to_bytes(str(cmd["opcode"]))
    if len(dest) != 2:
        raise ValueError(f"destination must be 2 bytes: {cmd['destination']}")
    if len(opcode) != 1:
        raise ValueError(f"opcode must be 1 byte: {cmd['opcode']}")

    data_len = len(payload)
    header = bytes(
        [
            SOP_IOT,
            SRC_IOT,
            dest[0],
            dest[1],
            opcode[0],
            (data_len >> 8) & 0xFF,
            data_len & 0xFF,
        ]
    )
    body = header + payload
    return body + iot_checksum(body)


def build_startup(spec: dict[str, Any]) -> bytes:
    return build_iot_command(spec, CMD_START_UP)


def build_shutdown(spec: dict[str, Any]) -> bytes:
    return build_iot_command(spec, CMD_SHUTDOWN)


def build_system_status_request(spec: dict[str, Any]) -> bytes:
    return build_iot_command(spec, CMD_SYSTEM_STATUS)


def _verify_iot_checksum(frame: bytes) -> bool:
    if len(frame) < IOT_HEADER_LEN + IOT_CHECKSUM_LEN:
        return False
    body, cs = frame[:-IOT_CHECKSUM_LEN], frame[-IOT_CHECKSUM_LEN:]
    return iot_checksum(body) == cs


def iter_iot_frames(buffer: bytes) -> tuple[list[bytes], bytes]:
    """Split accumulated notify data into complete IoT frames; return remainder."""
    frames: list[bytes] = []
    i = 0
    while i < len(buffer):
        if buffer[i] != SOP_IOT:
            i += 1
            continue
        if i + IOT_HEADER_LEN > len(buffer):
            break
        data_len = (buffer[i + 5] << 8) | buffer[i + 6]
        total = IOT_HEADER_LEN + data_len + IOT_CHECKSUM_LEN
        if i + total > len(buffer):
            break
        frame = buffer[i : i + total]
        if _verify_iot_checksum(frame):
            frames.append(frame)
        else:
            _LOGGER.debug("Plus BLE: dropping frame with bad checksum: %s", frame.hex())
        i += total
    return frames, buffer[i:]


def parse_iot_frame_payload(frame: bytes) -> tuple[int, int, bytes]:
    """Return (opcode, destination_hi_lo as int pair conceptually), payload."""
    if len(frame) < IOT_HEADER_LEN + IOT_CHECKSUM_LEN:
        raise ValueError("frame too short")
    opcode = frame[4]
    data_len = (frame[5] << 8) | frame[6]
    payload = frame[IOT_HEADER_LEN : IOT_HEADER_LEN + data_len]
    return opcode, data_len, payload


def parse_system_status(payload: bytes) -> dict[str, int | None]:
    """Map ``system_status`` response bytes (53-byte field map, relative offsets)."""
    if len(payload) < 2:
        return {"mu_state": None, "sm_state": None, "cleaning_mode": None}
    return {
        "mu_state": payload[0],
        "sm_state": payload[1],
        "cleaning_mode": payload[3] if len(payload) > 3 else None,
    }


def sm_state_implies_power_on(sm_state: int | None) -> bool | None:
    if sm_state is None:
        return None
    return sm_state != 0


def sm_state_to_power_state(sm_state: int | None) -> PowerState:
    inferred = sm_state_implies_power_on(sm_state)
    if inferred is None:
        return PowerState.UNKNOWN
    return PowerState.ON if inferred else PowerState.OFF
