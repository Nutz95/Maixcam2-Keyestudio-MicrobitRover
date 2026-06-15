import glob

from lib.evdev_constants import XBOX_VENDOR_ID
from lib.evdev_sysfs_reader import EvdevSysfsReader


class EvdevDeviceFinder:
  """Trouve le peripherique input Xbox (evdev ou js)."""

  def __init__(self):
    self._sysfs = EvdevSysfsReader()

  def find_js(self):
    devices = sorted(glob.glob("/dev/input/js*"))
    return devices[0] if devices else None

  def find_xbox_event(self):
    for path in sorted(glob.glob("/dev/input/event*")):
      if self._is_xbox(path):
        name = self._sysfs.read_name(path)
        vendor = self._sysfs.read_vendor(path)
        print(f"input: {path} vendor={vendor!r} name={name!r}")
        return path
    return None

  def list_devices(self):
    for path in sorted(glob.glob("/dev/input/event*")):
      name = self._sysfs.read_name(path)
      vendor = self._sysfs.read_vendor(path)
      print(f"input: {path} vendor={vendor!r} name={name!r}")

  def _is_xbox(self, event_path):
    vendor = self._sysfs.read_vendor(event_path).lower()
    if vendor == XBOX_VENDOR_ID:
      return True
    name = self._sysfs.read_name(event_path).lower()
    return "xbox" in name or "x-box" in name or ("microsoft" in name and "controller" in name)
