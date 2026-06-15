import select
import struct

from lib.controller_state import ControllerState
from lib.evdev_axis_mapper import EvdevAxisMapper, EvdevTriggerMapper
from lib.evdev_constants import (
  BTN_NAME_BY_CODE, BTN_TL2, BTN_TR2, EV_ABS, EV_KEY, EV_SYN, SYN_REPORT,
)
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

  def open(self):
    self._file = open(self.event_path, "rb")

  def close(self):
    if self._file is not None:
      try:
        self._file.close()
      except OSError:
        pass
      self._file = None

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
      self._sync_axes()
    elif ev_type == EV_KEY:
      self._feed_key(code, value)
    elif ev_type == EV_SYN and code == SYN_REPORT:
      self._sync_axes()

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
    mapper = self._ensure_mapper(code, value)
    mapper.set_raw(value)

  def _feed_key(self, code, value):
    if code == BTN_TL2:
      self._lt_btn = 32767 if value else 0
      return
    if code == BTN_TR2:
      self._rt_btn = 32767 if value else 0
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
