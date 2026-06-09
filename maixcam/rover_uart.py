"""UART + protocole binaire rover micro:bit."""

from maix import uart, pinmap, err, sys, time

PROTO_SYNC = 0xAA
PROTO_ACK = 0x55
CMD_STOP = 0x00
CMD_JOYSTICK = 0x30
DEFAULT_SPEED = 100


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
