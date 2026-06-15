import threading
import traceback

from maix import time

from lib.bluetooth_pairing_service import BluetoothPairingService
from lib.config_store import ConfigStore
from lib.controller_mapping_engine import ControllerMappingEngine
from lib.controller_state import ControllerState
from lib.evdev_device_finder import EvdevDeviceFinder
from lib.evdev_reader import EvdevReader


class XboxInputService:
  """Background thread: BlueZ + evdev read + mapping."""

  def __init__(self, config_store):
    self._config_store = config_store
    self._pairing = BluetoothPairingService(config_store)
    self._finder = EvdevDeviceFinder()
    self._mapper = ControllerMappingEngine(config_store.get())
    self._log_drive_mapping()
    self._lock = threading.Lock()
    self.state = ControllerState()
    self.drive = None
    self.status = "Ready"
    self.connected = False
    self.busy = False
    self._stop = threading.Event()
    self._thread = None
    self._reader = None
    self._force_pair = False

  def _log_drive_mapping(self):
    axes = self._config_store.get().get("mapping", {}).get("axes", {})
    print(
      "drive mapping:"
      f" F={axes.get('drive_forward', 'left_y')}"
      f" C={axes.get('drive_strafe', 'trigger_diff')}"
      f" R={axes.get('drive_rotate', 'left_x')}"
    )

  def snapshot(self):
    with self._lock:
      return self.status, self.connected, self.busy, self.state, self.drive

  def start_connect(self):
    with self._lock:
      if self.connected:
        return
      if self.busy:
        return
    self._start_worker(force_pair=False)

  def start_pairing(self):
    with self._lock:
      if self.busy:
        return
    self._start_worker(force_pair=True)

  def _start_worker(self, force_pair):
    if self._thread and self._thread.is_alive():
      return
    self._stop.clear()
    with self._lock:
      self.busy = True
      self.connected = False
      self.drive = None
    self._force_pair = force_pair
    self._set_status("Scan BLE (hold sync)..." if force_pair else "Connecting...")
    self._thread = threading.Thread(target=self._worker, daemon=True)
    self._thread.start()

  def request_stop(self):
    self._stop.set()
    reader = self._reader
    if reader is not None:
      reader.close()

  def _set_status(self, status):
    with self._lock:
      self.status = status

  def _set_connected(self, connected):
    with self._lock:
      self.connected = connected

  def _update_drive(self):
    if self._reader is None:
      return
    with self._lock:
      self.state = self._reader.state
      self.drive = self._mapper.compute(self.state)

  def _worker(self):
    try:
      self._mapper.update_config(self._config_store.get())

      if not self._force_pair:
        with self._lock:
          already = self.connected and self._reader is not None
        if already:
          return
        ev_path = self._finder.find_xbox_event()
        if ev_path:
          print(f"input already present: {ev_path}")
          self._run_evdev_loop(ev_path)
          return

      if self._force_pair:
        self._set_status("Scan BLE (hold sync)...")
        mac, err = self._pairing.scan_for_controller()
        if err:
          self._set_status(err)
          return
        if self._stop.is_set():
          return
        self._set_status("Pairing...")
        output, err = self._pairing.pair_mac(mac)
      else:
        output, err = self._pairing.connect_saved()
      print("--- bluetoothctl ---")
      print(output)
      if err:
        self._set_status(err)
        return
      if self._stop.is_set():
        return

      ev_path = self._wait_for_input()
      if ev_path is None:
        return
      self._run_evdev_loop(ev_path)

    except OSError as exc:
      if exc.errno == 19:
        self._set_status("Controller disconnected")
      else:
        self._set_status(f"Erreur: {exc}")
        print(exc)
        traceback.print_exc()
    except Exception as exc:
      self._set_status(f"Erreur: {exc}")
      print(exc)
      traceback.print_exc()
    finally:
      with self._lock:
        self.connected = False
        self.drive = None
        self.busy = False
        if self.status.startswith("Erreur") or self.status in (
          "Connecting...", "Scan BLE (hold sync)...", "Pairing...",
        ):
          self.status = "Ready"
      if self._reader is not None:
        self._reader.close()
        self._reader = None

  def _wait_for_input(self):
    self._set_status("Waiting Xbox input...")
    deadline = time.ticks_ms() + 15000
    while time.ticks_ms() < deadline and not self._stop.is_set():
      ev_path = self._finder.find_xbox_event()
      if ev_path and self._can_open(ev_path):
        return ev_path
      time.sleep_ms(400)
    self._finder.list_devices()
    self._set_status("Input Xbox absent")
    return None

  def _can_open(self, ev_path):
    try:
      f = open(ev_path, "rb")
      f.close()
      return True
    except OSError:
      return False

  def _run_evdev_loop(self, ev_path):
    self._reader = None
    for attempt in range(20):
      if self._stop.is_set():
        return
      try:
        self._reader = EvdevReader(ev_path, self._config_store.get())
        self._reader.open()
        break
      except OSError as exc:
        if exc.errno != 19:
          raise
        print(f"evdev open retry {attempt + 1}/20: {ev_path}")
        time.sleep_ms(500)
        ev_path = self._finder.find_xbox_event() or ev_path
    else:
      self._set_status("Input open failed")
      return

    self._set_connected(True)
    self._set_status("Connected — drive")
    self._update_drive()
    print(f"input: {ev_path}")

    last_dbg = time.ticks_ms()
    while not self._stop.is_set():
      try:
        if self._reader.wait_and_poll(0.05):
          self._update_drive()
      except OSError as exc:
        if exc.errno == 19:
          self._set_status("Controller disconnected")
          break
        raise

      now = time.ticks_ms()
      if now - last_dbg >= 3000:
        s = self._reader.state
        d = self._mapper.compute(s)
        print(
          f"evdev alive events={self._reader.event_count}"
          f" abs={self._reader._abs_event_count}"
          f" lx={s.left_x} ly={s.left_y} rx={s.right_x} ry={s.right_y}"
          f" lt={s.lt} rt={s.rt}"
          f" drive F={d.axis_y} C={d.axis_x} R={d.axis_rot}"
        )
        last_dbg = now
