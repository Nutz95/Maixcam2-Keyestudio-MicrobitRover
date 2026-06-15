# Protocole UART MaixCam ↔ micro:bit (rover mécanum)

Firmware : `microbit/src/`  
Vitesse : **115200** baud, 8N1  
Broches edge micro:bit : **P1 = TX**, **P2 = RX**

Le même protocole est accepté sur **P1/P2** (MaixCam) et sur le **port USB mbed** (tests PC).

---

## Octets communs

| Valeur | Nom | Rôle |
|--------|-----|------|
| `0xAA` | `PROTO_SYNC` | Début de trame |
| `0x55` | `PROTO_ACK` | Accusé réception (voir ci-dessous) |

---

## 1. Trame prédéfinie (4 octets)

```
[0xAA] [CMD] [SPEED] [CHECKSUM]
```

| Champ | Description |
|-------|-------------|
| `CMD` | Code mouvement (table ci-dessous) |
| `SPEED` | PWM moteur `0..255` (`0` = arrêt) |
| `CHECKSUM` | `(0xAA + CMD + SPEED) & 0xFF` |

### Codes CMD

| CMD | Nom | Mouvement |
|-----|-----|-----------|
| `0x00` | STOP | Arrêt immédiat |
| `0x01` | FORWARD | Tout en avant |
| `0x02` | BACKWARD | Tout en arrière |
| `0x03` | STRAFE_LEFT | Crab gauche |
| `0x04` | STRAFE_RIGHT | Crab droite |
| `0x05` | DIAG_FL | Diagonale avant-gauche |
| `0x06` | DIAG_FR | Diagonale avant-droite |
| `0x07` | DIAG_BL | Diagonale arrière-gauche |
| `0x08` | DIAG_BR | Diagonale arrière-droite |
| `0x09` | SPIN_LEFT | Rotation sur place (anti-horaire) |
| `0x0A` | SPIN_RIGHT | Rotation sur place (horaire) |
| `0x0B` | PIVOT_RIGHT | Pivot côté droit |
| `0x0C` | PIVOT_REAR | Pivot axe arrière |
| `0x20` | RAW | Directions par roue (voir §3) |
| `0x30` | JOYSTICK | Axes analogiques 3D (voir §4) |

### Exemples (SPEED = 100 = `0x64`)

| Action | Trame hex |
|--------|-----------|
| Avancer | `AA 01 64 0F` |
| Arrêter | `AA 00 00 AA` |
| Strafe droite | `AA 04 64 12` |
| Spin droite | `AA 0A 64 18` |

---

## 2. Accusé de réception (ACK)

Après une trame valide :

```
[0x55] [CMD]
```

`CMD` = octet de commande reçu (ex. `0x30` pour joystick).

---

## 3. Trame RAW mécanum (5 octets)

```
[0xAA] [0x20] [WHEEL_DIRS] [SPEED] [CHECKSUM]
```

| Champ | Description |
|-------|-------------|
| `WHEEL_DIRS` | 2 bits par roue : UL, UR, LL, LR |
| `SPEED` | PWM `0..255` |
| `CHECKSUM` | `(0xAA + 0x20 + WHEEL_DIRS + SPEED) & 0xFF` |

### Bits WHEEL_DIRS

| Bits | Roue |
|------|------|
| 0-1 | Upper Left (avant gauche) |
| 2-3 | Upper Right (avant droite) |
| 4-5 | Lower Left (arrière gauche) |
| 6-7 | Lower Right (arrière droite) |

| Valeur 2 bits | Direction |
|---------------|-----------|
| `00` | Stop |
| `01` | Avant |
| `10` | Arrière |
| `11` | Réservé (traité comme stop) |

---

## 4. Trame joystick analogique (10 octets) — format actuel

Mixer mécanum 3 axes : strafe (X), forward (Y), rotation (R).

```
[0xAA] [0x30] [X_LO] [X_HI] [Y_LO] [Y_HI] [R_LO] [R_HI] [MAX_SPEED] [CHECKSUM]
```

| Champ | Type | Description |
|-------|------|-------------|
| `X` | int16 LE | **Strafe** (crab) : `> 0` = droite |
| `Y` | int16 LE | **Forward** : `< 0` = avant (repère HID / écran) |
| `R` | int16 LE | **Rotation** : `> 0` = spin left |
| `MAX_SPEED` | uint8 | Plafond PWM `0..255` |
| `CHECKSUM` | uint8 | Somme des 9 premiers octets `& 0xFF` |

Plage axes : `-32768..32767` (style Xbox).

### Mixer firmware (`MecanumJoystickMapper`)

Après deadzone (défaut **2 %**, `DEFAULT_JOYSTICK_DEADZONE_PERCENT` dans `Protocol.h`) :

```
UL =  Y + X + R
UR =  Y - X - R
LL =  Y - X + R
LR =  Y + X - R
```

(Y est inversé côté firmware : `forward = -axis_y` reçu.)

Vitesse effective proportionnelle à l'amplitude :

```
effective = MAX_SPEED × max(|X|, |Y|, |R|) / 32768
```

### Exemple Python

```python
def build_joystick(axis_x, axis_y, axis_rot, max_speed):
    payload = (
        int(axis_x).to_bytes(2, "little", signed=True)
        + int(axis_y).to_bytes(2, "little", signed=True)
        + int(axis_rot).to_bytes(2, "little", signed=True)
        + bytes([max(0, min(255, max_speed))])
    )
    frame = bytes([0xAA, 0x30]) + payload
    return frame + bytes([sum(frame) & 0xFF])
```

Stop : `build_joystick(0, 0, 0, 0)`

### Ancien format (8 octets, obsolète)

```
[0xAA] [0x30] [X] [Y] [MAX_SPEED] [CHK]
```

Incompatible avec le firmware actuel.

---

## 5. Côté MaixCam

| Fichier | Rôle |
|---------|------|
| `lib/joystick_frame_builder.py` | Trame 10 octets |
| `lib/controller_mapping_engine.py` | Manette → X, Y, R |

Mapping par défaut : stick G Y/X = forward/rotation, LT/RT = crab.

---

## 6. Test PC

```bash
python tools/test_rover_menu.py
```

Port COM **mbed Serial** (pas DAPLink).
