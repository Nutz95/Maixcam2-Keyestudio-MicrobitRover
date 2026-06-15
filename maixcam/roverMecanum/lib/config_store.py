import json
import os

from lib.config_defaults import default_config
from lib.paths import resolve_config_path


class ConfigStore:
  """
  Load and persist config.json.

  The file is resolved at runtime (see resolve_config_path). Editing the repo
  config.json has no effect on the device until it is copied to the MaixCam
  (deploy -SyncConfig or manual scp).
  """

  def __init__(self, path=None):
    self._explicit_path = path
    self.path = path or resolve_config_path()
    self._data = None
    self._mtime = 0

  def load(self):
    """Read config from disk; merge missing keys from defaults."""
    self.path = self._explicit_path or resolve_config_path()
    if not os.path.isfile(self.path):
      print(f"config: no file at {self.path}, creating defaults")
      self._data = default_config()
      self.save()
      self._mtime = os.path.getmtime(self.path)
      return self._data

    with open(self.path, "r") as f:
      self._data = json.load(f)
    self._merge_defaults()
    self._mtime = os.path.getmtime(self.path)
    return self._data

  def reload_if_changed(self):
    """Reload from disk when the file was modified (hot-tune on device)."""
    path = self._explicit_path or resolve_config_path()
    if not os.path.isfile(path):
      return self.get()
    mtime = os.path.getmtime(path)
    if self._data is None or mtime != self._mtime or path != self.path:
      self.path = path
      return self.load()
    return self._data

  def save(self):
    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
    with open(self.path, "w") as f:
      json.dump(self._data, f, indent=2)
      f.write("\n")
    if os.path.isfile(self.path):
      self._mtime = os.path.getmtime(self.path)

  def get(self):
    if self._data is None:
      self.load()
    return self._data

  def rover_settings(self):
    """Return rover tuning block (always from latest in-memory config)."""
    return dict(self.get().get("rover", {}))

  def set_controller_mac(self, mac):
    data = self.get()
    data["controller_mac"] = mac.upper()
    self.save()

  def clear_controller_mac(self):
    data = self.get()
    data["controller_mac"] = ""
    self.save()

  def log_rover_settings(self):
    rover = self.rover_settings()
    print(
      "config:"
      f" path={self.path}"
      f" max_speed={rover.get('max_speed', 255)}"
      f" deadzone={rover.get('deadzone_percent', 2)}%"
      f" curve={rover.get('axis_curve', 'expo')}"
      f" sensitivity={rover.get('axis_sensitivity_percent', 100)}%"
      f" send_ms={rover.get('send_interval_ms', 30)}"
    )

  def _merge_defaults(self):
    base = default_config()
    changed = False
    for key, value in base.items():
      if key not in self._data:
        self._data[key] = value
        changed = True

    target_revision = base.get("mapping_revision", 0)
    if self._data.get("mapping_revision", 0) < target_revision:
      if "mapping" not in self._data:
        self._data["mapping"] = dict(base["mapping"])
      if "evdev" not in self._data:
        self._data["evdev"] = dict(base["evdev"])
      self._data["mapping_revision"] = target_revision
      self._data["mapping"]["axes"] = dict(base["mapping"]["axes"])
      if "dpad" in base["mapping"]:
        self._data["mapping"]["dpad"] = dict(base["mapping"]["dpad"])
      self._data["evdev"] = dict(base["evdev"])
      if "camera" in base:
        self._data["camera"] = dict(base["camera"])
      changed = True
      print(
        "config: mapping upgraded to revision"
        f" {target_revision} (forward=left_y strafe=triggers spin=right_x pivot=left_x)"
      )

    for section in ("rover", "mapping", "evdev", "camera"):
      if section not in self._data:
        self._data[section] = base[section]
        continue
      for key, value in base[section].items():
        if key not in self._data[section]:
          self._data[section][key] = value
    if "axes" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["axes"].items():
        if key not in self._data["mapping"]["axes"]:
          self._data["mapping"]["axes"][key] = value
    if "invert" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["invert"].items():
        if key not in self._data["mapping"]["invert"]:
          self._data["mapping"]["invert"][key] = value
    if "buttons" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["buttons"].items():
        if key not in self._data["mapping"]["buttons"]:
          self._data["mapping"]["buttons"][key] = value
    if "dpad" in base.get("mapping", {}):
      if "dpad" not in self._data.get("mapping", {}):
        self._data["mapping"]["dpad"] = dict(base["mapping"]["dpad"])
      else:
        for key, value in base["mapping"]["dpad"].items():
          if key not in self._data["mapping"]["dpad"]:
            self._data["mapping"]["dpad"][key] = value

    if changed:
      self.save()
