import os
import select
import struct
from typing import Union

from lib.abs_range import AbsRange
from lib.controller_state import ControllerState
from lib.evdev_axis_mapper import EvdevAxisMapper
from lib.evdev_event_format import EvdevEventFormat
from lib.evdev_trigger_mapper import EvdevTriggerMapper
from lib.evdev_constants import (
  ABS_HAT0X, ABS_HAT0Y, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT, BTN_DPAD_UP,
  BTN_NAME_BY_CODE, BTN_THUMBL, BTN_THUMBR, BTN_TL, BTN_TL2, BTN_TR, BTN_TR2,
  EV_ABS, EV_KEY, EV_SYN, SYN_REPORT, default_abs_range,
)
from lib.evdev_ioctl import read_absinfo
from lib.evdev_sysfs_reader import EvdevSysfsReader
from lib.evdev_xbox_layout import XboxAxisLayout

_VALID_EV_TYPES = {0, 1, 2, 3, 4, 0x11, 0x14, 0x15, 0x17}


class EvdevReader:
  """Read Xbox evdev events (teleop thread only)."""

  def __init__(self, event_path, evdev_settings=None, drain_max_events: int = 24):
    self.event_path = event_path
    self.state = ControllerState()
    self._sysfs = EvdevSysfsReader()
    self._layout = XboxAxisLayout.detect(self._sysfs, event_path, evdev_settings)
    event_format = self._detect_event_size(event_path)
    self._ev_struct = event_format.event_struct
    self._ev_size = event_format.size
    self._mappers = {}
    self._file = None
    self.event_count = 0
    self.kernel_state_available = False
    self._drain_max = drain_max_events
    self._axis_codes = set(self._layout.stick_and_trigger_codes())
    self._lt_btn = 0
    self._rt_btn = 0
    self._dpad_x = 0
    self._dpad_y = 0
    self._dpad_btn_x = 0
    self._dpad_btn_y = 0

  def open(self) -> None:
    """Open evdev unbuffered/non-blocking. Buffered ``open()`` blocks on 8K reads."""
    fd = os.open(self.event_path, os.O_RDONLY | os.O_NONBLOCK)
    self._file = os.fdopen(fd, "rb", buffering=0)
    self._init_mappers()

  def _init_mappers(self) -> None:
    """Create axis mappers from EVIOCGABS (source of truth for sticks/triggers)."""
    layout = self._layout
    trigger_codes = {layout.lt, layout.rt}
    for code in layout.stick_and_trigger_codes():
      prefer_trigger = code in trigger_codes
      info = read_absinfo(self._file, code)
      if info is not None:
        self.kernel_state_available = True
        self._ensure_mapper_with_range(
          code, info.value, info.minimum, info.maximum, info.flat, prefer_trigger,
        )
        continue
      axis_range = self._axis_range(code, prefer_trigger)
      raw = axis_range.minimum if prefer_trigger else (
        (axis_range.minimum + axis_range.maximum) // 2
      )
      self._ensure_mapper_with_range(
        code, raw, axis_range.minimum, axis_range.maximum, axis_range.flat, prefer_trigger,
      )

  def close(self) -> None:
    if self._file is not None:
      try:
        self._file.close()
      except OSError as io_error:
        print(f"evdev: close failed: {io_error}")
      self._file = None

  def drain_available(self) -> int:
    """Read pending evdev events (non-blocking, capped)."""
    return self._drain_events()

  def poll_inputs(self) -> None:
    """Buttons/hats from event drain; sticks/triggers from EVIOCGABS."""
    if self._file is None:
      return
    self._drain_events()
    self.sync_axes_from_kernel()

  def sync_axes_from_kernel(self) -> None:
    """Force stick/trigger state from kernel (ioctl, then sysfs fallback)."""
    layout = self._layout
    trigger_codes = {layout.lt, layout.rt}
    for code in layout.stick_and_trigger_codes():
      info = read_absinfo(self._file, code)
      if info is not None:
        self.kernel_state_available = True
        self._ensure_mapper_with_range(
          code, info.value, info.minimum, info.maximum, info.flat, code in trigger_codes,
        )
        continue
      if self.kernel_state_available:
        continue
      val = self._sysfs.read_abs_value(self.event_path, code)
      if val is not None:
        self.kernel_state_available = True
        self._apply_axis_value(code, val)
    self._sync_axes()

  def _ensure_mapper_with_range(
    self, code, raw, min_v, max_v, flat, prefer_trigger,
  ) -> None:
    """Create or refresh a mapper when kernel absinfo arrives."""
    if prefer_trigger and max_v - min_v > 1024:
      prefer_trigger = False
    mapper = self._mappers.get(code)
    needs_rebuild = (
      mapper is None
      or mapper.min_v != min_v
      or mapper.max_v != max_v
      or mapper.flat != flat
      or isinstance(mapper, EvdevTriggerMapper) != prefer_trigger
    )
    if needs_rebuild:
      mapper = (
        EvdevTriggerMapper(min_v, max_v, flat)
        if prefer_trigger
        else EvdevAxisMapper(min_v, max_v, flat)
      )
      self._mappers[code] = mapper
    mapper.set_raw(raw)

  def _drain_events(self) -> int:
    # Cap ABS flood: a moving stick streams events forever. Emptying the queue
    # without a limit holds the GIL and the HUD falls seconds behind the motors.
    # Limit comes from config timing.evdev_drain_max_events (default 24 ≈ a few
    # full stick reports; EVIOCGABS then supplies the live axis truth).
    if self._file is None:
      return 0
    count = 0
    while count < self._drain_max and self._file is not None:
      ready, _, _ = select.select([self._file], [], [], 0)
      if not ready:
        break
      try:
        data = os.read(self._file.fileno(), self._ev_size)
      except BlockingIOError:
        break
      except OSError as read_error:
        if read_error.errno in (11, 19):  # EAGAIN / ENODEV
          if read_error.errno == 19:
            raise
          break
        raise
      if not data or len(data) < self._ev_size:
        break
      self._process_event(data)
      count += 1
    return count

  def _process_event(self, data) -> None:
    _sec, _usec, ev_type, code, value = self._ev_struct.unpack(data)
    self.event_count += 1
    if ev_type == EV_ABS:
      self._feed_abs(code, value)
    elif ev_type == EV_KEY:
      self._feed_key(code, value)
    elif ev_type == EV_SYN and code == SYN_REPORT:
      pass

  def _axis_range(self, code, prefer_trigger=False) -> AbsRange:
    info = self._sysfs.read_absinfo_real(self.event_path, code)
    if info is not None:
      return info
    return default_abs_range(code, prefer_trigger=prefer_trigger)

  def _create_mapper(
    self, code, prefer_trigger,
  ) -> Union[EvdevAxisMapper, EvdevTriggerMapper]:
    axis_range = self._axis_range(code, prefer_trigger)
    if prefer_trigger and axis_range.span > 1024:
      prefer_trigger = False
    if prefer_trigger:
      return EvdevTriggerMapper(axis_range.minimum, axis_range.maximum, axis_range.flat)
    return EvdevAxisMapper(axis_range.minimum, axis_range.maximum, axis_range.flat)

  def _apply_axis_value(self, code, value) -> None:
    """Update an existing stick/trigger mapper (created at open from kernel)."""
    mapper = self._mappers.get(code)
    if mapper is None:
      trigger_codes = {self._layout.lt, self._layout.rt}
      mapper = self._create_mapper(code, code in trigger_codes)
      self._mappers[code] = mapper
    mapper.set_raw(value)

  def _feed_abs(self, code, value) -> None:
    if code in (ABS_HAT0X, 6):
      self._dpad_x = self._hat_value(value)
      return
    if code in (ABS_HAT0Y, 7):
      self._dpad_y = self._hat_value(value)
      return
    # Sticks/triggers: EVIOCGABS is the truth when kernel absinfo works.
    if self.kernel_state_available and code in self._axis_codes:
      return
    self._apply_axis_value(code, value)

  @staticmethod
  def _hat_value(value) -> int:
    if value > 0:
      return 1
    if value < 0:
      return -1
    return 0

  def _feed_key(self, code, value) -> None:
    pressed = value != 0
    if code in (BTN_TL, BTN_THUMBL):
      self.state.set_button("btn_lb", pressed)
      return
    if code in (BTN_TR, BTN_THUMBR):
      self.state.set_button("btn_rb", pressed)
      return
    if code == BTN_TL2:
      self._lt_btn = 32767 if pressed else 0
      return
    if code == BTN_TR2:
      self._rt_btn = 32767 if pressed else 0
      return
    if code == BTN_DPAD_LEFT:
      self._dpad_btn_x = -1 if value else 0
      return
    if code == BTN_DPAD_RIGHT:
      self._dpad_btn_x = 1 if value else 0
      return
    if code == BTN_DPAD_UP:
      self._dpad_btn_y = -1 if value else 0
      return
    if code == BTN_DPAD_DOWN:
      self._dpad_btn_y = 1 if value else 0
      return
    name = BTN_NAME_BY_CODE.get(code)
    if name is None:
      return
    self.state.set_button(name, value != 0)

  def _sync_axes(self) -> None:
    layout = self._layout
    self.state.left_x = self._read_axis(layout.left_x)
    self.state.left_y = self._read_axis(layout.left_y)
    self.state.right_x = self._read_axis(layout.right_x)
    self.state.right_y = self._read_axis(layout.right_y)
    self.state.lt = max(self._read_axis(layout.lt), self._lt_btn)
    self.state.rt = max(self._read_axis(layout.rt), self._rt_btn)
    hat_x = self._dpad_x if self._dpad_x != 0 else self._dpad_btn_x
    hat_y = self._dpad_y if self._dpad_y != 0 else self._dpad_btn_y
    self.state.dpad_x = hat_x
    self.state.dpad_y = hat_y

  def _read_axis(self, code) -> int:
    mapper = self._mappers.get(code)
    if mapper is None:
      return 0
    return mapper.to_axis()

  def _detect_event_size(self, event_path) -> EvdevEventFormat:
    candidates = []
    if struct.calcsize("L") == 8:
      candidates.append(EvdevEventFormat(struct.Struct("QQHHi"), 24))
    candidates.append(EvdevEventFormat(struct.Struct("llHHi"), 16))

    chunk = b""
    try:
      fd = os.open(event_path, os.O_RDONLY | os.O_NONBLOCK)
      try:
        ready, _, _ = select.select([fd], [], [], 0.3)
        if ready:
          chunk = os.read(fd, 256)
      finally:
        os.close(fd)
    except OSError as io_error:
      print(f"evdev: event-size probe failed: {io_error}")

    best = candidates[0]
    best_score = -1
    for candidate in candidates:
      score = self._score_event_chunk(chunk, candidate.event_struct, candidate.size)
      if score > best_score:
        best_score = score
        best = candidate

    return best

  def _score_event_chunk(self, chunk, st, size) -> int:
    score = 0
    off = 0
    while off + size <= len(chunk):
      try:
        ev_type, code = st.unpack_from(chunk, off)[2:4]
      except struct.error:
        break
      if ev_type in _VALID_EV_TYPES:
        score += 1
      if ev_type == EV_ABS and code <= 0x3f:
        score += 2
      off += size
    return score
