"""Camera + HUD display cadence from config.json."""

from lib.app_config.parse_helpers import as_bool, as_int, as_str, section


class CameraSettings:
  """Camera + HUD display cadence."""

  __slots__ = (
    "enabled", "width", "height", "fps", "format", "display_fps",
    "ready_timeout_ms", "ready_poll_ms", "paused_poll_ms",
    "frame_yield_ms", "no_frame_sleep_ms", "stop_join_ms",
  )

  def __init__(self, raw: dict):
    cam = section(raw, "camera")
    timing = section(raw, "timing")
    self.enabled = as_bool(cam, "enabled", True)
    self.width = as_int(cam, "width", 640)
    self.height = as_int(cam, "height", 480)
    self.fps = max(1, min(30, as_int(cam, "fps", 30)))
    self.format = as_str(cam, "format", "rgb888")
    self.display_fps = max(5, min(30, as_int(cam, "display_fps", 20)))
    self.ready_timeout_ms = as_int(timing, "camera_ready_timeout_ms", 8000)
    self.ready_poll_ms = as_int(timing, "camera_ready_poll_ms", 20)
    self.paused_poll_ms = as_int(timing, "camera_paused_poll_ms", 40)
    self.frame_yield_ms = as_int(timing, "camera_frame_yield_ms", 1)
    self.no_frame_sleep_ms = as_int(timing, "camera_no_frame_sleep_ms", 5)
    self.stop_join_ms = as_int(timing, "camera_stop_join_ms", 2500)

  @property
  def display_interval_ms(self) -> int:
    return max(1, 1000 // self.display_fps)
