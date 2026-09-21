"""UART binary protocol — Maix-free (MaixCam app + PC tools)."""

from lib.dpad_axes import DpadAxes

PROTO_SYNC = 0xAA
PROTO_ACK = 0x55
DEFAULT_SPEED = 100

CMD_STOP = 0x00
CMD_FORWARD = 0x01
CMD_BACKWARD = 0x02
CMD_STRAFE_LEFT = 0x03
CMD_STRAFE_RIGHT = 0x04
CMD_DIAG_FL = 0x05
CMD_DIAG_FR = 0x06
CMD_DIAG_BL = 0x07
CMD_DIAG_BR = 0x08
CMD_SPIN_LEFT = 0x09
CMD_SPIN_RIGHT = 0x0A
CMD_PIVOT_RIGHT = 0x0B
CMD_PIVOT_REAR = 0x0C
CMD_RAW = 0x20
CMD_JOYSTICK = 0x30

WHEEL_DIR_STOP = 0x00
WHEEL_DIR_FORWARD = 0x01
WHEEL_DIR_BACKWARD = 0x02

# Preset name -> UART cmd + d-pad axis pair (strafe, forward).
DRIVE_ACTIONS = {
  "stop": {"cmd": CMD_STOP, "strafe": 0, "forward": 0},
  "forward": {"cmd": CMD_FORWARD, "strafe": 0, "forward": -32767},
  "backward": {"cmd": CMD_BACKWARD, "strafe": 0, "forward": 32767},
  "strafe_left": {"cmd": CMD_STRAFE_LEFT, "strafe": -32767, "forward": 0},
  "strafe_right": {"cmd": CMD_STRAFE_RIGHT, "strafe": 32767, "forward": 0},
  "diag_fl": {"cmd": CMD_DIAG_FL, "strafe": -32767, "forward": -32767},
  "diag_fr": {"cmd": CMD_DIAG_FR, "strafe": 32767, "forward": -32767},
  "diag_bl": {"cmd": CMD_DIAG_BL, "strafe": -32767, "forward": 32767},
  "diag_br": {"cmd": CMD_DIAG_BR, "strafe": 32767, "forward": 32767},
  "spin_left": {"cmd": CMD_SPIN_LEFT, "strafe": 0, "forward": 0},
  "spin_right": {"cmd": CMD_SPIN_RIGHT, "strafe": 0, "forward": 0},
  "pivot_right": {"cmd": CMD_PIVOT_RIGHT, "strafe": 0, "forward": 0},
  "pivot_rear": {"cmd": CMD_PIVOT_REAR, "strafe": 0, "forward": 0},
}

PRESET_ACTIONS = {name: spec["cmd"] for name, spec in DRIVE_ACTIONS.items()}

PRESET_COMMANDS = [
  ("0", "STOP", CMD_STOP),
  ("1", "Avant", CMD_FORWARD),
  ("2", "Arriere", CMD_BACKWARD),
  ("3", "Strafe gauche", CMD_STRAFE_LEFT),
  ("4", "Strafe droite", CMD_STRAFE_RIGHT),
  ("5", "Diag avant-gauche", CMD_DIAG_FL),
  ("6", "Diag avant-droite", CMD_DIAG_FR),
  ("7", "Diag arriere-gauche", CMD_DIAG_BL),
  ("8", "Diag arriere-droite", CMD_DIAG_BR),
  ("9", "Rotation gauche (CCW)", CMD_SPIN_LEFT),
  ("a", "Rotation droite (CW)", CMD_SPIN_RIGHT),
  ("b", "Pivot cote droit", CMD_PIVOT_RIGHT),
  ("c", "Pivot axe arriere", CMD_PIVOT_REAR),
]


def checksum3(b0, b1, b2):
  return (b0 + b1 + b2) & 0xFF


def checksum4(b0, b1, b2, b3):
  return (b0 + b1 + b2 + b3) & 0xFF


def build_preset_frame(cmd, speed):
  speed = max(0, min(255, int(speed)))
  return bytes([PROTO_SYNC, cmd, speed, checksum3(PROTO_SYNC, cmd, speed)])


def build_raw_frame(wheel_dirs, speed):
  speed = max(0, min(255, int(speed)))
  return bytes([
    PROTO_SYNC, CMD_RAW, wheel_dirs, speed,
    checksum4(PROTO_SYNC, CMD_RAW, wheel_dirs, speed),
  ])


def build_joystick_frame(axis_strafe, axis_forward, speed, axis_spin=0, axis_pivot=0):
  axis_strafe = max(-32768, min(32767, int(axis_strafe)))
  axis_forward = max(-32768, min(32767, int(axis_forward)))
  axis_spin = max(-32768, min(32767, int(axis_spin)))
  axis_pivot = max(-32768, min(32767, int(axis_pivot)))
  speed = max(0, min(255, int(speed)))
  payload = (
    axis_strafe.to_bytes(2, "little", signed=True)
    + axis_forward.to_bytes(2, "little", signed=True)
    + axis_spin.to_bytes(2, "little", signed=True)
    + axis_pivot.to_bytes(2, "little", signed=True)
    + bytes([speed])
  )
  frame = bytes([PROTO_SYNC, CMD_JOYSTICK]) + payload
  return frame + bytes([sum(frame) & 0xFF])


def dpad_axes_for_action(action):
  """Return DpadAxes for a d-pad action name, or None."""
  spec = DRIVE_ACTIONS.get(action)
  if spec is None:
    return None
  return DpadAxes(spec["strafe"], spec["forward"])
