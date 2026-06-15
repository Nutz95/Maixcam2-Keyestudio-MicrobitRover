from lib.protocol_constants import CMD_STOP, PROTO_SYNC


class PresetFrameBuilder:
  """Construit les trames preset 4 octets."""

  def build(self, cmd, speed):
    speed = max(0, min(255, int(speed)))
    frame = bytes([PROTO_SYNC, cmd, speed])
    return frame + bytes([(PROTO_SYNC + cmd + speed) & 0xFF])

  def build_stop(self):
    return self.build(CMD_STOP, 0)
