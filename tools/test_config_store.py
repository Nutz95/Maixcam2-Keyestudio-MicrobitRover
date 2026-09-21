"""Unit tests for ConfigStore atomic load/save."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum"))

from lib.config_store import ConfigStore


class TestConfigStoreAtomic(unittest.TestCase):
  def test_empty_file_restored_from_template(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = os.path.join(tmp, "config.json")
      with open(path, "w", encoding="utf-8") as handle:
        handle.write("")
      store = ConfigStore(path=path)
      data = store.load()
      self.assertIsInstance(data, dict)
      self.assertIn("rover", data)
      with open(path, "r", encoding="utf-8") as handle:
        self.assertTrue(handle.read().strip())

  def test_atomic_save_roundtrip(self):
    with tempfile.TemporaryDirectory() as tmp:
      path = os.path.join(tmp, "config.json")
      store = ConfigStore(path=path)
      store.load()
      store.set_controller_mac("aa:bb:cc:dd:ee:ff")
      store2 = ConfigStore(path=path)
      self.assertEqual(store2.load().get("controller_mac"), "AA:BB:CC:DD:EE:FF")


if __name__ == "__main__":
  unittest.main()
