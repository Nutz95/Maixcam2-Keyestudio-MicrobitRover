from maix import image


class UiDrawer:
  """HUD minimaliste par-dessus la video plein ecran (480x640 portrait)."""

  def __init__(self, width, height):
    self.width = width
    self.height = height
    self._img_back = self._load_back_btn(width)
    self._layout_buttons()

  def _layout_buttons(self):
    pad = 8
    back_size = 44
    self._back_pad = [pad, pad, back_size, back_size]
    disc_w, disc_h = 52, 32
    self._disconnect_rect = [self.width - disc_w - pad, pad, disc_w, disc_h]
    y = self.height - 52
    gap = 10
    half_w = (self.width - gap * 3) // 2
    self._pair_rect = [gap, y, half_w, 44]
    self._connect_rect = [gap * 2 + half_w, y, half_w, 44]

  def back_rect(self):
    return list(self._back_pad)

  def pair_rect(self):
    return list(self._pair_rect)

  def connect_rect(self):
    return list(self._connect_rect)

  def disconnect_rect(self):
    return list(self._disconnect_rect)

  def draw_overlay(self, img, connected, busy, state, drive):
    bx, by, bw, bh = self._back_pad
    img.draw_rect(bx, by, bw, bh, image.Color.from_rgb(0, 0, 0), thickness=-1)
    icon_x = bx + (bw - self._img_back.width()) // 2
    icon_y = by + (bh - self._img_back.height()) // 2
    img.draw_image(icon_x, icon_y, self._img_back)

    if connected:
      self._draw_button(img, self.disconnect_rect(), "DISC", image.Color.from_rgb(180, 60, 40))
      gauge_cy = self.height // 2
      radius = min(72, (self.width - 120) // 4)
      bar_h = radius * 2 + 6
      bar_y = gauge_cy - bar_h // 2
      left_cx = self.width // 4 + 4
      right_cx = self.width - self.width // 4 - 4

      self._draw_bumper(img, 6, bar_y - 16, state.buttons.get("btn_lb", False), "LB")
      self._draw_bumper(img, self.width - 34, bar_y - 16, state.buttons.get("btn_rb", False), "RB")

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
      self._draw_button(img, self.pair_rect(), "...", image.Color.from_rgb(80, 80, 80))
      self._draw_button(img, self.connect_rect(), "...", image.Color.from_rgb(80, 80, 80))
    else:
      self._draw_bottom_bar(img)
      self._draw_button(img, self.pair_rect(), "PAIR", image.Color.from_rgb(40, 80, 160))
      self._draw_button(img, self.connect_rect(), "CONNECT", image.Color.from_rgb(40, 120, 60))

  def _draw_bottom_bar(self, img):
    y = self.height - 58
    img.draw_rect(0, y - 6, self.width, 58, image.Color.from_rgb(0, 0, 0), thickness=-1)

  def _draw_gauge(self, img, cx, cy, axis_x, axis_y, radius=72, label=""):
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(40, 40, 40), thickness=2)
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(200, 200, 200), thickness=1)
    dx = int((axis_x / 32767.0) * (radius - 10))
    dy = int((axis_y / 32767.0) * (radius - 10))
    img.draw_circle(cx + dx, cy + dy, 10, image.Color.from_rgb(255, 140, 40), thickness=-1)
    if label:
      size = image.string_size(label, scale=1.0, thickness=1)
      img.draw_string(cx - size.width() // 2, cy - radius - 14, label, image.COLOR_WHITE, scale=1.0)

  def _draw_bumper(self, img, x, y, pressed, label):
    color = image.Color.from_rgb(80, 200, 100) if pressed else image.Color.from_rgb(30, 30, 30)
    img.draw_rect(x, y, 28, 14, color, thickness=-1)
    img.draw_rect(x, y, 28, 14, image.COLOR_WHITE, thickness=1)
    size = image.string_size(label, scale=0.9, thickness=1)
    img.draw_string(x + (28 - size.width()) // 2, y + 1, label, image.COLOR_WHITE, scale=0.9)

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

  def _draw_button(self, img, rect, label, color):
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], color, thickness=-1)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], image.COLOR_WHITE, thickness=2)
    size = image.string_size(label, scale=1.1, thickness=1)
    tx = rect[0] + (rect[2] - size.width()) // 2
    ty = rect[1] + (rect[3] - size.height()) // 2
    img.draw_string(tx, ty, label, image.COLOR_WHITE, scale=1.1)

  def _load_back_btn(self, width):
    img = image.load("/maixapp/share/icon/ret.png")
    w = 28
    h = img.height() * w // img.width()
    if w % 2:
      w += 1
    if h % 2:
      h += 1
    return img.resize(w, h)
