import errno
import threading
import traceback

from maix import time

from lib.app_config import AppConfig
from lib.bluetooth_pairing_service import BluetoothPairingService
from lib.controller_mapping_engine import ControllerMappingEngine
from lib.controller_state import ControllerState
from lib.evdev_device_finder import EvdevDeviceFinder
from lib.evdev_reader import EvdevReader


class XboxInputService:
  """BlueZ in background thread; evdev polled on teleop thread (MaixPy GIL)."""

  def __init__(self, config_store):
    self._config_store = config_store
    self._cfg = config_store.settings()
    self._pairing = BluetoothPairingService(config_store)
    self._finder = EvdevDeviceFinder()
    self._mapper = ControllerMappingEngine(self._cfg.raw)
    self._log_drive_mapping()
    self._lock = threading.Lock()
    self.state = ControllerState()
    self.drive = None
    self.status = "Ready"
    self.progress = 0.0
    self.connected = False
    self.busy = False
    self._stop = threading.Event()
    self._thread = None
    self._reader = None
    self._force_pair = False
    self._handoff = False
    self._pending_speed_lb = False
    self._pending_speed_rb = False
    self._hid_logged = False
    self._pairing.ensure_agent()

  def apply_config(self, cfg: AppConfig):
    """Refresh cached settings + mapping (called after throttled config reload)."""
    self._cfg = cfg
    self._mapper.update_config(cfg.raw)

  def _log_drive_mapping(self):
    axes = self._cfg.mapping.get("axes", {})
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
    """Return (status, connected, busy, state, drive, progress)."""
    with self._lock:
      state_copy = self.state.copy()
      return self.status, self.connected, self.busy, state_copy, self.drive, self.progress

  def connected_drive(self):
    """Lightweight teleop read — no state copy."""
    with self._lock:
      return self.connected, self.drive

  def poll(self):
    """Drain evdev on teleop thread — no config disk I/O here."""
    with self._lock:
      if not self._handoff or self._reader is None:
        return
      reader = self._reader
    try:
      reader.poll_inputs()
      if reader.event_count and not self._hid_logged:
        self._hid_logged = True
        print(f"input: HID reports flowing ({reader.event_count})")
      live = reader.state.copy()
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
    except OSError as io_error:
      if io_error.errno in (errno.ENODEV, errno.ENOENT):
        self._on_reader_lost("Controller disconnected")
      else:
        raise

  def start_connect(self):
    """Start a background CONNECT to the saved controller MAC."""
    with self._lock:
      if self.connected or self.busy:
        return
    self._start_worker(force_pair=False)

  def start_pairing(self):
    """Start a background PAIR (remove bond + encrypted re-pair)."""
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
      self.progress = 0.05
    self._force_pair = force_pair
    self._set_status(
      "Pairing (hold SYNC)..." if force_pair else "Connecting...",
      0.05,
    )
    self._thread = threading.Thread(target=self._worker, daemon=True)
    self._thread.start()

  def request_stop(self):
    """Drop the live HID session and mark the pad disconnected."""
    self._stop.set()
    self._close_reader()
    with self._lock:
      self.connected = False
      self.drive = None
      self.progress = 0.0
      if self.status == "Connected — drive":
        self.status = "Ready"

  def close(self):
    """Stop evdev and the BlueZ agent (app shutdown)."""
    self.request_stop()
    self._pairing.close()

  def _set_status(self, status, progress=None):
    with self._lock:
      self.status = status
      if progress is not None:
        self.progress = float(progress)

  def _close_reader(self):
    with self._lock:
      reader = self._reader
      self._reader = None
      self._handoff = False
      self._hid_logged = False
    if reader is not None:
      reader.close()

  def _on_reader_lost(self, status):
    self._close_reader()
    with self._lock:
      self.connected = False
      self.drive = None
      self.progress = 0.0
      self.status = status

  def _worker(self):
    handed_off = False
    try:
      self.apply_config(self._config_store.settings())

      if self._force_pair:
        self._set_status("Pairing (hold SYNC)...", 0.1)
        scan = self._pairing.scan_for_controller()
        if not scan.ok():
          self._set_status(scan.error, 0.0)
          return
        if self._stop.is_set():
          return
        self._set_status("Bonding Xbox...", 0.45)
        result = self._pairing.pair_mac(scan.mac)
        print("--- bluetoothctl ---")
        print(result.output)
        if not result.ok():
          self._set_status(result.error, 0.0)
          return
        self._set_status("Opening input...", 0.8)
        handed_off = self._claim_hid()
        return

      # CONNECT never disconnects: a failed reconnect must not power off the pad.
      with self._lock:
        already = self._handoff and self._reader is not None
      if already:
        return
      self._set_status("Connecting...", 0.2)
      ev_path = self._finder.find_xbox_event()
      if ev_path and self._can_open(ev_path):
        print(f"input already present: {ev_path}")
        handed_off = self._open_evdev(ev_path)
        if handed_off:
          return
        print("input: event node unusable — trying BlueZ connect")

      self._set_status("Waiting Xbox (agent on)...", 0.4)
      ev_path = self._wait_for_input(timeout_ms=self._cfg.timing.hid_quick_wait_ms)
      if ev_path:
        handed_off = self._open_evdev(ev_path)
        if handed_off:
          return

      self._set_status("BlueZ connect...", 0.6)
      result = self._pairing.connect_saved()
      print("--- bluetoothctl ---")
      print(result.output)
      self._set_status("Opening input...", 0.85)
      handed_off = self._claim_hid()
      if handed_off:
        return
      if not result.ok():
        self._set_status(result.error, 0.0)

    except OSError as io_error:
      if io_error.errno in (errno.ENODEV, errno.ENOENT):
        self._set_status("Controller disconnected", 0.0)
      else:
        self._set_status(f"Erreur: {io_error}", 0.0)
        print(io_error)
        traceback.print_exc()
    except Exception as runtime_error:
      self._set_status(f"Erreur: {runtime_error}", 0.0)
      print(runtime_error)
      traceback.print_exc()
    finally:
      with self._lock:
        self.busy = False
        if not handed_off:
          self.connected = False
          self.drive = None
          self.progress = 0.0
          if self.status.startswith("Erreur") or self.status in (
            "Connecting...",
            "Pairing (hold SYNC)...",
            "Pairing...",
            "Waiting Xbox (agent on)...",
            "Waiting Xbox input...",
            "Bonding Xbox...",
            "Opening input...",
            "BlueZ connect...",
          ):
            self.status = "Ready"
      if not handed_off:
        self._close_reader()

  def _claim_hid(self):
    """Wait for and open the Xbox evdev node without disconnecting it."""
    if self._stop.is_set():
      return False
    ev_path = self._wait_for_input(timeout_ms=self._cfg.timing.hid_wait_ms)
    if ev_path and self._open_evdev(ev_path):
      return True
    self._set_status("Xbox input unavailable", 0.0)
    return False

  def _wait_for_input(self, timeout_ms):
    """Wait until /dev/input/event* for the Xbox can be opened."""
    self._set_status("Waiting Xbox input...")
    deadline = time.ticks_ms() + timeout_ms
    retry_s = self._cfg.timing.evdev_retry_ms / 1000.0
    while time.ticks_ms() < deadline and not self._stop.is_set():
      ev_path = self._finder.find_xbox_event()
      if ev_path and self._can_open(ev_path):
        return ev_path
      self._stop.wait(timeout=retry_s)
    self._finder.list_devices()
    self._set_status("Input Xbox absent", 0.0)
    return None

  def _can_open(self, ev_path):
    try:
      handle = open(ev_path, "rb")
      handle.close()
      return True
    except OSError:
      return False

  def _open_evdev(self, ev_path):
    reader = None
    attempts = self._cfg.timing.evdev_open_attempts
    retry_s = self._cfg.timing.evdev_retry_ms / 1000.0
    for attempt in range(attempts):
      if self._stop.is_set():
        return False
      if not self._can_open(ev_path):
        print(f"evdev open retry {attempt + 1}/{attempts}: {ev_path} not ready")
        self._stop.wait(timeout=retry_s)
        ev_path = self._finder.find_xbox_event() or ev_path
        continue
      try:
        reader = EvdevReader(ev_path, self._cfg.raw)
        reader.open()
        break
      except OSError as io_error:
        if io_error.errno not in (errno.ENODEV, errno.ENOENT):
          raise
        print(f"evdev open retry {attempt + 1}/{attempts}: {ev_path} ({io_error})")
        self._stop.wait(timeout=retry_s)
        ev_path = self._finder.find_xbox_event() or ev_path
    else:
      self._set_status("Input open failed", 0.0)
      return False

    with self._lock:
      self._reader = reader
      self._handoff = True
      self.connected = True
      self.status = "Connected — drive"
      self.progress = 1.0
    reader.poll_inputs()
    live = reader.state.copy()
    drive = self._mapper.compute(live)
    with self._lock:
      self.state = live
      self.drive = drive
    print(f"input: {ev_path} (teleop-thread poll)")
    return True
