# SCREEK BP2-POE + Maytronics Dolphin Plus

Use this with **SCREEK BP2-POE** Bluetooth proxies and Home Assistant integration **v0.1.8+**.

You cannot edit firmware in place — you **reflash** with a modified YAML. You do **not** need the original YAML from the device; start from SCREEK’s published config.

## 1. Get SCREEK’s base YAML

Pick one:

- **GitHub** (when available): [screekworkshop/Screek-Bluetooth-Proxy-BP2-POE](https://github.com/screekworkshop/Screek-Bluetooth-Proxy-BP2-POE) → `SCREEK-BP2-POE.yaml`
- **Recovery tool** (USB-C): [screek.io/bp2-poe](https://screek.io/bp2-poe) — can restore stock firmware and view logs
- **ESPHome logs** from a working unit: `esphome logs --device <IP> path/to/SCREEK-BP2-POE.yaml` (confirms your copy matches the device)

Save SCREEK’s file as e.g. `screek-bp2-poe.yaml` in the same folder as this repo’s `esphome/` files.

## 2. Add Dolphin Plus GATT support

**Option A — package include (easiest)**

At the **end** of `screek-bp2-poe.yaml`:

```yaml
packages:
  maytronics_dolphin_plus: !include dolphin-plus-gatt-addon.yaml
```

Copy `dolphin-plus-gatt-addon.yaml` into the same directory.

**Option B — manual merge**

Copy the blocks from `dolphin-plus-gatt-addon.yaml` into your SCREEK YAML. If you already have `api:`, merge `actions:` into that block (one `api:` key only).

## 3. Raise BLE connection limit

BP2 already has `esp32_ble`. Edit that block (do **not** add a second one):

```yaml
esp32_ble:
  max_connections: 5   # was lower; needs room for proxy + GATT server
```

Stock BP2 uses **4** proxy connection slots; proxy + GATT server share this pool on one radio.

## 4. Build and flash

BP2 is **Ethernet/PoE** (W5500), not Wi‑Fi. Typical paths:

```bash
esphome compile screek-bp2-poe.yaml
esphome upload screek-bp2-poe.yaml --device <BP2_IP>
```

Or USB-C via SCREEK’s web recovery tool after compiling to `.bin`.

**Before flashing:** note the **API encryption key** in HA (ESPHome device → Configure) if you want to avoid re-pairing.

**After flashing:** HA may prompt for a new key or you re-add via **Settings → Devices → ESPHome → Add → IP address**.

## 5. Configure Dolphin Plus in HA

1. Install integration **v0.1.8+**
2. **Dolphin Plus → Configure**
   - **IoT command backend:** `ESPHome proxy GATT server` or `Auto`
   - **ESPHome proxy device:** your BP2
3. **Developer tools → Services** — confirm `esphome.<node_name>_dolphin_iot_notify` exists  
   (e.g. `esphome.screek_bp2_poe_d70854_dolphin_iot_notify` with MAC suffix)

## 6. Hardware notes (BP2)

From SCREEK BP2 logs / docs:

| Item | Value |
|------|--------|
| MCU | ESP32-S3, PSRAM |
| Ethernet | W5500 SPI |
| Proxy slots | 4 (stock) |
| Framework | esp-idf |

Dual **bluetooth_proxy + esp32_ble_server** on one chip is required for IoT PSU (E35i / IoT230) — same idea as the MyDolphin Plus phone app. This path is **experimental** on Maytronics hardware.

## Troubleshooting

| Problem | What to try |
|---------|-------------|
| Compile fails / OOM | BP2 has PSRAM; stay on esp-idf; don’t enable web_server |
| HA can’t adopt after flash | Add by **IP** (not mDNS); same VLAN as HA |
| No `dolphin_iot_notify` service | Reflash; check `api.actions` merged correctly |
| Connect works, power doesn’t | Check logs for `ESPHome IoT notify sent`; robot may not subscribe yet |
| Don’t want to touch BP2 | Add a cheap ESP32 with `dolphin-plus-ble-proxy.yaml.example` at the pool instead |

## Files in this folder

| File | Purpose |
|------|---------|
| `dolphin-plus-gatt-addon.yaml` | GATT server + HA API action (include from any proxy YAML) |
| `dolphin-plus-ble-proxy.yaml.example` | Generic proxy add-on notes (non-SCREEK) |
| `screek-bp2-poe-dolphin-plus.yaml.example` | Minimal package-include stub |
