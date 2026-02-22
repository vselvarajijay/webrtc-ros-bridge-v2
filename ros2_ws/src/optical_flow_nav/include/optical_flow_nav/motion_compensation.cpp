#include "optical_flow_nav/motion_compensation.hpp"
#include <cmath>
#include <algorithm>

namespace optical_flow_nav
{

namespace
{
constexpr double DEG2RAD = 3.141592653589793 / 180.0;
}

MotionCompensation::MotionCompensation(const MotionCompensationParams & params)
: params_(params)
{
}

void MotionCompensation::set_params(const MotionCompensationParams & params)
{
  params_ = params;
}

MotionCompensationResult MotionCompensation::apply(
  const BandMagnitudes & raw,
  const Telemetry & telemetry) const
{
  MotionCompensationResult out;
  out.adjusted = raw;

  if (!params_.enabled || !telemetry.has_data) {
    return out;
  }

  double lin = telemetry.linear_velocity;
  double ang_deg_s = std::fabs(telemetry.angular_velocity) / DEG2RAD;
  double threshold_deg_s = params_.ignore_rotation_threshold_deg_s;

  if (lin < params_.min_linear_velocity) {
    out.ignore_forward_risk = true;
  }

  if (ang_deg_s >= threshold_deg_s) {
    float d = static_cast<float>(params_.angular_damping_factor);
    d = std::max(0.0f, std::min(1.0f, d));
    out.adjusted.flow_mag_center = raw.flow_mag_center * d;
    out.adjusted.flow_mag_left = raw.flow_mag_left;
    out.adjusted.flow_mag_right = raw.flow_mag_right;
  }

  return out;
}

}  // namespace optical_flow_nav
