#ifndef OPTICAL_FLOW_NAV__TYPES_HPP_
#define OPTICAL_FLOW_NAV__TYPES_HPP_

#include <string>
#include <vector>

namespace optical_flow_nav
{

struct FlowParams
{
  std::string method = "lucas_kanade";
  int resize_width = 320;
  int resize_height = 240;
  int history_window = 5;
  int min_features = 100;
};

struct FloorBandParams
{
  double bottom_fraction = 0.4;
};

struct PolygonParams
{
  std::vector<double> x;
  std::vector<double> y;
};

struct HSVFloorParams
{
  int h_min = 0, h_max = 180;
  int s_min = 0, s_max = 255;
  int v_min = 0, v_max = 255;
};

struct MaskParams
{
  bool enabled = true;
  std::string type = "floor_band";
  FloorBandParams floor_band;
  PolygonParams polygon;
  HSVFloorParams hsv_floor;
};

struct MotionCompensationParams
{
  bool enabled = true;
  double min_linear_velocity = 0.05;
  double ignore_rotation_threshold_deg_s = 15.0;
  double angular_damping_factor = 0.7;
};

struct RiskParams
{
  float forward_risk_threshold = 0.6f;
  float center_weight = 1.5f;
  float urgency_gain = 1.2f;
  float smoothing_alpha = 0.4f;
};

struct BandMagnitudes
{
  float flow_mag_left = 0.0f;
  float flow_mag_center = 0.0f;
  float flow_mag_right = 0.0f;
};

struct Telemetry
{
  double linear_velocity = 0.0;
  double angular_velocity = 0.0;
  bool has_data = false;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__TYPES_HPP_
