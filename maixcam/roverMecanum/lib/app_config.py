"""Typed config deserialized from config.json (no string-key .get in call sites)."""

from __future__ import annotations


def _section(data: dict, name: str) -> dict:
  value = data.get(name)
  return value if isinstance(value, dict) else {}


def _int(section: dict, key: str, default: int) -> int:
  try:
    return int(section.get(key, default))
  except (TypeError, ValueError):
    return default


def _float(section: dict, key: str, default: float) -> float:
  try:
    return float(section.get(key, default))
  except (TypeError, ValueError):
    return default


def _bool(section: dict, key: str, default: bool) -> bool:
  value = section.get(key, default)
  if isinstance(value, bool):
    return value
  if isinstance(value, str):
    return value.strip().lower() in ("1", "true", "yes", "on")
  return bool(value) if value is not None else default


def _str(section: dict, key: str, default: str) -> str:
  value = section.get(key, default)
  return default if value is None else str(value)


class CameraSettings:
  """Camera + HUD display cadence."""

  __slots__ = (
    "enabled", "width", "height", "fps", "format", "display_fps",
    "ready_timeout_ms", "ready_poll_ms", "paused_poll_ms",
    "frame_yield_ms", "no_frame_sleep_ms", "stop_join_ms",
  )

  def __init__(self, raw: dict):
    cam = _section(raw, "camera")
    timing = _section(raw, "timing")
    self.enabled = _bool(cam, "enabled", True)
    self.width = _int(cam, "width", 640)
    self.height = _int(cam, "height", 480)
    self.fps = max(1, min(30, _int(cam, "fps", 30)))
    self.format = _str(cam, "format", "rgb888")
    self.display_fps = max(5, min(30, _int(cam, "display_fps", 20)))
    self.ready_timeout_ms = _int(timing, "camera_ready_timeout_ms", 8000)
    self.ready_poll_ms = _int(timing, "camera_ready_poll_ms", 20)
    self.paused_poll_ms = _int(timing, "camera_paused_poll_ms", 40)
    self.frame_yield_ms = _int(timing, "camera_frame_yield_ms", 1)
    self.no_frame_sleep_ms = _int(timing, "camera_no_frame_sleep_ms", 5)
    self.stop_join_ms = _int(timing, "camera_stop_join_ms", 2500)

  @property
  def display_interval_ms(self) -> int:
    return max(1, int(1000 / self.display_fps))


class RoverSettings:
  """UART teleop tuning."""

  __slots__ = (
    "max_speed", "send_interval_ms", "deadzone_percent",
    "axis_sensitivity_percent", "axis_expo", "axis_curve",
    "speed_step", "wait_ack",
  )

  def __init__(self, raw: dict):
    rover = _section(raw, "rover")
    self.max_speed = max(0, min(255, _int(rover, "max_speed", 255)))
    self.send_interval_ms = max(5, _int(rover, "send_interval_ms", 10))
    self.deadzone_percent = _int(rover, "deadzone_percent", 5)
    self.axis_sensitivity_percent = _int(rover, "axis_sensitivity_percent", 70)
    self.axis_expo = _float(rover, "axis_expo", 2.2)
    self.axis_curve = _str(rover, "axis_curve", "expo")
    self.speed_step = max(1, _int(rover, "speed_step", 5))
    self.wait_ack = _bool(rover, "wait_ack", False)


class TimingSettings:
  """Loop sleeps / debounces (ms). Prefer Event.wait where a stop flag exists."""

  __slots__ = (
    "main_loop_sleep_ms", "teleop_poll_sleep_ms", "config_reload_ms",
    "touch_debounce_ms", "speed_debounce_ms",
    "evdev_retry_ms", "evdev_open_attempts",
    "hid_wait_ms", "hid_quick_wait_ms",
  )

  def __init__(self, raw: dict):
    timing = _section(raw, "timing")
    self.main_loop_sleep_ms = max(1, _int(timing, "main_loop_sleep_ms", 10))
    self.teleop_poll_sleep_ms = max(1, _int(timing, "teleop_poll_sleep_ms", 5))
    self.config_reload_ms = max(100, _int(timing, "config_reload_ms", 500))
    self.touch_debounce_ms = max(0, _int(timing, "touch_debounce_ms", 900))
    self.speed_debounce_ms = max(0, _int(timing, "speed_debounce_ms", 160))
    self.evdev_retry_ms = max(50, _int(timing, "evdev_retry_ms", 250))
    self.evdev_open_attempts = max(1, _int(timing, "evdev_open_attempts", 8))
    self.hid_wait_ms = max(1000, _int(timing, "hid_wait_ms", 12000))
    self.hid_quick_wait_ms = max(500, _int(timing, "hid_quick_wait_ms", 5000))


class AppConfig:
  """
  Full app settings built once from the JSON dict.

  Call sites use attributes (``cfg.camera.display_fps``), not string keys.
  Mapping / evdev blocks stay as dicts for the existing engines.
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
    self.controller_name = _str(raw, "controller_name", "Xbox Wireless Controller")
    aliases = raw.get("controller_name_aliases") or []
    self.controller_name_aliases = list(aliases) if isinstance(aliases, list) else []
    self.controller_mac = _str(raw, "controller_mac", "").upper()
    self.bluetooth_scan_timeout_sec = _float(raw, "bluetooth_scan_timeout_sec", 20.0)
    self.mapping = dict(_section(raw, "mapping"))
    self.evdev = dict(_section(raw, "evdev"))

  @classmethod
  def from_dict(cls, raw: dict) -> AppConfig:
    return cls(raw)
