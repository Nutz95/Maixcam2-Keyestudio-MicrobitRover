"""Loop / Bluetooth / evdev timing from config.json."""

from lib.app_config.parse_helpers import as_int, section


class TimingSettings:
  """
  Sleeps and waits in milliseconds.

  Bluetooth: poll intervals + one kernel settle (``bt_kernel_settle_ms``) used
  only when BlueZ emits no useful completion line (post-remove HCI cool-down).
  Everywhere else waits on bluetoothctl output.
  """

  __slots__ = (
    "main_loop_sleep_ms", "teleop_poll_sleep_ms", "config_reload_ms",
    "touch_debounce_ms", "speed_debounce_ms",
    "evdev_retry_ms", "evdev_open_attempts", "evdev_drain_max_events",
    "hid_wait_ms", "hid_quick_wait_ms",
    "bt_kernel_settle_ms",
    "bt_poll_ms", "bt_scan_poll_ms", "bt_devices_query_ms",
    "bt_pair_timeout_s", "bt_connect_timeout_s", "bt_remove_timeout_s",
  )

  def __init__(self, raw: dict):
    timing = section(raw, "timing")
    self.main_loop_sleep_ms = max(1, as_int(timing, "main_loop_sleep_ms", 10))
    self.teleop_poll_sleep_ms = max(1, as_int(timing, "teleop_poll_sleep_ms", 5))
    self.config_reload_ms = max(100, as_int(timing, "config_reload_ms", 500))
    self.touch_debounce_ms = max(0, as_int(timing, "touch_debounce_ms", 900))
    self.speed_debounce_ms = max(0, as_int(timing, "speed_debounce_ms", 160))
    self.evdev_retry_ms = max(50, as_int(timing, "evdev_retry_ms", 250))
    self.evdev_open_attempts = max(1, as_int(timing, "evdev_open_attempts", 8))
    # Cap ABS flood per poll so the GIL stays available for the HUD.
    self.evdev_drain_max_events = max(1, as_int(timing, "evdev_drain_max_events", 24))
    self.hid_wait_ms = max(1000, as_int(timing, "hid_wait_ms", 12000))
    self.hid_quick_wait_ms = max(500, as_int(timing, "hid_quick_wait_ms", 5000))
    # Legacy: accept old settle_long key if kernel settle is absent.
    if "bt_kernel_settle_ms" in timing:
      kernel_ms = as_int(timing, "bt_kernel_settle_ms", 2000)
    else:
      kernel_ms = as_int(timing, "bt_settle_long_ms", 2000)
    self.bt_kernel_settle_ms = max(100, kernel_ms)
    self.bt_poll_ms = max(20, as_int(timing, "bt_poll_ms", 100))
    self.bt_scan_poll_ms = max(50, as_int(timing, "bt_scan_poll_ms", 200))
    self.bt_devices_query_ms = max(100, as_int(timing, "bt_devices_query_ms", 600))
    self.bt_pair_timeout_s = max(5, as_int(timing, "bt_pair_timeout_s", 25))
    self.bt_connect_timeout_s = max(3, as_int(timing, "bt_connect_timeout_s", 12))
    self.bt_remove_timeout_s = max(2, as_int(timing, "bt_remove_timeout_s", 8))

  def sleep_s(self, ms: int) -> float:
    return max(0.0, ms / 1000.0)
