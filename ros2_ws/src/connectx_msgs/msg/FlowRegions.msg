# 3-region optical flow (left, center, right) single band.
# Units: magnitudes and vx/vy in pixels per second.

std_msgs/Header header

float32 left_mag
float32 center_mag
float32 right_mag

float32 left_vx
float32 left_vy
float32 center_vx
float32 center_vy
float32 right_vx
float32 right_vy
