"""Background IMU yaw publisher with MaixPy gyro calibration."""

import math
import threading
from types import SimpleNamespace

from maix import ahrs, time
from maix.ext_dev import imu

from lib.app_config.imu_settings import ImuSettings
from lib.imu_snapshot import ImuSnapshot


class ImuYawService:
  """Poll the onboard IMU and publish Mahony yaw for closed-loop turns."""

  def __init__(self, settings: ImuSettings):
    """Create a stopped service; call start() after the app is ready."""
    self._settings = settings
    self._lock = threading.Lock()
    self._stop = threading.Event()
    self._thread = None
    self._sensor = None
    self._filter = None
    self._calib_request = threading.Event()
    self._ready = False
    self._calibrated = False
    self._calibrating = False
    self._yaw_deg = None
    self._gyro_z_dps = None
    self._status = "off"
    self._calib_started_ms = None
    self._calib_duration_ms = 0
    # Software bias from cooperative calib (MaixPy calib_gyro holds the GIL).
    self._bias_x = 0.0
    self._bias_y = 0.0
    self._bias_z = 0.0
    self._use_software_bias = False

  def start(self) -> None:
    """Start the IMU worker, or mark disabled when config turns it off."""
    if not self._settings.enabled:
      with self._lock:
        self._status = "disabled"
      return
    if self._thread is not None:
      return
    self._stop.clear()
    self._thread = threading.Thread(target=self._run, name="imu-yaw", daemon=True)
    self._thread.start()

  def stop(self) -> None:
    """Stop the worker and clear the live yaw snapshot."""
    self._stop.set()
    thread = self._thread
    if thread is not None:
      thread.join(timeout=3.0)
    self._thread = None
    with self._lock:
      self._ready = False
      self._yaw_deg = None
      self._gyro_z_dps = None
      self._calibrating = False
      self._calib_started_ms = None
      self._status = "stopped"

  def request_calib(self) -> None:
    """Queue gyro bias sampling; HUD sees calibrating immediately."""
    if not self._settings.enabled:
      print("imu: calib ignored (disabled)")
      return
    with self._lock:
      if self._calibrating:
        return
      self._calibrating = True
      self._ready = False
      self._status = "calibrating"
      self._calib_duration_ms = self._settings.calib_ms
      self._calib_started_ms = time.ticks_ms()
    self._calib_request.set()

  def apply_settings(self, settings: ImuSettings) -> None:
    """Replace poll/calib tuning after a config reload."""
    self._settings = settings

  def snapshot(self) -> ImuSnapshot:
    """Return a consistent yaw/calibration snapshot for HUD and control."""
    with self._lock:
      progress = 0.0
      if self._calibrating and self._calib_started_ms is not None:
        duration = max(1, self._calib_duration_ms)
        elapsed = time.ticks_ms() - self._calib_started_ms
        progress = max(0.0, min(0.99, elapsed / float(duration)))
      return ImuSnapshot(
        ready=self._ready,
        calibrated=self._calibrated,
        calibrating=self._calibrating,
        yaw_deg=self._yaw_deg,
        gyro_z_dps=self._gyro_z_dps,
        status=self._status,
        calib_progress=progress,
      )

  def _run(self) -> None:
    try:
      self._sensor = imu.IMU(
        "default",
        mode=imu.Mode.DUAL,
        acc_scale=imu.AccScale.ACC_SCALE_2G,
        acc_odr=imu.AccOdr.ACC_ODR_1000,
        gyro_scale=imu.GyroScale.GYRO_SCALE_256DPS,
        gyro_odr=imu.GyroOdr.GYRO_ODR_8000,
      )
    except Exception as imu_error:
      print(f"imu: init failed: {imu_error}")
      with self._lock:
        self._status = "no_imu"
      return

    self._filter = ahrs.MahonyAHRS(
      self._settings.mahony_kp,
      self._settings.mahony_ki,
    )
    try:
      if self._sensor.calib_gyro_exists():
        self._sensor.load_calib_gyro()
        self._use_software_bias = False
        with self._lock:
          self._calibrated = True
          self._status = "ok"
        print("imu: loaded gyro bias")
      else:
        with self._lock:
          self._calibrated = False
          self._status = "need_calib"
        print("imu: no gyro bias - press GYRO (hold still)")
    except Exception as load_error:
      print(f"imu: load calib failed: {load_error}")
      with self._lock:
        self._calibrated = False
        self._status = "need_calib"

    last_s = time.ticks_s()
    while not self._stop.is_set():
      poll_s = max(0.005, self._settings.poll_ms / 1000.0)
      if self._calib_request.is_set():
        self._calib_request.clear()
        self._run_calib()
        last_s = time.ticks_s()
        continue
      try:
        data = self._sensor.read_all(
          calib_gryo=not self._use_software_bias,
          radian=True,
        )
        gyro = data.gyro
        if self._use_software_bias:
          gyro = SimpleNamespace(
            x=float(data.gyro.x) - self._bias_x,
            y=float(data.gyro.y) - self._bias_y,
            z=float(data.gyro.z) - self._bias_z,
          )
        now_s = time.ticks_s()
        dt = now_s - last_s
        last_s = now_s
        if dt <= 0.0 or dt > 1.0:
          dt = poll_s
        angle = self._filter.get_angle(
          data.acc, gyro, data.mag, dt, radian=False,
        )
        with self._lock:
          self._yaw_deg = float(angle.z)
          self._gyro_z_dps = float(math.degrees(gyro.z))
          self._ready = self._calibrated and not self._calibrating
          if self._calibrated and not self._calibrating:
            self._status = "ok"
      except Exception as read_error:
        print(f"imu: read failed: {read_error}")
        with self._lock:
          self._ready = False
          self._status = "error"
      self._stop.wait(timeout=poll_s)

  def _run_calib(self) -> None:
    """
    Sample gyro bias with short waits so the HUD progress bar can animate.

    # ponytail: MaixPy calib_gyro(ms) holds the GIL (~10s UI freeze); we average
    # samples cooperatively instead and keep bias in RAM (+ try official save).
    """
    print("imu: calibrating - do not move")
    duration_ms = max(1000, self._settings.calib_ms)
    with self._lock:
      self._calibrating = True
      self._ready = False
      self._status = "calibrating"
      self._calib_duration_ms = duration_ms
      self._calib_started_ms = time.ticks_ms()
    try:
      sum_x = 0.0
      sum_y = 0.0
      sum_z = 0.0
      count = 0
      start_ms = time.ticks_ms()
      while not self._stop.is_set():
        elapsed = time.ticks_ms() - start_ms
        if elapsed >= duration_ms:
          break
        data = self._sensor.read_all(calib_gryo=False, radian=True)
        sum_x += float(data.gyro.x)
        sum_y += float(data.gyro.y)
        sum_z += float(data.gyro.z)
        count += 1
        self._stop.wait(timeout=0.05)
      if count <= 0:
        raise RuntimeError("no gyro samples")
      self._bias_x = sum_x / count
      self._bias_y = sum_y / count
      self._bias_z = sum_z / count
      self._use_software_bias = True
      # Best-effort persistent save (may freeze HUD briefly).
      try:
        self._sensor.calib_gyro(min(2000, duration_ms))
        self._use_software_bias = False
        print("imu: saved MaixPy gyro bias file")
      except Exception as save_error:
        print(f"imu: bias file save skipped: {save_error}")
      if self._filter is not None:
        self._filter.reset()
      with self._lock:
        self._calibrated = True
        self._calibrating = False
        self._calib_started_ms = None
        self._status = "ok"
      print(f"imu: calib done ({count} samples)")
    except Exception as calib_error:
      print(f"imu: calib failed: {calib_error}")
      with self._lock:
        self._calibrating = False
        self._calib_started_ms = None
        self._status = "calib_failed"
