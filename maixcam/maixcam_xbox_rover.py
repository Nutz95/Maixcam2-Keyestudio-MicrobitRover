"""
MaixCam2 : manette Xbox -> UART rover (CMD_JOYSTICK).

IHM tactile :
  - CONNECT  : bluetoothctl trust/connect puis lecture /dev/input/js0
  - DISCONNECT / retour : stop moteurs
  - Stick gauche Xbox pilote le rover en continu

Sur Linux, quand BlueZ connecte la manette (Connected: yes), le joystick passe
par le noyau (/dev/input/event* ou js*). bleak GATT n'est pas accessible.
"""

import asyncio
import glob
import os
import struct
import subprocess
import threading
import traceback

from maix import app, display, image, touchscreen, uart, pinmap, err, sys, time

try:
    from bleak import BleakClient, BleakScanner
    from bleak.exc import BleakError
except ImportError:
    BleakClient = None

XBOX_ADDRESS = "78:86:2E:97:BD:9C"
DEFAULT_SPEED = 100
SEND_INTERVAL_MS = 50

PROTO_SYNC = 0xAA
CMD_JOYSTICK = 0x30

SCR_W = 640
SCR_H = 480


# --- UART / protocole rover -------------------------------------------------

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


class RoverUart:
    def __init__(self, serial, speed=DEFAULT_SPEED):
        self.serial = serial
        self.speed = speed
        self.last_ack = ""

    def send_joystick(self, axis_x, axis_y):
        frame = build_joystick_frame(axis_x, axis_y, self.speed)
        self.serial.write(frame)
        self.last_ack = self._read_ack()

    def send_stop(self):
        frame = build_joystick_frame(0, 0, 0)
        self.serial.write(frame)
        self.last_ack = self._read_ack()

    def _read_ack(self):
        buf = bytearray()
        deadline = time.ticks_ms() + 80
        while time.ticks_ms() < deadline:
            data = self.serial.read()
            if data:
                buf.extend(data)
                if len(buf) >= 2:
                    return f"{buf[0]:02X} {buf[1]:02X}"
            time.sleep_ms(2)
        return ""


JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80

EV_SYN = 0x00
EV_ABS = 0x03
SYN_REPORT = 0
ABS_X = 0x00
ABS_Y = 0x01

SNAP_DEADZONE = 3500
AXIS_MAX = 32767


def _input_event_struct():
    if struct.calcsize("L") == 8:
        return struct.Struct("QQHHi"), 24
    return struct.Struct("llHHi"), 16


def snap_deadzone(axis_x, axis_y):
    if max(abs(axis_x), abs(axis_y)) <= SNAP_DEADZONE:
        return 0, 0
    return axis_x, axis_y


def read_abs_axis_info(event_path, axis_code):
    base = os.path.basename(event_path)
    for rel in (f"absinfo/{axis_code}", f"absinfo/{axis_code:02x}"):
        root = f"/sys/class/input/{base}/device/{rel}"
        try:
            min_v = int(_read_text(f"{root}/min"))
            max_v = int(_read_text(f"{root}/max"))
            flat = int(_read_text(f"{root}/flat"))
            return min_v, max_v, flat
        except (OSError, ValueError):
            pass
    return 0, 65535, 4096


def _read_text(path):
    with open(path, "r") as f:
        return f.read().strip()


class EvdevStickMapper:
    """Convertit ABS_X/ABS_Y evdev en axes protocol rover (-32768..32767)."""

    def __init__(self, event_path, invert_y=False):
        self.min_x, self.max_x, self.flat_x = read_abs_axis_info(event_path, ABS_X)
        self.min_y, self.max_y, self.flat_y = read_abs_axis_info(event_path, ABS_Y)
        self.invert_y = invert_y
        self.raw_x = (self.min_x + self.max_x) // 2
        self.raw_y = (self.min_y + self.max_y) // 2
        print(
            f"mapper: X[{self.min_x}..{self.max_x}] flat={self.flat_x} "
            f"Y[{self.min_y}..{self.max_y}] flat={self.flat_y} invert_y={invert_y}"
        )

    def _axis_from_raw(self, raw, min_v, max_v, flat, invert):
        center = (min_v + max_v) // 2
        half = max(1, (max_v - min_v) // 2)
        delta = int(raw) - center
        if invert:
            delta = -delta
        if abs(delta) <= flat:
            return 0
        sign = 1 if delta > 0 else -1
        mag = abs(delta) - flat
        span = max(1, half - flat)
        scaled = min(AXIS_MAX, int(mag * AXIS_MAX / span))
        return sign * scaled

    def feed_abs(self, code, value):
        if code == ABS_X:
            self.raw_x = int(value)
        elif code == ABS_Y:
            self.raw_y = int(value)

    def get_axes(self):
        axis_x = self._axis_from_raw(self.raw_x, self.min_x, self.max_x, self.flat_x, False)
        axis_y = self._axis_from_raw(self.raw_y, self.min_y, self.max_y, self.flat_y, self.invert_y)
        return snap_deadzone(axis_x, axis_y)


XBOX_VENDOR_ID = "045e"


def _sysfs_input_field(event_path, field):
    base = os.path.basename(event_path)
    path = f"/sys/class/input/{base}/device/{field}"
    try:
        with open(path, "r") as f:
            return f.read().strip()
    except OSError:
        return ""


def read_input_name(event_path):
    return _sysfs_input_field(event_path, "name")


def read_input_vendor(event_path):
    return _sysfs_input_field(event_path, "id/vendor")


def is_xbox_input(event_path):
    vendor = read_input_vendor(event_path).lower()
    if vendor == XBOX_VENDOR_ID:
        return True
    name = read_input_name(event_path).lower()
    return "xbox" in name or "x-box" in name or ("microsoft" in name and "controller" in name)


def find_js_device():
    devices = sorted(glob.glob("/dev/input/js*"))
    if devices:
        return devices[0]
    return None


def find_xbox_event_device():
    for path in sorted(glob.glob("/dev/input/event*")):
        name = read_input_name(path)
        vendor = read_input_vendor(path)
        print(f"input: {path} vendor={vendor!r} name={name!r}")
        if is_xbox_input(path):
            return path
    return None


def list_input_devices():
    for path in sorted(glob.glob("/dev/input/event*")):
        name = read_input_name(path)
        vendor = read_input_vendor(path)
        print(f"input: {path} vendor={vendor!r} name={name!r}")
    js_list = glob.glob("/dev/input/js*")
    if js_list:
        print("input: js devices:", js_list)


def wait_input_device(timeout_sec=12):
    deadline = time.ticks_ms() + int(timeout_sec * 1000)
    while time.ticks_ms() < deadline:
        js_path = find_js_device()
        if js_path:
            return "js", js_path
        ev_path = find_xbox_event_device()
        if ev_path:
            return "ev", ev_path
        time.sleep_ms(400)
    print("input: peripherique Xbox introuvable")
    list_input_devices()
    return None, None


# --- BLE Xbox (fallback) ----------------------------------------------------

def _uuid_short(uuid_str):
    u = uuid_str.lower().replace("-", "")
    return u[-8:] if len(u) >= 8 else u


def parse_left_stick(data):
    if len(data) < 4:
        return 0, 0
    raw_x = data[0] | (data[1] << 8)
    raw_y = data[2] | (data[3] << 8)
    return raw_x - 32768, raw_y - 32768


def find_hid_notify_char(client):
    for service in client.services:
        if _uuid_short(service.uuid) != "00001812":
            continue
        for char in service.characteristics:
            if "notify" in char.properties and _uuid_short(char.uuid) == "00002a4d":
                return char
        for char in service.characteristics:
            if "notify" in char.properties:
                return char
    return None


def has_hid_service(client):
    for service in client.services:
        if _uuid_short(service.uuid) == "00001812":
            return True
    return False


def dump_services(client, title):
    print(title)
    for service in client.services:
        print(f"  Service {service.uuid}")
        for char in service.characteristics:
            print(f"    Char {char.uuid} [{','.join(char.properties)}]")


class XboxBleBridge:
    def __init__(self, address=XBOX_ADDRESS):
        self.address = address
        self.axis_x = 0
        self.axis_y = 0
        self.status = "Pret"
        self.connected = False
        self.busy = False
        self._stop = threading.Event()
        self._thread = None
        self._loop = None
        self._client = None
        self._input_file = None

    def start_connect(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.busy = True
        self.connected = False
        self.status = "Demarrage..."
        self._thread = threading.Thread(target=self._thread_main, daemon=True)
        self._thread.start()

    def request_stop(self):
        self._stop.set()
        if self._input_file is not None:
            try:
                self._input_file.close()
            except Exception:
                pass
            self._input_file = None
        if self._loop is not None:
            try:
                asyncio.run_coroutine_threadsafe(self._async_disconnect(), self._loop)
            except Exception:
                pass

    def _thread_main(self):
        try:
            self._connect_worker()
        except Exception as exc:
            self.status = f"Erreur: {exc}"
            print(self.status)
            traceback.print_exc()
        finally:
            self.connected = False
            self.busy = False
            if self._input_file is not None:
                try:
                    self._input_file.close()
                except Exception:
                    pass
                self._input_file = None
            if self.status.startswith("Erreur") or self.status == "Demarrage...":
                self.status = "Pret"

    def _run_bluetoothctl_sync(self):
        self.status = "Bluetoothctl connect..."
        addr = self.address.upper()
        script = "\n".join([
            "power on",
            "agent on",
            "default-agent",
            f"info {addr}",
            f"trust {addr}",
            f"connect {addr}",
            f"info {addr}",
            "quit",
            "",
        ])
        proc = subprocess.run(
            ["bluetoothctl"],
            input=script,
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = proc.stdout or ""
        print("--- bluetoothctl ---")
        print(text)
        print("--- suite input ---")
        return text

    def _read_js_loop(self, js_path):
        self.status = "Connecte — piloter stick G"
        print(f"input: lecture js {js_path}")
        self._input_file = open(js_path, "rb")
        self.connected = True
        print("input: pret, bougez le stick gauche")
        while not self._stop.is_set():
            data = self._input_file.read(8)
            if len(data) < 8:
                time.sleep_ms(10)
                continue
            _evt_time, value, ev_type, number = struct.unpack("<IhBB", data)
            ev_type &= ~JS_EVENT_INIT
            if ev_type != JS_EVENT_AXIS:
                continue
            if number == 0:
                self.axis_x, self.axis_y = snap_deadzone(value, self.axis_y)
            elif number == 1:
                self.axis_x, self.axis_y = snap_deadzone(self.axis_x, value)

    def _read_ev_loop(self, ev_path):
        self.status = "Connecte — piloter stick G"
        print(f"input: lecture evdev {ev_path}")
        mapper = EvdevStickMapper(ev_path, invert_y=False)
        ev_struct, ev_size = _input_event_struct()
        self._input_file = open(ev_path, "rb")
        self.connected = True
        print("input: pret, bougez le stick gauche")
        while not self._stop.is_set():
            data = self._input_file.read(ev_size)
            if len(data) < ev_size:
                time.sleep_ms(10)
                continue
            _sec, _usec, ev_type, code, value = ev_struct.unpack(data)
            if ev_type == EV_ABS and code in (ABS_X, ABS_Y):
                mapper.feed_abs(code, value)
                self.axis_x, self.axis_y = mapper.get_axes()
            elif ev_type == EV_SYN and code == SYN_REPORT:
                self.axis_x, self.axis_y = mapper.get_axes()

    def _connect_worker(self):
        btctl_output = self._run_bluetoothctl_sync()
        if "Paired: no" in btctl_output:
            self.status = "Manette non appairee"
            return
        if "not available" in btctl_output:
            self.status = "Manette introuvable"
            return
        if self._stop.is_set():
            return

        if "Connection successful" not in btctl_output and "Connected: yes" not in btctl_output:
            self.status = "BlueZ connect echoue"
            return

        self.status = "Attente input Xbox..."
        kind, input_path = wait_input_device(12)
        if kind == "js":
            self._read_js_loop(input_path)
            if not self._stop.is_set():
                self.status = "Deconnecte"
            else:
                self.status = "Pret"
            return
        if kind == "ev":
            self._read_ev_loop(input_path)
            if not self._stop.is_set():
                self.status = "Deconnecte"
            else:
                self.status = "Pret"
            return

        print("input: event Xbox absent, fallback bleak")
        if BleakClient is None:
            self.status = "js0 absent, bleak indispo"
            return

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._async_ble_fallback(btctl_output))
        finally:
            self._loop.close()
            self._loop = None

    def _on_hid_report(self, _handle, data):
        self.axis_x, self.axis_y = parse_left_stick(data)

    async def _async_disconnect(self):
        if self._client is not None and self._client.is_connected:
            await self._client.disconnect()

    async def _find_device(self, btctl_output):
        target = self.address.upper()
        for attempt in range(3):
            self.status = f"Scan BLE ({attempt + 1}/3)..."
            devices = await BleakScanner.discover(timeout=8.0)
            for device in devices:
                name = device.name or ""
                print(f"  scan: {device.address} {name}")
                if device.address.upper() == target:
                    return device
            await asyncio.sleep(1.0)

        if "Connected: yes" in btctl_output:
            print("scan vide mais BlueZ Connected:yes -> connexion directe MAC")
            return self.address

        return None

    async def _connect_with_hid(self, device, bluez_connected=False):
        last_error = None
        for attempt in range(3):
            self.status = f"Connexion bleak ({attempt + 1}/3)..."
            print(f"bleak: tentative {attempt + 1}...")
            client = BleakClient(device, timeout=30.0, pair=not bluez_connected)
            self._client = client
            try:
                await client.connect()
                print(f"bleak: connecte={client.is_connected}")
                dump_services(client, "bleak services:")

                if has_hid_service(client):
                    return client

                print("bleak: HID absent, pair() chiffrement...")
                try:
                    await client.pair()
                except Exception as exc:
                    print(f"bleak pair: {repr(exc)}")

                if client.is_connected:
                    await client.disconnect()
                await asyncio.sleep(2.0)
            except Exception as exc:
                last_error = exc
                print(f"bleak tentative {attempt + 1}: {repr(exc)}")
                traceback.print_exc()
                try:
                    if client.is_connected:
                        await client.disconnect()
                except Exception:
                    pass
                await asyncio.sleep(2.0)

        if last_error is not None:
            raise last_error
        raise BleakError("HID 0x1812 indisponible")

    async def _async_ble_fallback(self, btctl_output):
        device = await self._find_device(btctl_output)
        if device is None:
            self.status = "Manette off — bouton Xbox"
            return

        bluez_connected = (
            "Connection successful" in btctl_output
            or "Connected: yes" in btctl_output
        )

        try:
            client = await self._connect_with_hid(device, bluez_connected=bluez_connected)
            notify_char = find_hid_notify_char(client)
            if notify_char is None:
                self.status = "HID absent (fallback bleak)"
                await client.disconnect()
                return

            await client.start_notify(notify_char.uuid, self._on_hid_report)
            self.connected = True
            self.status = "Connecte bleak — stick G"

            while not self._stop.is_set() and client.is_connected:
                await asyncio.sleep(0.2)
        except Exception as exc:
            self.status = f"BLE: {exc}"
            print(f"bleak fallback: {repr(exc)}")
            traceback.print_exc()
        finally:
            self.connected = False
            self.axis_x = 0
            self.axis_y = 0
            if self._client is not None and self._client.is_connected:
                await self._client.disconnect()
            if not self._stop.is_set():
                self.status = "Deconnecte"
            else:
                self.status = "Pret"


# --- IHM --------------------------------------------------------------------

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


def draw_button(img, rect, label, color, pressed=False):
    fill = image.Color.from_rgb(120, 30, 30) if pressed else color
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], fill, thickness=-1)
    img.draw_rect(rect[0], rect[1], rect[2], rect[3], image.COLOR_WHITE, thickness=2)
    size = image.string_size(label, scale=1.4, thickness=1)
    tx = rect[0] + (rect[2] - size.width()) // 2
    ty = rect[1] + (rect[3] - size.height()) // 2
    img.draw_string(tx, ty, label, image.COLOR_WHITE, scale=1.4)


def draw_stick_gauge(img, cx, cy, axis_x, axis_y, radius=90):
    img.draw_circle(cx, cy, radius, image.Color.from_rgb(60, 60, 80), thickness=2)
    img.draw_line(cx - radius, cy, cx + radius, cy, image.COLOR_GRAY, thickness=1)
    img.draw_line(cx, cy - radius, cx, cy + radius, image.COLOR_GRAY, thickness=1)

    dx = int((axis_x / 32767.0) * (radius - 10))
    dy = int((axis_y / 32767.0) * (radius - 10))
    img.draw_circle(cx + dx, cy + dy, 12, image.Color.from_rgb(255, 140, 40), thickness=-1)
    img.draw_circle(cx + dx, cy + dy, 12, image.COLOR_WHITE, thickness=2)


def main():
    disp = display.Display()
    ts = touchscreen.TouchScreen()
    serial = init_uart()
    rover = RoverUart(serial)
    bridge = XboxBleBridge()

    img_back = get_back_btn(SCR_W)
    back_rect = [4, 4, img_back.width(), img_back.height()]
    connect_rect = [80, 400, 200, 56]
    disconnect_rect = [360, 400, 200, 56]

    send_ms = 0
    was_connected = False

    while not app.need_exit():
        img = image.Image(SCR_W, SCR_H, bg=image.COLOR_BLACK)
        img.draw_image(back_rect[0], back_rect[1], img_back)
        img.draw_string(110, 12, "Xbox -> Rover", image.COLOR_WHITE, scale=2)

        status_color = image.Color.from_rgb(80, 220, 120) if bridge.connected else image.COLOR_YELLOW
        img.draw_string(20, 55, bridge.status, status_color, scale=1.5)

        if bridge.connected:
            draw_stick_gauge(img, SCR_W // 2, 220, bridge.axis_x, bridge.axis_y)
            img.draw_string(20, 100, "Stick gauche = pilotage", image.COLOR_WHITE, scale=1.3)
            draw_button(img, disconnect_rect, "DISCONNECT", image.Color.from_rgb(180, 60, 40))
        elif bridge.busy:
            img.draw_string(20, 100, "Patientez (pairing)...", image.COLOR_GRAY, scale=1.3)
            draw_button(img, connect_rect, "...", image.Color.from_rgb(80, 80, 80))
        else:
            img.draw_string(20, 100, "Bouton Xbox ON puis CONNECT", image.COLOR_WHITE, scale=1.3)
            draw_button(img, connect_rect, "CONNECT", image.Color.from_rgb(40, 120, 60))

        line = f"X={bridge.axis_x:6d}  Y={bridge.axis_y:6d}  SPD={rover.speed}"
        if rover.last_ack:
            line += f"  ACK={rover.last_ack}"
        img.draw_string(8, SCR_H - 28, line, image.COLOR_YELLOW, scale=1.2)
        disp.show(img)

        x, y, pressed = ts.read()
        if pressed:
            if in_rect(x, y, back_rect):
                bridge.request_stop()
                rover.send_stop()
                app.set_exit_flag(True)
                break
            if not bridge.busy and not bridge.connected and in_rect(x, y, connect_rect):
                bridge.start_connect()
            if bridge.connected and in_rect(x, y, disconnect_rect):
                bridge.request_stop()
                rover.send_stop()

        now = time.ticks_ms()
        if bridge.connected and now - send_ms >= SEND_INTERVAL_MS:
            rover.send_joystick(bridge.axis_x, bridge.axis_y)
            send_ms = now
        elif was_connected and not bridge.connected:
            rover.send_stop()

        was_connected = bridge.connected

        time.sleep_ms(20)

    bridge.request_stop()
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
