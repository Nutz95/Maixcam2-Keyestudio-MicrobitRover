from lib.uart_protocol import build_joystick_frame, build_preset_frame


class RoverUartClient:
  """Send UART frames to the micro:bit rover (joystick + presets)."""

  def __init__(self, serial, max_speed=255):
    self.serial = serial
    self.max_speed = max(0, min(255, max_speed))

  def set_max_speed(self, speed):
    """Update top motor speed byte sent in every joystick frame (0-255)."""
    self.max_speed = max(0, min(255, speed))

  def send_joystick(self, axis_strafe, axis_forward, axis_spin=0, axis_pivot=0, speed=None):
    """Send CMD_JOYSTICK 0x30 with four axes and max_speed cap."""
    spd = self.max_speed if speed is None else speed
    self.serial.write(
      build_joystick_frame(axis_strafe, axis_forward, spd, axis_spin, axis_pivot)
    )

  def send_preset(self, cmd, speed=None):
    """Send a named preset command frame."""
    spd = self.max_speed if speed is None else speed
    self.serial.write(build_preset_frame(cmd, spd))

  def send_stop(self):
    """Send a zero joystick frame (speed=0) to halt all wheels."""
    self.serial.write(build_joystick_frame(0, 0, 0, 0, 0))
