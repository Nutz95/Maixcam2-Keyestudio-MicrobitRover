"""Evdev axis layout selection from config.json."""

from lib.app_config.parse_helpers import as_str, section


class EvdevSettings:
  """Xbox axis layout profile and optional explicit ABS codes."""

  __slots__ = (
    "layout",
    "left_x", "left_y", "right_x", "right_y", "lt", "rt",
  )

  def __init__(self, raw: dict):
    evdev = section(raw, "evdev")
    self.layout = as_str(evdev, "layout", "auto")
    self.left_x = self._optional_int(evdev, "left_x")
    self.left_y = self._optional_int(evdev, "left_y")
    self.right_x = self._optional_int(evdev, "right_x")
    self.right_y = self._optional_int(evdev, "right_y")
    self.lt = self._optional_int(evdev, "lt")
    self.rt = self._optional_int(evdev, "rt")

  @staticmethod
  def _optional_int(block: dict, key: str):
    if key not in block or block[key] is None:
      return None
    try:
      return int(block[key])
    except (TypeError, ValueError):
      return None

  def has_explicit_codes(self) -> bool:
    """True when config overrides every stick/trigger ABS code."""
    return None not in (
      self.left_x, self.left_y, self.right_x, self.right_y, self.lt, self.rt,
    )
