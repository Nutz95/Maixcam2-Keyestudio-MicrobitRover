"""HUD / teleop snapshot of Xbox input service state."""

from typing import Optional

from lib.controller_state import ControllerState
from lib.drive_output import DriveOutput


class XboxInputSnapshot:
  """Status + connection + mapped drive for one UI or teleop tick."""

  __slots__ = ("status", "connected", "busy", "state", "drive", "progress")

  def __init__(
    self,
    status: str,
    connected: bool,
    busy: bool,
    state: ControllerState,
    drive: Optional[DriveOutput],
    progress: float,
  ):
    self.status = status
    self.connected = connected
    self.busy = busy
    self.state = state
    self.drive = drive
    self.progress = progress
