# Bluetooth MaixCam2 + manette Xbox

## Activation

```shell
bluetoothctl power on
echo "bluetoothctl power on" >> /etc/rc.local
```

BlueZ (`bluetoothctl`) est fourni par Ubuntu sur MaixCam2 — pas de dépendance Python supplémentaire.

Doc Sipeed : https://wiki.sipeed.com/maixpy/doc/en/modules/bluetooth.html

## Application production

L'app packagée **`maixcam/roverMecanum/`** gère le scan, l'appairage et la connexion Xbox via **bluetoothctl** + **evdev**.

| Composant | Rôle |
|-----------|------|
| `lib/bluetoothctl_runner.py` | Scan, pair, connect (BlueZ natif) |
| `lib/bluetooth_pairing_service.py` | Flux PAIR / CONNECT de l'UI |
| `lib/xbox_input_service.py` | Thread BT + poll evdev |

## Déploiement MaixCam

```powershell
cd tools
.\deploy_rover_mecanum.ps1
```

Installe dans `/root/roverMecanum/` (config, lib, script principal).

Voir [`maixcam/roverMecanum/README_FR.md`](roverMecanum/README_FR.md) pour le mapping manette.

## Manette Xbox

Ne jamais `bluetoothctl disconnect` (éteint la manette).

Sans pairing chiffré, seuls les services Microsoft/batterie sont visibles
(pas de joystick). C'est le comportement normal avant appairage.

Erreurs fréquentes :
- `device not found` → maintenir le bouton sync Xbox, relancer PAIR (scan bluetoothctl)
- HID absent après connect → refaire pairing (`bluetoothctl remove MAC` puis relancer)

L'exemple doc Sipeed qui lit `MODEL_NBR_UUID = 1A2A` est un exemple générique.
Ce n'est **pas** le bon UUID pour piloter une manette.

## Deadzone joystick rover

Le firmware micro:bit applique une deadzone de **2%** par défaut (`DEFAULT_JOYSTICK_DEADZONE_PERCENT`).

Les tests PC avec de petites valeurs reçoivent bien un ACK mais **ne bougent pas** les moteurs :
c'est normal si la valeur est sous la deadzone.

Pour tester :
- app MaixCam : sticks Xbox
- menu Windows `tools/test_rover_menu.py` → `j` : utiliser par ex. `X=0`, `Y=-20000`
