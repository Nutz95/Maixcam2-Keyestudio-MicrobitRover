"""
UI tactile MaixCam pour tester le rover micro:bit (protocole binaire UART).

Copier sur le MaixCam et lancer depuis l'app MaixPy.
Branchement maixcam2 : A21=TX, A22=RX -> micro:bit P2(RX), P1(TX), GND commun.
"""

from maix import app, display, image, touchscreen, uart, pinmap, err, sys, time

PROTO_SYNC = 0xAA
PROTO_ACK = 0x55

CMD_STOP = 0x00
CMD_FORWARD = 0x01
CMD_BACKWARD = 0x02
CMD_STRAFE_LEFT = 0x03
CMD_STRAFE_RIGHT = 0x04
CMD_DIAG_FL = 0x05
CMD_DIAG_FR = 0x06
CMD_DIAG_BL = 0x07
CMD_DIAG_BR = 0x08
CMD_SPIN_LEFT = 0x09
CMD_SPIN_RIGHT = 0x0A
CMD_PIVOT_RIGHT = 0x0B
CMD_PIVOT_REAR = 0x0C

SCR_W = 640
SCR_H = 480
DEFAULT_SPEED = 100


def checksum3(b0, b1, b2):
    return (b0 + b1 + b2) & 0xFF


def build_frame(cmd, speed):
    return bytes([PROTO_SYNC, cmd, speed, checksum3(PROTO_SYNC, cmd, speed)])


def in_rect(x, y, rect):
    return rect[0] <= x < rect[0] + rect[2] and rect[1] <= y < rect[1] + rect[3]


def get_back_btn(width):
    img = image.load("/maixapp/share/icon/ret.png")
    w = int(width * 0.1)
    h = img.height() * w // img.width()
    if w % 2:
        w += 1
    if h % 2:
        h += 1
    return img.resize(w, h)


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


def draw_button(img, rect, label, color, pressed=False):
    fill = image.Color.from_rgb(180, 40, 40) if pressed else color
    border = image.Color.from_rgb(255, 255, 255)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], fill, thickness=-1)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], border, thickness=2)
    size = image.string_size(label, scale=1.5, thickness=1)
    tx = rect[0] + (rect[2] - size.width()) // 2
    ty = rect[1] + (rect[3] - size.height()) // 2
    img.draw_string(tx, ty, label, image.COLOR_WHITE, scale=1.5, thickness=1)


class RoverClient:
    def __init__(self, ser):
        self.ser = ser
        self.speed = DEFAULT_SPEED
        self.last_label = "Pret"
        self.last_ack = ""

    def send_cmd(self, cmd, label):
        spd = 0 if cmd == CMD_STOP else self.speed
        frame = build_frame(cmd, spd)
        self.ser.write(frame)
        self.last_label = label
        self.last_ack = self._read_ack()
        print(f"TX {label}: {' '.join(f'{b:02X}' for b in frame)}")
        if self.last_ack:
            print(f"ACK: {self.last_ack}")

    def _read_ack(self):
        buf = bytearray()
        deadline = time.ticks_ms() + 300
        while time.ticks_ms() < deadline:
            data = self.ser.read()
            if data:
                buf.extend(data)
                if len(buf) >= 2:
                    return f"{buf[0]:02X} {buf[1]:02X}"
            time.sleep_ms(5)
        return ""

    def set_speed(self, speed):
        self.speed = max(0, min(255, speed))


def build_ui():
    buttons = []
    cols = 4
    margin = 8
    top = 75
    btn_w = (SCR_W - margin * (cols + 1)) // cols
    btn_h = 52
    gap = margin

    items = [
        ("STOP", CMD_STOP, image.Color.from_rgb(183, 28, 28)),
        ("Avant", CMD_FORWARD, image.Color.from_rgb(30, 136, 229)),
        ("Arriere", CMD_BACKWARD, image.Color.from_rgb(30, 136, 229)),
        ("Strafe G", CMD_STRAFE_LEFT, image.Color.from_rgb(56, 142, 60)),
        ("Strafe D", CMD_STRAFE_RIGHT, image.Color.from_rgb(56, 142, 60)),
        ("Diag AG", CMD_DIAG_FL, image.Color.from_rgb(0, 150, 136)),
        ("Diag AD", CMD_DIAG_FR, image.Color.from_rgb(0, 150, 136)),
        ("Diag RG", CMD_DIAG_BL, image.Color.from_rgb(0, 121, 107)),
        ("Diag RD", CMD_DIAG_BR, image.Color.from_rgb(0, 121, 107)),
        ("Rot G", CMD_SPIN_LEFT, image.Color.from_rgb(123, 31, 162)),
        ("Rot D", CMD_SPIN_RIGHT, image.Color.from_rgb(123, 31, 162)),
        ("Pivot D", CMD_PIVOT_RIGHT, image.Color.from_rgb(255, 143, 0)),
        ("Pivot Arr", CMD_PIVOT_REAR, image.Color.from_rgb(255, 143, 0)),
    ]

    for i, (label, cmd, color) in enumerate(items):
        row = i // cols
        col = i % cols
        x = margin + col * (btn_w + gap)
        y = top + row * (btn_h + gap)
        buttons.append({
            "label": label,
            "cmd": cmd,
            "color": color,
            "rect": [x, y, btn_w, btn_h],
        })

    speed_down = [640 - 2*130 , SCR_H - 64, 120, 48]
    speed_up = [640 - 130, SCR_H - 64, 120, 48]
    return buttons, speed_down, speed_up


def main():
    disp = display.Display()
    screen = touchscreen.TouchScreen()
    serial = init_uart()
    rover = RoverClient(serial)
    buttons, speed_down, speed_up = build_ui()
    img_back = get_back_btn(SCR_W)
    back_rect = [4, 4, img_back.width(), img_back.height()]

    pressed_id = None
    pressed_aux = None

    while not app.need_exit():
        img = image.Image(SCR_W, SCR_H, bg=image.COLOR_BLACK)
        img.draw_image(back_rect[0], back_rect[1], img_back)
        img.draw_string(110, 12, "Rover micro:bit test", image.COLOR_WHITE, scale=2)

        for i, btn in enumerate(buttons):
            draw_button(img, btn["rect"], btn["label"], btn["color"], pressed_id == i)

        draw_button(img, speed_down, "Vitesse -", image.Color.from_rgb(84, 110, 122), pressed_aux == "down")
        draw_button(img, speed_up, "Vitesse +", image.Color.from_rgb(84, 110, 122), pressed_aux == "up")

        status = f"Derniere: {rover.last_label}  |  Vitesse: {rover.speed}"
        if rover.last_ack:
            status += f"  |  ACK: {rover.last_ack}"
        img.draw_string(8, SCR_H - 24, status, image.COLOR_YELLOW, scale=1.2)

        disp.show(img)

        x, y, pressed = screen.read()

        if pressed:
            if in_rect(x, y, back_rect):
                rover.send_cmd(CMD_STOP, "STOP")
                app.set_exit_flag(True)
            elif in_rect(x, y, speed_down):
                pressed_aux = "down"
            elif in_rect(x, y, speed_up):
                pressed_aux = "up"
            else:
                for i, btn in enumerate(buttons):
                    if in_rect(x, y, btn["rect"]):
                        pressed_id = i
                        break
        else:
            if pressed_id is not None:
                btn = buttons[pressed_id]
                rover.send_cmd(btn["cmd"], btn["label"])
                pressed_id = None
            if pressed_aux == "down":
                rover.set_speed(rover.speed - 10)
                pressed_aux = None
            elif pressed_aux == "up":
                rover.set_speed(rover.speed + 10)
                pressed_aux = None

        time.sleep_ms(20)

    serial.write(build_frame(CMD_STOP, 0))


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
