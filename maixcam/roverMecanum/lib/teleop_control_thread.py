"""High-rate Xbox → UART drive thread (separate from HUD)."""

import threading

from maix import app, time


class TeleopControlThread:
  """Poll pad + send UART frames on a dedicated thread."""

  def __init__(
    self, xbox, rover, send_drive, send_interval_ms=15, poll_sleep_ms=5, on_tick=None,
  ):
    self._xbox = xbox
    self._rover = rover
    self._send_drive = send_drive
    self._send_interval_ms = max(5, send_interval_ms)
    self._poll_sleep_ms = max(1, poll_sleep_ms)
    self._on_tick = on_tick
    self._stop = threading.Event()
    self._thread = None

  def set_send_interval_ms(self, ms):
    self._send_interval_ms = max(5, ms)

  def set_poll_sleep_ms(self, ms):
    self._poll_sleep_ms = max(1, ms)

  def start(self):
    if self._thread is not None and self._thread.is_alive():
      return
    self._stop.clear()
    self._thread = threading.Thread(target=self._run, daemon=True, name="teleop-ctrl")
    self._thread.start()

  def stop(self):
    self._stop.set()
    if self._thread is not None:
      self._thread.join(timeout=1.0)
      self._thread = None

  def _run(self):
    send_ms = 0
    was_connected = False
    while not self._stop.is_set() and not app.need_exit():
      self._xbox.poll()
      if self._on_tick is not None:
        self._on_tick()
      view = self._xbox.connected_drive()
      now = time.ticks_ms()
      if view.connected and view.drive is not None and now - send_ms >= self._send_interval_ms:
        self._send_drive(view.drive)
        send_ms = now
      elif was_connected and not view.connected:
        try:
          self._rover.send_stop()
        except Exception as stop_error:
          print(f"teleop: send_stop failed: {stop_error}")
      was_connected = view.connected
      # Event.wait releases the GIL; timeout comes from config timing.teleop_poll_sleep_ms.
      self._stop.wait(timeout=self._poll_sleep_ms / 1000.0)
