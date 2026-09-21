"""Typed root config loaded once from config.json."""

from lib.app_config.camera_settings import CameraSettings
from lib.app_config.evdev_settings import EvdevSettings
from lib.ball_follow_settings import BallFollowSettings
from lib.app_config.mapping_settings import MappingSettings
from lib.config_parse_helpers import as_float, as_int, as_str, as_str_list
from lib.app_config.rover_settings import RoverSettings
from lib.app_config.timing_settings import TimingSettings


class AppConfig:
  """Immutable snapshot of config.json used by the rest of the app."""

  __slots__ = (
    "mapping_revision",
    "controller_name",
    "controller_name_aliases",
    "controller_mac",
    "bluetooth_scan_timeout_sec",
    "camera",
    "rover",
    "timing",
    "mapping",
    "evdev",
    "ball_follow",
  )

  def __init__(self, raw: dict):
    self.mapping_revision = as_int(raw, "mapping_revision", 0)
    self.controller_name = as_str(raw, "controller_name", "Xbox Wireless Controller")
    self.controller_name_aliases = as_str_list(raw, "controller_name_aliases")
    self.controller_mac = as_str(raw, "controller_mac", "").upper()
    self.bluetooth_scan_timeout_sec = as_float(raw, "bluetooth_scan_timeout_sec", 20.0)
    self.camera = CameraSettings(raw)
    self.rover = RoverSettings(raw)
    self.timing = TimingSettings(raw)
    self.mapping = MappingSettings(raw)
    self.evdev = EvdevSettings(raw)
    self.ball_follow = BallFollowSettings(raw)

  @classmethod
  def from_dict(cls, raw: dict) -> "AppConfig":
    """Build from a loaded JSON object (JSON → object only; never the reverse)."""
    return cls(raw if isinstance(raw, dict) else {})
