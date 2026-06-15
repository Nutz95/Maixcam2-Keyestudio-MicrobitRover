import asyncio


class BleDeviceScanner:
  """BLE scan (bleak) by peripheral name."""

  async def find_by_name(self, name, timeout=15.0):
    try:
      from bleak import BleakScanner
    except ImportError:
      return None

    target = name.lower().strip()
    if not target:
      return None

    devices = await BleakScanner.discover(timeout=timeout)
    exact = None
    partial = None
    for device in devices:
      device_name = (device.name or "").strip()
      print(f"  ble scan: {device.address} {device.name}")
      if not device_name:
        continue
      dn = device_name.lower()
      if dn == target:
        exact = device.address.upper()
        break
      if target in dn:
        partial = partial or device.address.upper()
    return exact or partial

  def find_by_name_sync(self, name, timeout=15.0):
    return asyncio.run(self.find_by_name(name, timeout))
