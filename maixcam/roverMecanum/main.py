"""
MaixVision entry point — Xbox controller -> Mecanum rover.

MaixVision runs this file from /tmp/maixpy_run/main.py.
Shared code lives under /root/roverMecanum/ (deploy with tools/deploy_rover_mecanum.ps1).
"""

import sys

ROVER_MECANUM_ROOT = "/root/roverMecanum"

if ROVER_MECANUM_ROOT not in sys.path:
  sys.path.insert(0, ROVER_MECANUM_ROOT)

from lib.xbox_rover_app import XboxRoverApp


def main():
  app_instance = XboxRoverApp()
  try:
    app_instance.run()
  finally:
    app_instance.shutdown()


if __name__ == "__main__":
  try:
    main()
  except Exception:
    import gc
    import traceback

    from maix import app, display, image, time

    msg = traceback.format_exc()
    print(msg)
    try:
      disp = display.Display()
      img = image.Image(disp.width(), disp.height(), bg=image.COLOR_BLACK)
      img.draw_string(0, 0, msg, image.COLOR_WHITE, scale=1.2)
      disp.show(img)
      while not app.need_exit():
        time.sleep_ms(100)
    except Exception:
      pass
    gc.collect()
