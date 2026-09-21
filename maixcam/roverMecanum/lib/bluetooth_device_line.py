"""Parsed bluetoothctl Device line (MAC + advertised name)."""


class BluetoothDeviceLine:
  """One BlueZ device listing entry."""

  __slots__ = ("mac", "name")

  def __init__(self, mac: str, name: str):
    self.mac = mac
    self.name = name
