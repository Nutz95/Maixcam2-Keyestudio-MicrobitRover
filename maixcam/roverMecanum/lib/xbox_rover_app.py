import threading

from maix import app, display, image, time, touchscreen

from lib.bluetooth_installer import BluetoothInstaller
from lib.camera_preview_service import CameraPreviewService
from lib.config_store import ConfigStore
from lib.rover_uart_client import RoverUartClient
from lib.uart_initializer import UartInitializer
from lib.ui_drawer import UiDrawer
from lib.xbox_input_service import XboxInputService


class XboxRoverApp:
  """Control loop (UART + touch) and separate display thread for camera HUD."""

  TOUCH_DEBOUNCE_MS = 900

  def __init__(self):
    self._config_store = ConfigStore()
    self._config = self._config_store.load()
    rover_cfg = self._config.get("rover", {})
    cam_cfg = self._config.get("camera", {})
    display_fps = max(1, min(30, int(cam_cfg.get("display_fps", 15))))
    self._display_interval_ms = max(1, int(1000 / display_fps))
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
    self._send_interval = rover_cfg.get("send_interval_ms", 30)
    self._exit = threading.Event()
    self._touch_action = None
    self._touch_lock = threading.Lock()
    self._touch_ignore_until = 0
    self._was_connected = False
    self._was_busy = False
    self._camera = None
    self._shutdown_done = False

  def run(self):
    BluetoothInstaller().install()
    self._start_camera()

    display_thread = threading.Thread(target=self._display_loop, daemon=True)
    display_thread.start()

    send_ms = 0
    was_connected = False

    try:
      while not app.need_exit() and not self._exit.is_set():
        self._xbox.poll()
        self._read_touch()
        self._handle_touch()
        self._on_connection_change()

        _status, connected, _busy, _state, drive = self._xbox.snapshot()
        now = time.ticks_ms()
        if connected and drive is not None and now - send_ms >= self._send_interval:
          self._send_drive(drive)
          send_ms = now
        elif was_connected and not connected:
          self._rover.send_stop()

        was_connected = connected
        time.sleep_ms(1)
    finally:
      self.shutdown()
      display_thread.join(timeout=1.0)

  def _display_loop(self):
    last_draw = 0
    while not app.need_exit() and not self._exit.is_set():
      now = time.ticks_ms()
      if now - last_draw >= self._display_interval_ms:
        self._draw_frame()
        last_draw = now
      time.sleep_ms(4)

  def shutdown(self):
    if self._shutdown_done:
      return
    self._shutdown_done = True
    self._exit.set()
    self._xbox.request_stop()
    try:
      self._rover.send_stop()
    except Exception:
      pass
    if self._camera is not None:
      self._camera.stop()
      self._camera = None

  def _start_camera(self):
    cam_cfg = self._config.get("camera", {})
    if not cam_cfg.get("enabled", True):
      return
    width = int(cam_cfg.get("width", 1280))
    height = int(cam_cfg.get("height", 720))
    fps = int(cam_cfg.get("fps", 60))
    pixel_format = cam_cfg.get("format", "rgb888")
    self._camera = CameraPreviewService(
      self._disp, width, height, fps=fps, pixel_format=pixel_format,
    )
    self._camera.start()
    if self._camera.error:
      print(f"camera disabled: {self._camera.error}")
      self._camera.stop()
      self._camera = None
    else:
      print(f"display: {int(1000 / self._display_interval_ms)} fps target")

  def _draw_frame(self):
    frame = None
    if self._camera is not None:
      frame = self._camera.get_frame()
    if frame is None:
      frame = image.Image(self._disp.width(), self._disp.height(), bg=image.COLOR_BLACK)

    _status, connected, busy, state, drive = self._xbox.snapshot()
    self._ui.draw_overlay(frame, connected, busy, state, drive)
    self._disp.show(frame)

  def _read_touch(self):
    x, y, pressed = self._ts.read()
    if pressed:
      with self._touch_lock:
        self._touch_action = (x, y)

  def _on_connection_change(self):
    _status, connected, busy, _s, _d = self._xbox.snapshot()
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
    self._rover.send_joystick(
      drive.axis_strafe,
      drive.axis_forward,
      drive.axis_spin,
      drive.axis_pivot,
    )

  def _in_rect(self, x, y, rect):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
