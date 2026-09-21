"""Per-axis invert flags from config.json mapping.invert."""

from lib.app_config.parse_helpers import as_bool, section


class InvertSettings:
  """Which stick/trigger sources are sign-flipped before shaping."""

  __slots__ = ("left_x", "left_y", "right_x", "right_y", "lt", "rt", "trigger_diff")

  def __init__(self, mapping: dict):
    invert = section(mapping, "invert")
    self.left_x = as_bool(invert, "left_x", False)
    self.left_y = as_bool(invert, "left_y", False)
    self.right_x = as_bool(invert, "right_x", False)
    self.right_y = as_bool(invert, "right_y", False)
    self.lt = as_bool(invert, "lt", False)
    self.rt = as_bool(invert, "rt", False)
    self.trigger_diff = as_bool(invert, "trigger_diff", False)

  def for_source(self, source: str) -> bool:
    """Return invert flag for a named axis source."""
    if source == "left_x":
      return self.left_x
    if source == "left_y":
      return self.left_y
    if source == "right_x":
      return self.right_x
    if source == "right_y":
      return self.right_y
    if source == "lt":
      return self.lt
    if source == "rt":
      return self.rt
    if source == "trigger_diff":
      return self.trigger_diff
    return False
