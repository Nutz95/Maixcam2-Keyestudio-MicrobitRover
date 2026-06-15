"""Constantes protocole UART rover micro:bit."""

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
CMD_JOYSTICK = 0x30

PRESET_ACTIONS = {
  "stop": CMD_STOP,
  "forward": CMD_FORWARD,
  "backward": CMD_BACKWARD,
  "strafe_left": CMD_STRAFE_LEFT,
  "strafe_right": CMD_STRAFE_RIGHT,
  "diag_fl": CMD_DIAG_FL,
  "diag_fr": CMD_DIAG_FR,
  "diag_bl": CMD_DIAG_BL,
  "diag_br": CMD_DIAG_BR,
  "spin_left": CMD_SPIN_LEFT,
  "spin_right": CMD_SPIN_RIGHT,
  "pivot_right": CMD_PIVOT_RIGHT,
  "pivot_rear": CMD_PIVOT_REAR,
}
