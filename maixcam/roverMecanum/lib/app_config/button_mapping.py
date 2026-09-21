"""Face/shoulder button → preset action mapping."""

from lib.config_parse_helpers import section


class ButtonMapping:
  """Xbox button names mapped to UART preset actions (None = unused)."""

  __slots__ = (
    "btn_a", "btn_b", "btn_x", "btn_y",
    "btn_lb", "btn_rb", "btn_start", "btn_select",
  )

  def __init__(self, mapping: dict):
    buttons = section(mapping, "buttons")
    self.btn_a = self._action(buttons, "btn_a", "stop")
    self.btn_b = self._action(buttons, "btn_b", None)
    self.btn_x = self._action(buttons, "btn_x", None)
    self.btn_y = self._action(buttons, "btn_y", None)
    self.btn_lb = self._action(buttons, "btn_lb", None)
    self.btn_rb = self._action(buttons, "btn_rb", None)
    self.btn_start = self._action(buttons, "btn_start", None)
    self.btn_select = self._action(buttons, "btn_select", None)

  @staticmethod
  def _action(block: dict, key: str, default):
    if key not in block:
      return default
    value = block[key]
    return None if value is None else str(value)

  def bindings(self):
    """Yield (button_name, action) for configured presets."""
    return (
      ("btn_a", self.btn_a),
      ("btn_b", self.btn_b),
      ("btn_x", self.btn_x),
      ("btn_y", self.btn_y),
      ("btn_lb", self.btn_lb),
      ("btn_rb", self.btn_rb),
      ("btn_start", self.btn_start),
      ("btn_select", self.btn_select),
    )
