# Rover Mecanum — MaixCam2 + Xbox

Installation sur la caméra : `/root/roverMecanum/`

Déploiement Windows : `tools/deploy_rover_mecanum.ps1`

Protocole UART (Little Endian, trame 12 octets) : [`../../microbit/PROTOCOL_FR.md`](../../microbit/PROTOCOL_FR.md)

---

## Schéma manette Xbox

Référence visuelle : [`../XBoxControler.jpg`](../XBoxControler.jpg)

---

## Table de correspondance (schéma → config)

### Axes analogiques

| Schéma manette | Rôle | Clé `config.json` | Code evdev MaixCam BT |
|----------------|------|-------------------|------------------------|
| Stick G — X | Horizontal gauche | `left_x` | ABS `0` |
| Stick G — Y | Vertical gauche | `left_y` | ABS `1` |
| Stick D — X | Horizontal droit | `right_x` | ABS `2` |
| Stick D — Y | Vertical droit | `right_y` | ABS `5` |
| LT | Gâchette gauche | `lt` | ABS `10` (BRAKE) |
| RT | Gâchette droite | `rt` | ABS `9` (GAS) |
| LT − RT | Crab | `trigger_diff` | calculé |

### Profil de conduite par défaut (`mapping_revision` ≥ 4)

| Axe rover | Clé config | Stick | Effet |
|-----------|------------|-------|-------|
| **forward** | `drive_forward` → `left_y` | Stick G Y | Avant / arrière |
| **strafe** | `drive_strafe` → `trigger_diff` | LT / RT | Crab latéral |
| **spin** | `drive_spin` → `right_x` | Stick D X | Rotation sur place |
| **pivot** | `drive_pivot` → `left_x` | Stick G X | Virage type voiture |

> **Spin** ≠ **Pivot** : spin = tourne sur place ; pivot = freine un côté (comme une voiture).

### D-pad (`mapping.dpad`)

Directions à **100 %** de vitesse (prioritaire sur les sticks).

| Direction | Clé | Action |
|-----------|-----|--------|
| Haut | `up` | `forward` |
| Bas | `down` | `backward` |
| Gauche / droite | `left` / `right` | `strafe_left` / `strafe_right` |
| Diagonales | `up_left`, … | `diag_fl`, … |

---

## Exemple config

```json
"mapping": {
  "axes": {
    "drive_forward": "left_y",
    "drive_strafe": "trigger_diff",
    "drive_spin": "right_x",
    "drive_pivot": "left_x"
  }
}
```

---

## Caméra / affichage

Preview vidéo + HUD. Écran MaixCam2 : **480×640 portrait**.

| Clé | Défaut | Description |
|-----|--------|-------------|
| `width` / `height` | `1280` / `720` | Résolution capteur (preview redimensionnée à l'écran) |
| `fps` | `30` | FPS capture |
| `format` | `yuv420` | `yuv420` (recommandé), `rgb888` max ~640×480 sur MaixCam2 |
| `display_fps` | `15` | FPS HUD — garder bas pour ne pas bloquer la manette |

**Priorité manette** : evdev est lu sur la boucle principale (~1 ms). La caméra et l'affichage tournent en threads séparés avec pacing.

Latence minimale vidéo : `"width": 480, "height": 640, "format": "yuv420"`.

Désactiver la caméra : `"enabled": false`.

---

## Firmware micro:bit

**Reflasher** après mise à jour (trame 12 octets, axes nommés strafe/forward/spin/pivot).

---

## Fichiers lib/ importants

| Module | Rôle |
|--------|------|
| `camera_preview_service.py` | Capture 1080p (thread) |
| `controller_mapping_engine.py` | Manette → forward, strafe, spin, pivot |
| `joystick_frame_builder.py` | Trame UART |
| `ProtocolParser.h` (micro:bit) | `UartIncomingFrame`, noms d’octets explicites |
