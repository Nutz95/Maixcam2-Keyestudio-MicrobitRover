"""Unit tests for ConfigStore atomic load/save."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum"))

from lib.app_config import AppConfig
from lib.config_store import ConfigStore


class TestConfigStoreAtomic(unittest.TestCase):
  def test_empty_file_restored_from_template(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = os.path.join(tmp, "config.json")
      with open(path, "w", encoding="utf-8") as handle:
        handle.write("")
      store = ConfigStore(path=path)
      settings = store.load()
      self.assertIsInstance(settings, AppConfig)
      self.assertEqual(settings.rover.max_speed, 255)
      with open(path, "r", encoding="utf-8") as handle:
        self.assertTrue(handle.read().strip())

  def test_atomic_save_roundtrip(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = os.path.join(tmp, "config.json")
      store = ConfigStore(path=path)
      store.load()
      store.set_controller_mac("aa:bb:cc:dd:ee:ff")
      store2 = ConfigStore(path=path)
      store2.load()
      self.assertEqual(store2.settings().controller_mac, "AA:BB:CC:DD:EE:FF")
      self.assertEqual(store2.settings().mapping.dpad.up, "forward")

  def test_legacy_ball_thresholds_fill_missing_color_presets(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = os.path.join(tmp, "config.json")
      store = ConfigStore(path=path)
      store.load()
      with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
      raw["ball_follow"] = {
        "thresholds": [[0, 80, -120, -10, 0, 30]],
        "area_threshold": 120,
      }
      with open(path, "w", encoding="utf-8") as handle:
        json.dump(raw, handle)

      settings = store.load()

      # Missing keys are filled from the packaged template, not rewritten values.
      self.assertEqual(
        settings.ball_follow.thresholds_for("green"),
        [[40, 90, -90, -40, 25, 75]],
      )
      self.assertEqual(
        settings.ball_follow.thresholds_for("red"),
        [[0, 80, 40, 80, 10, 80]],
      )


if __name__ == "__main__":
  unittest.main()
