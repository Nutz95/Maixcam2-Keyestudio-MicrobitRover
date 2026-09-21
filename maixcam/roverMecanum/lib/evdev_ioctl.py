"""Read current evdev ABS axis state via Linux EVIOCGABS ioctl."""

import array
import fcntl
import struct
from typing import Optional

from lib.abs_info import AbsInfo

# struct input_absinfo { value, minimum, maximum, fuzz, flat, resolution }
_ABSINFO_FMT = "iiiiii"
_ABSINFO_SIZE = struct.calcsize(_ABSINFO_FMT)


def _eviocgabs_request(axis_code: int) -> int:
  """Build EVIOCGABS(axis) ioctl request number (Linux input.h)."""
  return (2 << 30) | (_ABSINFO_SIZE << 16) | (ord("E") << 8) | (0x40 + axis_code)


def read_absinfo(fd, axis_code: int) -> Optional[AbsInfo]:
  """
  Read kernel ABS state for one axis.

  Returns AbsInfo or None if ioctl unsupported.
  """
  if fd is None:
    return None
  fileno = fd.fileno()
  buf = array.array("i", [0] * 6)
  try:
    fcntl.ioctl(fileno, _eviocgabs_request(axis_code), buf, True)
    return AbsInfo(int(buf[0]), int(buf[1]), int(buf[2]), int(buf[4]))
  except OSError:
    return None
