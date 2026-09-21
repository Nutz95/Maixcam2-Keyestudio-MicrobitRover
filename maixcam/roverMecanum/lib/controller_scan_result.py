"""Result of scanning for an Xbox controller MAC address."""


class ControllerScanResult:
  """MAC discovery outcome used by the Bluetooth pairing flow."""

  def __init__(self, mac="", error=""):
    self.mac = mac
    self.error = error

  def ok(self):
    """Return True when a MAC was found."""
    return bool(self.mac) and not self.error
