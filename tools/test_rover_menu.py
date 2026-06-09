#!/usr/bin/env python3
"""
Menu interactif pour tester le protocole binaire du rover micro:bit.

Connexion : adaptateur USB-serie ou MaixCam sur P1 (TX) / P2 (RX), 115200 8N1.
  PC RX  <--  P1 (TX micro:bit)
  PC TX  -->  P2 (RX micro:bit)
  GND    ---  GND

Usage:
  python test_rover_menu.py
  python test_rover_menu.py -p COM12
  python test_rover_menu.py -p COM12 -s 80
"""

from __future__ import annotations

import argparse
import sys
import time

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Dependance manquante : pip install pyserial")
    sys.exit(1)

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
CMD_RAW = 0x20

WHEEL_FORWARD = 0x01
WHEEL_BACKWARD = 0x02

PRESET_COMMANDS: list[tuple[str, str, int]] = [
    ("0", "STOP", CMD_STOP),
    ("1", "Avant", CMD_FORWARD),
    ("2", "Arriere", CMD_BACKWARD),
    ("3", "Strafe gauche", CMD_STRAFE_LEFT),
    ("4", "Strafe droite", CMD_STRAFE_RIGHT),
    ("5", "Diag avant-gauche", CMD_DIAG_FL),
    ("6", "Diag avant-droite", CMD_DIAG_FR),
    ("7", "Diag arriere-gauche", CMD_DIAG_BL),
    ("8", "Diag arriere-droite", CMD_DIAG_BR),
    ("9", "Rotation gauche (CCW)", CMD_SPIN_LEFT),
    ("a", "Rotation droite (CW)", CMD_SPIN_RIGHT),
    ("b", "Pivot cote droit", CMD_PIVOT_RIGHT),
    ("c", "Pivot axe arriere", CMD_PIVOT_REAR),
]

RAW_PRESETS: list[tuple[str, str, int]] = [
    ("r1", "RAW: 4 roues avant", 0x55),
    ("r2", "RAW: 4 roues arriere", 0xAA),
    ("r3", "RAW: strafe droite", 0xA5),
    ("r4", "RAW: strafe gauche", 0x5A),
    ("r0", "RAW: tout stop", 0x00),
]


def checksum3(b0: int, b1: int, b2: int) -> int:
    return (b0 + b1 + b2) & 0xFF


def checksum4(b0: int, b1: int, b2: int, b3: int) -> int:
    return (b0 + b1 + b2 + b3) & 0xFF


def build_preset_frame(cmd: int, speed: int) -> bytes:
    return bytes([PROTO_SYNC, cmd, speed, checksum3(PROTO_SYNC, cmd, speed)])


def build_raw_frame(wheel_dirs: int, speed: int) -> bytes:
    return bytes(
        [PROTO_SYNC, CMD_RAW, wheel_dirs, speed, checksum4(PROTO_SYNC, CMD_RAW, wheel_dirs, speed)]
    )


def list_serial_ports() -> list:
    return list(list_ports.comports())


def pick_port(requested: str | None) -> str:
    ports = list_serial_ports()
    if requested:
        return requested
    if not ports:
        print("Aucun port serie detecte.")
        return input("Entrer le port manuellement (ex: COM12): ").strip()
    if len(ports) == 1:
        print(f"Port auto-selectionne : {ports[0].device} ({ports[0].description})")
        return ports[0].device
    print("Ports disponibles :")
    print("  -> Choisir le port 'mbed Serial' / 'USB Serial', PAS 'DAPLink CMSIS-DAP'")
    for i, info in enumerate(ports, 1):
        marker = " *" if "mbed" in info.description.lower() or "usb serial" in info.description.lower() else ""
        print(f"  {i}. {info.device}  {info.description}{marker}")
    while True:
        choice = input(f"Choisir [1-{len(ports)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(ports):
            return ports[int(choice) - 1].device
        print("Choix invalide.")


def read_ack(ser: serial.Serial, timeout_s: float = 0.3) -> bytes:
    deadline = time.time() + timeout_s
    buf = bytearray()
    while time.time() < deadline:
        waiting = ser.in_waiting
        if waiting:
            buf.extend(ser.read(waiting))
            if len(buf) >= 2:
                return bytes(buf[:2])
        time.sleep(0.02)
    return bytes(buf)


def send_frame(ser: serial.Serial, frame: bytes, label: str) -> None:
    ser.reset_input_buffer()
    ser.write(frame)
    ser.flush()
    hex_frame = " ".join(f"{b:02X}" for b in frame)
    print(f"  TX [{label}] : {hex_frame}")
    ack = read_ack(ser)
    if len(ack) == 2 and ack[0] == PROTO_ACK:
        print(f"  ACK recu     : {ack[0]:02X} {ack[1]:02X}")
    elif ack:
        print(f"  Reponse      : {' '.join(f'{b:02X}' for b in ack)}")
    else:
        print("  ACK          : (aucune reponse)")


def print_menu(speed: int) -> None:
    print()
    print("=" * 52)
    print(f"  Test rover micro:bit  |  vitesse = {speed}")
    print("=" * 52)
    for key, label, _ in PRESET_COMMANDS:
        print(f"  {key:>2}  {label}")
    print("  -- RAW mecanum --")
    for key, label, _ in RAW_PRESETS:
        print(f"  {key:<3} {label}")
    print("  s   Changer la vitesse")
    print("  h   Afficher l'aide connexion")
    print("  q   Quitter (envoie STOP avant de partir)")
    print("=" * 52)


def print_help() -> None:
    print()
    print("Branchement USB-serie <-> micro:bit :")
    print("  Adaptateur TX  -->  P2 (RX)")
    print("  Adaptateur RX  <--  P1 (TX)")
    print("  GND            ---  GND")
    print("  115200 baud, 8N1")
    print()
    print("Le port COM du micro:bit USB (mbed) n'est PAS utilise par le firmware.")
    print("Il faut passer par P1/P2 ou par le MaixCam relie au robot.")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Menu de test du rover micro:bit")
    parser.add_argument("-p", "--port", help="Port serie (ex: COM12)")
    parser.add_argument("-s", "--speed", type=int, default=100, help="Vitesse PWM 0-255")
    parser.add_argument("-b", "--baud", type=int, default=115200, help="Baudrate")
    args = parser.parse_args()

    speed = max(0, min(255, args.speed))
    port = pick_port(args.port)

    print(f"\nOuverture de {port} @ {args.baud} baud...")
    try:
        ser = serial.Serial(port, args.baud, timeout=0.1)
    except serial.SerialException as exc:
        print(f"Erreur ouverture port : {exc}")
        return 1

    print("Connecte. Si le bon port est utilise, le firmware doit repondre avec un ACK.")

    cmd_map = {key: cmd for key, _, cmd in PRESET_COMMANDS}
    raw_map = {key: dirs for key, _, dirs in RAW_PRESETS}

    try:
        while True:
            print_menu(speed)
            choice = input("Commande > ").strip().lower()
            if not choice:
                continue
            if choice == "q":
                send_frame(ser, build_preset_frame(CMD_STOP, 0), "STOP")
                break
            if choice == "h":
                print_help()
                continue
            if choice == "s":
                raw = input(f"Nouvelle vitesse [0-255, actuel={speed}]: ").strip()
                if raw.isdigit():
                    speed = max(0, min(255, int(raw)))
                continue
            if choice in cmd_map:
                cmd = cmd_map[choice]
                spd = 0 if cmd == CMD_STOP else speed
                send_frame(ser, build_preset_frame(cmd, spd), choice)
                continue
            if choice in raw_map:
                send_frame(ser, build_raw_frame(raw_map[choice], speed), choice)
                continue
            print("Commande inconnue.")
    except KeyboardInterrupt:
        print("\nInterruption - envoi STOP...")
        send_frame(ser, build_preset_frame(CMD_STOP, 0), "STOP")
    finally:
        ser.close()
        print("Port ferme.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
