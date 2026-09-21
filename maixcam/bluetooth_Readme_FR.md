# Bluetooth MaixCam2 + manette Xbox

## Activation

```shell
bluetoothctl power on
bluetoothctl pairable on
```

BlueZ (`bluetoothctl`) est fourni par Ubuntu sur MaixCam2 — pas de dépendance Python supplémentaire.

Doc Sipeed : https://wiki.sipeed.com/maixpy/doc/en/modules/bluetooth.html

## Pairing chiffré (obligatoire pour le joystick)

Sans connexion chiffrée, BlueZ peut afficher `Connected: yes` + UUID HID **sans** créer
`/dev/input/event*` pour la manette. Les sticks ne marchent pas.

L'app démarre un **bluetoothctl PTY** au lancement (`agent NoInputNoOutput`) et
le laisse vivant jusqu'à la sortie.

**ERTM** (`disable_ertm=Y`) : mode L2CAP « Enhanced Retransmission ». Sur le
noyau **4.19** de la MaixCam2, ERTM casse souvent le HID Xbox (boucle
`Connected: yes/no`, pas de `/dev/input/event*`). L'app écrit `Y` dans
`/sys/module/bluetooth/parameters/disable_ertm` au démarrage — voir
`lib/bluetooth_installer.py`.

| Bouton UI | Action |
|-----------|--------|
| **PAIR** | retire l'ancien bond + nouveau bond chiffré (hold **SYNC**, logo clignote vite) |
| **CONNECT** | reconnecte un bond déjà bon (logo Xbox court, pas SYNC) |

Succès réel = logo **fixe** + `HID reports flowing` dans les logs (pas seulement `Connected: yes`).

Aussi : **oublier la manette sur le PC** pendant le pair (sinon elle reste collée au PC).

## Application production

| Composant | Rôle |
|-----------|------|
| `lib/bluetoothctl_session.py` | Session PTY longue durée + agent BlueZ |
| `lib/bluetoothctl_runner.py` | Parse des sorties bluetoothctl |
| `lib/bluetooth_pairing_service.py` | Flux PAIR / CONNECT de l'UI |
| `lib/xbox_input_service.py` | Thread BT + poll evdev |

```powershell
cd tools
.\deploy_rover_mecanum.ps1 -DeployOnly -SyncConfig
```

Voir [`maixcam/roverMecanum/README_FR.md`](roverMecanum/README_FR.md) pour le mapping manette.

## Erreurs fréquentes

- Scan vide → SYNC clignotement rapide, <1 m, manette oubliée sur le PC
- Boucle `Connected: yes` / `Connected: no` avant PAIR → ancien bond cassé (souvent firmware Xbox / noyau 4.19). Appuyer **PAIR** (l'app fait `remove` + re-bond). Si le scan ne trouve rien, l'app lit aussi `bluetoothctl devices`
- Logo clignote + Connected yes/no après PAIR → firmware Xbox pas à jour via **Xbox Accessories** (Windows), puis re-PAIR
- HID UUID sans event → PAIR (remove + bond chiffré)
- Crash `JSONDecodeError` sur `config.json` → corrigé (écriture atomique) ; si le fichier est encore vide, redéployer `-SyncConfig`
- Ne jamais `bluetoothctl disconnect` hors PAIR (éteint souvent la manette)

## Deadzone joystick rover

Le firmware micro:bit applique une deadzone de **2%** par défaut (`DEFAULT_JOYSTICK_DEADZONE_PERCENT`).

Pour tester sans MaixCam : `tools/test_rover_menu.py` → `j` avec par ex. `X=0`, `Y=-20000`.
