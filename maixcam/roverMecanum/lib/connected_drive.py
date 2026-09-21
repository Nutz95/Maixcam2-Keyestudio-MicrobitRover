"""Lightweight teleop view: connected flag + current DriveOutput."""

from typing import Optional

from lib.drive_output import DriveOutput


class ConnectedDrive:
  """Whether HID is live and the latest mapped drive axes."""

  __slots__ = ("connected", "drive")

  def __init__(self, connected: bool, drive: Optional[DriveOutput]):
    self.connected = connected
    self.drive = drive
