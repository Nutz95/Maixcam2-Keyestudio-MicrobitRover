"""Fullscreen gyro calibration hold-still overlay."""

from maix import image


class GyroCalibOverlay:
  """Hide sticks and show ASCII hold-still + live progress during calib."""

  def __init__(self, width: int, height: int, back_rect, back_image):
    """Keep display size and back-button chrome for the calib screen."""
    self.width = width
    self.height = height
    self._back_rect = list(back_rect)
    self._back_image = back_image

  def draw(self, img, imu_snapshot) -> None:
    """Paint the calibration screen over the current frame."""
    img.draw_rect(
      0, 0, self.width, self.height,
      image.Color.from_rgb(0, 0, 0), thickness=-1,
    )
    bx, by, bw, bh = self._back_rect
    img.draw_rect(bx, by, bw, bh, image.Color.from_rgb(40, 40, 40), thickness=-1)
    icon_x = bx + (bw - self._back_image.width()) // 2
    icon_y = by + (bh - self._back_image.height()) // 2
    img.draw_image(icon_x, icon_y, self._back_image)

    # ASCII only: MaixPy default font drops many Unicode glyphs.
    title = "GYRO CALIBRATION"
    title_size = image.string_size(title, scale=1.6, thickness=2)
    img.draw_string(
      (self.width - title_size.width()) // 2, 120, title,
      image.COLOR_WHITE, scale=1.6, thickness=2,
    )
    hold = "HOLD STILL - DO NOT MOVE"
    hold_size = image.string_size(hold, scale=1.4, thickness=2)
    img.draw_string(
      (self.width - hold_size.width()) // 2, 180, hold,
      image.Color.from_rgb(255, 220, 60), scale=1.4, thickness=2,
    )

    pct = max(0.0, min(1.0, float(imu_snapshot.calib_progress)))
    pct_label = f"{int(pct * 100)}%"
    pct_size = image.string_size(pct_label, scale=2.0, thickness=2)
    img.draw_string(
      (self.width - pct_size.width()) // 2, 250, pct_label,
      image.COLOR_WHITE, scale=2.0, thickness=2,
    )

    bar_x = 32
    bar_w = self.width - 64
    bar_y = 320
    bar_h = 36
    img.draw_rect(bar_x, bar_y, bar_w, bar_h, image.Color.from_rgb(50, 50, 50), thickness=-1)
    img.draw_rect(bar_x, bar_y, bar_w, bar_h, image.COLOR_WHITE, thickness=3)
    fill = int((bar_w - 8) * pct)
    if fill > 0:
      img.draw_rect(
        bar_x + 4, bar_y + 4, fill, bar_h - 8,
        image.Color.from_rgb(40, 200, 80), thickness=-1,
      )

    tip = "Motors stopped  Xbox ignored"
    tip_size = image.string_size(tip, scale=1.2, thickness=2)
    img.draw_string(
      (self.width - tip_size.width()) // 2, 380, tip,
      image.Color.from_rgb(200, 200, 200), scale=1.2, thickness=2,
    )
