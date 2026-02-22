#ifndef OPTICAL_FLOW_NAV__FLOW_ESTIMATOR_HPP_
#define OPTICAL_FLOW_NAV__FLOW_ESTIMATOR_HPP_

#include <opencv2/core.hpp>
#include "optical_flow_nav/types.hpp"

namespace optical_flow_nav
{

class FlowEstimator
{
public:
  explicit FlowEstimator(const FlowParams & params);

  void set_params(const FlowParams & params);

  /**
   * Compute flow magnitude map from previous and current grayscale frames.
   * Mask: 0 = ignore, non-zero = use. Optional; if empty, use full image.
   * Returns single-channel float magnitude image (same size as curr).
   * On failure returns empty cv::Mat and feature_count is 0.
   */
  cv::Mat compute_flow(
    const cv::Mat & prev_gray,
    const cv::Mat & curr_gray,
    const cv::Mat & mask,
    int & feature_count);

private:
  cv::Mat compute_flow_lucas_kanade(
    const cv::Mat & prev_gray,
    const cv::Mat & curr_gray,
    const cv::Mat & mask,
    int & feature_count);

  cv::Mat compute_flow_farneback(
    const cv::Mat & prev_gray,
    const cv::Mat & curr_gray,
    const cv::Mat & mask);

  FlowParams params_;
  cv::Mat prev_points_buf_;
  cv::Mat curr_points_buf_;
  std::vector<cv::Point2f> prev_points_;
  std::vector<cv::Point2f> curr_points_;
};

}  // namespace optical_flow_nav

#endif  // OPTICAL_FLOW_NAV__FLOW_ESTIMATOR_HPP_
