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

  def decide(
    self,
    observation: Optional[BallObservation],
    now_ms: int,
  ) -> BallFollowCommand:
    """Return one bounded command for the current observation or loss state."""
    if observation is None:
      return self._lost_command(now_ms)

    self._phase = _PHASE_TRACK
    self._phase_started_ms = None
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
      spin = self._bounded(damped, self._settings.max_spin_axis)
      return BallFollowCommand(
        spin=self._settings.spin_axis_sign * spin,
        reason="align",
      )

    if (
      predicted_height >= self._settings.too_close_height_ratio
      or observation.y_ratio >= self._settings.too_close_center_y_ratio
    ):
      distance_error = max(
        self._settings.min_distance_error,
        predicted_height - self._settings.target_height_ratio,
      )
      backward = self._bounded(
        distance_error * self._settings.forward_gain,
        self._settings.max_forward_axis,
      )
      return BallFollowCommand(
        forward=-self._settings.forward_axis_sign * backward,
        reason="too_close",
      )

    if (
      predicted_height < (
        self._settings.target_height_ratio
        - self._settings.target_tolerance_ratio
      )
      or observation.y_ratio < self._settings.far_center_y_ratio
    ):
      distance_error = max(
        self._settings.min_distance_error,
        self._settings.target_height_ratio - predicted_height,
      )
      forward = self._bounded(
        distance_error * self._settings.forward_gain,
        self._settings.max_forward_axis,
      )
      return BallFollowCommand(
        forward=self._settings.forward_axis_sign * forward,
        reason="approach",
      )

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

  def _lost_command(self, now_ms: int) -> BallFollowCommand:
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

    if self._phase == _PHASE_SEARCH:
      if now_ms - self._phase_started_ms < self._settings.search_turn_ms:
        return BallFollowCommand(
          spin=self._search_spin_sign * self._settings.search_spin_axis,
          reason="search",
        )
      # Stop between turn and retreat so timed turns do not blend into a second spin.
      self._after_search_pause = _PHASE_RETREAT
      self._phase = _PHASE_SEARCH_PAUSE
      self._phase_started_ms = now_ms

    if self._phase == _PHASE_SEARCH_PAUSE:
      if now_ms - self._phase_started_ms < self._settings.search_pause_ms:
        return BallFollowCommand(reason="search_pause")
      self._phase = self._after_search_pause
      self._phase_started_ms = now_ms

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
  def _bounded(value: float, limit: int) -> int:
    return max(-limit, min(limit, int(value)))
