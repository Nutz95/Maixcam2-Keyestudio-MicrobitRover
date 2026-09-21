"""Named d-pad strafe/forward axes for a preset action."""


class DpadAxes:
  """Strafe and forward signed axis values for one d-pad action."""

  __slots__ = ("strafe", "forward")

  def __init__(self, strafe: int, forward: int):
    self.strafe = strafe
    self.forward = forward
