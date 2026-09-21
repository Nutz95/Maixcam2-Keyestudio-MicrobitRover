"""Host tests for green-ball selection and sequential follow policy."""

import os
import sys
import unittest
from unittest.mock import Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum"))

from lib.ball_detector import BallDetector
from lib.ball_follow_controller import BallFollowController
from lib.ball_follow_command import BallFollowCommand
from lib.ball_follow_policy import BallFollowPolicy
from lib.ball_follow_settings import BallFollowSettings
from lib.ball_observation import BallObservation


class TestBallFollow(unittest.TestCase):
  """Verify the pure ball-follow decisions without MaixPy hardware."""

  def setUp(self):
    self.settings = BallFollowSettings({})

  def test_detector_selects_largest_compact_candidate(self):
    detector = BallDetector(self.settings)
    image = Mock()
    image.width.return_value = 640
    image.height.return_value = 480
    large_blob = Mock()
    large_blob.w.return_value = 40
    large_blob.h.return_value = 38
    large_blob.area.return_value = 1200
    large_blob.cx.return_value = 320
    large_blob.cy.return_value = 280
    small_blob = Mock()
    small_blob.w.return_value = 12
    small_blob.h.return_value = 12
    small_blob.area.return_value = 144
    small_blob.cx.return_value = 80
    small_blob.cy.return_value = 80
    image.find_blobs.return_value = [small_blob, large_blob]

    observation = detector.detect(image, 1000)

    self.assertIsNotNone(observation)
    self.assertEqual(observation.center_x, 320)
    self.assertEqual(observation.height, 38)

  def test_horizontal_error_rotates_without_forward_motion(self):
    policy = BallFollowPolicy(self.settings)
    observation = BallObservation(500, 260, 36, 36, 900, 900.0, 1000, 640, 480)

    command = policy.decide(observation, 1000)

    self.assertNotEqual(command.spin, 0)
    self.assertEqual(command.forward, 0)
    self.assertEqual(command.reason, "align")
    # Breakaway floor: small visual error still clears motor static friction.
    self.assertGreaterEqual(abs(command.spin), self.settings.min_spin_axis)

  def test_small_high_ball_approaches(self):
    policy = BallFollowPolicy(self.settings)
    observation = BallObservation(320, 100, 24, 24, 500, 500.0, 1000, 640, 480)

    command = policy.decide(observation, 1000)

    self.assertLess(command.forward, 0)
    self.assertEqual(command.spin, 0)
    self.assertEqual(command.reason, "approach")
    self.assertGreaterEqual(abs(command.forward), self.settings.min_forward_axis)

  def test_large_low_ball_reverses(self):
    policy = BallFollowPolicy(self.settings)
    observation = BallObservation(320, 440, 280, 270, 50000, 50000.0, 1000, 640, 480)

    command = policy.decide(observation, 1000)

    self.assertGreater(command.forward, 0)
    self.assertEqual(command.reason, "too_close")
    self.assertLessEqual(abs(command.forward), self.settings.max_retreat_axis)

  def test_lost_ball_searches_after_timeout(self):
    policy = BallFollowPolicy(self.settings)
    observation = BallObservation(320, 250, 80, 72, 5000, 5000.0, 1000, 640, 480)
    policy.decide(observation, 1000)

    stopped = policy.decide(None, 1400)
    searching = policy.decide(None, 3100)

    self.assertEqual(stopped, BallFollowCommand(reason="target_lost"))
    self.assertEqual(searching.reason, "search")
    self.assertNotEqual(searching.spin, 0)

  def test_search_follows_exit_side_then_retreats_after_one_turn(self):
    policy = BallFollowPolicy(self.settings)
    left_side = BallObservation(100, 250, 40, 40, 1200, 1200.0, 1000, 640, 480)
    policy.decide(left_side, 1000)

    searching = policy.decide(None, 3100)
    after_turn = policy.decide(None, 3100 + self.settings.search_turn_ms)
    still_paused = policy.decide(
      None, 3100 + self.settings.search_turn_ms + 100,
    )
    after_pause = policy.decide(
      None,
      3100 + self.settings.search_turn_ms + self.settings.search_pause_ms,
    )

    self.assertEqual(searching.reason, "search")
    self.assertLess(searching.spin, 0)
    self.assertEqual(after_turn.reason, "search_pause")
    self.assertEqual(still_paused.reason, "search_pause")
    self.assertEqual(after_pause.reason, "search_retreat")
    self.assertNotEqual(after_pause.forward, 0)

  def test_search_follows_rightward_exit_trajectory(self):
    policy = BallFollowPolicy(self.settings)
    first = BallObservation(280, 250, 40, 40, 1200, 1200.0, 1000, 640, 480)
    second = BallObservation(420, 250, 40, 40, 1200, 1200.0, 1050, 640, 480)
    policy.decide(first, 1000)
    policy.decide(second, 1050)

    searching = policy.decide(None, 3200)

    self.assertEqual(searching.reason, "search")
    self.assertGreater(searching.spin, 0)

  def test_controller_publishes_recent_bbox_trajectory(self):
    controller = BallFollowController(self.settings)
    controller.set_enabled(True)
    frame = Mock()
    frame.width.return_value = 640
    frame.height.return_value = 480
    first_blob = Mock()
    first_blob.w.return_value = 40
    first_blob.h.return_value = 40
    first_blob.area.return_value = 1200
    first_blob.cx.return_value = 280
    first_blob.cy.return_value = 240
    second_blob = Mock()
    second_blob.w.return_value = 40
    second_blob.h.return_value = 40
    second_blob.area.return_value = 1200
    second_blob.cx.return_value = 320
    second_blob.cy.return_value = 240
    frame.find_blobs.side_effect = [[first_blob], [second_blob]]

    controller.update(frame)
    controller.update(frame)

    snapshot = controller.snapshot()
    self.assertEqual(len(snapshot.trajectory), 2)
    self.assertEqual(snapshot.observation.center_x, 320)

  def test_thresholds_are_ints_for_maixpy(self):
    settings = BallFollowSettings({
      "ball_follow": {
        "colors": {
          "green": [[40.0, 90.0, -90.0, -40.0, 25.0, 75.0]],
          "red": [[0.2, 80.7, 40.1, 80.9, 10.0, 80.0]],
        },
      },
    })
    green = settings.thresholds_for("green")
    red = settings.thresholds_for("red")
    self.assertEqual(green, [[40, 90, -90, -40, 25, 75]])
    self.assertEqual(red, [[0, 81, 40, 81, 10, 80]])
    self.assertTrue(all(isinstance(value, int) for row in green for value in row))

  def test_align_spin_is_damped_when_ball_returns_to_center(self):
    policy = BallFollowPolicy(self.settings)
    # Far-right ball sliding left: PD output stays above the breakaway floor.
    first = BallObservation(630, 250, 80, 80, 5000, 5000.0, 1000, 640, 480)
    returning = BallObservation(580, 250, 80, 80, 5000, 5000.0, 1050, 640, 480)
    policy.decide(first, 1000)
    static = BallFollowPolicy(self.settings)
    static_cmd = static.decide(
      BallObservation(580, 250, 80, 80, 5000, 5000.0, 1000, 640, 480),
      1000,
    )
    damped_cmd = policy.decide(returning, 1050)

    self.assertEqual(static_cmd.reason, "align")
    self.assertEqual(damped_cmd.reason, "align")
    self.assertGreaterEqual(static_cmd.spin, self.settings.min_spin_axis)
    self.assertLessEqual(damped_cmd.spin, static_cmd.spin)

  def test_controller_cycles_green_and_red(self):
    controller = BallFollowController(self.settings)
    self.assertEqual(controller.color, "green")
    self.assertEqual(controller.cycle_color(), "red")
    self.assertEqual(controller.cycle_color(), "green")
    self.assertEqual(controller.snapshot().mode_label, "MANUAL")
    controller.set_enabled(True)
    self.assertEqual(controller.snapshot().mode_label, "BALL GREEN")
