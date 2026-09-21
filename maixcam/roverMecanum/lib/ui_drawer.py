from maix import image

from lib.ball_follow_snapshot import BallFollowSnapshot


class UiDrawer:
  """Full-screen HUD overlay (480x640 portrait) for camera + controller state."""

  SPEED_BAR_H = 22

  def __init__(self, width, height):
    self.width = width
    self.height = height
    self._img_back = self._load_back_btn(width)
    self._layout_buttons()

  def _layout_buttons(self):
    pad = 8
    back_size = 44
    self._back_pad = [pad, pad, back_size, back_size]
    # Always-available gyro calib (top-right; works before Xbox connect).
    gyro_w = 96
    self._gyro_top_rect = [self.width - pad - gyro_w, pad, gyro_w, back_size]
    # Finger-sized (MaixAiRover): ~72 px tall, full bottom half-width each.
    btn_h = 72
    gap = 12
    y = self.height - btn_h - 10
    half_w = (self.width - gap * 3) // 2
    self._pair_rect = [gap, y, half_w, btn_h]
    self._connect_rect = [gap * 2 + half_w, y, half_w, btn_h]
    self._disconnect_rect = [gap, y, half_w, btn_h]
    self._gyro_rect = [gap * 2 + half_w, y, half_w, btn_h]
    self._bottom_bar_top = y - 10

  def back_rect(self):
    return list(self._back_pad)

  def pair_rect(self):
    return list(self._pair_rect)

  def connect_rect(self):
    return list(self._connect_rect)

  def disconnect_rect(self):
    return list(self._disconnect_rect)

  def gyro_rect(self):
    return list(self._gyro_rect)

  def gyro_top_rect(self):
    return list(self._gyro_top_rect)

  def draw_overlay(
    self,
    img,
    connected,
    busy,
    state,
    drive,
    max_speed=255,
    status="",
    progress=0.0,
    ball_snapshot=None,
    imu_snapshot=None,
  ):
    """Draw HUD: speed bar, sticks, triggers, d-pad, pairing progress, buttons."""
    bx, by, bw, bh = self._back_pad
    img.draw_rect(bx, by, bw, bh, image.Color.from_rgb(0, 0, 0), thickness=-1)
    icon_x = bx + (bw - self._img_back.width()) // 2
    icon_y = by + (bh - self._img_back.height()) // 2
    img.draw_image(icon_x, icon_y, self._img_back)

    calibrating = imu_snapshot is not None and imu_snapshot.calibrating
    if calibrating:
      self._draw_gyro_calib_overlay(img, imu_snapshot)
      return

    self._draw_gyro_button(img, self.gyro_top_rect(), imu_snapshot, compact=True)

    if connected:
      self._draw_bottom_bar(img)
      self._draw_button(img, self.disconnect_rect(), "DISCONNECT", image.Color.from_rgb(180, 60, 40))
      self._draw_gyro_button(img, self.gyro_rect(), imu_snapshot, compact=False)
      lb = state.buttons.get("btn_lb", False)
      rb = state.buttons.get("btn_rb", False)
      self._draw_speed_bar(img, max_speed, lb, rb)

      show_joystick = ball_snapshot is None or not ball_snapshot.enabled
      if show_joystick:
        gauge_cy = self.height // 2 - 20
        radius = min(68, (self.width - 120) // 4)
        bar_h = radius * 2 + 6
        bar_y = gauge_cy - bar_h // 2
        left_cx = self.width // 4 + 4
        right_cx = self.width - self.width // 4 - 4

        self._draw_gauge(
          img, left_cx, gauge_cy, state.left_x, state.left_y, radius=radius, label="L",
        )
        self._draw_gauge(
          img, right_cx, gauge_cy, state.right_x, state.right_y, radius=radius, label="R",
        )
        self._draw_trigger_bar(
          img, 6, bar_y, 26, bar_h, state.lt, "LT", image.Color.from_rgb(60, 120, 220),
        )
        self._draw_trigger_bar(
          img, self.width - 32, bar_y, 26, bar_h, state.rt, "RT",
          image.Color.from_rgb(220, 100, 60),
        )
        self._draw_dpad(img, self.width // 2, gauge_cy + radius + 28, state.dpad_x, state.dpad_y)
    elif busy:
      self._draw_bottom_bar(img)
      self._draw_progress(img, status, progress)
      self._draw_button(img, self.pair_rect(), "...", image.Color.from_rgb(80, 80, 80))
      self._draw_button(img, self.connect_rect(), "...", image.Color.from_rgb(80, 80, 80))
    else:
      self._draw_bottom_bar(img)
      self._draw_button(img, self.pair_rect(), "PAIR", image.Color.from_rgb(40, 80, 160))
      self._draw_button(img, self.connect_rect(), "CONNECT", image.Color.from_rgb(40, 120, 60))
    if ball_snapshot is not None:
      self._draw_ball_status(img, ball_snapshot)
      self._draw_ball_observation(img, ball_snapshot)
    if imu_snapshot is not None:
      self._draw_imu_status(img, imu_snapshot)

  def _draw_ball_status(self, img, ball_snapshot: BallFollowSnapshot):
    """Draw a large, high-contrast permanent control-mode indicator."""
    label = ball_snapshot.mode_label
    if not ball_snapshot.enabled:
      background = image.Color.from_rgb(70, 70, 70)
    elif ball_snapshot.color == "red":
      background = image.Color.from_rgb(160, 40, 40)
    else:
      background = image.Color.from_rgb(20, 120, 60)
    size = image.string_size(label, scale=1.4, thickness=2)
    x = 60
    y = 8
    img.draw_rect(x, y, size.width() + 16, size.height() + 12, background, thickness=-1)
    img.draw_rect(x, y, size.width() + 16, size.height() + 12, image.COLOR_WHITE, thickness=2)
    img.draw_string(x + 8, y + 6, label, image.COLOR_WHITE, scale=1.4, thickness=2)

  def _draw_gyro_button(self, img, rect, imu_snapshot, compact=False):
    """GYRO calib control; color reflects calibration state."""
    if imu_snapshot is None:
      color = image.Color.from_rgb(80, 80, 80)
      label = "GYRO"
    elif imu_snapshot.calibrating:
      color = image.Color.from_rgb(180, 120, 20)
      label = "HOLD" if compact else "HOLD STILL"
    elif imu_snapshot.calibrated:
      color = image.Color.from_rgb(40, 120, 60)
      label = "GYRO"
    elif imu_snapshot.status in ("no_imu", "disabled"):
      color = image.Color.from_rgb(80, 80, 80)
      label = "GYRO"
    else:
      color = image.Color.from_rgb(160, 80, 20)
      label = "GYRO"
    self._draw_button(img, rect, label, color)

  def _draw_imu_status(self, img, imu_snapshot):
    """Compact yaw / calib line under the speed bar, top-right."""
    if imu_snapshot.yaw_deg is not None and imu_snapshot.calibrated:
      text = f"YAW {imu_snapshot.yaw_deg:.0f}"
    else:
      text = f"IMU {imu_snapshot.status}"
    size = image.string_size(text, scale=1.0)
    x = max(8, self.width - size.width() - 8)
    img.draw_string(x, 78, text, image.COLOR_WHITE, scale=1.0)

  def _draw_gyro_calib_overlay(self, img, imu_snapshot):
    """Fullscreen calib UI: hide sticks, show hold-still + timed progress."""
    img.draw_rect(
      0, 0, self.width, self.height,
      image.Color.from_rgb(0, 0, 0), thickness=-1,
    )
    bx, by, bw, bh = self._back_pad
    img.draw_rect(bx, by, bw, bh, image.Color.from_rgb(40, 40, 40), thickness=-1)
    icon_x = bx + (bw - self._img_back.width()) // 2
    icon_y = by + (bh - self._img_back.height()) // 2
    img.draw_image(icon_x, icon_y, self._img_back)

    # ASCII only: MaixPy default font drops many Unicode glyphs.
    title = "GYRO CALIBRATION"
    title_size = image.string_size(title, scale=1.6, thickness=2)
    img.draw_string(
      (self.width - title_size.width()) // 2,
      120,
      title,
      image.COLOR_WHITE,
      scale=1.6,
      thickness=2,
    )
    hold = "HOLD STILL - DO NOT MOVE"
    hold_size = image.string_size(hold, scale=1.4, thickness=2)
    img.draw_string(
      (self.width - hold_size.width()) // 2,
      180,
      hold,
      image.Color.from_rgb(255, 220, 60),
      scale=1.4,
      thickness=2,
    )

    pct = max(0.0, min(1.0, float(imu_snapshot.calib_progress)))
    pct_label = f"{int(pct * 100)}%"
    pct_size = image.string_size(pct_label, scale=2.0, thickness=2)
    img.draw_string(
      (self.width - pct_size.width()) // 2,
      250,
      pct_label,
      image.COLOR_WHITE,
      scale=2.0,
      thickness=2,
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
      (self.width - tip_size.width()) // 2,
      380,
      tip,
      image.Color.from_rgb(200, 200, 200),
      scale=1.2,
      thickness=2,
    )

  def _draw_ball_observation(self, img, ball_snapshot: BallFollowSnapshot):
    """Draw the selected blob, its recent trajectory, and policy reason."""
    if not ball_snapshot.enabled:
      return
    self._draw_ball_trajectory(img, ball_snapshot)
    observation = ball_snapshot.observation
    box_color = (
      image.Color.from_rgb(240, 80, 80)
      if ball_snapshot.color == "red"
      else image.Color.from_rgb(80, 220, 80)
    )
    if observation is None:
      img.draw_string(
        8,
        80,
        f"BALL {ball_snapshot.command.reason}",
        box_color,
        scale=1.1,
      )
      return
    scale_x = img.width() / max(1, observation.image_width)
    scale_y = img.height() / max(1, observation.image_height)
    left = int((observation.center_x - observation.width // 2) * scale_x)
    top = int((observation.center_y - observation.height // 2) * scale_y)
    width = max(1, int(observation.width * scale_x))
    height = max(1, int(observation.height * scale_y))
    img.draw_rect(
      left,
      top,
      width,
      height,
      box_color,
      thickness=3,
    )
    img.draw_circle(
      int(observation.center_x * scale_x),
      int(observation.center_y * scale_y),
      4,
      image.Color.from_rgb(255, 255, 255),
      thickness=-1,
    )
    img.draw_string(
      8,
      80,
      f"BALL {ball_snapshot.command.reason}",
      box_color,
      scale=1.1,
    )

  def _draw_ball_trajectory(self, img, ball_snapshot: BallFollowSnapshot):
    """Draw the recent center path behind the current bounding box."""
    previous_x = None
    previous_y = None
    for point in ball_snapshot.trajectory:
      scale_x = img.width() / max(1, point.image_width)
      scale_y = img.height() / max(1, point.image_height)
      point_x = int(point.center_x * scale_x)
      point_y = int(point.center_y * scale_y)
      if previous_x is not None and previous_y is not None:
        img.draw_line(
          previous_x,
          previous_y,
          point_x,
          point_y,
          image.Color.from_rgb(255, 180, 40),
          thickness=2,
        )
      img.draw_circle(
        point_x,
        point_y,
        3,
        image.Color.from_rgb(255, 180, 40),
        thickness=-1,
      )
      previous_x = point_x
      previous_y = point_y

  def _draw_progress(self, img, status, progress):
    """Show pairing/connect status text and a simple progress bar."""
    pct = max(0.0, min(1.0, float(progress)))
    bar_x = 24
    bar_w = self.width - 48
    bar_y = self.height // 2 - 10
    bar_h = 18
    label = status or "Working..."
    size = image.string_size(label, scale=1.1, thickness=1)
    img.draw_string(
      (self.width - size.width()) // 2,
      bar_y - 28,
      label,
      image.COLOR_WHITE,
      scale=1.1,
    )
    img.draw_rect(bar_x, bar_y, bar_w, bar_h, image.Color.from_rgb(30, 30, 30), thickness=-1)
    img.draw_rect(bar_x, bar_y, bar_w, bar_h, image.COLOR_WHITE, thickness=1)
    fill = int((bar_w - 4) * pct)
    if fill > 0:
      img.draw_rect(
        bar_x + 2, bar_y + 2, fill, bar_h - 4,
        image.Color.from_rgb(60, 160, 220), thickness=-1,
      )

  def _draw_speed_bar(self, img, max_speed, lb_pressed, rb_pressed):
    """Top horizontal max-speed gauge; LB/RB adjust speed in the app loop."""
    y = 52
    x = 54
    w = self.width - 108
    h = self.SPEED_BAR_H
    pct = max(0, min(100, int(round(max_speed * 100 / 255))))

    img.draw_rect(x, y, w, h, image.Color.from_rgb(20, 20, 20), thickness=-1)
    img.draw_rect(x, y, w, h, image.COLOR_WHITE, thickness=1)
    fill_w = max(0, int(w * pct / 100))
    if fill_w > 0:
      img.draw_rect(x + 1, y + 1, fill_w - 2, h - 2, image.Color.from_rgb(40, 180, 90), thickness=-1)

    label = f"SPD {pct}%"
    size = image.string_size(label, scale=1.0, thickness=1)
    img.draw_string(x + (w - size.width()) // 2, y + 4, label, image.COLOR_WHITE, scale=1.0)

    lb_c = image.Color.from_rgb(80, 200, 100) if lb_pressed else image.Color.from_rgb(35, 35, 35)
    rb_c = image.Color.from_rgb(80, 200, 100) if rb_pressed else image.Color.from_rgb(35, 35, 35)
    img.draw_rect(x - 30, y + 2, 26, h - 4, lb_c, thickness=-1)
    img.draw_rect(x + w + 4, y + 2, 26, h - 4, rb_c, thickness=-1)
    img.draw_string(x - 26, y + 5, "LB", image.COLOR_WHITE, scale=0.85)
    img.draw_string(x + w + 8, y + 5, "RB", image.COLOR_WHITE, scale=0.85)

  def _draw_bottom_bar(self, img):
    y = self._bottom_bar_top
    img.draw_rect(0, y, self.width, self.height - y, image.Color.from_rgb(0, 0, 0), thickness=-1)

  def _draw_button(self, img, rect, label, color):
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], color, thickness=-1)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], image.COLOR_WHITE, thickness=2)
    scale = 1.4 if rect[3] >= 64 else 1.1
    size = image.string_size(label, scale=scale, thickness=1)
    tx = rect[0] + (rect[2] - size.width()) // 2
    ty = rect[1] + (rect[3] - size.height()) // 2
    img.draw_string(tx, ty, label, image.COLOR_WHITE, scale=scale)

  def _draw_gauge(self, img, cx, cy, axis_x, axis_y, radius=72, label=""):
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(40, 40, 40), thickness=2)
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(200, 200, 200), thickness=1)
    dx = int((axis_x / 32767.0) * (radius - 10))
    dy = int((axis_y / 32767.0) * (radius - 10))
    img.draw_circle(cx + dx, cy + dy, 10, image.Color.from_rgb(255, 140, 40), thickness=-1)
    if label:
      size = image.string_size(label, scale=1.0, thickness=1)
      img.draw_string(cx - size.width() // 2, cy - radius - 14, label, image.COLOR_WHITE, scale=1.0)

  def _draw_dpad(self, img, cx, cy, dx, dy):
    r = 7
    gap = 14
    dim = image.Color.from_rgb(30, 30, 30)
    on = image.Color.from_rgb(255, 180, 40)
    dirs = [
      (0, -gap, dy < 0 and dx == 0),
      (0, gap, dy > 0 and dx == 0),
      (-gap, 0, dx < 0 and dy == 0),
      (gap, 0, dx > 0 and dy == 0),
      (-gap, -gap, dy < 0 and dx < 0),
      (gap, -gap, dy < 0 and dx > 0),
      (-gap, gap, dy > 0 and dx < 0),
      (gap, gap, dy > 0 and dx > 0),
    ]
    for ox, oy, active in dirs:
      color = on if active else dim
      img.draw_circle(cx + ox, cy + oy, r, color, thickness=-1)

  def _draw_trigger_bar(self, img, x, y, w, h, value, label, color):
    img.draw_rect(x, y, w, h, image.Color.from_rgb(30, 30, 30), thickness=-1)
    img.draw_rect(x, y, w, h, image.COLOR_WHITE, thickness=1)
    mag = min(32767, abs(int(value)))
    fill_h = int((mag / 32767.0) * (h - 6))
    if fill_h > 0:
      fy = y + h - 3 - fill_h
      img.draw_rect(x + 3, fy, w - 6, fill_h, color, thickness=-1)
    size = image.string_size(label, scale=1.0, thickness=1)
    img.draw_string(x + (w - size.width()) // 2, y + h + 2, label, image.COLOR_WHITE, scale=1.0)

  def _load_back_btn(self, width):
    img = image.load("/maixapp/share/icon/ret.png")
    w = 28
    h = img.height() * w // img.width()
    if w % 2:
      w += 1
    if h % 2:
      h += 1
    return img.resize(w, h)
