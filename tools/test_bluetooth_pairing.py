"""Unit tests for bluetoothctl scan line parsing (MaixAiRover-ported)."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum"))

from lib.bluetoothctl_runner import BluetoothctlRunner
from lib.config_store import ConfigStore


SAMPLE = """
Discovery started
[CHG] Controller 38:7A:CC:98:34:39 Discovering: yes
[NEW] Device 28:E6:A9:4D:63:53 49" Odyssey OLED G9
[NEW] Device 78:86:2E:AC:8D:03 Xbox Wireless Controller
[CHG] Device 78:86:2E:AC:8D:03 TxPower: 20
[CHG] Device 78:86:2E:AC:8D:03 UUIDs: 00001812-0000-1000-8000-00805f9b34fb
"""


class TestBluetoothScanParse(unittest.TestCase):
  def test_parse_new_device_line_with_name(self):
    runner = BluetoothctlRunner()
    mac, name = runner._parse_device_line(
      "[NEW] Device 78:86:2E:AC:8D:03 Xbox Wireless Controller"
    )
    self.assertEqual(mac, "78:86:2E:AC:8D:03")
    self.assertEqual(name, "Xbox Wireless Controller")

  def test_last_connected_flag_ignores_transient_yes(self):
    runner = BluetoothctlRunner()
    output = """
[CHG] Device 78:86:2E:AC:8D:03 Connected: yes
Failed to connect: org.bluez.Error.Failed le-connection-abort-by-local
Device 78:86:2E:AC:8D:03 (public)
	Paired: yes
	Connected: no
"""
    self.assertFalse(runner.last_flag_yes(output, "Connected"))
    self.assertTrue(runner.last_flag_yes(output, "Paired"))

  def test_pair_succeeded_false_when_failed_even_if_paired_yes(self):
    output = """
Failed to pair: org.bluez.Error.ConnectionAttemptFailed
	Paired: yes
	Connected: no
"""
    self.assertFalse(BluetoothctlRunner.pair_succeeded(output))

  def test_pair_succeeded_true_on_pairing_successful(self):
    output = """
Attempting to pair with 78:86:2E:AC:8D:03
Pairing successful
	Paired: yes
"""
    self.assertTrue(BluetoothctlRunner.pair_succeeded(output))

  def test_match_scan_output(self):
    runner = BluetoothctlRunner()
    exact, partial, seen = runner._match_scan_output(
      SAMPLE, ["xbox wireless controller"]
    )
    self.assertEqual(exact, "78:86:2E:AC:8D:03")
    self.assertGreaterEqual(seen, 2)
    self.assertTrue(partial is None or partial == exact)

  def test_match_devices_list_line(self):
    """Known pads appear as ``Device MAC Name`` without [NEW]."""
    runner = BluetoothctlRunner()
    listing = "Device 78:86:2E:97:BD:9C Xbox Wireless Controller\n"
    exact, partial, seen = runner._match_scan_output(
      listing, ["xbox wireless controller"]
    )
    self.assertEqual(exact, "78:86:2E:97:BD:9C")
    self.assertEqual(seen, 1)
    self.assertIsNone(partial)

  def test_pairing_adv_requires_manufacturer_or_new_xbox(self):
    mac = "78:86:2E:AC:8D:03"
    rssi_only = f"[CHG] Device {mac} RSSI: -45\n"
    self.assertFalse(BluetoothctlRunner.xbox_pairing_advertisement(rssi_only, mac))
    pairing = (
      f"[CHG] Device {mac} ManufacturerData Key: 0x0006\n"
      f"[CHG] Device {mac} ManufacturerData Value:\n"
      "  03 00 80                                         ...\n"
    )
    self.assertTrue(BluetoothctlRunner.xbox_pairing_advertisement(pairing, mac))
    fresh = f"[NEW] Device {mac} Xbox Wireless Controller\n"
    self.assertTrue(BluetoothctlRunner.xbox_pairing_advertisement(fresh, mac))


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
