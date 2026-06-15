# MaixCam2 × micro:bit — Keyestudio Mecanum Rover

> 🇫🇷 Version française (documentation complète) : [README_FR.md](README_FR.md)

<p align="center">
  <a href="resources/MaixCam2_Mecanum_Rover.jpg">
    <img src="resources/MaixCam2_Mecanum_Rover.jpg" width="520" alt="MaixCam2 mounted on Keyestudio mecanum rover with micro:bit">
  </a>
</p>

<p align="center"><em>Click the image to open full size.</em></p>

Drive a **Keyestudio 4WD Mecanum Robot Car V2** with a **MaixCam2** brain and an **Xbox controller** — while the **BBC micro:bit V2** stays focused on what it does best: real-time motor control over I2C.

---

## Why this project?

Mecanum wheels are genuinely fun: strafe sideways, spin in place, diagonal moves — but wiring that up from scratch is painful. This repo gives you:

- **A clean binary UART protocol** between host and rover (preset moves, raw wheel control, 4-axis joystick)
- **Production-ready micro:bit firmware** (PlatformIO, C++, HR8833 motor driver via I2C)
- **A MaixCam2 app** with live camera preview, on-screen HUD, Bluetooth Xbox pairing, and configurable drive mapping
- **PC test tools** so you can debug motors without the camera board

Split the problem the right way: **MaixCam handles vision + human input**, **micro:bit handles motors + timing**.

```
  Xbox Controller (BLE)
         │
         ▼
   MaixCam2  ── UART 115200 ──►  micro:bit V2  ── I2C ──►  Keyestudio motor board
   (Python)      P1/P2              (C++)              HR8833 × 4 mecanum wheels
   evdev + HUD
```

---

## What's in the repo?

| Path | What it is |
|------|------------|
| [`microbit/`](microbit/) | Firmware — protocol parser, mecanum mixer, motor driver |
| [`maixcam/roverMecanum/`](maixcam/roverMecanum/) | MaixVision / packaged app — Xbox → UART pipeline |
| [`tools/`](tools/) | PowerShell + Python scripts to test from a PC |
| [`microbit/PROTOCOL.md`](microbit/PROTOCOL.md) | Protocol index → [EN](microbit/PROTOCOL_EN.md) / [FR](microbit/PROTOCOL_FR.md) |

### Firmware highlights

- Dual serial: **edge UART (P1/P2)** for the MaixCam + **USB mbed** for PC debugging
- Named presets (forward, strafe, spin, pivot…) and **RAW** per-wheel control
- **Joystick frame `0x30`** — strafe, forward, spin, pivot with proportional speed and deadzone
- ACK bytes `0x55 + CMD` after valid frames

### MaixCam app highlights

- Pair / connect an **Xbox Wireless Controller** over Bluetooth (BlueZ + Linux evdev)
- **Live camera HUD** with stick gauges, triggers, d-pad, speed bar
- **LB / RB** adjust max speed on the fly
- Tunable response curve (`expo`, `log`, sensitivity, deadzone) via `config.json`
- Packaged as a MaixPy app or run from MaixVision with deploy script

Full app docs: [maixcam/roverMecanum/README_EN.md](maixcam/roverMecanum/README_EN.md)

---

## Quick start

### 1. Flash the micro:bit

```bash
cd microbit
pio run -t upload
```

Plug the micro:bit via **USB** (data cable). Windows should show a **`MICROBIT`** drive — PlatformIO copies the `.hex` there.  
UART to the rover uses **P1 = TX**, **P2 = RX** on the edge connector (115200 8N1).

### 2. Test from your PC (no MaixCam needed)

```powershell
cd tools
.\run_test_rover.ps1 -Port COM9 -Speed 80
```

Use the **mbed Serial Port** COM name, not the DAPLink debug port.  
You should see `[rover] ready (usb+p1p2, 115200)` in the monitor.

### 3. Run on MaixCam2

**MaixVision (dev):**

```powershell
.\tools\deploy_rover_mecanum.ps1 -DeployOnly -SyncConfig
```

Open `maixcam/roverMecanum` in MaixVision and run `main.py`.

**Packaged app:** build from `app.yaml`, install to `/maixapp/apps/mecanum_rover_controler/`.

---

## Protocol in one minute

Every frame starts with sync byte **`0xAA`**. Simple preset move:

```
[0xAA] [CMD] [SPEED 0-255] [CHECKSUM]
CHECKSUM = (0xAA + CMD + SPEED) & 0xFF
```

Analog drive (4 axes, little-endian `int16`):

```
[0xAA] [0x30] [strafe] [forward] [spin] [pivot] [max_speed] [CHECKSUM]
```

The firmware mixes all four axes into per-wheel speeds — you can combine forward + strafe + spin + pivot in one frame.

**Deep dive:** [microbit/PROTOCOL_EN.md](microbit/PROTOCOL_EN.md) (includes endianness primer)

---

## Hardware wiring (MaixCam ↔ micro:bit)

| MaixCam2 | micro:bit edge |
|----------|----------------|
| A21 (UART TX) | P2 (RX) |
| A22 (UART RX) | P1 (TX) |
| GND | GND |

Motor board stays on the Keyestudio harness (I2C `0x30`, PWM channels 1–8).

---

## For developers

- **Extend the protocol** — add commands in `Protocol.h`, handler in `CommandDispatcher`, document in `PROTOCOL_EN.md`
- **Remap the Xbox layout** — `maixcam/roverMecanum/config.json` (`mapping.axes`, `evdev.layout`)
- **Tune drive feel** — `deadzone_percent`, `axis_curve`, `axis_expo`, `max_speed` in the same config
- **Keep micro:bit lean** — BLE/HID on the MaixCam (Linux kernel), not on the nRF52

French docs cover flash troubleshooting, Windows COM ports, and Python examples in more detail: [README_FR.md](README_FR.md).

---

## Pictures

Click any thumbnail to open the full-resolution image.

<p align="center">
  <a href="resources/MaixCam2_Mecanum_Rover2.jpg"><img src="resources/MaixCam2_Mecanum_Rover2.jpg" width="240" alt="Top view — MaixPy booting"></a>
  &nbsp;
  <a href="resources/MaixCam2_Mecanum_Rover3.jpg"><img src="resources/MaixCam2_Mecanum_Rover3.jpg" width="240" alt="Bluetooth pairing screen"></a>
  &nbsp;
  <a href="resources/MaixCam2_Mecanum_Rover4.jpg"><img src="resources/MaixCam2_Mecanum_Rover4.jpg" width="240" alt="Live FPV with Xbox HUD"></a>
</p>

| | | |
|:---:|:---:|:---:|
| **Top view** — MaixPy boot on MaixCam2 | **Pairing** — connect an Xbox controller over BLE | **Driving** — camera feed + stick gauges + speed bar |

---

## References

- Keyestudio Python examples in `examples/`
- Original text serial commands: `examples/LiaisonSerie.txt` (replaced by binary protocol here)

---

## License / contributions

Issues and PRs welcome. If you build on this stack — another host board, ROS bridge, autonomous mode — we'd love to see it.
