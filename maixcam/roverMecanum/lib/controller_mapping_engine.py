from lib.app_config import AppConfig
from lib.axis_curve import apply_curve
from lib.drive_output import DriveOutput
from lib.protocol_constants import PRESET_ACTIONS
from lib.uart_protocol import dpad_axes_for_action


class ControllerMappingEngine:
  """
  Apply config mapping: sticks, triggers, d-pad -> rover drive axes.

  Shaping pipeline per axis: invert -> deadzone -> response curve -> sensitivity.
  Mapping rules are cached in ``update_config()``; ``compute()`` only transforms state.
  """

  def __init__(self, app_config: AppConfig):
    self._deadzone = 0
    self._sensitivity = 1.0
    self._expo = 2.2
    self._curve = "expo"
    self._forward_src = "left_y"
    self._strafe_src = "trigger_diff"
    self._spin_src = "right_x"
    self._pivot_src = "left_x"
    self._invert_forward = False
    self._invert_strafe = False
    self._invert_spin = False
    self._invert_pivot = False
    self._dpad = None
    self._buttons = None
    self.update_config(app_config)

  def update_config(self, app_config: AppConfig):
    """Cache deadzone, curve, and axis sources from typed settings."""
    rover = app_config.rover
    mapping = app_config.mapping
    sensitivity = max(1, min(100, rover.axis_sensitivity_percent))
    self._deadzone = 32768 * rover.deadzone_percent // 100
    self._sensitivity = sensitivity / 100.0
    self._expo = max(0.3, min(3.0, rover.axis_expo))
    self._curve = rover.axis_curve
    self._forward_src = mapping.drive_forward
    self._strafe_src = mapping.drive_strafe
    self._spin_src = mapping.drive_spin
    self._pivot_src = mapping.drive_pivot
    self._invert_forward = mapping.invert.for_source(mapping.drive_forward)
    self._invert_strafe = mapping.invert.for_source(mapping.drive_strafe)
    self._invert_spin = mapping.invert.for_source(mapping.drive_spin)
    self._invert_pivot = mapping.invert.for_source(mapping.drive_pivot)
    self._dpad = mapping.dpad
    self._buttons = mapping.buttons

  def compute(self, state):
    """Build DriveOutput from a ControllerState snapshot."""
    out = DriveOutput()
    deadzone = self._deadzone
    sensitivity = self._sensitivity
    expo = self._expo
    curve = self._curve

    dpad = self._dpad_axes(state)
    if dpad is not None:
      out.axis_strafe = self._shape_axis(dpad.strafe, deadzone, sensitivity, expo, curve)
      out.axis_forward = self._shape_axis(dpad.forward, deadzone, sensitivity, expo, curve)
      preset = self._button_preset(state)
      if preset is not None:
        out.preset_cmd = preset
      return out

    forward = self._source_value(state, self._forward_src)
    strafe = self._source_value(state, self._strafe_src)
    spin = self._source_value(state, self._spin_src)
    pivot = self._source_value(state, self._pivot_src)

    if self._invert_forward:
      forward = -forward
    if self._invert_strafe:
      strafe = -strafe
    if self._invert_spin:
      spin = -spin
    if self._invert_pivot:
      pivot = -pivot

    out.axis_forward = self._shape_axis(forward, deadzone, sensitivity, expo, curve)
    out.axis_strafe = self._shape_axis(strafe, deadzone, sensitivity, expo, curve)
    out.axis_spin = self._shape_axis(spin, deadzone, sensitivity, expo, curve)
    out.axis_pivot = self._shape_axis(pivot, deadzone, sensitivity, expo, curve)

    preset = self._button_preset(state)
    if preset is not None:
      out.preset_cmd = preset

    return out

  def _source_value(self, state, source):
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

  def _apply_deadzone(self, value, deadzone):
    if abs(value) <= deadzone:
      return 0
    sign = 1 if value > 0 else -1
    mag = abs(value) - deadzone
    span = max(1, 32767 - deadzone)
    return sign * min(32767, mag * 32767 // span)

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

  def _dpad_axes(self, state):
    dpad = self._dpad
    if dpad is None:
      return None
    dx = state.dpad_x
    dy = state.dpad_y
    if dx == 0 and dy == 0:
      return None

    if dy < 0 and dx < 0:
      action = dpad.up_left
    elif dy < 0 and dx > 0:
      action = dpad.up_right
    elif dy > 0 and dx < 0:
      action = dpad.down_left
    elif dy > 0 and dx > 0:
      action = dpad.down_right
    elif dy < 0:
      action = dpad.up
    elif dy > 0:
      action = dpad.down
    elif dx < 0:
      action = dpad.left
    elif dx > 0:
      action = dpad.right
    else:
      return None

    if not action:
      return None
    return dpad_axes_for_action(action)

  def _button_preset(self, state):
    buttons = self._buttons
    if buttons is None:
      return None
    preset = None
    for btn_name, action in buttons.bindings():
      if not action:
        continue
      if not state.pressed_edge.get(btn_name):
        continue
      state.pressed_edge.pop(btn_name, None)
      cmd = PRESET_ACTIONS.get(action)
      if cmd is not None:
        preset = cmd
    return preset
