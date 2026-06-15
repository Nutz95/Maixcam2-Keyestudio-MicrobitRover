# Rover Mecanum — MaixCam2 + Xbox

Install path on camera: `/root/roverMecanum/`

Deploy from Windows: `tools/deploy_rover_mecanum.ps1`

UART protocol (Little Endian, 12-byte frame): [`../../microbit/PROTOCOL_EN.md`](../../microbit/PROTOCOL_EN.md)

---

## Xbox controller diagram

Visual reference: [`../XBoxControler.jpg`](../XBoxControler.jpg)

---

## Mapping table (diagram → config)

### Analog axes

| Controller label | Physical role | `config.json` source | MaixCam BT evdev code |
|------------------|---------------|----------------------|------------------------|
| Left stick X | Horizontal | `left_x` | ABS `0` |
| Left stick Y | Vertical | `left_y` | ABS `1` |
| Right stick X | Horizontal | `right_x` | ABS `2` |
| Right stick Y | Vertical | `right_y` | ABS `5` |
| LT | Left trigger | `lt` | ABS `10` (BRAKE) |
| RT | Right trigger | `rt` | ABS `9` (GAS) |
| LT − RT | Crab strafe | `trigger_diff` | computed |

### Default drive profile (`mapping_revision` ≥ 4)

| Rover axis | Config key | Stick | Effect |
|------------|------------|-------|--------|
| **forward** | `drive_forward` → `left_y` | Left Y | Forward / backward |
| **strafe** | `drive_strafe` → `trigger_diff` | LT / RT | Lateral crab |
| **spin** | `drive_spin` → `right_x` | Right X | Rotate in place |
| **pivot** | `drive_pivot` → `left_x` | Left X | Car-like turn |

> **Spin** ≠ **Pivot**: spin rotates on the spot; pivot brakes one side like a car.

### D-pad (`mapping.dpad`)

Full-speed movement while pressed (overrides sticks).

---

## Sample config

```json
"mapping": {
  "axes": {
    "drive_forward": "left_y",
    "drive_strafe": "trigger_diff",
    "drive_spin": "right_x",
    "drive_pivot": "left_x"
  }
}
```

---

## 1080p camera

Live preview with HUD overlay. Disable with:

```json
"camera": { "enabled": false }
```

---

## micro:bit firmware

**Reflash** after updates (12-byte frame, explicit axis names).

---

## Key lib/ files

| Module | Role |
|--------|------|
| `camera_preview_service.py` | 1080p capture thread |
| `controller_mapping_engine.py` | Gamepad → forward, strafe, spin, pivot |
| `joystick_frame_builder.py` | UART frame builder |
| `ProtocolParser.h` (micro:bit) | `UartIncomingFrame`, readable byte names |
