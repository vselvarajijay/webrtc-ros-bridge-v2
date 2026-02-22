#include "optical_flow_nav/risk_estimator.hpp"
#include <cmath>
#include <algorithm>

namespace optical_flow_nav
{

namespace
{
float clamp01(float x)
{
  if (std::isnan(x) || std::isinf(x)) { return 0.0f; }
  return std::max(0.0f, std::min(1.0f, x));
}
}  // namespace

RiskEstimator::RiskEstimator(const RiskParams & params)
: params_(params)
{
}

void RiskEstimator::set_params(const RiskParams & params)
{
  params_ = params;
}

void RiskEstimator::set_prev_forward_risk(float r)
{
  prev_forward_risk_ = clamp01(r);
}

void RiskEstimator::set_rotation_active(bool active)
{
  rotation_active_ = active;
}

RiskOutput RiskEstimator::compute(
  const BandMagnitudes & bands,
  bool ignore_forward_risk,
  int feature_count,
  float flow_variance,
  float mask_coverage,
  bool flow_failed)
{
  RiskOutput out;
  if (flow_failed) {
    out.confidence = 0.0f;
    out.forward_safe = true;
    out.forward_risk = 0.0f;
    out.safest_turn = 0;
    out.turn_confidence = 0.0f;
    out.urgency_score = 0.0f;
    return out;
  }

  float left = bands.flow_mag_left;
  float center = bands.flow_mag_center;
  float right = bands.flow_mag_right;
  if (std::isnan(left)) { left = 0.0f; }
  if (std::isnan(center)) { center = 0.0f; }
  if (std::isnan(right)) { right = 0.0f; }

  float forward_risk = 0.0f;
  if (!ignore_forward_risk) {
    float weighted_center = center * params_.center_weight;
    float denom = left + right + 1e-6f;
    forward_risk = weighted_center / (1.0f + denom * 0.5f);
    forward_risk = clamp01(forward_risk);
  }
  out.forward_risk = forward_risk;
  out.forward_safe = (forward_risk < params_.forward_risk_threshold);

  float diff = std::fabs(left - right);
  float sum_lr = left + right + 1e-6f;
  out.turn_confidence = clamp01(diff / sum_lr);
  if (left < right) {
    out.safest_turn = -1;
  } else if (right < left) {
    out.safest_turn = 1;
  } else {
    out.safest_turn = 0;
  }

  float risk_growth = forward_risk - prev_forward_risk_;
  float smoothed_risk = params_.smoothing_alpha * forward_risk +
    (1.0f - params_.smoothing_alpha) * prev_forward_risk_;
  float urgency = (smoothed_risk + std::max(0.0f, risk_growth)) * params_.urgency_gain;
  out.urgency_score = clamp01(urgency);
  prev_forward_risk_ = forward_risk;

  float conf = 1.0f;
  if (feature_count >= 0 && feature_count < 20) {
    conf *= 0.3f + 0.7f * (feature_count / 20.0f);
  }
  if (flow_variance >= 0.0f && flow_variance > 1e6f) {
    conf *= 0.5f;
  }
  if (mask_coverage >= 0.0f && mask_coverage < 0.1f) {
    conf *= 0.5f;
  }
  if (rotation_active_) {
    conf *= 0.8f;
  }
  out.confidence = clamp01(conf);

  return out;
}

}  // namespace optical_flow_nav
