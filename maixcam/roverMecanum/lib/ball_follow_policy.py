"""Sequential visual policy for approaching a colored ball safely."""

from typing import Optional

from lib.ball_follow_command import BallFollowCommand
from lib.ball_follow_settings import BallFollowSettings
from lib.ball_observation import BallObservation

_PHASE_TRACK = "track"
_PHASE_LOST_WAIT = "lost_wait"
_PHASE_SEARCH = "search"
_PHASE_SEARCH_PAUSE = "search_pause"
_PHASE_RETREAT = "retreat"


class BallFollowPolicy:
  """Rotate first, then approach or retreat using blob size and image position."""

  def __init__(self, settings: BallFollowSettings):
    """Create a stateful policy with loss timing and short prediction."""
    self._settings = settings
    self._last_observation = None
    self._last_seen_ms = None
    self._velocity_x = 0.0
    self._velocity_height = 0.0
    self._phase = _PHASE_TRACK
    self._phase_started_ms = None
    self._search_spin_sign = 1
    self._after_search_pause = _PHASE_RETREAT
    self._search_yaw_last = None
    self._search_yaw_accum = 0.0
    self._holding_distance = False

  def reset(self) -> None:
    """Forget the target and force the next decision to stop safely."""
    self._last_observation = None
    self._last_seen_ms = None
    self._velocity_x = 0.0
    self._velocity_height = 0.0
    self._phase = _PHASE_TRACK
    self._phase_started_ms = None
    self._search_spin_sign = 1
    self._after_search_pause = _PHASE_RETREAT
    self._search_yaw_last = None
    self._search_yaw_accum = 0.0
    self._holding_distance = False

  def decide(
    self,
    observation: Optional[BallObservation],
    now_ms: int,
    yaw_deg: Optional[float] = None,
  ) -> BallFollowCommand:
    """Return one bounded command for the current observation or loss state."""
    if observation is None:
      return self._lost_command(now_ms, yaw_deg)

    self._phase = _PHASE_TRACK
    self._phase_started_ms = None
    self._search_yaw_last = None
    self._search_yaw_accum = 0.0
    self._update_velocity(observation)
    self._last_observation = observation
    self._last_seen_ms = observation.timestamp_ms
    center = self._settings.image_center_x_ratio
    predicted_x = observation.x_ratio + (
      self._velocity_x * self._settings.prediction_ms / 1000.0
    )
    predicted_height = observation.height_ratio + (
      self._velocity_height * self._settings.prediction_ms / 1000.0
    )
    predicted_x = max(0.0, min(1.0, predicted_x))
    predicted_height = max(0.0, min(1.0, predicted_height))

    horizontal_error = predicted_x - center
    if abs(horizontal_error) > self._settings.horizontal_deadzone:
      # PD on image x: damp when the ball is already sliding back toward center.
      damped = (
        horizontal_error * self._settings.spin_gain
        + self._velocity_x * self._settings.spin_damping
      )
      # Near center: soft ceiling; far off-center: full max_spin.
      spin_floor, spin_max = self._progressive_limits(
        self._settings.min_spin_axis,
        self._settings.max_spin_axis,
        abs(horizontal_error),
        0.40,
      )
      spin = self._drive_axis(damped, spin_floor, spin_max)
      return BallFollowCommand(
        spin=self._settings.spin_axis_sign * spin,
        reason="align",
      )

    if (
      predicted_height >= self._settings.too_close_height_ratio
      or (
        predicted_height >= self._settings.target_height_ratio
        and observation.y_ratio >= self._settings.too_close_center_y_ratio
      )
    ):
      self._holding_distance = False
      distance_error = max(
        self._settings.min_distance_error,
        predicted_height - self._settings.target_height_ratio,
      )
      hard_floor = min(self._settings.min_forward_axis, self._settings.max_retreat_axis)
      retreat_floor, retreat_max = self._progressive_limits(
        hard_floor,
        self._settings.max_retreat_axis,
        distance_error,
        max(0.08, self._settings.too_close_height_ratio - self._settings.target_height_ratio),
      )
      # Near the stop band: no breakaway floor so we don't punch past the target.
      if distance_error < self._settings.target_tolerance_ratio * 2:
        retreat_floor = 1
      backward = self._drive_axis(
        distance_error * self._settings.forward_gain,
        retreat_floor,
        retreat_max,
      )
      return BallFollowCommand(
        forward=-self._settings.forward_axis_sign * backward,
        reason="too_close",
      )

    approach_limit = (
      self._settings.target_height_ratio - self._settings.target_tolerance_ratio
    )
    if self._holding_distance:
      # Sticky stop band: only leave after the ball is clearly too far again.
      approach_limit -= self._settings.target_tolerance_ratio

    # Distance from blob height only. Secondary Y used to fight height causes
    # approach/retreat chatter when the ball is roughly ahead of the rover.
    if predicted_height < approach_limit:
      self._holding_distance = False
      distance_error = max(
        self._settings.min_distance_error,
        self._settings.target_height_ratio - predicted_height,
      )
      forward_floor, forward_max = self._progressive_limits(
        self._settings.min_forward_axis,
        self._settings.max_forward_axis,
        distance_error,
        max(0.08, self._settings.target_height_ratio),
      )
      if distance_error < self._settings.target_tolerance_ratio * 2:
        forward_floor = 1
      forward = self._drive_axis(
        distance_error * self._settings.forward_gain,
        forward_floor,
        forward_max,
      )
      return BallFollowCommand(
        forward=self._settings.forward_axis_sign * forward,
        reason="approach",
      )

    self._holding_distance = True
    return BallFollowCommand(reason="target_distance")

  def _update_velocity(self, observation: BallObservation) -> None:
    if self._last_observation is None:
      self._velocity_x = 0.0
      self._velocity_height = 0.0
      return
    elapsed_ms = observation.timestamp_ms - self._last_observation.timestamp_ms
    if elapsed_ms <= 0 or elapsed_ms > self._settings.velocity_timeout_ms:
      self._velocity_x = 0.0
      self._velocity_height = 0.0
      return
    elapsed_s = elapsed_ms / 1000.0
    self._velocity_x = (
      observation.x_ratio - self._last_observation.x_ratio
    ) / elapsed_s
    self._velocity_height = (
      observation.height_ratio - self._last_observation.height_ratio
    ) / elapsed_s

  def _lost_command(
    self,
    now_ms: int,
    yaw_deg: Optional[float],
  ) -> BallFollowCommand:
    if self._last_seen_ms is None:
      return BallFollowCommand(reason="no_target")

    if self._phase == _PHASE_TRACK:
      self._search_spin_sign = self._exit_direction_sign()
      self._phase = _PHASE_LOST_WAIT
      self._phase_started_ms = now_ms

    if self._phase == _PHASE_LOST_WAIT:
      if now_ms - self._last_seen_ms < self._settings.lost_search_ms:
        return BallFollowCommand(reason="target_lost")
      self._phase = _PHASE_SEARCH
      self._phase_started_ms = now_ms
      self._search_yaw_last = None
      self._search_yaw_accum = 0.0

    if self._phase == _PHASE_SEARCH:
      if not self._search_turn_done(now_ms, yaw_deg):
        return BallFollowCommand(
          spin=self._search_spin_sign * self._settings.search_spin_axis,
          reason="search",
        )
      # Stop between turn and retreat so turns do not blend into a second spin.
      self._after_search_pause = _PHASE_RETREAT
      self._phase = _PHASE_SEARCH_PAUSE
      self._phase_started_ms = now_ms
      self._search_yaw_last = None
      self._search_yaw_accum = 0.0

    if self._phase == _PHASE_SEARCH_PAUSE:
      if now_ms - self._phase_started_ms < self._settings.search_pause_ms:
        return BallFollowCommand(reason="search_pause")
      self._phase = self._after_search_pause
      self._phase_started_ms = now_ms
      if self._phase == _PHASE_SEARCH:
        self._search_yaw_last = None
        self._search_yaw_accum = 0.0

    if self._phase == _PHASE_RETREAT:
      if now_ms - self._phase_started_ms < self._settings.search_retreat_ms:
        return BallFollowCommand(
          forward=-self._settings.forward_axis_sign * self._settings.search_retreat_axis,
          reason="search_retreat",
        )
      self._after_search_pause = _PHASE_SEARCH
      self._phase = _PHASE_SEARCH_PAUSE
      self._phase_started_ms = now_ms
      return BallFollowCommand(reason="search_pause")

    return BallFollowCommand(reason="target_lost")

  def _search_turn_done(self, now_ms: int, yaw_deg: Optional[float]) -> bool:
    """Finish one search turn by accumulated |Δyaw| when IMU is ready, else timer."""
    elapsed_ms = now_ms - self._phase_started_ms
    use_yaw = yaw_deg is not None and self._settings.search_turn_deg > 0
    if use_yaw:
      if self._search_yaw_last is None:
        self._search_yaw_last = yaw_deg
        self._search_yaw_accum = 0.0
        return False
      # Accumulate sample-to-sample shortest steps so turns past 180° still work.
      self._search_yaw_accum += abs(self.yaw_delta_deg(self._search_yaw_last, yaw_deg))
      self._search_yaw_last = yaw_deg
      if self._search_yaw_accum >= self._settings.search_turn_deg:
        return True
      # Safety: do not spin forever if yaw stalls.
      return elapsed_ms >= self._settings.search_turn_ms * 3
    return elapsed_ms >= self._settings.search_turn_ms

  def _exit_direction_sign(self) -> int:
    """Choose search spin from the last known ball motion or image side."""
    center = self._settings.image_center_x_ratio
    if abs(self._velocity_x) >= self._settings.exit_velocity_threshold:
      direction = 1 if self._velocity_x > 0 else -1
    elif self._last_observation is not None:
      direction = 1 if self._last_observation.x_ratio >= center else -1
    else:
      direction = 1
    return self._settings.spin_axis_sign * direction

  @staticmethod
  def yaw_delta_deg(start_deg: float, now_deg: float) -> float:
    """Signed shortest yaw difference in degrees, in (-180, 180]."""
    return (now_deg - start_deg + 180.0) % 360.0 - 180.0

  @staticmethod
  def _progressive_limits(min_axis: int, max_axis: int, error: float, full_error: float):
    """Soft floor + ceiling from error size (gentle near goal, full when far)."""
    if max_axis <= min_axis:
      return min_axis, min_axis
    t = 1.0 if full_error <= 0 else max(0.0, min(1.0, abs(error) / full_error))
    # ponytail: soft floor can sit under breakaway near target; upgrade = gyro kick probe.
    floor = max(1, int(min_axis * (0.55 + 0.45 * t)))
    ceiling = max(floor, int(min_axis + t * (max_axis - min_axis)))
    return floor, ceiling

  @staticmethod
  def _drive_axis(value: float, min_axis: int, max_axis: int) -> int:
    """
    Linear vision→motor map with a breakaway floor.

    Joystick teleop uses expo (soft center). Ball-follow must not: small visual
    errors still need enough PWM to leave static friction. Zero stays zero;
    any non-zero command is raised to ``min_axis`` then capped at ``max_axis``.
    """
    if value == 0:
      return 0
    sign = 1 if value > 0 else -1
    magnitude = min(max_axis, abs(int(value)))
    if magnitude > 0:
      magnitude = max(min_axis, magnitude)
    return sign * magnitude
