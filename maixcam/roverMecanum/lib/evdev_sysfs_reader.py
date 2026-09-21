import os

from lib.abs_range import AbsRange
from lib.evdev_constants import ABS_BRAKE, ABS_GAS, ABS_RX, ABS_RY, ABS_RZ, ABS_X, ABS_Y, ABS_Z

# Linux input subsystem ABS_* names for sysfs paths.
_ABS_LINUX_NAMES = {
  ABS_X: "x",
  ABS_Y: "y",
  ABS_Z: "z",
  ABS_RX: "rx",
  ABS_RY: "ry",
  ABS_RZ: "rz",
  ABS_GAS: "gas",
  ABS_BRAKE: "brake",
}


class EvdevSysfsReader:
  """Read /sys/class/input metadata for evdev devices."""

  def __init__(self):
    self._reported_probe_errors = set()

  def _report_probe_error(self, operation, path, error):
    """Log each optional sysfs probe failure once without flooding the HUD."""
    key = (operation, path, type(error).__name__)
    if key in self._reported_probe_errors:
      return
    self._reported_probe_errors.add(key)
    print(f"evdev sysfs: {operation} failed for {path}: {error}")

  def read_field(self, event_path, field):
    for root in self._device_roots(event_path):
      path = f"{root}/{field}"
      try:
        with open(path, "r") as handle:
          return handle.read().strip()
      except OSError as error:
        self._report_probe_error("read field", path, error)
        continue
    return ""

  def read_name(self, event_path):
    return self.read_field(event_path, "name")

  def read_vendor(self, event_path):
    return self.read_field(event_path, "id/vendor")

  def read_absinfo_real(self, event_path, axis_code):
    """Return AbsRange for one axis from sysfs, or None."""
    for root in self._device_roots(event_path):
      for rel in (f"absinfo/{axis_code}", f"absinfo/{axis_code:02x}"):
        path = f"{root}/{rel}"
        try:
          return AbsRange(
            int(self._read_text(f"{path}/min")),
            int(self._read_text(f"{path}/max")),
            int(self._read_text(f"{path}/flat")),
          )
        except (OSError, ValueError) as error:
          self._report_probe_error("read absinfo", path, error)
          continue
    return None

  def read_abs_value(self, event_path, axis_code):
    """Read the kernel's current axis value (fallback when ioctl unavailable)."""
    name = _ABS_LINUX_NAMES.get(axis_code)
    for root in self._device_roots(event_path):
      rels = [
        f"abs/{axis_code:02x}/value",
        f"abs/{axis_code}/value",
        f"absinfo/{axis_code}/value",
        f"absinfo/{axis_code:02x}/value",
      ]
      if name:
        rels.extend([f"abs/ABS_{name.upper()}/value", f"abs/{name}/value"])
      for rel in rels:
        path = f"{root}/{rel}"
        try:
          return int(self._read_text(path))
        except (OSError, ValueError) as error:
          self._report_probe_error("read abs value", path, error)
          continue
    return None

  def read_abs_capabilities(self, event_path):
    text = self.read_field(event_path, "capabilities/abs")
    if not text:
      return 0
    try:
      return int(text, 16)
    except ValueError as error:
      self._report_probe_error("parse abs capabilities", event_path, error)
      return 0

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
    except OSError as io_error:
      print(f"evdev sysfs: realpath skip for {base}: {io_error}")
    return roots

  def _read_text(self, path):
    with open(path, "r") as handle:
      return handle.read().strip()
