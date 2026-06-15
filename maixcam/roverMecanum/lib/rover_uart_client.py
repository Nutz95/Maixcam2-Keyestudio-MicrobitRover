from maix import time

from lib.joystick_frame_builder import JoystickFrameBuilder
from lib.preset_frame_builder import PresetFrameBuilder


class RoverUartClient:
  """Envoie les commandes UART vers le micro:bit."""

  def __init__(self, serial, max_speed=255, wait_ack=False):
    self.serial = serial
    self.max_speed = max(0, min(255, int(max_speed)))
    self.wait_ack = wait_ack
    self.last_ack = ""
    self._joystick_builder = JoystickFrameBuilder()
    self._preset_builder = PresetFrameBuilder()

  def set_max_speed(self, speed):
    self.max_speed = max(0, min(255, int(speed)))

  def send_joystick(self, axis_strafe, axis_forward, axis_spin=0, axis_pivot=0, speed=None):
    spd = self.max_speed if speed is None else speed
    frame = self._joystick_builder.build(axis_strafe, axis_forward, axis_spin, axis_pivot, spd)
    self.serial.write(frame)
    if self.wait_ack:
      self.last_ack = self._read_ack()
    else:
      self.last_ack = ""

  def send_preset(self, cmd, speed=None):
    spd = self.max_speed if speed is None else speed
    frame = self._preset_builder.build(cmd, spd)
    self.serial.write(frame)
    if self.wait_ack:
      self.last_ack = self._read_ack()
    else:
      self.last_ack = ""

  def send_stop(self):
    frame = self._joystick_builder.build_stop()
    self.serial.write(frame)
    if self.wait_ack:
      self.last_ack = self._read_ack()
    else:
      self.last_ack = ""

  def _read_ack(self):
    buf = bytearray()
    deadline = time.ticks_ms() + 80
    while time.ticks_ms() < deadline:
      data = self.serial.read()
      if data:
        buf.extend(data)
        if len(buf) >= 2:
          return f"{buf[0]:02X} {buf[1]:02X}"
      time.sleep_ms(2)
    return ""
