"""Named evdev input_event struct layout."""


class EvdevEventFormat:
  """Struct format and byte size for one input_event record."""

  __slots__ = ("event_struct", "size")

  def __init__(self, event_struct, size: int):
    self.event_struct = event_struct
    self.size = size
