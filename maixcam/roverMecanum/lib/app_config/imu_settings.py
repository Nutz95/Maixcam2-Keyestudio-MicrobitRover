"""Typed IMU section from config.json."""

from lib.config_parse_helpers import as_bool, as_float, as_int, section


class ImuSettings:
  """Calibration and poll settings for the onboard IMU yaw service."""

  __slots__ = (
    "enabled",
    "calib_ms",
    "poll_ms",
    "mahony_kp",
    "mahony_ki",
  )

  def __init__(self, raw: dict):
    """Parse and bound the imu section at the config boundary."""
    block = section(raw, "imu")
    self.enabled = as_bool(block, "enabled", True)
    self.calib_ms = max(1000, as_int(block, "calib_ms", 10000))
    self.poll_ms = max(5, as_int(block, "poll_ms", 20))
    self.mahony_kp = max(0.01, as_float(block, "mahony_kp", 2.0))
    self.mahony_ki = max(0.0, as_float(block, "mahony_ki", 0.01))
