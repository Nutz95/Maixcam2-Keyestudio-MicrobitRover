from maix import image


class UiDrawer:
  """Xbox -> Rover UI (portrait 480x640)."""

  def __init__(self, width, height):
    self.width = width
    self.height = height
    self._img_back = self._load_back_btn(width)
    self._layout_buttons()

  def _layout_buttons(self):
    y = self.height - 58
    gap = 12
    half_w = (self.width - gap * 3) // 2
    self._pair_rect = [gap, y, half_w, 48]
    self._connect_rect = [gap * 2 + half_w, y, half_w, 48]
    # Top-right: away from CONNECT at bottom (avoids accidental double-tap)
    self._disconnect_rect = [self.width - 128, 38, 116, 40]

  def back_rect(self):
    img = self._img_back
    return [4, 4, img.width(), img.height()]

  def pair_rect(self):
    return list(self._pair_rect)

  def connect_rect(self):
    return list(self._connect_rect)

  def disconnect_rect(self):
    return list(self._disconnect_rect)

  def draw_frame(self, status, connected, busy, state, drive, speed, ack):
    img = image.Image(self.width, self.height, bg=image.COLOR_BLACK)
    img.draw_image(4, 4, self._img_back)
    title_x = max(72, self.width // 6)
    img.draw_string(title_x, 10, "Xbox -> Rover", image.COLOR_WHITE, scale=1.8)

    if connected:
      self._draw_button(img, self.disconnect_rect(), "DISC", image.Color.from_rgb(180, 60, 40))

    color = image.Color.from_rgb(80, 220, 120) if connected else image.COLOR_YELLOW
    img.draw_string(12, 52, status, color, scale=1.3)

    if connected:
      gauge_cy = self.height // 2 + 8
      radius = min(68, (self.width - 130) // 4)
      bar_h = radius * 2 + 8
      bar_y = gauge_cy - bar_h // 2
      left_cx = self.width // 4 + 8
      right_cx = self.width - self.width // 4 - 8

      self._draw_gauge(
        img, left_cx, gauge_cy, state.left_x, state.left_y, radius=radius, label="L",
      )
      self._draw_gauge(
        img, right_cx, gauge_cy, state.right_x, state.right_y, radius=radius, label="R",
      )
      self._draw_trigger_bar(
        img, 8, bar_y, 32, bar_h, state.lt, "LT", image.Color.from_rgb(60, 120, 220),
      )
      self._draw_trigger_bar(
        img, self.width - 40, bar_y, 32, bar_h, state.rt, "RT",
        image.Color.from_rgb(220, 100, 60),
      )
      mode = "MIX"
      if drive is not None and drive.preset_cmd is not None:
        mode = "PRESET"
      img.draw_string(12, 92, f"Mode: {mode}", image.COLOR_WHITE, scale=1.2)
    elif busy:
      img.draw_string(12, 92, "Please wait...", image.COLOR_GRAY, scale=1.2)
      self._draw_button(img, self.pair_rect(), "...", image.Color.from_rgb(80, 80, 80))
      self._draw_button(img, self.connect_rect(), "...", image.Color.from_rgb(80, 80, 80))
    else:
      img.draw_string(12, 92, "Sync -> PAIR then CONNECT", image.COLOR_WHITE, scale=1.2)
      self._draw_button(img, self.pair_rect(), "PAIR", image.Color.from_rgb(40, 80, 160))
      self._draw_button(img, self.connect_rect(), "CONNECT", image.Color.from_rgb(40, 120, 60))

    eff = speed
    sx = sy = sr = 0
    if drive is not None:
      sx = drive.axis_x
      sy = drive.axis_y
      sr = drive.axis_rot
      mag = max(abs(sx), abs(sy), abs(sr))
      eff = int(speed * mag / 32767) if mag > 0 else 0
    line = f"F={sy:4d} C={sx:4d} R={sr:4d} ~{eff}"
    if ack:
      line += f" ACK={ack}"
    img.draw_string(6, self.height - 22, line, image.COLOR_YELLOW, scale=1.0)
    return img

  def _draw_gauge(self, img, cx, cy, axis_x, axis_y, radius=68, label=""):
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(60, 60, 80), thickness=2)
    dx = int((axis_x / 32767.0) * (radius - 10))
    dy = int((axis_y / 32767.0) * (radius - 10))
    img.draw_circle(cx + dx, cy + dy, 11, image.Color.from_rgb(255, 140, 40), thickness=-1)
    if label:
      size = image.string_size(label, scale=1.0, thickness=1)
      img.draw_string(cx - size.width() // 2, cy - radius - 16, label, image.COLOR_WHITE, scale=1.0)

  def _draw_trigger_bar(self, img, x, y, w, h, value, label, color):
    img.draw_rect(x, y, w, h, image.Color.from_rgb(40, 40, 50), thickness=-1)
    img.draw_rect(x, y, w, h, image.COLOR_WHITE, thickness=2)
    mag = min(32767, abs(int(value)))
    fill_h = int((mag / 32767.0) * (h - 6))
    if fill_h > 0:
      fy = y + h - 3 - fill_h
      img.draw_rect(x + 3, fy, w - 6, fill_h, color, thickness=-1)
    size = image.string_size(label, scale=1.1, thickness=1)
    img.draw_string(x + (w - size.width()) // 2, y + h + 4, label, image.COLOR_WHITE, scale=1.1)

  def _draw_button(self, img, rect, label, color):
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], color, thickness=-1)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], image.COLOR_WHITE, thickness=2)
    size = image.string_size(label, scale=1.2, thickness=1)
    tx = rect[0] + (rect[2] - size.width()) // 2
    ty = rect[1] + (rect[3] - size.height()) // 2
    img.draw_string(tx, ty, label, image.COLOR_WHITE, scale=1.2)

  def _load_back_btn(self, width):
    img = image.load("/maixapp/share/icon/ret.png")
    w = max(40, int(width * 0.12))
    h = img.height() * w // img.width()
    if w % 2:
      w += 1
    if h % 2:
      h += 1
    return img.resize(w, h)
