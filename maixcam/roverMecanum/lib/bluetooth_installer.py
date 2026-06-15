import subprocess


class BluetoothInstaller:
  """Installe les dependances Bluetooth sur MaixCam2."""

  def install(self):
    results = []
    results.append(self._run_shell("bluetoothctl power on"))
    results.append(self._run_shell("pip install bleak"))
    self._ensure_rc_local()
    return "\n".join(results)

  def _ensure_rc_local(self):
    marker = "bluetoothctl power on"
    try:
      with open("/etc/rc.local", "r") as f:
        content = f.read()
      if marker in content:
        return "rc.local: deja configure"
      with open("/etc/rc.local", "a") as f:
        f.write(f'\necho "{marker}" | bluetoothctl\n')
      return "rc.local: bluetoothctl power on ajoute"
    except OSError as exc:
      return f"rc.local: skip ({exc})"

  def _run_shell(self, command):
    proc = subprocess.run(
      command,
      shell=True,
      capture_output=True,
      text=True,
      timeout=120,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    return out.strip() or f"OK: {command}"
