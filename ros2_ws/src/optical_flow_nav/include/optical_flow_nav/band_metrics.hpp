#ifndef OPTICAL_FLOW_NAV__BAND_METRICS_HPP_
#define OPTICAL_FLOW_NAV__BAND_METRICS_HPP_

#include <opencv2/core.hpp>
#include "optical_flow_nav/types.hpp"

namespace optical_flow_nav
{

/**
 * Divides image into N vertical bands (default 3) and computes mean flow
 * magnitude per band over valid (unmasked) pixels.
 */
class BandMetrics
{
public:
  static constexpr int DEFAULT_NUM_BANDS = 3;

  explicit BandMetrics(int num_bands = DEFAULT_NUM_BANDS);

  void set_num_bands(int num_bands);

  BandMagnitudes compute(
    const cv::Mat & flow_magnitude,
    const cv::Mat & mask) const;

private:
  int num_bands_;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__BAND_METRICS_HPP_
