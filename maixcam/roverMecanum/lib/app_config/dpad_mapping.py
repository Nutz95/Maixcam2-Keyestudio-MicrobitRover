"""D-pad action mapping from config.json mapping.dpad."""

from lib.config_parse_helpers import section


class DpadMapping:
  """Preset action names for each D-pad direction (None = unused)."""

  __slots__ = (
    "up", "down", "left", "right",
    "up_left", "up_right", "down_left", "down_right",
  )

  def __init__(self, mapping: dict):
    dpad = section(mapping, "dpad")
    self.up = self._action(dpad, "up", "forward")
    self.down = self._action(dpad, "down", "backward")
    self.left = self._action(dpad, "left", "strafe_left")
    self.right = self._action(dpad, "right", "strafe_right")
    self.up_left = self._action(dpad, "up_left", "diag_fl")
    self.up_right = self._action(dpad, "up_right", "diag_fr")
    self.down_left = self._action(dpad, "down_left", "diag_bl")
    self.down_right = self._action(dpad, "down_right", "diag_br")

  @staticmethod
  def _action(block: dict, key: str, default: str):
    if key not in block:
      return default
    value = block[key]
    return None if value is None else str(value)
