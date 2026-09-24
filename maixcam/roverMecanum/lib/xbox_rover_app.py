import threading

from maix import app, display, image, time, touchscreen

from lib.ball_follow_controller import BallFollowController
from lib.bluetooth_installer import BluetoothInstaller
from lib.camera_preview_service import CameraPreviewService
from lib.config_store import ConfigStore
from lib.drive_dispatcher import DriveDispatcher
from lib.imu_yaw_service import ImuYawService
from lib.rover_uart_client import RoverUartClient
from lib.teleop_control_thread import TeleopControlThread
from lib.uart_initializer import UartInitializer
from lib.ui_drawer import UiDrawer
from lib.xbox_input_service import XboxInputService


class XboxRoverApp:
  """
  Xbox teleop + camera HUD.

  Threads:
  - teleop-ctrl: evdev poll + UART (background)
  - imu-yaw: Mahony yaw + gyro calib (background)
  - main: touch + HUD draw + display.show (Maix display API is main-thread)
  """

  def __init__(self):
    self._config_store = ConfigStore()
    self._config_store.load()
    self._config_store.log_rover_settings()
    cfg = self._config_store.settings()
    self._timing = cfg.timing
    self._display_interval_ms = cfg.camera.display_interval_ms
    serial = UartInitializer().create()
    self._rover = RoverUartClient(
      serial,
      max_speed=cfg.rover.max_speed,
    )
    print(BluetoothInstaller().install())
    self._xbox = XboxInputService(self._config_store)
    self._ball_follow = BallFollowController(cfg.ball_follow)
    self._imu = ImuYawService(cfg.imu)
    self._imu_settings = cfg.imu
    self._disp = display.Display()
    self._ui = UiDrawer(self._disp.width(), self._disp.height())
    self._ts = touchscreen.TouchScreen()
    self._exit = threading.Event()
    self._touch_action = None
    self._touch_lock = threading.Lock()
    self._touch_ignore_until = 0
    self._touch_was_pressed = False
    self._was_connected = False
    self._was_busy = False
    self._camera = None
    self._manual_resume_pending = False
    self._ball_follow_settings = cfg.ball_follow
    self._shutdown_done = False
    self._config_max_speed = cfg.rover.max_speed
    self._session_max_speed = self._config_max_speed
    self._speed_step = cfg.rover.speed_step
    self._last_speed_change_ms = 0
    self._last_config_tick_ms = 0
    self._rover.set_max_speed(self._session_max_speed)
    self._drive = DriveDispatcher(
      rover=self._rover,
      ball_follow=self._ball_follow,
      imu=self._imu,
      get_frame=self._ball_frame,
    )
    self._control = TeleopControlThread(
      xbox=self._xbox,
      rover=self._rover,
      send_drive=self._send_drive,
      send_interval_ms=cfg.rover.send_interval_ms,
      poll_sleep_ms=cfg.timing.teleop_poll_sleep_ms,
      on_tick=self._control_tick,
    )

  def run(self):
    """Teleop in background; main thread draws the HUD and calls display.show."""
    self._start_camera()
    self._imu.start()
    self._control.start()
    loop_sleep_s = self._timing.main_loop_sleep_ms / 1000.0
    try:
      while not app.need_exit() and not self._exit.is_set():
        self._read_touch()
        self._handle_touch()
        self._on_connection_change()
        self._draw_frame()
        self._exit.wait(timeout=loop_sleep_s)
    finally:
      self.shutdown()

  def _control_tick(self):
    """Throttled config reload + LB/RB speed on the teleop thread."""
    now = time.ticks_ms()
    if now - self._last_config_tick_ms >= self._timing.config_reload_ms:
      self._apply_rover_config()
      self._last_config_tick_ms = now
    if self._xbox.consume_mode_toggle():
      self._toggle_ball_follow()
    if self._xbox.consume_color_toggle():
      self._cycle_ball_color()
    self._handle_speed_bumpers()

  def _apply_rover_config(self):
    cfg = self._config_store.reload_if_changed()
    self._timing = cfg.timing
    self._display_interval_ms = cfg.camera.display_interval_ms
    self._xbox.apply_config(cfg)
    if cfg.ball_follow is not self._ball_follow_settings:
      self._ball_follow.apply_settings(cfg.ball_follow)
      self._ball_follow_settings = cfg.ball_follow
    if cfg.imu is not self._imu_settings:
      self._imu.apply_settings(cfg.imu)
      self._imu_settings = cfg.imu
    rover = cfg.rover
    if rover.max_speed != self._config_max_speed:
      self._config_max_speed = rover.max_speed
      self._session_max_speed = rover.max_speed
    self._speed_step = rover.speed_step
    self._control.set_send_interval_ms(rover.send_interval_ms)
    self._control.set_poll_sleep_ms(cfg.timing.teleop_poll_sleep_ms)
    self._rover.set_max_speed(self._session_max_speed)

  def _toggle_ball_follow(self):
    """Toggle automatic mode from one Xbox View/Select press."""
    if self._imu.snapshot().calibrating:
      print("ball: ignored while gyro calibrating")
      return
    enabled = not self._ball_follow.enabled
    self._ball_follow.set_enabled(enabled)
    self._rover.send_stop()
    self._manual_resume_pending = not enabled
    print(f"ball: {'enabled' if enabled else 'disabled'}")

  def _cycle_ball_color(self):
    """Cycle green/red LAB presets from one Xbox Menu/Start press."""
    color = self._ball_follow.cycle_color()
    if self._ball_follow.enabled:
      self._rover.send_stop()
    print(f"ball: color={color}")

  def _start_gyro_calib(self):
    """Stop motion and queue MaixPy calib_gyro on the IMU thread."""
    snap = self._imu.snapshot()
    if snap.calibrating:
      return
    if snap.status in ("disabled", "no_imu", "off", "stopped"):
      print(f"imu: calib unavailable ({snap.status})")
      return
    if self._ball_follow.enabled:
      self._ball_follow.set_enabled(False)
      self._manual_resume_pending = True
    self._rover.send_stop()
    print("imu: hold still — calibrating gyro bias")
    self._imu.request_calib()

  def _handle_speed_bumpers(self):
    if not self._xbox.connected_drive().connected:
      return
    edges = self._xbox.consume_speed_edges()
    if not edges.lb_pressed and not edges.rb_pressed:
      return
    now = time.ticks_ms()
    if now - self._last_speed_change_ms < self._timing.speed_debounce_ms:
      return
    changed = False
    if edges.lb_pressed:
      self._session_max_speed = max(10, self._session_max_speed - self._speed_step)
      changed = True
    if edges.rb_pressed:
      self._session_max_speed = min(255, self._session_max_speed + self._speed_step)
      changed = True
    if changed:
      self._last_speed_change_ms = now
      self._rover.set_max_speed(self._session_max_speed)
      print(f"speed: {int(self._session_max_speed * 100 / 255)}% ({self._session_max_speed}/255)")

  def shutdown(self):
    if self._shutdown_done:
      return
    self._shutdown_done = True
    self._exit.set()
    self._ball_follow.set_enabled(False)
    self._control.stop()
    self._imu.stop()
    self._xbox.close()
    try:
      self._rover.send_stop()
    except Exception as stop_error:
      print(f"app: send_stop on shutdown failed: {stop_error}")
    if self._camera is not None:
      self._camera.stop()
      self._camera = None

  def _start_camera(self):
    cam = self._config_store.settings().camera
    if not cam.enabled:
      print("camera: disabled (black HUD)")
      print(f"display: {cam.display_fps} fps target")
      return
    self._camera = CameraPreviewService(self._disp, cam)
    self._camera.start()
    if self._camera.error:
      print(f"camera disabled: {self._camera.error}")
      self._camera.stop()
      self._camera = None
    else:
      print(f"display: {cam.display_fps} fps target")

  def _draw_frame(self):
    snap = self._xbox.snapshot()
    ball_snap = self._ball_follow.snapshot()
    imu_snap = self._imu.snapshot()
    if self._camera is not None:
      self._camera.set_paused(bool(snap.busy and not snap.connected))

    frame = None
    if self._camera is not None and not (snap.busy and not snap.connected):
      frame = self._camera.get_frame()
    if frame is None:
      frame = image.Image(self._disp.width(), self._disp.height(), bg=image.COLOR_BLACK)
    else:
      frame = self._drawable_rgb(frame)

    self._ui.draw_overlay(
      frame, snap.connected, snap.busy, snap.state, snap.drive, self._session_max_speed,
      status=snap.status, progress=snap.progress,
      ball_snapshot=ball_snap,
      imu_snapshot=imu_snap,
    )
    self._disp.show(frame)

  @staticmethod
  def _drawable_rgb(frame):
    try:
      fmt = frame.format()
    except Exception as format_error:
      print(f"hud: frame.format failed: {format_error}")
      return frame
    if fmt in (image.Format.FMT_RGB888, image.Format.FMT_BGR888):
      return frame
    try:
      return frame.to_format(image.Format.FMT_RGB888)
    except Exception as convert_error:
      print(f"hud: RGB convert failed: {convert_error}")
      return frame

  def _read_touch(self):
    x, y, pressed = self._ts.read()
    if pressed and not self._touch_was_pressed:
      with self._touch_lock:
        self._touch_action = (x, y)
    self._touch_was_pressed = bool(pressed)

  def _on_connection_change(self):
    snap = self._xbox.snapshot()
    now = time.ticks_ms()
    if snap.connected != self._was_connected or snap.busy != self._was_busy:
      self._touch_ignore_until = now + self._timing.touch_debounce_ms
      with self._touch_lock:
        self._touch_action = None
    self._was_connected = snap.connected
    self._was_busy = snap.busy

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
    snap = self._xbox.snapshot()

    if self._in_rect(x, y, self._ui.back_rect()):
      self._xbox.request_stop()
      self._rover.send_stop()
      self._exit.set()
      app.set_exit_flag(True)
      return

    if self._in_rect(x, y, self._ui.gyro_rect()):
      self._start_gyro_calib()
      return

    if not snap.busy and not snap.connected:
      if self._in_rect(x, y, self._ui.pair_rect()):
        self._xbox.start_pairing()
      elif self._in_rect(x, y, self._ui.connect_rect()):
        self._xbox.start_connect()
      return

    if snap.connected and self._in_rect(x, y, self._ui.disconnect_rect()):
      self._xbox.request_stop()
      self._rover.send_stop()

  def _ball_frame(self):
    if self._camera is not None and self._camera.ready:
      return self._camera.get_frame()
    return None

  def _send_drive(self, drive):
    """UART joystick/preset to micro:bit (protocol unchanged)."""
    self._manual_resume_pending = self._drive.dispatch(
      drive, self._manual_resume_pending,
    )

  def _in_rect(self, x, y, rect):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]
