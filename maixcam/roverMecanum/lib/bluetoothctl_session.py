"""Long-lived bluetoothctl PTY so the BlueZ agent stays registered."""

import os
import select
import subprocess
import threading
import time

from lib.app_config.timing_settings import TimingSettings
from lib.bluetoothctl_runner import BluetoothctlRunner


class BluetoothctlSession:
  """One bluetoothctl process for the whole app (agent NoInputNoOutput)."""

  def __init__(self, timing=None):
    self._timing = timing if timing is not None else TimingSettings({})
    self._lock = threading.Lock()
    self._chunks = []
    self._master = None
    self._proc = None
    self._alive = False

  def _kernel_settle(self) -> None:
    """Wait when BlueZ emits no useful completion line (HCI cool-down)."""
    time.sleep(self._timing.sleep_s(self._timing.bt_kernel_settle_ms))

  def start(self):
    """Power on, pairable, register agent; keep the process running."""
    if self._alive:
      return
    import pty

    master, slave = pty.openpty()
    self._proc = subprocess.Popen(
      ["bluetoothctl"],
      stdin=slave,
      stdout=slave,
      stderr=slave,
      close_fds=True,
    )
    os.close(slave)
    self._master = master
    self._alive = True
    threading.Thread(target=self._read_loop, daemon=True, name="btctl-pty").start()
    self.send("power on")
    self.send("pairable on")
    mark = self._mark()
    self.send("agent NoInputNoOutput")
    self.send("default-agent")
    self._wait_since(
      mark,
      ("Agent registered", "Default agent request successful"),
      self._timing.bt_connect_timeout_s,
    )
    print("bt: agent alive (NoInputNoOutput)")

  def close(self):
    """Quit bluetoothctl (app shutdown only — not DISCONNECT)."""
    if not self._alive:
      return
    self._alive = False
    try:
      self.send("quit")
    except OSError as io_error:
      print(f"bt: quit write failed: {io_error}")
    if self._proc is not None:
      try:
        self._proc.wait(timeout=3)
      except subprocess.TimeoutExpired:
        print("bt: bluetoothctl did not exit; killing")
        self._proc.kill()
      self._proc = None
    if self._master is not None:
      try:
        os.close(self._master)
      except OSError as io_error:
        print(f"bt: PTY close failed: {io_error}")
      self._master = None

  def send(self, cmd):
    """Write one bluetoothctl command."""
    if self._master is None:
      raise OSError("bluetoothctl session is not started")
    print(f"  btctl: {cmd}")
    os.write(self._master, (cmd + "\n").encode())

  def pair(self, mac):
    """Force a fresh encrypted bond (PAIR button). Always remove first."""
    self.start()
    mac = mac.upper()
    print("bt: PAIR = remove old bond + encrypted re-pair (hold SYNC)")
    self._remove_bond(mac)
    # ponytail: BlueZ remove completes but HCI/LE still needs cool-down; no line.
    self._kernel_settle()

    pair_out = ""
    seen = ""
    pair_timeout = self._timing.bt_pair_timeout_s
    for attempt in range(2):
      mark = self._mark()
      self.send("scan on")
      seen = self._wait_pairing_ready(mac, mark, pair_timeout)
      if not seen:
        self.send("scan off")
        print(f"bt: pair attempt {attempt + 1}/2 — not in SYNC mode")
        continue
      pair_mark = self._mark()
      # BlueZ 5.64 on MaixCAM must remain discovering while initiating LE pair.
      self.send(f"pair {mac}")
      pair_out = self._wait_since(
        pair_mark,
        ("Pairing successful", "Already paired", "Failed to pair"),
        pair_timeout,
      )
      if BluetoothctlRunner.pair_succeeded(pair_out):
        break
      print(f"bt: pair attempt {attempt + 1}/2 failed")
      self.send("scan off")
      if attempt == 0:
        self._remove_device(mac)
        self._kernel_settle()

    self._scan_off()
    if not BluetoothctlRunner.pair_succeeded(pair_out):
      return seen + pair_out

    self.send(f"trust {mac}")
    return seen + pair_out + self.info(mac)

  def connect(self, mac):
    """Connect an already-paired pad and wait until GATT/HID is resolved."""
    self.start()
    mac = mac.upper()
    mark = self._mark()
    self.send(f"trust {mac}")
    self.send(f"connect {mac}")
    out = self._wait_since(
      mark,
      ("Connection successful", "Failed to connect", "Paired: no"),
      self._timing.bt_connect_timeout_s,
    )
    if "Failed to connect" in out or "Paired: no" in out:
      self.info(mac)
      return self._since(mark)
    self._wait_hid_ready(mac)
    return self._since(mark)

  def info(self, mac):
    """Run ``info MAC`` and return the new output."""
    self.start()
    mark = self._mark()
    self.send(f"info {mac}")
    return BluetoothctlRunner.strip_ansi(
      self._wait_since(
        mark,
        ("Paired:", "Connected:", "Name:", "not available"),
        self._timing.bt_connect_timeout_s,
      )
    )

  def _remove_bond(self, mac):
    mark0 = self._mark()
    self.send(f"disconnect {mac}")
    self.send(f"remove {mac}")
    self._wait_since(
      mark0,
      ("Device has been removed", "not available", "Failed to disconnect"),
      self._timing.bt_remove_timeout_s,
    )

  def _remove_device(self, mac):
    """Clear a failed temporary device object before the second pair attempt."""
    mark = self._mark()
    self.send(f"remove {mac}")
    self._wait_since(
      mark,
      ("Device has been removed", "not available"),
      self._timing.bt_remove_timeout_s,
    )

  def _wait_pairing_ready(self, mac, mark, timeout_s):
    """Wait until Xbox is advertising for pairing (not a stale RSSI CHG)."""
    deadline = time.time() + timeout_s
    mac_u = mac.upper()
    poll_s = self._timing.sleep_s(self._timing.bt_poll_ms)
    while time.time() < deadline:
      chunk = BluetoothctlRunner.strip_ansi(self._since(mark))
      if BluetoothctlRunner.xbox_pairing_advertisement(chunk, mac_u):
        print(f"bt: pairing advert seen for {mac_u}")
        return chunk
      time.sleep(poll_s)
    return ""

  def _wait_hid_ready(self, mac):
    """Wait for GATT/HID services to resolve."""
    mark = self._mark()
    self.send(f"info {mac}")
    self._wait_since(
      mark,
      ("ServicesResolved: yes", "00001812-", "Human Interface Device"),
      self._timing.bt_connect_timeout_s,
    )

  def _scan_off(self):
    mark = self._mark()
    self.send("scan off")
    self._wait_since(
      mark,
      ("Discovering: no", "Discovery stopped"),
      self._timing.sleep_s(self._timing.bt_scan_poll_ms) + 2.0,
    )

  def scan_for_device_name(self, name, timeout_sec=20.0, aliases=None):
    """Find Xbox MAC via BlueZ device list, then discovery scan if needed."""
    self.start()
    runner = BluetoothctlRunner()
    targets = runner.build_targets(name, aliases)
    print(
      f"  bt tip: hold Xbox SYNC until logo blinks fast"
      f" — scanning up to {timeout_sec:.0f}s for: {targets[0]!r}"
    )

    # Already-known pads only emit CHG RSSI / Connected — no [NEW] Device Name.
    mac = self._mac_from_devices(runner, targets)
    if mac:
      print(f"  bt: using known BlueZ device {mac}")
      return mac

    mark = self._mark()
    self.send("scan on")
    deadline = time.time() + max(3.0, timeout_sec)
    next_devices = time.time() + 3.0
    mac = ""
    poll_s = self._timing.sleep_s(self._timing.bt_scan_poll_ms)
    while time.time() < deadline:
      chunk = self._since(mark)
      match = runner.match_scan_output(chunk, targets)
      mac = match.mac
      if mac:
        break
      # Re-query the cache: discovery alone often skips previously paired Xbox.
      if time.time() >= next_devices:
        mac = self._mac_from_devices(runner, targets)
        if mac:
          break
        next_devices = time.time() + 3.0
      time.sleep(poll_s)
    self._scan_off()
    return mac

  def _mac_from_devices(self, runner, targets) -> str:
    """Parse ``devices`` output for an Xbox name match."""
    mark = self._mark()
    self.send("devices")
    chunk = self._wait_since(
      mark,
      ("Device ",),
      self._timing.sleep_s(self._timing.bt_devices_query_ms),
    )
    return runner.match_scan_output(chunk, targets).mac

  def _read_loop(self):
    while self._alive and self._master is not None:
      ready, _, _ = select.select([self._master], [], [], 0.3)
      if not ready:
        continue
      try:
        data = os.read(self._master, 8192)
      except OSError as io_error:
        print(f"bt: PTY read ended: {io_error}")
        break
      if not data:
        break
      text = data.decode("utf-8", errors="replace")
      with self._lock:
        self._chunks.append(text)
        if len(self._chunks) > 80:
          del self._chunks[:-40]
      stripped = BluetoothctlRunner.strip_ansi(text)
      if stripped.strip():
        self._print_bt_output(stripped)

  def _print_bt_output(self, stripped):
    """Drop Connected yes/no chatter. Do not print it — print() holds the GIL."""
    low = stripped.lower()
    if ("connected: yes" in low or "connected: no" in low) and "failed" not in low:
      return
    print(stripped, end="" if stripped.endswith("\n") else "\n")

  def _mark(self):
    return len(self._snapshot())

  def _snapshot(self):
    with self._lock:
      return "".join(self._chunks)

  def _since(self, mark):
    return self._snapshot()[mark:]

  def _wait_since(self, mark, needles, timeout_s):
    deadline = time.time() + timeout_s
    poll_s = self._timing.sleep_s(self._timing.bt_poll_ms)
    while time.time() < deadline:
      chunk = BluetoothctlRunner.strip_ansi(self._since(mark))
      for needle in needles:
        if needle in chunk:
          return chunk
      time.sleep(poll_s)
    return BluetoothctlRunner.strip_ansi(self._since(mark))
