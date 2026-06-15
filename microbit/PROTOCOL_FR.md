# Protocole UART MaixCam ↔ micro:bit (rover mécanum)

Documentation complète en français. Version anglaise : [`PROTOCOL_EN.md`](PROTOCOL_EN.md).

Firmware : `microbit/src/`  
Vitesse : **115200** baud, 8N1  
Broches edge micro:bit : **P1 = TX**, **P2 = RX**

---

## Avant tout : comprendre les octets (Little Endian / Big Endian)

Un nombre comme **300** ou **-1000** ne tient pas dans **1 octet** (1 octet = 0 à 255).  
On utilise souvent **2 octets** (= 16 bits = un `int16`).

### Exemple : la valeur 300

En hexadécimal : **300 = 0x012C**

| Notation | Octet de poids fort | Octet de poids faible |
|----------|---------------------|------------------------|
| Big Endian (BE) | `01` puis `2C` | l’ordre « humain » (MSB d’abord) |
| Little Endian (LE) | `2C` puis `01` | l’octet **faible** est **en premier** |

**Notre protocole utilise LE (Little Endian)** — c’est le standard sur micro:bit, PC x86 et MaixCam.

### Exemple : -1 (nombre signé int16)

-1 en binaire signé 16 bits = **0xFFFF**  
En LE on envoie : **`FF FF`**

### Exemple concret dans une trame joystick

Strafe (crab) = **+100** :

```
100 = 0x0064  →  octets LE : 64 00
```

Forward = **-500** :

```
-500 = 0xFE0C  →  octets LE : 0C FE
```

En Python :

```python
(100).to_bytes(2, "little", signed=True)   # b'\x64\x00'
(-500).to_bytes(2, "little", signed=True)  # b'\x0c\xfe'
```

---

## Octets communs

| Valeur | Nom | Rôle |
|--------|-----|------|
| `0xAA` | `PROTO_SYNC` | Début de trame |
| `0x55` | `PROTO_ACK` | Accusé de réception |

---

## 1. Trame prédéfinie (4 octets)

```
[SYNC 0xAA] [COMMAND] [MOTOR_SPEED] [CHECKSUM]
```

| Champ | Description |
|-------|-------------|
| `COMMAND` | Code mouvement (table ci-dessous) |
| `MOTOR_SPEED` | PWM moteur `0..255` (`0` = arrêt) |
| `CHECKSUM` | `(0xAA + COMMAND + MOTOR_SPEED) & 0xFF` |

### Codes COMMAND

| Code | Nom | Mouvement |
|------|-----|-----------|
| `0x00` | STOP | Arrêt |
| `0x01` | FORWARD | Tout en avant |
| `0x02` | BACKWARD | Tout en arrière |
| `0x03` | STRAFE_LEFT | Crab gauche |
| `0x04` | STRAFE_RIGHT | Crab droite |
| `0x05`–`0x08` | DIAG_* | Diagonales |
| `0x09` | SPIN_LEFT | Rotation sur place (anti-horaire) |
| `0x0A` | SPIN_RIGHT | Rotation sur place (horaire) |
| `0x0B` | PIVOT_RIGHT | Pivot type voiture |
| `0x0C` | PIVOT_REAR | Pivot axe arrière |
| `0x20` | RAW | Directions par roue (§3) |
| `0x30` | JOYSTICK | Joystick analogique (§4) |

---

## 2. Accusé de réception (ACK)

```
[0x55] [COMMAND]
```

---

## 3. Trame RAW mécanum (5 octets)

```
[SYNC][0x20][WHEEL_DIRECTION_BITS][MOTOR_SPEED][CHECKSUM]
```

2 bits par roue : avant-gauche, avant-droit, arrière-gauche, arrière-droit.

---

## 4. Trame joystick analogique (12 octets) — format actuel

Quatre axes analogiques + vitesse max :

```
[SYNC][CMD 0x30]
[STRAFE_LO][STRAFE_HI]
[FORWARD_LO][FORWARD_HI]
[SPIN_LO][SPIN_HI]
[PIVOT_LO][PIVOT_HI]
[MAX_SPEED][CHECKSUM]
```

| Champ | Type | Description |
|-------|------|-------------|
| **strafe** | int16 LE | Crab latéral : `> 0` = droite |
| **forward** | int16 LE | Avant/arrière : `< 0` = avant |
| **spin** | int16 LE | Rotation sur place : `> 0` = tourne à gauche |
| **pivot** | int16 LE | Virage type voiture : `> 0` = pivot droite |
| **MAX_SPEED** | uint8 | Plafond PWM `0..255` |
| **CHECKSUM** | uint8 | Somme des 11 premiers octets `& 0xFF` |

Plage des axes : `-32768..32767` (comme une manette Xbox).

### Noms dans le code (micro:bit)

| Concept | Fichier | Nom de variable |
|---------|---------|-----------------|
| Octets reçus | `ProtocolParser.h` | `UartIncomingFrame` |
| État du parseur | `ProtocolParser.h` | `UartParserState` |
| Octet strafe bas | | `strafe_byte_low` / `strafe_byte_high` |
| Octet forward bas | | `forward_byte_low` / `forward_byte_high` |
| Octet spin bas | | `spin_byte_low` / `spin_byte_high` |
| Octet pivot bas | | `pivot_byte_low` / `pivot_byte_high` |

### Mixer firmware (`MecanumJoystickMapper`)

```
roue_avant_gauche  = forward + strafe + spin  (+ pivot)
roue_avant_droite  = forward - strafe - spin
roue_arriere_gauche = forward - strafe + spin
roue_arriere_droite = forward + strafe - spin
```

Le **pivot** freine un côté (virage voiture). Le **spin** fait tourner sur place (toutes les roues).

### Exemple Python

```python
def build_joystick_frame(axis_strafe, axis_forward, axis_spin, axis_pivot, max_speed):
    payload = (
        int(axis_strafe).to_bytes(2, "little", signed=True)
        + int(axis_forward).to_bytes(2, "little", signed=True)
        + int(axis_spin).to_bytes(2, "little", signed=True)
        + int(axis_pivot).to_bytes(2, "little", signed=True)
        + bytes([max(0, min(255, max_speed))])
    )
    frame = bytes([0xAA, 0x30]) + payload
    return frame + bytes([sum(frame) & 0xFF])
```

Stop : `build_joystick_frame(0, 0, 0, 0, 0)`

---

## 5. Côté MaixCam

| Fichier | Rôle |
|---------|------|
| `lib/joystick_frame_builder.py` | Construit la trame 12 octets |
| `lib/controller_mapping_engine.py` | Manette → strafe, forward, spin, pivot |

Mapping par défaut : stick G Y = forward, stick G X = pivot, stick D X = spin, LT/RT = strafe.

---

## 6. Test PC

```bash
python tools/test_rover_menu.py
```

Port COM **mbed Serial** (pas DAPLink).
