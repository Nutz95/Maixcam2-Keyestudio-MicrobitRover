from lib.uart_protocol import build_joystick_frame


class JoystickFrameBuilder:
  """Build 12-byte CMD_JOYSTICK 0x30 frames."""

  def build(self, axis_strafe, axis_forward, axis_spin, axis_pivot, speed):
    return build_joystick_frame(axis_strafe, axis_forward, speed, axis_spin, axis_pivot)

  def build_stop(self):
    return build_joystick_frame(0, 0, 0, 0, 0)
