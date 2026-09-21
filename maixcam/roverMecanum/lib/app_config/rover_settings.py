"""UART teleop tuning from config.json."""

from lib.app_config.parse_helpers import as_bool, as_float, as_int, as_str, section


class RoverSettings:
  """UART teleop tuning."""

  __slots__ = (
    "max_speed", "send_interval_ms", "deadzone_percent",
    "axis_sensitivity_percent", "axis_expo", "axis_curve",
    "speed_step", "wait_ack",
  )

  def __init__(self, raw: dict):
    rover = section(raw, "rover")
    self.max_speed = max(0, min(255, as_int(rover, "max_speed", 255)))
    self.send_interval_ms = max(5, as_int(rover, "send_interval_ms", 10))
    self.deadzone_percent = as_int(rover, "deadzone_percent", 5)
    self.axis_sensitivity_percent = as_int(rover, "axis_sensitivity_percent", 70)
    self.axis_expo = as_float(rover, "axis_expo", 2.2)
    self.axis_curve = as_str(rover, "axis_curve", "expo")
    self.speed_step = max(1, as_int(rover, "speed_step", 5))
    self.wait_ack = as_bool(rover, "wait_ack", False)
