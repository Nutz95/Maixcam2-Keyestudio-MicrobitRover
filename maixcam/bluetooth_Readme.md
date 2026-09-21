# Bluetooth MaixCam2 + Xbox controller

## Enable

```shell
bluetoothctl power on
bluetoothctl pairable on
```

BlueZ (`bluetoothctl`) ships with Ubuntu on MaixCam2 — no extra Python Bluetooth package.

Sipeed docs: https://wiki.sipeed.com/maixpy/doc/en/modules/bluetooth.html

## Encrypted pairing (required for the joystick)

Without an encrypted bond, BlueZ can show `Connected: yes` + HID UUID **without**
creating `/dev/input/event*` for the pad. Sticks then do nothing.

The app starts a long-lived **bluetoothctl PTY** at launch (`agent NoInputNoOutput`)
and keeps it until exit.

### What is ERTM? (`disable_ertm=Y`)

**ERTM** = Enhanced Retransmission Mode, a Bluetooth L2CAP reliability mode.
On MaixCam2’s **Linux 4.19** Bluetooth stack, ERTM often breaks Xbox BLE HID
(endless `Connected: yes/no` flap, no evdev node). At app start we write `Y` to
`/sys/module/bluetooth/parameters/disable_ertm` so the controller can bond and
expose `/dev/input/event*`. See `lib/bluetooth_installer.py`.

| UI button | Action |
|-----------|--------|
| **PAIR** | remove old bond + fresh encrypted bond (hold **SYNC**, logo blinks fast) |
| **CONNECT** | reconnect a good bond (short Xbox logo press, not SYNC) |

Real success = solid logo + `HID reports flowing` in the logs (not only `Connected: yes`).

Also: **forget the pad on the PC** while pairing (otherwise it sticks to the PC).

## Production modules

| Component | Role |
|-----------|------|
| `lib/bluetoothctl_session.py` | Long-lived PTY + BlueZ agent |
| `lib/bluetoothctl_runner.py` | Parse bluetoothctl output |
| `lib/bluetooth_pairing_service.py` | PAIR / CONNECT UI flow |
| `lib/xbox_input_service.py` | BT worker + evdev poll |

```powershell
cd tools
.\deploy_rover_mecanum.ps1 -DeployOnly -SyncConfig
```

Controller mapping: [`maixcam/roverMecanum/README_EN.md`](roverMecanum/README_EN.md).
French Bluetooth notes: [`bluetooth_Readme_FR.md`](bluetooth_Readme_FR.md).

## Common failures

- Empty scan → SYNC fast blink, &lt;1 m, pad forgotten on the PC
- `Connected: yes` / `Connected: no` loop before PAIR → broken old bond (often Xbox firmware / kernel 4.19). Press **PAIR** (app does `remove` + re-bond). Scan also checks `bluetoothctl devices`
- Logo blinks + Connected yes/no after PAIR → update Xbox firmware via **Xbox Accessories** (Windows), then PAIR again
- HID UUID without event → PAIR (remove + encrypted bond)
- `JSONDecodeError` on `config.json` → fixed with atomic writes; if the file is still empty, redeploy `-SyncConfig`
- Never `bluetoothctl disconnect` outside PAIR (often powers the pad off)

## Rover joystick deadzone

micro:bit firmware applies a **2%** deadzone by default (`DEFAULT_JOYSTICK_DEADZONE_PERCENT`).

PC-only test: `tools/test_rover_menu.py` → `j` e.g. `X=0`, `Y=-20000`.
