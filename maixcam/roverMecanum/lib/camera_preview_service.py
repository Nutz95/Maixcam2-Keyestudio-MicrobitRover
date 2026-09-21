"""Camera capture thread paced for MaixCAM multi-core + GIL friendliness."""

import gc
import threading

from maix import app, camera, image, time

from lib.app_config import CameraSettings

_FORMATS = {
  "rgb888": image.Format.FMT_RGB888,
  "bgr888": image.Format.FMT_BGR888,
  "yuv420": image.Format.FMT_YVU420SP,
  "nv21": image.Format.FMT_YVU420SP,
  "yuv420sp": image.Format.FMT_YVU420SP,
}


def _resolve_format(name):
  """
  Resolve camera pixel format.

  HUD ``draw_*`` on MaixCAM2 needs RGB/BGR. YUV cannot be converted with
  ``to_format`` either, so map any YUV request to RGB888.
  """
  key = (name or "rgb888").strip().lower()
  if key in ("yuv420", "nv21", "yuv420sp", "yvu420sp"):
    print(f"camera: {key} cannot HUD-draw on MaixCAM2 → rgb888")
    key = "rgb888"
  if key in _FORMATS:
    return _FORMATS[key]
  return image.Format.FMT_RGB888


class CameraPreviewService:
  """Camera capture on a worker thread; main thread only samples latest frame."""

  def __init__(self, disp, settings: CameraSettings):
    self._disp = disp
    self._settings = settings
    # 0 = match display (avoids a second resize channel + keeps FPS up).
    self._capture_w = settings.width if settings.width > 0 else int(disp.width())
    self._capture_h = settings.height if settings.height > 0 else int(disp.height())
    self._fps = settings.fps
    self._pixel_format = settings.format
    self._lock = threading.Lock()
    self._latest = None
    self._cam = None
    self._preview = None
    self._direct_read = False
    self._thread = None
    self._stop = threading.Event()
    self._paused = threading.Event()
    self._ready = threading.Event()
    self._error = ""

  @property
  def error(self):
    return self._error

  @property
  def ready(self):
    return self._ready.is_set()

  def start(self):
    if self._thread and self._thread.is_alive():
      return
    self._stop.clear()
    self._paused.clear()
    self._ready.clear()
    self._thread = threading.Thread(target=self._worker, daemon=True, name="cam-preview")
    self._thread.start()
    deadline = time.ticks_ms() + self._settings.ready_timeout_ms
    poll_s = self._settings.ready_poll_ms / 1000.0
    while not self._ready.is_set() and time.ticks_ms() < deadline:
      if self._error:
        break
      # Event wait releases the GIL better than a busy sleep_ms loop.
      self._ready.wait(timeout=poll_s)

  def stop(self):
    if self._stop.is_set() and self._cam is None:
      return
    self._stop.set()
    self._paused.clear()
    if self._thread and self._thread.is_alive():
      self._thread.join(timeout=self._settings.stop_join_ms / 1000.0)
    self._release_hw()
    self._thread = None

  def set_paused(self, paused):
    """Pause capture (frees CPU while pairing UI is busy if needed)."""
    if paused:
      self._paused.set()
    else:
      self._paused.clear()

  def get_frame(self):
    with self._lock:
      return self._latest

  def _open_camera(self):
    fmt = _resolve_format(self._pixel_format)
    label = "rgb888" if fmt == image.Format.FMT_RGB888 else (
      "bgr888" if fmt == image.Format.FMT_BGR888 else self._pixel_format
    )
    cam = camera.Camera(self._capture_w, self._capture_h, fmt, fps=self._fps)
    print(f"camera: {self._capture_w}x{self._capture_h} {label} @{self._fps}fps")
    return cam

  def _worker(self):
    pause_s = self._settings.paused_poll_ms / 1000.0
    yield_s = self._settings.frame_yield_ms / 1000.0
    empty_s = self._settings.no_frame_sleep_ms / 1000.0
    try:
      self._direct_read = (
        self._capture_w == self._disp.width() and self._capture_h == self._disp.height()
      )
      self._cam = self._open_camera()
      if not self._direct_read:
        self._preview = self._cam.add_channel(self._disp.width(), self._disp.height())
        print(f"camera: preview channel {self._disp.width()}x{self._disp.height()}")
      else:
        print("camera: direct read (display-sized, no resize)")

      self._ready.set()
      while not self._stop.is_set() and not app.need_exit():
        if self._paused.is_set():
          self._stop.wait(timeout=pause_s)
          continue
        frame = None
        try:
          if self._direct_read:
            frame = self._cam.read()
          else:
            frame = self._preview.read()
        except Exception as camera_error:
          self._error = str(camera_error)
        if frame is not None:
          with self._lock:
            self._latest = frame
          # Yield GIL; camera.read() already paces when a new frame is ready.
          self._stop.wait(timeout=yield_s)
        else:
          self._stop.wait(timeout=empty_s)
    except Exception as camera_error:
      self._error = str(camera_error)
      print(f"camera error: {camera_error}")
    finally:
      self._release_hw()

  def _release_hw(self):
    self._ready.clear()
    with self._lock:
      self._latest = None
    try:
      if self._preview is not None:
        del self._preview
    except Exception as release_error:
      print(f"camera: preview release failed: {release_error}")
    self._preview = None
    try:
      if self._cam is not None:
        del self._cam
    except Exception as release_error:
      print(f"camera: camera release failed: {release_error}")
    self._cam = None
    gc.collect()
    print("camera: released")
