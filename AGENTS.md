# MaixCam2 Keyestudio micro:bit rover

## Architecture

```text
Xbox BLE -> MaixCam2 (BlueZ/evdev/MaixPy HUD) -> UART -> micro:bit motors
```

Keep Bluetooth and evdev on the MaixCam2. Keep deterministic motor control and
the UART protocol on the micro:bit.

## Quality guardrails

- Keep one top-level class per `maixcam/roverMecanum/lib` Python file.
- Do not use nested test classes or put unrelated test classes in one test file.
- An exception handler must log before swallowing with `pass` or `continue`.
- Use descriptive names at configuration and hardware boundaries; avoid names
  such as `cfg`, `exc`, or `x` when they hide the role of a value.
- Keep English documentation in English files and French documentation in
  `*_FR.md` files.
- Put tunable timing values in `config.json` rather than scattering literals.

## Tests

Run from the repository root:

```powershell
python tools/check_code_guardrails.py
python tools/test_app_config.py
python -m unittest discover -s tools -p "test_*.py"
```

The interactive `tools/test_rover_menu.py` is a hardware test and requires a
connected micro:bit serial port.
