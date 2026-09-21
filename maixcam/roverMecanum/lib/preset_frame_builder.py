from lib.uart_protocol import build_preset_frame


class PresetFrameBuilder:
  """Build 4-byte preset UART frames."""

  def build(self, cmd, speed):
    return build_preset_frame(cmd, speed)
