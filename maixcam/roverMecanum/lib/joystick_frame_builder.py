from lib.protocol_constants import CMD_JOYSTICK, PROTO_SYNC


class JoystickFrameBuilder:
  """Build CMD_JOYSTICK 0x30 frames (strafe, forward, rotation, max speed)."""

  def build(self, axis_x, axis_y, axis_rot, speed):
    axis_x = max(-32768, min(32767, int(axis_x)))
    axis_y = max(-32768, min(32767, int(axis_y)))
    axis_rot = max(-32768, min(32767, int(axis_rot)))
    speed = max(0, min(255, int(speed)))
    payload = (
      axis_x.to_bytes(2, "little", signed=True)
      + axis_y.to_bytes(2, "little", signed=True)
      + axis_rot.to_bytes(2, "little", signed=True)
      + bytes([speed])
    )
    frame = bytes([PROTO_SYNC, CMD_JOYSTICK]) + payload
    return frame + bytes([sum(frame) & 0xFF])

  def build_stop(self):
    return self.build(0, 0, 0, 0)
