# Maytronics Dolphin Plus (BLE) for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Community integration for **Maytronics Dolphin** robots paired with the **MyDolphin Plus** app (v3.x). Control power and read status locally over Bluetooth — no cloud account required for BLE control.

> **Not the right integration?** Robots using the older **MyDolphin** app (GATT service `FFF0`) should use **[ha-maytronics-dolphin](https://github.com/randrcomputers/ha-maytronics-dolphin)** instead. The two integrations are separate; install only the one that matches your app.

---

## What you get (v0.1.0)

| Feature | Status |
|---------|--------|
| **Power on/off** | `start_up_dolphin` / `shutdown_dolphin` over Nordic UART |
| **Status poll** | `system_status` → SM state, MU state, cleaning mode |
| **Short BLE sessions** | Connect per command/poll, then disconnect (same pattern as the legacy integration) |
| Schedule, autoclean, joystick, Pool Cleaner Card | Not yet — BLE MVP |

---

## Requirements

| Requirement | Notes |
|-------------|--------|
| **Home Assistant 2024.1+** | HAOS, Supervised, Container, or Core |
| **Bluetooth** | Built-in adapter or [Bluetooth proxy](https://www.home-assistant.io/integrations/bluetooth/) near the pool |
| **Robot BLE MAC** | From **Settings → Devices & services → Bluetooth**, or nRF Connect |
| **MyDolphin Plus app** | Close the app on your phone while HA is controlling the robot |
| **Robot class** | **IoT / PS Plus** profile (default). POP/buoy profiles are experimental |

---

## Install (HACS)

1. Install [HACS](https://hacs.xyz/) if needed.
2. HACS → **Integrations** → **⋮** → **Custom repositories**
3. Add: `https://github.com/randrcomputers/ha-maytronics-dolphin-plus` — category **Integration**
4. Download → restart Home Assistant
5. **Settings → Devices & services → Add integration → Maytronics Dolphin Plus (BLE)**
6. Enter the **Bluetooth MAC** and optional name.

### Manual install

Copy `custom_components/maytronics_dolphin_plus` into your HA `config/custom_components/` folder and restart.

---

## Setup options

During setup:

| Field | Default | When to change |
|-------|---------|----------------|
| **Protocol profile** | IoT / PS Plus | POP cordless or buoy models (experimental) |
| **BLE transport** | Nordic UART (`6E400001`) | Try **Alternate IoT GATT** (`fd5abba0`) if connect/write fails |

**Settings → Configure** (after install):

| Option | Default | Description |
|--------|---------|-------------|
| **State poll interval** | 45 s | How often `system_status` is read. `0` = commands only. |
| **Periodic BLE release** | 120 s | Safety disconnect if a session is still held. `0` = off. |

---

## Entities

| Entity | Type | Purpose |
|--------|------|---------|
| **Power** | Switch | Turn robot on / off |
| **SM state** | Sensor | Raw state machine byte (`0` ≈ off) |
| **MU state** | Sensor | Motor unit state byte |
| **Cleaning mode** | Sensor | Mode byte from status packet |

Power display follows `sm_state` when polls succeed; the switch may show **assumed** state briefly after a tap until the next poll confirms.

---

## How this differs from the legacy integration

| | **This repo** (Plus) | **[ha-maytronics-dolphin](https://github.com/randrcomputers/ha-maytronics-dolphin)** (legacy) |
|---|---|---|
| App | MyDolphin **Plus** 3.x | MyDolphin 2.x |
| BLE transport | Nordic UART / Plus IoT frames | GATT `FFF0` / `FFF8` |
| Protocol | Plus IoT SDK (`0xAB` frames) | 19-byte `BTCommand` |
| Typical robots | Triton PS Plus, Wi-Fi/IoT generation | Older BLE-only Dolphins |

You do **not** need both integrations unless you own two different robots.

---

## Bluetooth tips

1. Confirm the robot appears under **Settings → Bluetooth** when awake and in range.
2. **Close MyDolphin Plus** on your phone — only one BLE client at a time.
3. Use a **Bluetooth proxy** in the pool area if HA is far from the robot.
4. If power works but status stays unknown, open an issue with debug logs:

```yaml
logger:
  default: info
  logs:
    custom_components.maytronics_dolphin_plus: debug
```

---

## Supported hardware

Protocol derived from **MyDolphin Plus Android 3.4** (`com.maytronics.app`). Tested framing matches shipped `ble_iot_protocol.json`. Real-world confirmation on specific models is welcome via [issues](https://github.com/randrcomputers/ha-maytronics-dolphin-plus/issues).

**WiFi / cloud control** is out of scope for this integration (Plus app uses AWS IoT for Wi-Fi path). For cloud Wi-Fi robots see community projects such as [dolphin-robot](https://github.com/sh00t2kill/dolphin-robot) / `mydolphin_plus`.

---

## Legal

Maytronics®, Dolphin®, and MyDolphin® are trademarks of their respective owners. Independent community software — not endorsed by Maytronics.

---

## Links

- **Issues:** [github.com/randrcomputers/ha-maytronics-dolphin-plus/issues](https://github.com/randrcomputers/ha-maytronics-dolphin-plus/issues)
- **Legacy BLE integration:** [ha-maytronics-dolphin](https://github.com/randrcomputers/ha-maytronics-dolphin)
