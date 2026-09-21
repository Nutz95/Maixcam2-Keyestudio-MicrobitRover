"""Named result of bluetoothctl device-list / scan parsing."""


class ScanMatchResult:
  """Exact name match, partial match, and how many device lines were seen."""

  __slots__ = ("exact_mac", "partial_mac", "devices_seen")

  def __init__(self, exact_mac: str = "", partial_mac: str = "", devices_seen: int = 0):
    self.exact_mac = exact_mac or ""
    self.partial_mac = partial_mac or ""
    self.devices_seen = devices_seen

  @property
  def mac(self) -> str:
    """Preferred MAC: exact match wins over partial."""
    return self.exact_mac or self.partial_mac
