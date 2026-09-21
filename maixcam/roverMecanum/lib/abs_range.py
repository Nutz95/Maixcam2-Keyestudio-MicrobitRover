"""Named ABS range (min/max/flat) from kernel or defaults."""


class AbsRange:
  """Axis calibration span from sysfs, ioctl, or a documented fallback."""

  __slots__ = ("minimum", "maximum", "flat")

  def __init__(self, minimum: int, maximum: int, flat: int = 0):
    self.minimum = minimum
    self.maximum = maximum
    self.flat = flat

  @property
  def span(self) -> int:
    return self.maximum - self.minimum

  def looks_like_trigger(self) -> bool:
    """True when the range matches typical Xbox trigger absinfo."""
    if self.minimum >= 0 and self.span <= 1024:
      return True
    return self.minimum >= 0 and self.maximum <= 255
