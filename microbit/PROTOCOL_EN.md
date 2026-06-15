# UART protocol MaixCam ↔ micro:bit (mecanum rover)

Full documentation in English. French version: [`PROTOCOL_FR.md`](PROTOCOL_FR.md).

Firmware: `microbit/src/`  
Baud rate: **115200**, 8N1  
micro:bit edge pins: **P1 = TX**, **P2 = RX**

---

## First: understanding bytes (Little Endian vs Big Endian)

Numbers like **300** or **-1000** do not fit in **1 byte** (0–255).  
We often use **2 bytes** (= 16 bits = an `int16`).

### Example: value 300

In hexadecimal: **300 = 0x012C**

| Encoding | High byte | Low byte |
|----------|-----------|----------|
| Big Endian (BE) | `01` then `2C` | “human” order (MSB first) |
| Little Endian (LE) | `2C` then `01` | **low byte first** |

**This protocol uses LE (Little Endian)** — standard on micro:bit, x86 PC, and MaixCam.

### Example: -1 (signed int16)

-1 as signed 16-bit = **0xFFFF**  
LE bytes: **`FF FF`**

### Example in a joystick frame

Strafe (crab) = **+100**:

```
100 = 0x0064  →  LE bytes: 64 00
```

Forward = **-500**:

```
-500 = 0xFE0C  →  LE bytes: 0C FE
```

In Python:

```python
(100).to_bytes(2, "little", signed=True)   # b'\x64\x00'
(-500).to_bytes(2, "little", signed=True)  # b'\x0c\xfe'
```

---

## Common bytes

| Value | Name | Role |
|-------|------|------|
| `0xAA` | `PROTO_SYNC` | Frame start |
| `0x55` | `PROTO_ACK` | Acknowledgement |

---

## 1. Preset frame (4 bytes)

```
[SYNC 0xAA] [COMMAND] [MOTOR_SPEED] [CHECKSUM]
```

| Field | Description |
|-------|-------------|
| `COMMAND` | Movement code (table below) |
| `MOTOR_SPEED` | Motor PWM `0..255` (`0` = stop) |
| `CHECKSUM` | `(0xAA + COMMAND + MOTOR_SPEED) & 0xFF` |

### COMMAND codes

| Code | Name | Movement |
|------|------|----------|
| `0x00` | STOP | Stop |
| `0x01` | FORWARD | All wheels forward |
| `0x02` | BACKWARD | All wheels backward |
| `0x03` | STRAFE_LEFT | Crab left |
| `0x04` | STRAFE_RIGHT | Crab right |
| `0x05`–`0x08` | DIAG_* | Diagonals |
| `0x09` | SPIN_LEFT | Rotate in place (CCW) |
| `0x0A` | SPIN_RIGHT | Rotate in place (CW) |
| `0x0B` | PIVOT_RIGHT | Car-like pivot |
| `0x0C` | PIVOT_REAR | Rear pivot |
| `0x20` | RAW | Per-wheel directions (§3) |
| `0x30` | JOYSTICK | Analog joystick (§4) |

---

## 2. Acknowledgement (ACK)

```
[0x55] [COMMAND]
```

---

## 3. RAW mecanum frame (5 bytes)

```
[SYNC][0x20][WHEEL_DIRECTION_BITS][MOTOR_SPEED][CHECKSUM]
```

2 bits per wheel: upper-left, upper-right, lower-left, lower-right.

---

## 4. Analog joystick frame (12 bytes) — current format

Four analog axes + max speed:

```
[SYNC][CMD 0x30]
[STRAFE_LO][STRAFE_HI]
[FORWARD_LO][FORWARD_HI]
[SPIN_LO][SPIN_HI]
[PIVOT_LO][PIVOT_HI]
[MAX_SPEED][CHECKSUM]
```

| Field | Type | Description |
|-------|------|-------------|
| **strafe** | int16 LE | Lateral crab: `> 0` = right |
| **forward** | int16 LE | Forward/back: `< 0` = forward |
| **spin** | int16 LE | Rotate in place: `> 0` = spin left |
| **pivot** | int16 LE | Car-like turn: `> 0` = pivot right |
| **MAX_SPEED** | uint8 | PWM cap `0..255` |
| **CHECKSUM** | uint8 | Sum of first 11 bytes `& 0xFF` |

Axis range: `-32768..32767` (Xbox-style).

### Names in firmware (micro:bit)

| Concept | File | Variable name |
|---------|------|---------------|
| Received bytes | `ProtocolParser.h` | `UartIncomingFrame` |
| Parser state | `ProtocolParser.h` | `UartParserState` |
| Strafe low byte | | `strafe_byte_low` / `strafe_byte_high` |
| Forward low byte | | `forward_byte_low` / `forward_byte_high` |
| Spin low byte | | `spin_byte_low` / `spin_byte_high` |
| Pivot low byte | | `pivot_byte_low` / `pivot_byte_high` |

### Firmware mixer (`MecanumJoystickMapper`)

```
upper_left  = forward + strafe + spin  (+ pivot)
upper_right = forward - strafe - spin
lower_left  = forward - strafe + spin
lower_right = forward + strafe - spin
```

**Pivot** brakes one side (car turn). **Spin** rotates in place (all wheels).

### Python example

```python
def build_joystick_frame(axis_strafe, axis_forward, axis_spin, axis_pivot, max_speed):
    payload = (
        int(axis_strafe).to_bytes(2, "little", signed=True)
        + int(axis_forward).to_bytes(2, "little", signed=True)
        + int(axis_spin).to_bytes(2, "little", signed=True)
        + int(axis_pivot).to_bytes(2, "little", signed=True)
        + bytes([max(0, min(255, max_speed))])
    )
    frame = bytes([0xAA, 0x30]) + payload
    return frame + bytes([sum(frame) & 0xFF])
```

Stop: `build_joystick_frame(0, 0, 0, 0, 0)`

---

## 5. MaixCam side

| File | Role |
|------|------|
| `lib/joystick_frame_builder.py` | Builds 12-byte frame |
| `lib/controller_mapping_engine.py` | Gamepad → strafe, forward, spin, pivot |

Default mapping: left stick Y = forward, left stick X = pivot, right stick X = spin, LT/RT = strafe.

---

## 6. PC test

```bash
python tools/test_rover_menu.py
```

Use **mbed Serial** COM port (not DAPLink).
