"""
Connexion BLE Xbox Wireless Controller sur MaixCam2.

Prerequis :
  pip install bleak
  bluetoothctl disponible (BlueZ)

Le service HID 0x1812 n'apparait qu'apres pairing chiffre (comme sur ESP32/NimBLE).
Ce script lance bluetoothctl (agent + pair/trust/connect) puis bleak avec pair=True.
"""

import asyncio
from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

XBOX_ADDRESS = "78:86:2E:97:BD:9C"
HID_SERVICE_UUID = "00001812-0000-1000-8000-00805f9b34fb"
HID_REPORT_UUID = "00002a4d-0000-1000-8000-00805f9b34fb"


def on_hid_report(_handle, data: bytearray):
    if len(data) < 16:
        print(f"HID report court ({len(data)}): {data.hex(' ')}")
        return

    left_x = int.from_bytes(data[0:2], "little", signed=False) - 32768
    left_y = int.from_bytes(data[2:4], "little", signed=False) - 32768
    print(f"stick L: x={left_x:6d} y={left_y:6d}  raw={data.hex(' ')}")


def _uuid_short(uuid: str) -> str:
    u = uuid.lower().replace("-", "")
    return u[-8:] if len(u) >= 8 else u


def find_hid_notify_char(client):
    """Cherche une characteristic notify sur le service HID."""
    for service in client.services:
        if _uuid_short(service.uuid) != "00001812":
            continue
        for char in service.characteristics:
            if "notify" not in char.properties:
                continue
            if _uuid_short(char.uuid) == "00002a4d":
                return char
        for char in service.characteristics:
            if "notify" in char.properties:
                return char
    return None


def has_hid_service(client) -> bool:
    for service in client.services:
        if _uuid_short(service.uuid) == "00001812":
            return True
    return False


def dump_services(client, title: str):
    print(title)
    for service in client.services:
        print(f"Service {service.uuid}")
        for char in service.characteristics:
            props = ",".join(char.properties)
            print(f"  Char {char.uuid} [{props}]")


async def run_bluetoothctl_pair(address: str, scan_seconds: float = 12.0) -> str:
    """Lance bluetoothctl : agent, scan, pair, trust, connect."""
    print("bluetoothctl: preparation pairing...")
    proc = await asyncio.create_subprocess_exec(
        "bluetoothctl",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )

    async def send(cmd: str, delay: float = 0.3):
        proc.stdin.write((cmd + "\n").encode())
        await proc.stdin.drain()
        await asyncio.sleep(delay)

    await send("power on", 0.5)
    await send("agent on", 0.2)
    await send("default-agent", 0.2)
    await send("scan on", 0.2)
    print(f"bluetoothctl: scan {scan_seconds:.0f}s (manette allumee)...")
    await asyncio.sleep(scan_seconds)
    await send("scan off", 0.5)

    addr = address.upper()
    await send(f"pair {addr}", 8.0)
    await send(f"trust {addr}", 1.0)
    await send(f"connect {addr}", 5.0)
    await send("quit", 0.2)

    stdout, _ = await proc.communicate()
    text = stdout.decode(errors="replace")
    print(text)
    return text


def pairing_looks_ok(btctl_output: str) -> bool:
    ok_markers = (
        "Pairing successful",
        "Already paired",
        "Connection successful",
        "Connected: yes",
    )
    return any(m in btctl_output for m in ok_markers)


async def find_xbox_device(address: str):
    print("Scan bleak...")
    devices = await BleakScanner.discover(timeout=10.0)
    target = address.upper()

    for device in devices:
        name = device.name or "(sans nom)"
        print(f"  {device.address}: {name}")
        if device.address.upper() == target:
            print(f"Manette trouvee: {device.address} ({name})")
            return device

    print(f"Adresse {address} absente du scan bleak.")
    return None


async def connect_with_hid(device, pair: bool = True):
    """Connecte bleak, tente pairing, reconnecte si HID absent."""
    client = BleakClient(device, timeout=25.0, pair=pair)

    print(f"Connexion bleak (pair={pair})...")
    await client.connect()
    print(f"Connecte: {client.is_connected}")
    dump_services(client, "Services apres 1ere connexion:")

    if has_hid_service(client):
        return client

    print("HID 0x1812 absent -> pairing bleak...")
    try:
        await client.pair()
        print("pair() bleak OK")
    except Exception as exc:
        print(f"pair() bleak: {exc}")

    await client.disconnect()
    await asyncio.sleep(2.0)

    print("Reconnexion bleak apres pairing...")
    await client.connect()
    dump_services(client, "Services apres reconnexion:")
    return client


async def subscribe_hid(client) -> bool:
    notify_char = find_hid_notify_char(client)
    if notify_char is None:
        print("Pas de characteristic HID notify trouvee.")
        return False

    print(f"Abonnement notify sur {notify_char.uuid}")
    await client.start_notify(notify_char.uuid, on_hid_report)
    return True


async def main():
    address = XBOX_ADDRESS

    btctl_out = await run_bluetoothctl_pair(address)
    if not pairing_looks_ok(btctl_out):
        print("Pairing bluetoothctl incertain — on continue quand meme avec bleak.")

    device = await find_xbox_device(address)
    if device is None:
        return

    client = None
    try:
        client = await connect_with_hid(device, pair=True)

        if not await subscribe_hid(client):
            print("Echec abonnement HID. Suggestions :")
            print("  - Maintenir le bouton sync manette jusqu'au clignotement rapide")
            print("  - bluetoothctl remove " + address + " puis relancer ce script")
            print("  - Verifier firmware manette (Xbox Accessories app sur Windows)")
            return

        print("Bougez le joystick. Ctrl+C pour arreter.")
        while client.is_connected:
            await asyncio.sleep(1.0)

    except BleakError as exc:
        print(f"Erreur BLE: {exc}")
    finally:
        if client is not None and client.is_connected:
            await client.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Arret.")
