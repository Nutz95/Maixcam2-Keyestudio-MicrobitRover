"""Linux evdev axis codes used by Xbox controllers."""

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0

ABS_X = 0x00
ABS_Y = 0x01
ABS_Z = 0x02
ABS_RX = 0x03
ABS_RY = 0x04
ABS_RZ = 0x05
ABS_HAT0X = 0x10
ABS_HAT0Y = 0x11
ABS_GAS = 0x09
ABS_BRAKE = 0x0A

AXIS_MAX = 32767
XBOX_VENDOR_ID = "045e"

# All axis codes we may probe on Xbox gamepads.
XBOX_AXIS_CODES = (
  ABS_X, ABS_Y, ABS_Z, ABS_RX, ABS_RY, ABS_RZ,
  ABS_HAT0X, ABS_HAT0Y, ABS_GAS, ABS_BRAKE,
)

BTN_A = 0x130
BTN_B = 0x131
BTN_X = 0x133
BTN_Y = 0x134
BTN_TL = 0x136
BTN_TR = 0x137
BTN_TL2 = 0x138
BTN_TR2 = 0x139
BTN_SELECT = 0x13A
BTN_START = 0x13B

BTN_DPAD_UP = 0x220
BTN_DPAD_DOWN = 0x221
BTN_DPAD_LEFT = 0x222
BTN_DPAD_RIGHT = 0x223

BTN_NAME_BY_CODE = {
  BTN_A: "btn_a",
  BTN_B: "btn_b",
  BTN_X: "btn_x",
  BTN_Y: "btn_y",
  BTN_TL: "btn_lb",
  BTN_TR: "btn_rb",
  BTN_TL2: "btn_lt",
  BTN_TR2: "btn_rt",
  BTN_SELECT: "btn_select",
  BTN_START: "btn_start",
}
