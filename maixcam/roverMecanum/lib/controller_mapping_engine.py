from lib.protocol_constants import PRESET_ACTIONS


class DriveOutput:
  """Mapping output -> rover command."""

  def __init__(self):
    self.axis_x = 0
    self.axis_y = 0
    self.axis_rot = 0
    self.preset_cmd = None


class ControllerMappingEngine:
  """Apply config.json mapping: left stick Y/X + LT/RT triggers."""

  def __init__(self, config):
    self._config = config

  def update_config(self, config):
    self._config = config

  def compute(self, state):
    out = DriveOutput()
    mapping = self._config.get("mapping", {})
    axes_map = mapping.get("axes", {})
    invert = mapping.get("invert", {})
    rover = self._config.get("rover", {})

    deadzone = int(32768 * rover.get("deadzone_percent", 2) / 100)

    forward = self._source_value(state, axes_map.get("drive_forward", "left_y"))
    strafe = self._source_value(state, axes_map.get("drive_strafe", "trigger_diff"))
    rotate = self._source_value(state, axes_map.get("drive_rotate", "left_x"))

    forward = self._maybe_invert(forward, invert.get("left_y", False))
    strafe = self._maybe_invert(strafe, invert.get("trigger_diff", False))
    rotate = self._maybe_invert(rotate, invert.get("left_x", False))

    out.axis_y = self._apply_deadzone(forward, deadzone)
    out.axis_x = self._apply_deadzone(strafe, deadzone)
    out.axis_rot = self._apply_deadzone(rotate, deadzone)

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

  def _maybe_invert(self, value, invert):
    return -value if invert else value

  def _apply_deadzone(self, value, deadzone):
    if abs(value) <= deadzone:
      return 0
    sign = 1 if value > 0 else -1
    mag = abs(value) - deadzone
    span = max(1, 32767 - deadzone)
    return sign * min(32767, int(mag * 32767 / span))

  def _button_preset(self, state):
    buttons = self._config.get("mapping", {}).get("buttons", {})
    edges = state.consume_edges()
    for btn_name, action in buttons.items():
      if not edges.get(btn_name):
        continue
      if not action:
        continue
      cmd = PRESET_ACTIONS.get(action)
      if cmd is not None:
        return cmd
    return None
