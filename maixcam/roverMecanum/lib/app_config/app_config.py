"""Root typed config built once from config.json."""

from __future__ import annotations

from lib.app_config.camera_settings import CameraSettings
from lib.app_config.parse_helpers import as_float, as_str, section
from lib.app_config.rover_settings import RoverSettings
from lib.app_config.timing_settings import TimingSettings


class AppConfig:
  """
  Full app settings from the JSON dict.

  Call sites use attributes (``cfg.camera.display_fps``), not string keys.
  Mapping / evdev blocks stay as dicts for engines not yet fully typed.
  """

  __slots__ = (
    "camera", "rover", "timing",
    "controller_name", "controller_name_aliases", "controller_mac",
    "bluetooth_scan_timeout_sec", "mapping", "evdev", "raw",
  )

  def __init__(self, raw: dict):
    if not isinstance(raw, dict):
      raw = {}
    self.raw = raw
    self.camera = CameraSettings(raw)
    self.rover = RoverSettings(raw)
    self.timing = TimingSettings(raw)
    self.controller_name = as_str(raw, "controller_name", "Xbox Wireless Controller")
    aliases = raw.get("controller_name_aliases") or []
    self.controller_name_aliases = list(aliases) if isinstance(aliases, list) else []
    self.controller_mac = as_str(raw, "controller_mac", "").upper()
    self.bluetooth_scan_timeout_sec = as_float(raw, "bluetooth_scan_timeout_sec", 20.0)
    self.mapping = dict(section(raw, "mapping"))
    self.evdev = dict(section(raw, "evdev"))

  @classmethod
  def from_dict(cls, raw: dict) -> AppConfig:
    return cls(raw)
