"""Controller → drive axis mapping from config.json."""

from lib.app_config.button_mapping import ButtonMapping
from lib.app_config.dpad_mapping import DpadMapping
from lib.app_config.invert_settings import InvertSettings
from lib.app_config.parse_helpers import as_str, section


class MappingSettings:
  """Stick/trigger/dpad/button mapping rules (parsed once at load)."""

  __slots__ = (
    "drive_forward", "drive_strafe", "drive_spin", "drive_pivot",
    "invert", "dpad", "buttons",
  )

  def __init__(self, raw: dict):
    mapping = section(raw, "mapping")
    axes = section(mapping, "axes")
    self.drive_forward = as_str(axes, "drive_forward", "left_y")
    self.drive_strafe = as_str(axes, "drive_strafe", "trigger_diff")
    self.drive_spin = as_str(axes, "drive_spin", "right_x")
    self.drive_pivot = as_str(axes, "drive_pivot", "left_x")
    self.invert = InvertSettings(mapping)
    self.dpad = DpadMapping(mapping)
    self.buttons = ButtonMapping(mapping)
