import select
import struct

from lib.controller_state import ControllerState
from lib.evdev_axis_mapper import EvdevAxisMapper, EvdevTriggerMapper
from lib.evdev_constants import (
  ABS_HAT0X, ABS_HAT0Y, BTN_DPAD_DOWN, BTN_DPAD_LEFT, BTN_DPAD_RIGHT, BTN_DPAD_UP,
  BTN_NAME_BY_CODE, BTN_THUMBL, BTN_THUMBR, BTN_TL, BTN_TL2, BTN_TR, BTN_TR2,
  EV_ABS, EV_KEY, EV_SYN, SYN_REPORT,
)
from lib.evdev_ioctl import read_absinfo
from lib.evdev_sysfs_reader import EvdevSysfsReader
from lib.evdev_xbox_layout import XboxAxisLayout

_VALID_EV_TYPES = {0, 1, 2, 3, 4, 0x11, 0x14, 0x15, 0x17}


class EvdevReader:
  """Read Xbox evdev events (input thread only)."""

  def __init__(self, event_path, config=None):
    self.event_path = event_path
    self._config = config or {}
    self.state = ControllerState()
    self._sysfs = EvdevSysfsReader()
    evdev_cfg = self._config.get("evdev", {})
    self._layout = XboxAxisLayout.detect(self._sysfs, event_path, evdev_cfg)
    self._ev_struct, self._ev_size = self._detect_event_size(event_path)
    self._mappers = {}
    self._observed = {}
    self._file = None
    self.event_count = 0
    self._abs_event_count = 0
    self._lt_btn = 0
    self._rt_btn = 0
    self._dpad_x = 0
    self._dpad_y = 0
    self._dpad_btn_x = 0
    self._dpad_btn_y = 0

  def open(self):
    self._file = open(self.event_path, "rb")
    self._init_mappers()

  def _init_mappers(self):
    """Create axis mappers up front so kernel sync always has a target."""
    layout = self._layout
    trigger_codes = {layout.lt, layout.rt}
    for code in (layout.left_x, layout.left_y, layout.right_x, layout.right_y, layout.lt, layout.rt):
      info = read_absinfo(self._file, code)
      if info is not None:
        raw = info[0]
      else:
        min_v, max_v, flat = self._axis_range(code, code in trigger_codes)
        raw = (min_v + max_v) // 2
      self._ensure_mapper(code, raw)

  def close(self):
    if self._file is not None:
      try:
        self._file.close()
      except OSError:
        pass
      self._file = None

  def drain_available(self):
    """Read every pending evdev event (non-blocking)."""
    if self._file is None:
      return 0
    count = 0
    while self._file is not None:
      ready, _, _ = select.select([self._file], [], [], 0)
      if not ready:
        break
      try:
        data = self._file.read(self._ev_size)
      except OSError as exc:
        if exc.errno == 19:
          raise
        break
      if not data or len(data) < self._ev_size:
        break
      self._process_event(data)
      count += 1
    return count

  def poll_inputs(self):
    """
    One input frame: events for buttons, then kernel ABS truth for sticks.

    Axes are read via EVIOCGABS every poll so missed evdev packets cannot
    leave sticks stuck at the last value.
    """
    if self._file is None:
      return
    self.drain_available()
    self.sync_axes_from_kernel()

  def sync_axes_from_kernel(self):
    """Force stick/trigger state from kernel (ioctl, then sysfs fallback)."""
    layout = self._layout
    trigger_codes = {layout.lt, layout.rt}
    for code in (layout.left_x, layout.left_y, layout.right_x, layout.right_y, layout.lt, layout.rt):
      info = read_absinfo(self._file, code)
      if info is not None:
        raw, min_v, max_v, flat = info
        self._ensure_mapper_with_range(code, raw, min_v, max_v, flat, code in trigger_codes)
        continue
      val = self._sysfs.read_abs_value(self.event_path, code)
      if val is not None:
        self._feed_abs(code, val)
    self._sync_axes()

  def _ensure_mapper_with_range(self, code, raw, min_v, max_v, flat, prefer_trigger):
    mapper = self._mappers.get(code)
    if mapper is None:
      if prefer_trigger and max_v - min_v > 1024:
        prefer_trigger = False
      mapper = (
        EvdevTriggerMapper(min_v, max_v, flat)
        if prefer_trigger
        else EvdevAxisMapper(min_v, max_v, flat, invert=False)
      )
      self._mappers[code] = mapper
    mapper.set_raw(raw)

  def wait_and_poll(self, timeout_sec=0.05):
    if self._file is None:
      return False
    fd = self._file.fileno()
    ready, _, _ = select.select([fd], [], [], timeout_sec)
    if not ready:
      return False
    return self._drain_events()

  def _drain_events(self):
    got = False
    while self._file is not None:
      ready, _, _ = select.select([self._file], [], [], 0)
      if not ready:
        break
      try:
        data = self._file.read(self._ev_size)
      except OSError as exc:
        if exc.errno == 19:
          raise
        break
      if not data or len(data) < self._ev_size:
        break
      self._process_event(data)
      got = True
    return got

  def _process_event(self, data):
    _sec, _usec, ev_type, code, value = self._ev_struct.unpack(data)
    self.event_count += 1
    if ev_type == EV_ABS:
      self._abs_event_count += 1
      if self._abs_event_count <= 6:
        print(f"evdev abs code={code} raw={value}")
      self._feed_abs(code, value)
    elif ev_type == EV_KEY:
      self._feed_key(code, value)
    elif ev_type == EV_SYN and code == SYN_REPORT:
      pass

  def _axis_range(self, code, as_trigger):
    info = self._sysfs.read_absinfo_real(self.event_path, code)
    if info is not None:
      return info
    if as_trigger:
      return 0, 1023, 64
    return 0, 65535, 4096

  def _create_mapper(self, code, prefer_trigger):
    min_v, max_v, flat = self._axis_range(code, prefer_trigger)
    if prefer_trigger and max_v - min_v > 1024:
      prefer_trigger = False
    if prefer_trigger:
      return EvdevTriggerMapper(min_v, max_v, flat)
    return EvdevAxisMapper(min_v, max_v, flat, invert=False)

  def _ensure_mapper(self, code, value):
    obs = self._observed.get(code)
    if obs is None:
      obs = {"min": value, "max": value}
      self._observed[code] = obs
    else:
      obs["min"] = min(obs["min"], value)
      obs["max"] = max(obs["max"], value)

    mapper = self._mappers.get(code)
    if mapper is not None:
      return mapper

    trigger_codes = {self._layout.lt, self._layout.rt}
    prefer_trigger = code in trigger_codes
    span = obs["max"] - obs["min"]
    if prefer_trigger and span > 1024:
      prefer_trigger = False
    if not prefer_trigger and span <= 1024 and obs["min"] >= 0 and code in trigger_codes:
      prefer_trigger = True

    mapper = self._create_mapper(code, prefer_trigger)
    self._mappers[code] = mapper
    print(f"evdev: mapper axis {code} trigger={prefer_trigger} seen={obs['min']}..{obs['max']}")
    return mapper

  def _feed_abs(self, code, value):
    if code in (ABS_HAT0X, 6):
      self._dpad_x = self._hat_value(value)
      return
    if code in (ABS_HAT0Y, 7):
      self._dpad_y = self._hat_value(value)
      return
    mapper = self._ensure_mapper(code, value)
    mapper.set_raw(value)

  @staticmethod
  def _hat_value(value):
    if value > 0:
      return 1
    if value < 0:
      return -1
    return 0

  def _feed_key(self, code, value):
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

  def _sync_axes(self):
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

  def _read_axis(self, code):
    mapper = self._mappers.get(code)
    if mapper is None:
      return 0
    return mapper.to_axis()

  def _detect_event_size(self, event_path):
    candidates = []
    if struct.calcsize("L") == 8:
      candidates.append((struct.Struct("QQHHi"), 24))
    candidates.append((struct.Struct("llHHi"), 16))

    chunk = b""
    try:
      with open(event_path, "rb") as f:
        ready, _, _ = select.select([f], [], [], 0.3)
        if ready:
          chunk = f.read(256)
    except OSError:
      pass

    best = candidates[0]
    best_score = -1
    for st, size in candidates:
      score = self._score_event_chunk(chunk, st, size)
      print(f"evdev: candidate {size}-byte score={score}")
      if score > best_score:
        best_score = score
        best = (st, size)

    st, size = best
    print(f"evdev: using {size}-byte events (score={best_score})")
    return st, size

  def _score_event_chunk(self, chunk, st, size):
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
