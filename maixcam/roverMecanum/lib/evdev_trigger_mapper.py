from lib.evdev_constants import AXIS_MAX


class EvdevTriggerMapper:
  """Map a one-sided trigger axis (0..max) to 0..32767."""

  def __init__(self, min_v, max_v, flat):
    self.min_v = min_v
    self.max_v = max_v
    self.flat = flat
    self.raw = min_v

  def set_raw(self, value):
    self.raw = int(value)

  def to_axis(self):
    if self.raw <= self.min_v + self.flat:
      return 0
    mag = self.raw - self.min_v - self.flat
    span = max(1, self.max_v - self.min_v - self.flat)
    return min(AXIS_MAX, int(mag * AXIS_MAX / span))
