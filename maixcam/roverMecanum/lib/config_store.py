"""Load and persist config.json with atomic writes + typed AppConfig cache."""

import json
import os
import tempfile

from lib.app_config import AppConfig
from lib.paths import resolve_config_path


class ConfigStore:
  """
  Load and persist config.json (hot-reload safe).

  In-memory ``AppConfig`` is the source of truth for callers. Disk is only
  touched on ``load`` / ``save`` / throttled ``reload_if_changed`` (mtime).
  """

  def __init__(self, path=None):
    self._explicit_path = path
    self.path = path or resolve_config_path()
    self._data = None
    self._settings = None
    self._mtime = 0

  def load(self):
    """Read config from disk; restore template if missing or corrupt."""
    self.path = self._explicit_path or resolve_config_path()
    if not os.path.isfile(self.path):
      print(f"config: no file at {self.path}, creating from template")
      self._data = self._load_template()
      self.save()
      self._mtime = os.path.getmtime(self.path)
      self._settings = AppConfig.from_dict(self._data)
      return self._data

    try:
      with open(self.path, "r", encoding="utf-8") as handle:
        raw = handle.read()
      if not raw.strip():
        raise json.JSONDecodeError("empty file", raw, 0)
      self._data = json.loads(raw)
      if not isinstance(self._data, dict):
        raise json.JSONDecodeError("root must be object", raw, 0)
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
      print(f"config: corrupt at {self.path} ({error}); restoring template")
      self._data = self._load_template()
      self.save()
      self._mtime = os.path.getmtime(self.path)
      self._settings = AppConfig.from_dict(self._data)
      return self._data

    self._merge_template()
    self._mtime = os.path.getmtime(self.path)
    self._settings = AppConfig.from_dict(self._data)
    return self._data

  def settings(self) -> AppConfig:
    """Cached typed settings — no disk I/O."""
    if self._settings is None:
      self.load()
    return self._settings

  def reload_if_changed(self) -> AppConfig:
    """
    Return cached settings unless config.json mtime changed.

    Call this sparingly (e.g. every ``timing.config_reload_ms``), not per poll.
    """
    path = self._explicit_path or self.path or resolve_config_path()
    if not os.path.isfile(path):
      path = resolve_config_path()
      if not os.path.isfile(path):
        return self.settings()
    mtime = os.path.getmtime(path)
    if self._settings is None or mtime != self._mtime or path != self.path:
      self.path = path
      self.load()
    return self._settings

  def save(self):
    """Atomically write config to avoid empty-file races with hot-reload."""
    if self._data is None:
      return
    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
    directory = os.path.dirname(self.path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=directory)
    try:
      with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(self._data, handle, indent=2)
        handle.write("\n")
      os.replace(tmp_path, self.path)
    except Exception:
      try:
        os.unlink(tmp_path)
      except OSError:
        pass
      raise
    if os.path.isfile(self.path):
      self._mtime = os.path.getmtime(self.path)
    self._settings = AppConfig.from_dict(self._data)

  def get(self):
    """Return the in-memory JSON dict (mapping engines / MAC writes)."""
    if self._data is None:
      self.load()
    return self._data

  def rover_settings(self):
    """Typed rover block (prefer ``settings().rover``)."""
    return self.settings().rover

  def set_controller_mac(self, mac):
    """Persist the paired controller MAC address."""
    data = self.get()
    data["controller_mac"] = mac.upper()
    self.save()

  def clear_controller_mac(self):
    """Clear the saved controller MAC from config.json."""
    data = self.get()
    data["controller_mac"] = ""
    self.save()

  def log_rover_settings(self):
    """Print a one-line summary of rover tuning for the console."""
    cfg = self.settings()
    rover = cfg.rover
    print(
      "config:"
      f" path={self.path}"
      f" max_speed={rover.max_speed}"
      f" deadzone={rover.deadzone_percent}%"
      f" curve={rover.axis_curve}"
      f" sensitivity={rover.axis_sensitivity_percent}%"
      f" send_ms={rover.send_interval_ms}"
    )

  def _template_path(self):
    return os.path.join(os.path.dirname(__file__), "..", "config.json")

  def _load_template(self):
    with open(self._template_path(), "r", encoding="utf-8") as handle:
      return json.load(handle)

  def _merge_template(self):
    base = self._load_template()
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

    for section in ("rover", "mapping", "evdev", "camera", "timing"):
      if section not in base:
        continue
      if section not in self._data:
        self._data[section] = dict(base[section])
        changed = True
        continue
      for key, value in base[section].items():
        if key not in self._data[section]:
          self._data[section][key] = value
          changed = True
    if "axes" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["axes"].items():
        if key not in self._data["mapping"]["axes"]:
          self._data["mapping"]["axes"][key] = value
          changed = True
    if "invert" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["invert"].items():
        if key not in self._data["mapping"]["invert"]:
          self._data["mapping"]["invert"][key] = value
          changed = True
    if "buttons" in self._data.get("mapping", {}):
      for key, value in base["mapping"]["buttons"].items():
        if key not in self._data["mapping"]["buttons"]:
          self._data["mapping"]["buttons"][key] = value
          changed = True
    if "dpad" in base.get("mapping", {}):
      if "dpad" not in self._data.get("mapping", {}):
        self._data["mapping"]["dpad"] = dict(base["mapping"]["dpad"])
        changed = True
      else:
        for key, value in base["mapping"]["dpad"].items():
          if key not in self._data["mapping"]["dpad"]:
            self._data["mapping"]["dpad"][key] = value
            changed = True

    if changed:
      self.save()
