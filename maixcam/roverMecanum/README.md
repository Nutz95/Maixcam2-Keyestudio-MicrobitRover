# Rover Mecanum — MaixCam2 + Xbox

Installation sur la caméra : `/root/roverMecanum/`

Déploiement depuis Windows : `tools/deploy_rover_mecanum.ps1`

## config.json

Fichier persistant : `/root/roverMecanum/config.json` (jamais `/tmp/`).

| Clé | Description |
|-----|-------------|
| `controller_name` | Nom BLE affiché au scan (ex. `Xbox Wireless Controller`) |
| `controller_mac` | Rempli automatiquement après le premier scan/appairage |
| `rover.max_speed` | 0–255 (`255` = 100 % vitesse moteurs) |
| `rover.deadzone_percent` | Deadzone logicielle MaixCam (défaut `2`) |
| `rover.rotate_threshold` | Seuil stick droit pour rotation (défaut `12000`) |
| `rover.send_interval_ms` | Période d'envoi UART (défaut `50`) |
| `rover.wait_ack` | `false` recommandé en batterie (moins de blocage UART) |

## Mapping axes (`mapping.axes`)

Sources disponibles pour `drive_forward`, `drive_strafe`, `drive_rotate` :

| Source | Description |
|--------|-------------|
| `left_x` | Stick gauche horizontal |
| `left_y` | Stick gauche vertical (avant/arrière) |
| `right_x` | Stick droit horizontal (rotation par défaut) |
| `right_y` | Stick droit vertical |
| `lt` | Gâchette gauche (LT) |
| `rt` | Gâchette droite (RT) |
| `trigger_diff` | RT − LT (crab / strafe) |

### Profil par défaut

- **Avant/arrière** : `left_y`
- **Crab (strafe)** : `trigger_diff` (LT / RT)
- **Rotation** : `right_x` (envoie `spin_left` / `spin_right`)

Inversions : `mapping.invert.left_y`, `trigger_diff`, `right_x` (`true` / `false`).

## Mapping boutons (`mapping.buttons`)

Valeurs d'action possibles :

| Action | Effet rover |
|--------|-------------|
| `stop` | Arrêt |
| `forward` | Avant |
| `backward` | Arrière |
| `strafe_left` | Crab gauche |
| `strafe_right` | Crab droite |
| `diag_fl` / `diag_fr` / `diag_bl` / `diag_br` | Diagonales |
| `spin_left` / `spin_right` | Rotation sur place |
| `pivot_right` / `pivot_rear` | Pivot |
| `null` | Ignoré |

Boutons reconnus : `btn_a`, `btn_b`, `btn_x`, `btn_y`, `btn_lb`, `btn_rb`, `btn_start`, `btn_select`.

## Firmware micro:bit

Reflasher après changement de `DEFAULT_JOYSTICK_DEADZONE_PERCENT` (défaut projet : **2 %**).

## Structure lib/

Une classe = un fichier :

- `config_store.py` — lecture/écriture config
- `bluetooth_installer.py` — `pip install bleak`, `bluetoothctl power on`
- `bluetooth_pairing_service.py` — scan par nom + appairage
- `xbox_input_service.py` — thread connexion + evdev
- `controller_mapping_engine.py` — mapping config → commandes
- `rover_uart_client.py` — envoi UART
- `xbox_rover_app.py` — boucle IHM
