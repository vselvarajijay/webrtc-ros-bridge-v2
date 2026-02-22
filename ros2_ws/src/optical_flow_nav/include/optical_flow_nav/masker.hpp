#ifndef OPTICAL_FLOW_NAV__MASKER_HPP_
#define OPTICAL_FLOW_NAV__MASKER_HPP_

#include <opencv2/core.hpp>
#include "optical_flow_nav/types.hpp"

namespace optical_flow_nav
{

/**
 * Produces a single-channel mask (0 = ignore, 255 = use).
 * Image can be BGR or grayscale; for hsv_floor, BGR is converted to HSV.
 */
class Masker
{
public:
  explicit Masker(const MaskParams & params);

  void set_params(const MaskParams & params);

  cv::Mat compute_mask(const cv::Mat & image);

private:
  cv::Mat compute_none(const cv::Mat & image);
  cv::Mat compute_floor_band(const cv::Mat & image);
  cv::Mat compute_polygon(const cv::Mat & image);
  cv::Mat compute_hsv_floor(const cv::Mat & image);

  MaskParams params_;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__MASKER_HPP_
