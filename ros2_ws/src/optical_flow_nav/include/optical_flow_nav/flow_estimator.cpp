#include "optical_flow_nav/flow_estimator.hpp"
#include <opencv2/imgproc.hpp>
#include <opencv2/video.hpp>

namespace optical_flow_nav
{

FlowEstimator::FlowEstimator(const FlowParams & params)
: params_(params)
{
}

void FlowEstimator::set_params(const FlowParams & params)
{
  params_ = params;
}

cv::Mat FlowEstimator::compute_flow(
  const cv::Mat & prev_gray,
  const cv::Mat & curr_gray,
  const cv::Mat & mask,
  int & feature_count)
{
  feature_count = 0;
  if (prev_gray.empty() || curr_gray.empty() ||
      prev_gray.size() != curr_gray.size() ||
      prev_gray.type() != CV_8UC1 || curr_gray.type() != CV_8UC1)
  {
    return cv::Mat();
  }

  if (params_.method == "farneback") {
    cv::Mat mag = compute_flow_farneback(prev_gray, curr_gray, mask);
    if (!mag.empty()) {
      feature_count = prev_gray.total();
    }
    return mag;
  }

  return compute_flow_lucas_kanade(prev_gray, curr_gray, mask, feature_count);
}

cv::Mat FlowEstimator::compute_flow_lucas_kanade(
  const cv::Mat & prev_gray,
  const cv::Mat & curr_gray,
  const cv::Mat & mask,
  int & feature_count)
{
  feature_count = 0;
  cv::Mat use_mask = mask.empty() ? cv::Mat() : mask;

  cv::goodFeaturesToTrack(
    prev_gray,
    prev_points_,
    params_.min_features,
    0.01,
    7,
    use_mask,
    7,
    false,
    0.04
  );

  if (prev_points_.size() < 4u) {
    cv::Mat empty_mag(curr_gray.rows, curr_gray.cols, CV_32FC1);
    empty_mag.setTo(0.0f);
    return empty_mag;
  }

  curr_points_.resize(prev_points_.size());
  std::vector<uchar> status(prev_points_.size());
  std::vector<float> err(prev_points_.size());

  cv::calcOpticalFlowPyrLK(
    prev_gray,
    curr_gray,
    prev_points_,
    curr_points_,
    status,
    err,
    cv::Size(21, 21),
    3,
    cv::TermCriteria(cv::TermCriteria::COUNT + cv::TermCriteria::EPS, 30, 0.01)
  );

  cv::Mat mag_image(curr_gray.rows, curr_gray.cols, CV_32FC1);
  mag_image.setTo(0.0f);

  int count = 0;
  const int radius = 3;
  for (size_t i = 0; i < prev_points_.size(); ++i) {
    if (!status[i]) { continue; }
    float dx = curr_points_[i].x - prev_points_[i].x;
    float dy = curr_points_[i].y - prev_points_[i].y;
    float m = std::sqrt(dx * dx + dy * dy);
    int x = static_cast<int>(prev_points_[i].x + 0.5f);
    int y = static_cast<int>(prev_points_[i].y + 0.5f);
    if (x >= 0 && x < mag_image.cols && y >= 0 && y < mag_image.rows) {
      for (int dy = -radius; dy <= radius; ++dy) {
        for (int dx = -radius; dx <= radius; ++dx) {
          int nx = x + dx;
          int ny = y + dy;
          if (nx >= 0 && nx < mag_image.cols && ny >= 0 && ny < mag_image.rows) {
            float & v = mag_image.at<float>(ny, nx);
            v = (v + m) / 2.0f;
          }
        }
      }
      count++;
    }
  }
  feature_count = count;

  if (count > 0) {
    cv::GaussianBlur(mag_image, mag_image, cv::Size(5, 5), 1.0);
  }

  return mag_image;
}

cv::Mat FlowEstimator::compute_flow_farneback(
  const cv::Mat & prev_gray,
  const cv::Mat & curr_gray,
  const cv::Mat & mask)
{
  cv::Mat prev_use = prev_gray;
  cv::Mat curr_use = curr_gray;
  if (!mask.empty()) {
    prev_use = cv::Mat();
    curr_use = cv::Mat();
    prev_gray.copyTo(prev_use, mask);
    curr_gray.copyTo(curr_use, mask);
  }

  cv::Mat flow(prev_gray.rows, prev_gray.cols, CV_32FC2);
  cv::calcOpticalFlowFarneback(
    prev_use,
    curr_use,
    flow,
    0.5,
    3,
    15,
    3,
    5,
    1.2,
    0
  );

  std::vector<cv::Mat> channels(2);
  cv::split(flow, channels);
  cv::Mat mag;
  cv::magnitude(channels[0], channels[1], mag);
  mag.convertTo(mag, CV_32FC1);
  return mag;
}

}  // namespace optical_flow_nav
