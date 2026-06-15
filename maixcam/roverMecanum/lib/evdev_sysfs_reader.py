import os

from lib.evdev_constants import ABS_BRAKE, ABS_GAS, ABS_RZ, ABS_Z


class EvdevSysfsReader:
  """Read /sys/class/input metadata for evdev devices."""

  def read_field(self, event_path, field):
    for root in self._device_roots(event_path):
      path = f"{root}/{field}"
      try:
        with open(path, "r") as f:
          return f.read().strip()
      except OSError:
        pass
    return ""

  def read_name(self, event_path):
    return self.read_field(event_path, "name")

  def read_vendor(self, event_path):
    return self.read_field(event_path, "id/vendor")

  def read_absinfo(self, event_path, axis_code):
    real = self.read_absinfo_real(event_path, axis_code)
    if real is not None:
      return real
    return self.default_absinfo(axis_code)

  def read_absinfo_real(self, event_path, axis_code):
    for root in self._device_roots(event_path):
      for rel in (f"absinfo/{axis_code}", f"absinfo/{axis_code:02x}"):
        try:
          min_v = int(self._read_text(f"{root}/{rel}/min"))
          max_v = int(self._read_text(f"{root}/{rel}/max"))
          flat = int(self._read_text(f"{root}/{rel}/flat"))
          return min_v, max_v, flat
        except (OSError, ValueError):
          pass
    return None

  def read_abs_capabilities(self, event_path):
    text = self.read_field(event_path, "capabilities/abs")
    if not text:
      return 0
    try:
      return int(text, 16)
    except ValueError:
      return 0

  def default_absinfo(self, axis_code):
    if axis_code in (ABS_Z, ABS_RZ, ABS_GAS, ABS_BRAKE):
      return 0, 1023, 64
    return 0, 65535, 4096

  def abs_axis_exists(self, event_path, axis_code):
    for root in self._device_roots(event_path):
      for rel in (f"absinfo/{axis_code}", f"absinfo/{axis_code:02x}"):
        if os.path.isdir(f"{root}/{rel}"):
          return True
    return False

  def _device_roots(self, event_path):
    base = os.path.basename(event_path)
    roots = []
    seen = set()

    def add(path):
      if path and path not in seen:
        seen.add(path)
        roots.append(path)

    add(f"/sys/class/input/{base}/device")
    try:
      add(os.path.realpath(f"/sys/class/input/{base}/device"))
    except OSError:
      pass
    return roots

  def _read_text(self, path):
    with open(path, "r") as f:
      return f.read().strip()
