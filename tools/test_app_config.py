"""Minimal check: AppConfig attributes beat string-key .get."""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "maixcam", "roverMecanum")
sys.path.insert(0, ROOT)

from lib.app_config import AppConfig  # noqa: E402


def main():
  path = os.path.join(ROOT, "config.json")
  with open(path, "r", encoding="utf-8") as handle:
    raw = json.load(handle)
  cfg = AppConfig.from_dict(raw)
  assert cfg.camera.display_fps == raw["camera"]["display_fps"]
  assert cfg.rover.send_interval_ms == raw["rover"]["send_interval_ms"]
  assert cfg.timing.teleop_poll_sleep_ms == raw["timing"]["teleop_poll_sleep_ms"]
  assert cfg.camera.display_interval_ms == max(1, int(1000 / cfg.camera.display_fps))
  print("ok: AppConfig fields match config.json")


if __name__ == "__main__":
  main()
