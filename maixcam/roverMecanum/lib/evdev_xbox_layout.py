from lib.abs_code_pair import AbsCodePair
from lib.evdev_constants import (
  ABS_BRAKE, ABS_GAS, ABS_RX, ABS_RY, ABS_RZ, ABS_X, ABS_Y, ABS_Z,
  XBOX_VENDOR_ID,
)


class XboxAxisLayout:
  """Xbox evdev axis roles (USB/BT/kernel layouts differ on MaixCam)."""

  def __init__(self, left_x, left_y, right_x, right_y, lt, rt):
    self.left_x = left_x
    self.left_y = left_y
    self.right_x = right_x
    self.right_y = right_y
    self.lt = lt
    self.rt = rt

  def stick_and_trigger_codes(self):
    """ABS codes owned by the stick/trigger ioctl pipeline."""
    return (
      self.left_x, self.left_y, self.right_x, self.right_y, self.lt, self.rt,
    )

  @classmethod
  def detect(cls, sysfs, event_path, evdev_settings=None) -> "XboxAxisLayout":
    """Pick ABS codes from typed EvdevSettings, or auto-detect."""
    if evdev_settings is not None and evdev_settings.has_explicit_codes():
      layout = cls(
        evdev_settings.left_x,
        evdev_settings.left_y,
        evdev_settings.right_x,
        evdev_settings.right_y,
        evdev_settings.lt,
        evdev_settings.rt,
      )
      cls._log_layout(layout, "config")
      return layout

    layout_profile = "auto" if evdev_settings is None else evdev_settings.layout
    if layout_profile == "standard":
      layout = cls(ABS_X, ABS_Y, ABS_RX, ABS_RY, ABS_Z, ABS_RZ)
      cls._log_layout(layout, "standard")
      return layout
    if layout_profile == "maixcam_bt":
      layout = cls(ABS_X, ABS_Y, ABS_Z, ABS_RZ, ABS_BRAKE, ABS_GAS)
      cls._log_layout(layout, "maixcam_bt")
      return layout

    return cls._auto_detect(sysfs, event_path)

  @classmethod
  def _auto_detect(cls, sysfs, event_path) -> "XboxAxisLayout":
    caps = sysfs.read_abs_capabilities(event_path)
    vendor = sysfs.read_vendor(event_path)

    triggers = cls._pick_triggers(sysfs, event_path, caps)
    right = cls._pick_right_stick(
      sysfs, event_path, caps, triggers.first, triggers.second,
    )

    if vendor == XBOX_VENDOR_ID and caps == 0:
      layout = cls(ABS_X, ABS_Y, ABS_Z, ABS_RZ, ABS_BRAKE, ABS_GAS)
      cls._log_layout(layout, "auto/xbox-no-caps")
      return layout

    layout = cls(
      ABS_X, ABS_Y, right.first, right.second, triggers.first, triggers.second,
    )
    cls._log_layout(layout, f"auto/caps=0x{caps:x}" if caps else "auto")
    return layout

  @classmethod
  def _pick_triggers(cls, sysfs, event_path, caps) -> AbsCodePair:
    if caps:
      if caps & (1 << ABS_GAS) and caps & (1 << ABS_BRAKE):
        return AbsCodePair(ABS_BRAKE, ABS_GAS)
      z_info = sysfs.read_absinfo_real(event_path, ABS_Z)
      if z_info is not None and z_info.looks_like_trigger():
        return AbsCodePair(ABS_Z, ABS_RZ)

    z_info = sysfs.read_absinfo_real(event_path, ABS_Z)
    rz_info = sysfs.read_absinfo_real(event_path, ABS_RZ)
    if (
      z_info is not None and rz_info is not None
      and z_info.looks_like_trigger() and rz_info.looks_like_trigger()
    ):
      return AbsCodePair(ABS_Z, ABS_RZ)

    gas_info = sysfs.read_absinfo_real(event_path, ABS_GAS)
    brake_info = sysfs.read_absinfo_real(event_path, ABS_BRAKE)
    if gas_info is not None or brake_info is not None:
      return AbsCodePair(ABS_BRAKE, ABS_GAS)

    return AbsCodePair(ABS_BRAKE, ABS_GAS)

  @classmethod
  def _pick_right_stick(cls, sysfs, event_path, caps, lt, rt) -> AbsCodePair:
    trigger_set = {lt, rt}
    if caps and (caps & (1 << ABS_RX)) and (caps & (1 << ABS_RY)):
      if ABS_RX not in trigger_set and ABS_RY not in trigger_set:
        return AbsCodePair(ABS_RX, ABS_RY)

    z_info = sysfs.read_absinfo_real(event_path, ABS_Z)
    if z_info is not None and not z_info.looks_like_trigger():
      rz_info = sysfs.read_absinfo_real(event_path, ABS_RZ)
      if rz_info is not None and not rz_info.looks_like_trigger():
        return AbsCodePair(ABS_Z, ABS_RZ)

    return AbsCodePair(ABS_Z, ABS_RZ)

  @staticmethod
  def _log_layout(layout, source):
    print(
      f"xbox layout ({source}):"
      f" L=({layout.left_x},{layout.left_y})"
      f" R=({layout.right_x},{layout.right_y})"
      f" T=({layout.lt},{layout.rt})"
    )
