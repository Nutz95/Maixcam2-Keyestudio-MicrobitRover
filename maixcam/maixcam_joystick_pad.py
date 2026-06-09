"""
Pad tactile MaixCam pour piloter le rover via CMD_JOYSTICK (0x30).

- Rectangle central = zone de pilotage analogique
- Haut = avant, bas = arriere, gauche/droite = strafe
- Relacher le doigt = STOP
"""

from maix import app, display, image, touchscreen, uart, pinmap, err, sys, time

PROTO_SYNC = 0xAA
CMD_JOYSTICK = 0x30
DEFAULT_SPEED = 100

SCR_W = 640
SCR_H = 480
PAD_MARGIN_X = 90
PAD_TOP = 70
PAD_W = SCR_W - (PAD_MARGIN_X * 2)
PAD_H = SCR_H - PAD_TOP - 70
AXIS_MAX = 32767


def init_uart():
    if sys.device_id() == "maixcam2":
        pins = {"A21": "UART4_TX", "A22": "UART4_RX"}
        device = "/dev/ttyS4"
    else:
        pins = {"A16": "UART0_TX", "A17": "UART0_RX"}
        device = "/dev/ttyS0"

    for pin, func in pins.items():
        err.check_raise(pinmap.set_pin_function(pin, func),
                        f"Failed set pin {pin} to {func}")
    return uart.UART(device, 115200)


def build_joystick_frame(axis_x, axis_y, speed):
    axis_x = max(-32768, min(32767, int(axis_x)))
    axis_y = max(-32768, min(32767, int(axis_y)))
    speed = max(0, min(255, int(speed)))
    payload = (
        axis_x.to_bytes(2, "little", signed=True)
        + axis_y.to_bytes(2, "little", signed=True)
        + bytes([speed])
    )
    frame = bytes([PROTO_SYNC, CMD_JOYSTICK]) + payload
    return frame + bytes([sum(frame) & 0xFF])


def build_stop_frame():
    return build_joystick_frame(0, 0, 0)


class RoverUart:
    def __init__(self, serial, speed=DEFAULT_SPEED):
        self.serial = serial
        self.speed = speed
        self.last_ack = ""

    def send_joystick(self, axis_x, axis_y):
        frame = build_joystick_frame(axis_x, axis_y, self.speed)
        self.serial.write(frame)
        self.last_ack = self._read_ack()
        return frame

    def send_stop(self):
        frame = build_stop_frame()
        self.serial.write(frame)
        self.last_ack = self._read_ack()
        return frame

    def _read_ack(self):
        buf = bytearray()
        deadline = time.ticks_ms() + 120
        while time.ticks_ms() < deadline:
            data = self.serial.read()
            if data:
                buf.extend(data)
                if len(buf) >= 2:
                    return f"{buf[0]:02X} {buf[1]:02X}"
            time.sleep_ms(2)
        return ""


def get_back_btn(width):
    img = image.load("/maixapp/share/icon/ret.png")
    w = int(width * 0.1)
    h = img.height() * w // img.width()
    if w % 2:
        w += 1
    if h % 2:
        h += 1
    return img.resize(w, h)


def in_rect(x, y, rect):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def touch_to_axes(x, y, pad_rect):
    cx = pad_rect[0] + pad_rect[2] // 2
    cy = pad_rect[1] + pad_rect[3] // 2
    rx = max(1, pad_rect[2] // 2 - 12)
    ry = max(1, pad_rect[3] // 2 - 12)

    dx = max(-1.0, min(1.0, (x - cx) / rx))
    dy = max(-1.0, min(1.0, (y - cy) / ry))

    axis_x = int(dx * AXIS_MAX)
    axis_y = int(dy * AXIS_MAX)
    return axis_x, axis_y


def draw_pad(img, pad_rect, axis_x, axis_y, touching):
    border = image.Color.from_rgb(80, 180, 255)
    fill = image.Color.from_rgb(20, 35, 55)
    img.draw_rect(pad_rect[0], pad_rect[1], pad_rect[2], pad_rect[3], fill, thickness=-1)
    img.draw_rect(pad_rect[0], pad_rect[1], pad_rect[2], pad_rect[3], border, thickness=3)

    cx = pad_rect[0] + pad_rect[2] // 2
    cy = pad_rect[1] + pad_rect[3] // 2
    img.draw_line(pad_rect[0], cy, pad_rect[0] + pad_rect[2], cy, image.COLOR_GRAY, thickness=1)
    img.draw_line(cx, pad_rect[1], cx, pad_rect[1] + pad_rect[3], image.COLOR_GRAY, thickness=1)

    img.draw_string(pad_rect[0] + 8, pad_rect[1] + 8, "AVANT", image.COLOR_WHITE, scale=1.2)
    img.draw_string(pad_rect[0] + 8, pad_rect[1] + pad_rect[3] - 24, "ARRIERE", image.COLOR_WHITE, scale=1.2)

    if touching:
        dot_x = cx + int((axis_x / AXIS_MAX) * (pad_rect[2] // 2 - 16))
        dot_y = cy + int((axis_y / AXIS_MAX) * (pad_rect[3] // 2 - 16))
        img.draw_circle(dot_x, dot_y, 14, image.Color.from_rgb(255, 120, 40), thickness=-1)
        img.draw_circle(dot_x, dot_y, 14, image.COLOR_WHITE, thickness=2)


def main():
    disp = display.Display()
    ts = touchscreen.TouchScreen()
    serial = init_uart()
    rover = RoverUart(serial)

    img_back = get_back_btn(SCR_W)
    back_rect = [4, 4, img_back.width(), img_back.height()]
    pad_rect = [PAD_MARGIN_X, PAD_TOP, PAD_W, PAD_H]

    axis_x = 0
    axis_y = 0
    touching = False
    was_touching = False
    send_ms = 0

    while not app.need_exit():
        img = image.Image(SCR_W, SCR_H, bg=image.COLOR_BLACK)
        img.draw_image(back_rect[0], back_rect[1], img_back)
        img.draw_string(110, 12, "Rover joystick pad", image.COLOR_WHITE, scale=2)
        draw_pad(img, pad_rect, axis_x, axis_y, touching)

        status = f"X={axis_x:6d}  Y={axis_y:6d}  SPD={rover.speed}"
        if rover.last_ack:
            status += f"  ACK={rover.last_ack}"
        img.draw_string(8, SCR_H - 24, status, image.COLOR_YELLOW, scale=1.2)
        disp.show(img)

        x, y, pressed = ts.read()

        if pressed and in_rect(x, y, back_rect):
            rover.send_stop()
            app.set_exit_flag(True)
            break

        touching = pressed and in_rect(x, y, pad_rect)
        if touching:
            axis_x, axis_y = touch_to_axes(x, y, pad_rect)
        elif was_touching:
            axis_x = 0
            axis_y = 0
            rover.send_stop()

        now = time.ticks_ms()
        if touching and now - send_ms >= 50:
            rover.send_joystick(axis_x, axis_y)
            send_ms = now

        was_touching = touching
        time.sleep_ms(15)

    rover.send_stop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        msg = traceback.format_exc()
        print(msg)
        disp = display.Display()
        img = image.Image(disp.width(), disp.height(), bg=image.COLOR_BLACK)
        img.draw_string(0, 0, msg, image.COLOR_WHITE, scale=1.2)
        disp.show(img)
        while not app.need_exit():
            time.sleep_ms(100)
