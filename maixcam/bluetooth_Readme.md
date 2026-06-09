# Bluetooth MaixCam2 + manette Xbox

## Activation

```shell
bluetoothctl power on
echo "bluetoothctl power on" >> /etc/rc.local
pip install bleak
```

Doc Sipeed : https://wiki.sipeed.com/maixpy/doc/en/modules/bluetooth.html

## Scripts

| Script | Role |
|--------|------|
| `maixcam_scan_bluetooth.py` | Scan des peripheriques BLE |
| `bluetooth_connect.py` | Test console : connexion + abonnement HID Xbox |
| `maixcam_xbox_rover.py` | **IHM** : CONNECT manette -> stick G -> UART rover |
| `maixcam_joystick_pad.py` | Pad tactile -> UART rover |
| `maixcam_test_rover.py` | Boutons de mouvements discrets |

## Manette Xbox

`bluetooth_connect.py` fait tout automatiquement :

1. `bluetoothctl` : agent + scan + pair + trust + connect
2. Scan bleak + connexion avec `pair=True`
3. Si HID `0x1812` absent : `client.pair()` + reconnexion
4. Abonnement notify sur `0x2A4D` (service HID)

Sans pairing chiffre, seuls les services Microsoft/batterie sont visibles
(pas de joystick). C'est le comportement normal avant appairage.

Erreurs frequentes :
- `device not found` → relancer (scan bleak obligatoire avant connect)
- HID absent apres connect → refaire pairing (`bluetoothctl remove MAC` puis relancer)

L'exemple doc Sipeed qui lit `MODEL_NBR_UUID = 1A2A` est un exemple generique.
Ce n'est **pas** le bon UUID pour piloter une manette.

## Deadzone joystick rover

Le firmware micro:bit applique une deadzone de **12%** (~3932 sur 32768).

Les tests Windows avec `300` ou `1000` recoivent bien un ACK mais **ne bougent pas** les moteurs :
c'est normal, la valeur est sous la deadzone.

Pour tester :
- pad MaixCam : glisser le doigt vers le bord du rectangle
- menu Windows `j` : utiliser par ex. `X=0`, `Y=-20000`
