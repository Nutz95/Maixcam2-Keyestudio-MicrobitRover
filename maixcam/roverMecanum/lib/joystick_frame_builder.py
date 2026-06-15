from lib.protocol_constants import CMD_JOYSTICK, PROTO_SYNC


class JoystickFrameBuilder:
  """Trame CMD_JOYSTICK 0x30 : strafe, forward, spin, pivot, vitesse max."""

  def build(self, axis_strafe, axis_forward, axis_spin, axis_pivot, speed):
    axis_strafe = max(-32768, min(32767, int(axis_strafe)))
    axis_forward = max(-32768, min(32767, int(axis_forward)))
    axis_spin = max(-32768, min(32767, int(axis_spin)))
    axis_pivot = max(-32768, min(32767, int(axis_pivot)))
    speed = max(0, min(255, int(speed)))
    payload = (
      axis_strafe.to_bytes(2, "little", signed=True)
      + axis_forward.to_bytes(2, "little", signed=True)
      + axis_spin.to_bytes(2, "little", signed=True)
      + axis_pivot.to_bytes(2, "little", signed=True)
      + bytes([speed])
    )
    frame = bytes([PROTO_SYNC, CMD_JOYSTICK]) + payload
    return frame + bytes([sum(frame) & 0xFF])

  def build_stop(self):
    return self.build(0, 0, 0, 0, 0)
