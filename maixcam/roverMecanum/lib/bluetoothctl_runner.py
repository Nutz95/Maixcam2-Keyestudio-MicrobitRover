import re
import subprocess
import threading
import time


BLUETOOTH_OK_MARKERS = (
  "Connection successful",
  "Connected: yes",
  "Pairing successful",
  "Already paired",
  "Already Exists",
)


class BluetoothctlRunner:
  """Run bluetoothctl with delays and early exit on success (BlueZ on MaixCam Linux)."""

  _MAC_RE = re.compile(r"([0-9A-F]{2}(?::[0-9A-F]{2}){5})", re.IGNORECASE)

  def _run_session(self, steps, watch_mac=None, hard_timeout=90):
    proc = subprocess.Popen(
      ["bluetoothctl"],
      stdin=subprocess.PIPE,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      text=True,
      bufsize=1,
    )
    buf = []
    lock = threading.Lock()
    mac_key = watch_mac.upper().replace(":", "") if watch_mac else ""

    def reader():
      while True:
        line = proc.stdout.readline()
        if not line:
          if proc.poll() is not None:
            break
          time.sleep(0.05)
          continue
        with lock:
          buf.append(line)

    threading.Thread(target=reader, daemon=True).start()

    def output():
      with lock:
        return "".join(buf)

    def done():
      text = output()
      return any(m in text for m in BLUETOOTH_OK_MARKERS)

    def mac_seen():
      if not mac_key:
        return False
      compact = output().upper().replace(":", "")
      return mac_key in compact

    try:
      for cmd, max_wait in steps:
        if done():
          break
        if cmd:
          proc.stdin.write(cmd + "\n")
          proc.stdin.flush()
        deadline = time.time() + max_wait
        while time.time() < deadline:
          if done() or mac_seen():
            break
          time.sleep(0.15)
        if done():
          break

      proc.stdin.write("scan off\n")
      proc.stdin.flush()
      time.sleep(0.2)
      proc.stdin.write("quit\n")
      proc.stdin.flush()
      proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
      proc.kill()
    return output()

  def scan_for_device_name(self, name, timeout_sec=15.0):
    """BLE/classic scan via bluetoothctl; return MAC for exact or partial name match."""
    target = name.lower().strip()
    if not target:
      return None

    output = self._run_session([
      ("power on", 0.5),
      ("scan on", 0.3),
      ("", timeout_sec),
    ], hard_timeout=timeout_sec + 30)

    exact = None
    partial = None
    pending_mac = None
    for line in output.splitlines():
      line = line.strip()
      mac_match = self._MAC_RE.search(line)
      if mac_match:
        pending_mac = mac_match.group(1).upper()
      name_match = re.search(r"Name:\s*(.+)$", line, re.IGNORECASE)
      device_name = ""
      if name_match:
        device_name = name_match.group(1).strip()
      elif pending_mac and line.startswith("Device ") and "Name:" not in line:
        tail = line.split(pending_mac, 1)[-1].strip()
        if tail and not tail.startswith("("):
          device_name = tail

      if not pending_mac or not device_name:
        continue

      print(f"  bt scan: {pending_mac} {device_name}")
      dn = device_name.lower()
      if dn == target:
        exact = pending_mac
        break
      if target in dn:
        partial = partial or pending_mac
      pending_mac = None

    return exact or partial

  def quick_connect(self, mac):
    mac = mac.upper()
    return self._run_session([
      ("power on", 0.3),
      ("agent on", 0.2),
      ("default-agent", 0.2),
      (f"info {mac}", 0.5),
      (f"trust {mac}", 0.5),
      (f"connect {mac}", 6.0),
      (f"info {mac}", 0.3),
    ], watch_mac=mac, hard_timeout=20)

  def connect(self, mac):
    mac = mac.upper()
    return self._run_session([
      ("power on", 0.5),
      ("agent on", 0.3),
      ("default-agent", 0.3),
      ("scan on", 0.3),
      ("", 8.0),
      (f"info {mac}", 0.5),
      (f"trust {mac}", 0.8),
      (f"connect {mac}", 10.0),
      (f"info {mac}", 0.5),
    ], watch_mac=mac, hard_timeout=60)

  def pair(self, mac):
    mac = mac.upper()
    return self._run_session([
      ("power on", 0.5),
      ("agent on", 0.3),
      ("default-agent", 0.3),
      ("scan on", 0.3),
      ("", 10.0),
      (f"pair {mac}", 18.0),
      (f"trust {mac}", 0.8),
      (f"connect {mac}", 10.0),
      (f"info {mac}", 0.5),
    ], watch_mac=mac, hard_timeout=75)
