import json
import os

from lib.config_defaults import default_config
from lib.paths import CONFIG_PATH


class ConfigStore:
  """Charge et sauvegarde config.json sous /root/roverMecanum."""

  def __init__(self, path=CONFIG_PATH):
    self.path = path
    self._data = None

  def load(self):
    if not os.path.isfile(self.path):
      self._data = default_config()
      self.save()
      return self._data

    with open(self.path, "r") as f:
      self._data = json.load(f)
    self._merge_defaults()
    return self._data

  def save(self):
    os.makedirs(os.path.dirname(self.path), exist_ok=True)
    with open(self.path, "w") as f:
      json.dump(self._data, f, indent=2)
      f.write("\n")

  def get(self):
    if self._data is None:
      self.load()
    return self._data

  def set_controller_mac(self, mac):
    data = self.get()
    data["controller_mac"] = mac.upper()
    self.save()

  def clear_controller_mac(self):
    data = self.get()
    data["controller_mac"] = ""
    self.save()

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
