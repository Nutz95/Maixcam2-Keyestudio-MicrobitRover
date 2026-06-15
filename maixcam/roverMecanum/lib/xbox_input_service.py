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
  """BlueZ in background thread; evdev polled on main loop (MaixPy GIL)."""

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
    self._handoff = False
    self._pending_speed_lb = False
    self._pending_speed_rb = False

  def _log_drive_mapping(self):
    axes = self._config_store.get().get("mapping", {}).get("axes", {})
    print(
      "drive mapping:"
      f" forward={axes.get('drive_forward', 'left_y')}"
      f" strafe={axes.get('drive_strafe', 'trigger_diff')}"
      f" spin={axes.get('drive_spin', axes.get('drive_rotate', 'right_x'))}"
      f" pivot={axes.get('drive_pivot', 'left_x')}"
    )

  def consume_speed_edges(self):
    """LB/RB press edges for session max_speed (one shot per physical press)."""
    with self._lock:
      lb = self._pending_speed_lb
      rb = self._pending_speed_rb
      self._pending_speed_lb = False
      self._pending_speed_rb = False
    return lb, rb

  def snapshot(self):
    with self._lock:
      state_copy = self.state.copy() if hasattr(self.state, "copy") else self.state
      return self.status, self.connected, self.busy, state_copy, self.drive

  def poll(self):
    """Drain evdev on main thread — call every control-loop iteration."""
    self._config_store.reload_if_changed()
    with self._lock:
      if not self._handoff or self._reader is None:
        return
      reader = self._reader
    try:
      reader.poll_inputs()
      live = reader.state.copy()
      self._mapper.update_config(self._config_store.get())
      drive = self._mapper.compute(live)
      speed_lb = reader.state.take_edge("btn_lb")
      speed_rb = reader.state.take_edge("btn_rb")
      reader.state.pressed_edge.clear()
      with self._lock:
        self.state = live
        self.drive = drive
        if speed_lb:
          self._pending_speed_lb = True
        if speed_rb:
          self._pending_speed_rb = True
    except OSError as exc:
      if exc.errno == 19:
        self._on_reader_lost("Controller disconnected")
      else:
        raise

  def start_connect(self):
    with self._lock:
      if self.connected or self.busy:
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
    self._handoff = False
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
    self._close_reader()
    with self._lock:
      self.connected = False
      self.drive = None
      if self.status == "Connected — drive":
        self.status = "Ready"

  def _set_status(self, status):
    with self._lock:
      self.status = status

  def _set_connected(self, connected):
    with self._lock:
      self.connected = connected

  def _close_reader(self):
    with self._lock:
      reader = self._reader
      self._reader = None
      self._handoff = False
    if reader is not None:
      reader.close()

  def _on_reader_lost(self, status):
    self._close_reader()
    with self._lock:
      self.connected = False
      self.drive = None
      self.status = status

  def _worker(self):
    handed_off = False
    try:
      self._mapper.update_config(self._config_store.get())

      if not self._force_pair:
        with self._lock:
          already = self._handoff and self._reader is not None
        if already:
          return
        ev_path = self._finder.find_xbox_event()
        if ev_path:
          print(f"input already present: {ev_path}")
          handed_off = self._open_evdev(ev_path)
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
      handed_off = self._open_evdev(ev_path)

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
        self.busy = False
        if not handed_off:
          self.connected = False
          self.drive = None
          if self.status.startswith("Erreur") or self.status in (
            "Connecting...", "Scan BLE (hold sync)...", "Pairing...",
          ):
            self.status = "Ready"
      if not handed_off:
        self._close_reader()

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

  def _open_evdev(self, ev_path):
    reader = None
    for attempt in range(20):
      if self._stop.is_set():
        return False
      try:
        reader = EvdevReader(ev_path, self._config_store.get())
        reader.open()
        break
      except OSError as exc:
        if exc.errno != 19:
          raise
        print(f"evdev open retry {attempt + 1}/20: {ev_path}")
        time.sleep_ms(500)
        ev_path = self._finder.find_xbox_event() or ev_path
    else:
      self._set_status("Input open failed")
      return False

    with self._lock:
      self._reader = reader
      self._handoff = True
      self.connected = True
      self.status = "Connected — drive"
    reader.poll_inputs()
    live = reader.state.copy()
    drive = self._mapper.compute(live)
    with self._lock:
      self.state = live
      self.drive = drive
    print(f"input: {ev_path} (main-loop poll)")
    return True
