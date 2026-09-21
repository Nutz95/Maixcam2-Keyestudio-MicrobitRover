"""Bluetooth pairing/connect command result."""


class BluetoothCommandResult:
  """Outcome of a bluetoothctl pairing or connect operation."""

  def __init__(self, output="", error=""):
    self.output = output
    self.error = error

  def ok(self):
    """Return True when the command reported no error string."""
    return not self.error
