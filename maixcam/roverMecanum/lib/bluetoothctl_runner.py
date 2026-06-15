import subprocess
import threading
import time


class BluetoothctlRunner:
  """Run bluetoothctl with delays and early exit on success."""

  _OK_MARKERS = (
    "Connection successful",
    "Connected: yes",
    "Pairing successful",
    "Already paired",
  )

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
      return any(m in text for m in self._OK_MARKERS)

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

  def remove(self, mac):
    mac = mac.upper()
    return self._run_session([
      ("power on", 0.5),
      (f"remove {mac}", 1.0),
    ], watch_mac=mac, hard_timeout=15)

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
