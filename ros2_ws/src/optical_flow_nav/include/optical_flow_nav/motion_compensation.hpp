#ifndef OPTICAL_FLOW_NAV__MOTION_COMPENSATION_HPP_
#define OPTICAL_FLOW_NAV__MOTION_COMPENSATION_HPP_

#include "optical_flow_nav/types.hpp"

namespace optical_flow_nav
{

/**
 * Applies motion compensation: if rotating, damp center band; if linear velocity
 * below threshold, forward risk is ignored (caller can zero it). Returns
 * adjusted band magnitudes and a flag indicating whether forward risk should
 * be ignored.
 */
struct MotionCompensationResult
{
  BandMagnitudes adjusted;
  bool ignore_forward_risk = false;
};

class MotionCompensation
{
public:
  explicit MotionCompensation(const MotionCompensationParams & params);

  void set_params(const MotionCompensationParams & params);

  MotionCompensationResult apply(
    const BandMagnitudes & raw,
    const Telemetry & telemetry) const;

private:
  MotionCompensationParams params_;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__MOTION_COMPENSATION_HPP_
