from maix import uart, pinmap, err, sys


class UartInitializer:
  """Configure les broches UART MaixCam2 -> micro:bit."""

  def create(self):
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
