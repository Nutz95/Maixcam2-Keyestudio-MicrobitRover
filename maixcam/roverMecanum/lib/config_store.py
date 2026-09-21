"""Load and persist config.json with atomic writes; AppConfig is the in-memory model."""

import json
import os
import tempfile

from lib.app_config import AppConfig
from lib.paths import resolve_config_path


class ConfigStore:
  """
  Load and persist config.json (hot-reload safe).

  Runtime only sees ``AppConfig``. A dict is used solely to read/write the file
  (template sync, MAC patch) — never as an application model.
  """

  def __init__(self, path=None):
    self._explicit_path = path
    self.path = path or resolve_config_path()
    self._settings = None
    self._mtime = 0

  def load(self) -> AppConfig:
    """Read config from disk; restore template if missing or corrupt."""
    self.path = self._explicit_path or resolve_config_path()
    created = False
    if not os.path.isfile(self.path):
      print(f"config: no file at {self.path}, creating from template")
      raw = self._load_template()
      created = True
    else:
      try:
        raw = self._read_json()
      except (OSError, json.JSONDecodeError, UnicodeError) as error:
        print(f"config: corrupt at {self.path} ({error}); restoring template")
        raw = self._load_template()
        created = True

    synced = self._sync_with_template(raw)
    if created or synced:
      self._write_dict(raw)
    elif os.path.isfile(self.path):
      self._mtime = os.path.getmtime(self.path)
    self._settings = AppConfig.from_dict(raw)
    return self._settings

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

  def set_controller_mac(self, mac):
    """Patch controller_mac in config.json and refresh the typed snapshot."""
    self.settings()
    raw = self._read_json()
    raw["controller_mac"] = str(mac).upper()
    self._write_dict(raw)
    self._settings = AppConfig.from_dict(raw)

  def clear_controller_mac(self):
    """Clear the saved controller MAC from config.json."""
    self.set_controller_mac("")

  def log_rover_settings(self):
    """Print a one-line summary of rover tuning for the console."""
    app_config = self.settings()
    rover = app_config.rover
    print(
      "config:"
      f" path={self.path}"
      f" max_speed={rover.max_speed}"
      f" deadzone={rover.deadzone_percent}%"
      f" curve={rover.axis_curve}"
      f" sensitivity={rover.axis_sensitivity_percent}%"
      f" send_ms={rover.send_interval_ms}"
    )

  def _read_json(self) -> dict:
    with open(self.path, "r", encoding="utf-8") as handle:
      text = handle.read()
    if not text.strip():
      raise json.JSONDecodeError("empty file", text, 0)
    raw = json.loads(text)
    if not isinstance(raw, dict):
      raise json.JSONDecodeError("root must be object", text, 0)
    return raw

  def _write_dict(self, data: dict):
    """Atomic JSON write; updates mtime after replace."""
    os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
    directory = os.path.dirname(self.path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="config.", suffix=".tmp", dir=directory)
    try:
      with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
      os.replace(tmp_path, self.path)
    except Exception as save_error:
      print(f"config: atomic save failed: {save_error}")
      try:
        os.unlink(tmp_path)
      except OSError as unlink_error:
        print(f"config: temp cleanup failed: {unlink_error}")
      raise
    if os.path.isfile(self.path):
      self._mtime = os.path.getmtime(self.path)

  def _template_path(self):
    return os.path.join(os.path.dirname(__file__), "..", "config.json")

  def _load_template(self):
    with open(self._template_path(), "r", encoding="utf-8") as handle:
      return json.load(handle)

  def _sync_with_template(self, data: dict) -> bool:
    """
    Add missing template keys only. Never rewrite existing user values.

    Prints every key that was filled so a partial on-device config is obvious.
    mapping_revision upgrades remain the only intentional overwrite path.
    """
    base = self._load_template()
    missing = self._missing_paths(data, base)
    changed = False
    if missing:
      print(
        "config: incomplete vs packaged template; filling missing keys:"
        f" {', '.join(missing)}"
      )
      print(
        "config: redeploy maixcam/roverMecanum/config.json if values look stale"
      )
      changed = self._fill_missing(data, base)

    target_revision = base.get("mapping_revision", 0)
    if data.get("mapping_revision", 0) < target_revision:
      data["mapping_revision"] = target_revision
      data["mapping"] = dict(data.get("mapping") or {})
      data["mapping"]["axes"] = dict(base["mapping"]["axes"])
      if "dpad" in base["mapping"]:
        data["mapping"]["dpad"] = dict(base["mapping"]["dpad"])
      data["evdev"] = dict(base["evdev"])
      if "camera" in base:
        data["camera"] = dict(base["camera"])
      changed = True
      print(
        "config: mapping upgraded to revision"
        f" {target_revision} (forward=left_y strafe=triggers spin=right_x pivot=left_x)"
      )

    return changed

  @staticmethod
  def _missing_paths(destination: dict, template: dict, prefix: str = "") -> list:
    """Return dotted paths present in template but absent from destination."""
    missing = []
    for key, value in template.items():
      path = f"{prefix}.{key}" if prefix else str(key)
      if key not in destination:
        missing.append(path)
      elif isinstance(value, dict) and isinstance(destination[key], dict):
        missing.extend(
          ConfigStore._missing_paths(destination[key], value, path),
        )
    return missing

  @staticmethod
  def _fill_missing(destination: dict, template: dict) -> bool:
    """Recursively copy template keys that are absent from destination."""
    changed = False
    for key, value in template.items():
      if key not in destination:
        if isinstance(value, dict):
          destination[key] = dict(value)
        else:
          destination[key] = value
        changed = True
      elif isinstance(value, dict) and isinstance(destination[key], dict):
        if ConfigStore._fill_missing(destination[key], value):
          changed = True
    return changed
