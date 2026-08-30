# PookalBot Autonomous Control Service

Autonomous localization, closed-loop pure-pursuit trajectory following, and hardware bridge for PookalBot.

## Key Features:
- **Checkerboard Homography Calibration**: Maps overhead camera pixels to real-world floor centimeters.
- **Sensor Fusion**: Combines ArUco optical tracking with optical flow mouse odometry.
- **Closed-Loop Pure Pursuit**: Steers differential drive motors over UDP with pen servo actuation.
