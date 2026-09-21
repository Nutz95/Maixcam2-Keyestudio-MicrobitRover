"""Enable Bluetooth on MaixCam2 (BlueZ via bluetoothctl)."""


class BluetoothInstaller:
  """Apply MaixCam2 BlueZ workarounds; session owns power/pairable."""

  def install(self):
    """Apply the old-kernel Xbox workaround; session owns power/pairable."""
    results = []
    results.append(self._disable_ertm())
    results.append(self._ensure_rc_local())
    return "\n".join(results)

  def _disable_ertm(self):
    """
    Disable Bluetooth L2CAP Enhanced Retransmission Mode (ERTM).

    ERTM is a reliability mode for ACL links. On MaixCam2 Linux 4.19 it often
    prevents Xbox BLE HID from exposing ``/dev/input/event*`` (Connected flap).
    Writing ``Y`` here is the documented kernel workaround for that combo.
    """
    path = "/sys/module/bluetooth/parameters/disable_ertm"
    try:
      with open(path, "w", encoding="utf-8") as handle:
        handle.write("Y\n")
      return "bluetooth: ERTM disabled (Xbox / kernel 4.19 HID workaround)"
    except OSError as io_error:
      return f"bluetooth: ERTM workaround unavailable ({io_error})"

  def _ensure_rc_local(self):
    marker = "bluetoothctl power on"
    try:
      with open("/etc/rc.local", "r") as handle:
        content = handle.read()
      if marker in content:
        return "rc.local: already configured"
      with open("/etc/rc.local", "a") as handle:
        handle.write(f'\necho "{marker}" | bluetoothctl\n')
      return "rc.local: bluetoothctl power on added"
    except OSError as io_error:
      return f"rc.local: skip ({io_error})"
