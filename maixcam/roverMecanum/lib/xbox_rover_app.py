import threading

from maix import app, display, time, touchscreen

from lib.bluetooth_installer import BluetoothInstaller
from lib.config_store import ConfigStore
from lib.rover_uart_client import RoverUartClient
from lib.uart_initializer import UartInitializer
from lib.ui_drawer import UiDrawer
from lib.xbox_input_service import XboxInputService


class XboxRoverApp:
  """UI thread + main UART loop."""

  TOUCH_DEBOUNCE_MS = 900

  def __init__(self):
    self._config_store = ConfigStore()
    self._config = self._config_store.load()
    rover_cfg = self._config.get("rover", {})
    serial = UartInitializer().create()
    self._rover = RoverUartClient(
      serial,
      max_speed=rover_cfg.get("max_speed", 255),
      wait_ack=rover_cfg.get("wait_ack", False),
    )
    self._xbox = XboxInputService(self._config_store)
    self._disp = display.Display()
    self._ui = UiDrawer(self._disp.width(), self._disp.height())
    self._ts = touchscreen.TouchScreen()
    self._send_interval = rover_cfg.get("send_interval_ms", 50)
    self._exit = threading.Event()
    self._touch_action = None
    self._touch_lock = threading.Lock()
    self._touch_ignore_until = 0
    self._was_connected = False
    self._was_busy = False

  def run(self):
    BluetoothInstaller().install()
    ui_thread = threading.Thread(target=self._ui_loop, daemon=True)
    ui_thread.start()

    send_ms = 0
    was_connected = False

    while not app.need_exit() and not self._exit.is_set():
      self._handle_touch()
      self._on_connection_change()

      status, connected, _busy, _state, drive = self._xbox.snapshot()
      now = time.ticks_ms()
      if connected and drive is not None and now - send_ms >= self._send_interval:
        self._send_drive(drive)
        send_ms = now
      elif was_connected and not connected:
        self._rover.send_stop()

      was_connected = connected
      time.sleep_ms(10)

    self._exit.set()
    self._xbox.request_stop()
    self._rover.send_stop()
    ui_thread.join(timeout=1.0)

  def _ui_loop(self):
    while not app.need_exit() and not self._exit.is_set():
      status, connected, busy, state, drive = self._xbox.snapshot()
      img = self._ui.draw_frame(
        status, connected, busy, state, drive,
        self._rover.max_speed, self._rover.last_ack,
      )
      self._disp.show(img)

      x, y, pressed = self._ts.read()
      if pressed:
        with self._touch_lock:
          self._touch_action = (x, y)
      time.sleep_ms(25)

  def _on_connection_change(self):
    status, connected, busy, _s, _d = self._xbox.snapshot()
    now = time.ticks_ms()
    if connected != self._was_connected or busy != self._was_busy:
      self._touch_ignore_until = now + self.TOUCH_DEBOUNCE_MS
      with self._touch_lock:
        self._touch_action = None
    self._was_connected = connected
    self._was_busy = busy

  def _handle_touch(self):
    if time.ticks_ms() < self._touch_ignore_until:
      return

    action = None
    with self._touch_lock:
      if self._touch_action is not None:
        action = self._touch_action
        self._touch_action = None
    if action is None:
      return

    x, y = action
    _status, connected, busy, _state, _drive = self._xbox.snapshot()

    if self._in_rect(x, y, self._ui.back_rect()):
      self._xbox.request_stop()
      self._rover.send_stop()
      self._exit.set()
      app.set_exit_flag(True)
      return

    if not busy and not connected:
      if self._in_rect(x, y, self._ui.pair_rect()):
        self._xbox.start_pairing()
      elif self._in_rect(x, y, self._ui.connect_rect()):
        self._xbox.start_connect()
      return

    if connected and self._in_rect(x, y, self._ui.disconnect_rect()):
      self._xbox.request_stop()
      self._rover.send_stop()

  def _send_drive(self, drive):
    if drive.preset_cmd is not None:
      self._rover.send_preset(drive.preset_cmd)
      return
    self._rover.send_joystick(drive.axis_x, drive.axis_y, drive.axis_rot)

  def _in_rect(self, x, y, rect):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
