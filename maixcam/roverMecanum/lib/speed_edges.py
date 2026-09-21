"""LB/RB press edges for session max-speed bumps."""


class SpeedEdges:
  """One-shot bumper edges consumed by the app each tick."""

  __slots__ = ("lb_pressed", "rb_pressed")

  def __init__(self, lb_pressed: bool = False, rb_pressed: bool = False):
    self.lb_pressed = lb_pressed
    self.rb_pressed = rb_pressed
