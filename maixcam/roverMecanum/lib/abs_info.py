"""Named ABS axis snapshot from EVIOCGABS."""

from lib.abs_range import AbsRange


class AbsInfo:
  """Current kernel ABS state for one axis."""

  __slots__ = ("value", "minimum", "maximum", "flat")

  def __init__(self, value: int, minimum: int, maximum: int, flat: int):
    self.value = value
    self.minimum = minimum
    self.maximum = maximum
    self.flat = flat

  def to_range(self) -> AbsRange:
    """Drop the live value; keep calibration only."""
    return AbsRange(self.minimum, self.maximum, self.flat)
