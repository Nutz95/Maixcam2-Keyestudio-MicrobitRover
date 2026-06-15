from lib.axis_curve import apply_curve
from lib.protocol_constants import PRESET_ACTIONS


class DriveOutput:
  """Mapped stick/trigger values ready for UART (4 axes + optional preset)."""

  def __init__(self):
    self.axis_strafe = 0
    self.axis_forward = 0
    self.axis_spin = 0
    self.axis_pivot = 0
    self.preset_cmd = None

  def is_idle(self, threshold=250):
    """True when all drive axes are near zero (after shaping)."""
    return (
      abs(self.axis_strafe) <= threshold
      and abs(self.axis_forward) <= threshold
      and abs(self.axis_spin) <= threshold
      and abs(self.axis_pivot) <= threshold
    )


class ControllerMappingEngine:
  """
  Apply config.json mapping: sticks, triggers, d-pad -> rover drive axes.

  Shaping pipeline per axis: invert -> deadzone -> response curve -> sensitivity.
  """

  def __init__(self, config):
    self._config = config

  def update_config(self, config):
    """Refresh mapping rules (call after config reload)."""
    self._config = config

  def compute(self, state):
    """Build DriveOutput from a ControllerState snapshot."""
    out = DriveOutput()
    mapping = self._config.get("mapping", {})
    axes_map = mapping.get("axes", {})
    invert = mapping.get("invert", {})
    rover = self._config.get("rover", {})
    deadzone = int(32768 * rover.get("deadzone_percent", 2) / 100)
    sensitivity = max(1, min(100, int(rover.get("axis_sensitivity_percent", 70)))) / 100.0
    expo = max(0.3, min(3.0, float(rover.get("axis_expo", 2.2))))
    curve = rover.get("axis_curve", "expo")

    dpad = self._dpad_axes(state, mapping.get("dpad", {}))
    if dpad is not None:
      out.axis_strafe, out.axis_forward = dpad
      out.axis_strafe = self._shape_axis(out.axis_strafe, deadzone, sensitivity, expo, curve)
      out.axis_forward = self._shape_axis(out.axis_forward, deadzone, sensitivity, expo, curve)
      preset = self._button_preset(state)
      if preset is not None:
        out.preset_cmd = preset
      return out

    forward_src = axes_map.get("drive_forward", "left_y")
    strafe_src = axes_map.get("drive_strafe", "trigger_diff")
    spin_src = axes_map.get("drive_spin", axes_map.get("drive_rotate", "right_x"))
    pivot_src = axes_map.get("drive_pivot", "left_x")

    forward = self._source_value(state, forward_src)
    strafe = self._source_value(state, strafe_src)
    spin = self._source_value(state, spin_src)
    pivot = self._source_value(state, pivot_src)

    forward = self._apply_invert(forward, forward_src, invert)
    strafe = self._apply_invert(strafe, strafe_src, invert)
    spin = self._apply_invert(spin, spin_src, invert)
    pivot = self._apply_invert(pivot, pivot_src, invert)

    out.axis_forward = self._shape_axis(forward, deadzone, sensitivity, expo, curve)
    out.axis_strafe = self._shape_axis(strafe, deadzone, sensitivity, expo, curve)
    out.axis_spin = self._shape_axis(spin, deadzone, sensitivity, expo, curve)
    out.axis_pivot = self._shape_axis(pivot, deadzone, sensitivity, expo, curve)

    preset = self._button_preset(state)
    if preset is not None:
      out.preset_cmd = preset

    return out

  def _source_value(self, state, source):
    if not isinstance(source, str):
      return 0
    source = source.strip().lower()
    if source == "left_x":
      return state.left_x
    if source == "left_y":
      return state.left_y
    if source == "right_x":
      return state.right_x
    if source == "right_y":
      return state.right_y
    if source == "lt":
      return state.lt
    if source == "rt":
      return state.rt
    if source == "trigger_diff":
      return state.trigger_diff()
    return 0

  def _apply_invert(self, value, source, invert):
    if not isinstance(source, str):
      return value
    key = source.strip().lower()
    return -value if invert.get(key, False) else value

  def _apply_deadzone(self, value, deadzone):
    if abs(value) <= deadzone:
      return 0
    sign = 1 if value > 0 else -1
    mag = abs(value) - deadzone
    span = max(1, 32767 - deadzone)
    return sign * min(32767, int(mag * 32767 / span))

  def _shape_axis(self, value, deadzone, sensitivity, expo, curve):
    """Deadzone, response curve (log/expo/linear), then sensitivity scale."""
    value = self._apply_deadzone(value, deadzone)
    if value == 0:
      return 0
    sign = 1 if value > 0 else -1
    norm = min(1.0, abs(value) / 32767.0)
    norm = apply_curve(norm, curve, expo)
    norm = min(1.0, norm * sensitivity)
    return sign * int(norm * 32767)

  def _dpad_axes(self, state, dpad_map):
    if not dpad_map:
      return None
    dx = state.dpad_x
    dy = state.dpad_y
    if dx == 0 and dy == 0:
      return None

    action = None
    if dy < 0 and dx < 0:
      action = dpad_map.get("up_left")
    elif dy < 0 and dx > 0:
      action = dpad_map.get("up_right")
    elif dy > 0 and dx < 0:
      action = dpad_map.get("down_left")
    elif dy > 0 and dx > 0:
      action = dpad_map.get("down_right")
    elif dy < 0:
      action = dpad_map.get("up")
    elif dy > 0:
      action = dpad_map.get("down")
    elif dx < 0:
      action = dpad_map.get("left")
    elif dx > 0:
      action = dpad_map.get("right")

    if not action:
      return None
    return self._action_to_axes(action)

  def _action_to_axes(self, action):
    if action == "forward":
      return 0, -32767
    if action == "backward":
      return 0, 32767
    if action == "strafe_left":
      return -32767, 0
    if action == "strafe_right":
      return 32767, 0
    if action == "diag_fl":
      return -32767, -32767
    if action == "diag_fr":
      return 32767, -32767
    if action == "diag_bl":
      return -32767, 32767
    if action == "diag_br":
      return 32767, 32767
    return None

  def _button_preset(self, state):
    buttons = self._config.get("mapping", {}).get("buttons", {})
    preset = None
    for btn_name, action in buttons.items():
      if not action:
        continue
      if not state.pressed_edge.get(btn_name):
        continue
      state.pressed_edge.pop(btn_name, None)
      cmd = PRESET_ACTIONS.get(action)
      if cmd is not None:
        preset = cmd
    return preset
