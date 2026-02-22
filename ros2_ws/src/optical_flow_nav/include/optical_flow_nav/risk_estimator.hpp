#ifndef OPTICAL_FLOW_NAV__RISK_ESTIMATOR_HPP_
#define OPTICAL_FLOW_NAV__RISK_ESTIMATOR_HPP_

#include "optical_flow_nav/types.hpp"

namespace optical_flow_nav
{

struct RiskOutput
{
  bool forward_safe = true;
  float forward_risk = 0.0f;
  int8_t safest_turn = 0;
  float turn_confidence = 0.0f;
  float urgency_score = 0.0f;
  float confidence = 0.0f;
};

/**
 * Computes risk metrics from (possibly motion-compensated) band magnitudes.
 * Uses optional feature_count and flow_variance for confidence; flow_failed
 * forces confidence to 0 and safe defaults.
 */
class RiskEstimator
{
public:
  explicit RiskEstimator(const RiskParams & params);

  void set_params(const RiskParams & params);

  void set_prev_forward_risk(float r);
  void set_rotation_active(bool active);

  RiskOutput compute(
    const BandMagnitudes & bands,
    bool ignore_forward_risk,
    int feature_count,
    float flow_variance,
    float mask_coverage,
    bool flow_failed);

private:
  RiskParams params_;
  float prev_forward_risk_ = 0.0f;
  bool rotation_active_ = false;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__RISK_ESTIMATOR_HPP_
