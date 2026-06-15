"""Installation paths on MaixCam."""

import os

# Deploy target (see tools/deploy_rover_mecanum.ps1).
ROVER_MECANUM_ROOT = "/root/roverMecanum"

# Fallback when no config file exists yet.
DEFAULT_CONFIG_PATH = f"{ROVER_MECANUM_ROOT}/config.json"


def resolve_config_path():
  """
  Pick the active config.json.

  Search order:
    1. ./config.json relative to MaixVision cwd (usually /tmp/maixpy_run/)
    2. /root/roverMecanum/config.json (deployed copy)
    3. DEFAULT_CONFIG_PATH (created on first run if missing)
  """
  candidates = (
    os.path.join(os.getcwd(), "config.json"),
    f"{ROVER_MECANUM_ROOT}/config.json",
  )
  for path in candidates:
    if os.path.isfile(path):
      return path
  return DEFAULT_CONFIG_PATH
