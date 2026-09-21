"""Mapped stick/trigger values ready for UART."""


class DriveOutput:
  """Mapped stick/trigger values ready for UART (4 axes + optional preset)."""

  def __init__(self):
    self.axis_strafe = 0
    self.axis_forward = 0
    self.axis_spin = 0
    self.axis_pivot = 0
    self.preset_cmd = None

  def is_idle(self, threshold=250):
    """True when all drive axes are near zero (after shaping)."""
    return (
      abs(self.axis_strafe) <= threshold
      and abs(self.axis_forward) <= threshold
      and abs(self.axis_spin) <= threshold
      and abs(self.axis_pivot) <= threshold
    )
