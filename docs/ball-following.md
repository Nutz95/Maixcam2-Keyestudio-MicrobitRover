# Green-ball following mode

The rover has two control modes:

- `MANUAL`: the Xbox sticks drive the rover;
- `BALL FOLLOW`: the MaixCAM2 detects a colored ball and sends a bounded
  forward/spin command.

Press the Xbox **View/Select** button (button 6 in the evdev map) to toggle the
mode. Press **Menu/Start** to cycle the blob color between `green` and `red`
(the MaixPy demo red LAB band, useful for pink/orange balls). The HUD always
shows the active mode and color. Leaving `BALL FOLLOW` sends a stop before
manual joystick commands are accepted again. While `BALL FOLLOW` is active the
joystick gauges are hidden so the camera blob overlay stays readable.

<p align="center">
  <img src="../maixcam/XBoxControler.jpg" alt="Xbox controller button map" width="900">
</p>

## First implementation

The first controller is intentionally sequential:

1. Align the ball horizontally with a bounded rotation.
2. Approach while the ball is small or high in the image.
3. Retreat when the ball is too large or too low in the image.
4. Stop inside the target distance band.
5. Stop for two seconds when the target is lost.
6. Search with one turn toward the last exit side/trajectory (`search_turn_deg`
   when IMU yaw is ready, else `search_turn_ms`).
7. Pause, reverse briefly (ball may be under the camera), pause, then turn again.

Closed-loop control is intentional: every teleop tick runs detect → decide →
UART. Oscillation is a gain/delay problem, not a reason to freeze motors while
vision runs. Prediction defaults to `0` ms because predicting while the rover
itself is spinning often adds lag and overshoot.

Motor shaping differs from teleop: Xbox sticks use `rover.axis_curve` (usually
`expo`, soft center). Ball-follow uses a **linear** visual error with a
**breakaway floor** (`min_spin_axis` / `min_forward_axis`) so small corrections
still clear static friction, and a lower `max_retreat_axis` so too-close reverse
is less brutal than approach. Floor and ceiling also **scale with error size**
(far → full authority, near target/center → softer) so the rover eases in
instead of kicking at the same PWM for every correction.

## IMU yaw

`ImuYawService` runs Mahony AHRS on a worker thread (MaixPy `imu.IMU` +
`ahrs.MahonyAHRS`). On start it loads a saved gyro bias when present; otherwise
the HUD shows `need_calib`.

During gyro calibration the HUD switches to a fullscreen ASCII "HOLD STILL"
screen with a live percent + progress bar. Sampling is cooperative so the bar
can animate (MaixPy ``calib_gyro`` alone freezes the UI). Joystick overlays are
hidden; motors stay stopped; Xbox drive input is ignored.

When yaw is ready, lost-ball search rotates until `|Δyaw| >= search_turn_deg`
(default 350°), with a `3 × search_turn_ms` safety timeout. Without a usable
yaw sample, search falls back to the timed turn.

Still later (not in v1): breakaway probe from yaw-rate, and plant-ID seeding of
spin gains.

Camera tilt (~20°) mainly affects pitch/roll gravity axes and ground-plane
geometry. For yaw-only rotation control, calibrated gyro-Z / AHRS yaw is enough;
a full body↔camera quaternion is not required.

The command contains only `forward` and `spin`; strafe and pivot remain zero.
This avoids asking the mecanum mixer to solve several uncertain errors at once.
The `forward_axis_sign` and `spin_axis_sign` settings exist because the physical
sign must be checked with the wheels lifted before the first floor test.

Blob height is a distance proxy, not a metric depth measurement. The default
target is 22% of image height so the rover keeps more standoff than the first
30% setting. `too_close_height_ratio` is 38%.

The detector uses MaixPy `image.find_blobs()` with integer LAB thresholds
(`List[List[int]]`). The configured presets are:

- green: `[40, 90, -90, -40, 25, 75]` from live samples
  `L=60..70, A=-64..-61, B=47..52`;
- red/pink/orange: `[0, 80, 40, 80, 10, 80]` from the MaixPy find_blobs demo.

It filters tiny and very elongated blobs, then selects the largest compact
candidate. Tune these thresholds on the actual ball and lighting.

## Camera and performance

The configured capture target is 640×480 at 60 FPS, while the HUD remains at
its display cadence. The local MaixPy examples use 60 FPS at 640×360 and
320×320, and MaixCDK exposes FPS as a camera parameter. There is no project
evidence of an official 640×480 ceiling, so the setting is a measured target:
if the installed sensor/firmware rejects it, lower `camera.fps` in
`maixcam/roverMecanum/config.json`.

The current implementation uses blob detection, not YOLO or a second NPU model.
That keeps latency and memory predictable. A depth model can be added later if
the size/position calibration is not sufficient; it is not required for the
first safety-controlled approach loop.

## Geometry and safety assumptions

Current calibration assumptions:

- ball diameter: 35 mm;
- the initial green LAB threshold has been calibrated from the live samples
  `L=60..70, A=-64..-61, B=47..52`, with operating margin
  `[40, 90, -90, -40, 25, 75]`;
- the red preset uses the MaixPy demo band `[0, 80, 40, 80, 10, 80]` for
  pink/orange balls;
- camera pivot height: 7 cm above the wheel/ground plane;
- lens offset from the pivot: 4.5 cm along the 20° camera axis, which gives an
  estimated lens height of 8.5 cm and a horizontal offset of 4.2 cm;
- the supplied top view shows an approximately 11 cm rover footprint;
- OS04D10 lens: approximately 3.05 mm focal length, 90° horizontal FOV,
  51° vertical FOV.

The dimensions are useful for the next calibration pass, but they are not yet
used to claim metric distance. The current stop distance is deliberately
calibrated from blob height and center Y. The next geometry-based calibration
can use the estimated 8.5 cm lens height and 20° pitch for a ground-plane
projection.

The MaixPy depth example currently demonstrates `get_depth_image()` rendering,
not a numeric distance value for a selected pixel. ByteTrack is demonstrated
for YOLO objects and would require an object-detector object conversion for
blob candidates. The current bounded 80 ms prediction is therefore kept as the
low-latency first step.

The MaixPy IMU path is wired through `ImuYawService` for gyro bias calibration
and yaw-closed search turns. Visual horizontal error remains the primary
align correction; maximum spin is still limited in configuration. The robot
has no implemented shock sensor interface in this repository, so impact
prevention currently comes from the conservative too-close band and immediate
stop transitions.

## Calibration procedure

1. Lift the drive wheels and confirm the signs of forward and spin.
2. Put the ball at known distances (10, 20, 40, and 80 cm).
3. Record blob height, center Y, width, and detection stability.
4. Tune `thresholds`, `area_threshold`, and aspect limits.
5. Tune `target_height_ratio` to the desired stopping distance.
6. Tune `too_close_height_ratio` and `too_close_center_y_ratio` before increasing
   either speed limit.
7. Test target loss and search with the wheels lifted.
8. Test approach on a clear floor at the configured low limits.

## Deferred extensions

- metric distance from the 35 mm diameter and calibrated camera model;
- depth-model comparison or a second NPU model;
- IMU-assisted yaw-rate limiting and visual/IMU fusion;
- short-term trajectory prediction beyond the current bounded 80 ms blob
  prediction;
- a physical impact sensor and emergency-stop input.

These extensions should be added only after the blob controller is stable on
hardware.
