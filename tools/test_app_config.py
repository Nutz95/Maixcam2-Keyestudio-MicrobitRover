"""Minimal check: AppConfig attributes beat string-key .get."""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum")
sys.path.insert(0, ROOT)

from lib.app_config import AppConfig  # noqa: E402
from lib.controller_mapping_engine import ControllerMappingEngine  # noqa: E402
from lib.controller_state import ControllerState  # noqa: E402


def main():
  path = os.path.join(ROOT, "config.json")
  with open(path, "r", encoding="utf-8") as handle:
    raw = json.load(handle)
  app_config = AppConfig.from_dict(raw)
  assert app_config.camera.display_fps == raw["camera"]["display_fps"]
  assert app_config.rover.send_interval_ms == raw["rover"]["send_interval_ms"]
  assert app_config.timing.teleop_poll_sleep_ms == raw["timing"]["teleop_poll_sleep_ms"]
  assert app_config.timing.bt_kernel_settle_ms == raw["timing"]["bt_kernel_settle_ms"]
  assert app_config.timing.evdev_drain_max_events == raw["timing"]["evdev_drain_max_events"]
  assert app_config.camera.display_interval_ms == max(1, 1000 // app_config.camera.display_fps)
  assert app_config.mapping.drive_forward == raw["mapping"]["axes"]["drive_forward"]
  assert app_config.mapping.dpad.up == raw["mapping"]["dpad"]["up"]
  assert app_config.mapping.buttons.btn_a == raw["mapping"]["buttons"]["btn_a"]
  assert app_config.evdev.layout == raw["evdev"]["layout"]
  assert app_config.ball_follow.target_height_ratio == raw["ball_follow"]["target_height_ratio"]
  assert app_config.imu.enabled == raw["imu"]["enabled"]
  assert app_config.imu.calib_ms == raw["imu"]["calib_ms"]
  assert app_config.ball_follow.search_turn_deg == raw["ball_follow"]["search_turn_deg"]
  assert app_config.camera.fps == 60
  assert not hasattr(app_config, "raw")
  assert not hasattr(app_config, "to_dict")

  mapper = ControllerMappingEngine(app_config)
  state = ControllerState()
  state.left_y = 20000
  drive = mapper.compute(state)
  assert drive.axis_forward != 0

  state.left_y = 0
  state.dpad_y = -1
  drive = mapper.compute(state)
  assert drive.axis_forward != 0
  print("ok: typed AppConfig + dpad fields; mapping compute uses cached settings")


if __name__ == "__main__":
  main()
