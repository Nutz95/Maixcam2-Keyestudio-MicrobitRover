from lib.ble_device_scanner import BleDeviceScanner
from lib.bluetoothctl_runner import BluetoothctlRunner
from lib.config_store import ConfigStore


class BluetoothPairingService:
  """Pairing by controller name; MAC stored in config.json."""

  _OK_MARKERS = (
    "Connection successful",
    "Connected: yes",
    "Pairing successful",
    "Already paired",
    "Already Exists",
  )

  def __init__(self, config_store):
    self._config_store = config_store
    self._scanner = BleDeviceScanner()
    self._btctl = BluetoothctlRunner()

  def connect_saved(self):
    """Reconnect to the MAC already stored in config."""
    mac = self._saved_mac()
    if not mac:
      return "", "No saved controller — use PAIR first"
    return self._connect_mac(mac)

  def scan_for_controller(self):
    """BLE scan by name; saves MAC when found."""
    self._config_store.clear_controller_mac()
    config = self._config_store.get()
    name = config.get("controller_name", "Xbox Wireless Controller")
    print(f"pairing: BLE scan for '{name}'...")
    mac = self._scanner.find_by_name_sync(name)
    if not mac:
      return "", "Controller not found — hold Xbox sync button"
    self._config_store.set_controller_mac(mac)
    print(f"pairing: MAC saved {mac}")
    return mac, ""

  def pair_mac(self, mac):
    """Pair, trust and connect (BlueZ classic scan + pair)."""
    output = self._btctl.pair(mac)
    if self._is_success(output):
      return output, ""
    if "not available" in output.lower():
      return output, "Controller not seen by BlueZ — hold Xbox sync button, retry PAIR"
    return output, "Pairing failed"

  def discover_and_pair(self):
    mac, err = self.scan_for_controller()
    if err:
      return "", err
    return self.pair_mac(mac)

  def _saved_mac(self):
    config = self._config_store.get()
    return (config.get("controller_mac") or "").strip().upper()

  def _connect_mac(self, mac):
    output = self._btctl.quick_connect(mac)
    if self._is_success(output):
      return output, ""
    if "not available" not in output.lower():
      if "Paired: no" in output:
        print("pairing: pair required...")
        output += self._btctl.pair(mac)
        if self._is_success(output):
          return output, ""
    print("connect: trying scan...")
    output = self._btctl.connect(mac)
    if "not available" in output.lower():
      return output, "Controller unavailable — use PAIR"
    if "Paired: no" in output:
      print("pairing: pair required...")
      output += self._btctl.pair(mac)
    if self._is_success(output):
      return output, ""
    return output, "BlueZ connection failed"

  def _is_success(self, output):
    return any(marker in output for marker in self._OK_MARKERS)
