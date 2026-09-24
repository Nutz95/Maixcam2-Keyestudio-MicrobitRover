"""Typed IMU yaw state exposed to the HUD and ball-follow policy."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ImuSnapshot:
  """Latest yaw and calibration status for HUD and control."""

  ready: bool
  calibrated: bool
  calibrating: bool
  yaw_deg: Optional[float]
  status: str
  calib_progress: float = 0.0
