"""Named pair of ABS axis codes (stick X/Y or LT/RT)."""


class AbsCodePair:
  """Two related ABS codes (right stick or triggers)."""

  __slots__ = ("first", "second")

  def __init__(self, first: int, second: int):
    self.first = first
    self.second = second
