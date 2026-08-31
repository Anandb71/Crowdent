# Architecture

Six stages. Two of them look like networks; the rest is physics.

1. **Sensor conditioning** — accelerometer and gyroscope interpolated
   onto one 100 Hz clock.
2. **Alignment** — gravity gives roll and pitch; first motion gives yaw.
3. **Virtual odometer** — pedestrian bounce or 8-24 Hz chassis
   vibration to a speed. Never `∫ a dt`.
4. **Filter** — heading, speed, position, gyro bias. Corrected by the
   odometer, the non-holonomic constraint, and zero-velocity updates.
5. **Trust** — turn rate and speed jerk widen the measurement noise.
6. **Output** — 10 Hz pose, drift against a surveyed end point.

A network trained to emit position memorises roads. Speed and
uncertainty are local. Position is an integral of facts a vehicle
cannot break.

The room-walk and tunnel replays are synthetic. They exist so the
laptop fallback is deterministic offline. They are not IO-VNBD scores.
