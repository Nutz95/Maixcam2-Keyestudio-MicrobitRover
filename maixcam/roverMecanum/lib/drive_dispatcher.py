"""Choose stop / ball-follow / manual UART action for one teleop tick."""


class DriveDispatcher:
  """Keep mode arbitration out of the raw UART send path."""

  def __init__(self, rover, ball_follow, imu, get_frame):
    """Wire rover client, ball controller, IMU service, and a frame getter."""
    self._rover = rover
    self._ball_follow = ball_follow
    self._imu = imu
    self._get_frame = get_frame

  def dispatch(self, drive, manual_resume_pending: bool) -> bool:
    """
    Apply one teleop tick.

    Returns the updated ``manual_resume_pending`` flag.
    """
    imu_snap = self._imu.snapshot()
    if imu_snap.calibrating:
      self._rover.send_stop()
      return manual_resume_pending

    if self._ball_follow.enabled:
      frame = self._get_frame()
      yaw_deg = imu_snap.yaw_deg if imu_snap.ready else None
      command = self._ball_follow.update(frame, yaw_deg=yaw_deg)
      self._rover.send_joystick(0, command.forward, command.spin, 0)
      return manual_resume_pending

    if manual_resume_pending:
      self._rover.send_stop()
      return False

    if drive.preset_cmd is not None:
      self._rover.send_preset(drive.preset_cmd)
      return False
    if drive.is_idle():
      self._rover.send_stop()
      return False
    self._rover.send_joystick(
      drive.axis_strafe,
      drive.axis_forward,
      drive.axis_spin,
      drive.axis_pivot,
    )
    return False
