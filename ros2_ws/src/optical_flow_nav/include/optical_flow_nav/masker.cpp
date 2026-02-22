#include "optical_flow_nav/masker.hpp"
#include <opencv2/imgproc.hpp>

namespace optical_flow_nav
{

Masker::Masker(const MaskParams & params)
: params_(params)
{
}

void Masker::set_params(const MaskParams & params)
{
  params_ = params;
}

cv::Mat Masker::compute_mask(const cv::Mat & image)
{
  if (image.empty()) { return cv::Mat(); }
  if (!params_.enabled || params_.type == "none") {
    return compute_none(image);
  }
  if (params_.type == "floor_band") {
    return compute_floor_band(image);
  }
  if (params_.type == "polygon") {
    return compute_polygon(image);
  }
  if (params_.type == "hsv_floor") {
    return compute_hsv_floor(image);
  }
  return compute_none(image);
}

cv::Mat Masker::compute_none(const cv::Mat & image)
{
  cv::Mat mask(image.rows, image.cols, CV_8UC1);
  mask.setTo(255);
  return mask;
}

cv::Mat Masker::compute_floor_band(const cv::Mat & image)
{
  cv::Mat mask(image.rows, image.cols, CV_8UC1);
  mask.setTo(0);
  double f = params_.floor_band.bottom_fraction;
  f = std::max(0.0, std::min(1.0, f));
  int row_start = static_cast<int>((1.0 - f) * image.rows);
  if (row_start < image.rows) {
    mask.rowRange(row_start, image.rows).setTo(255);
  }
  return mask;
}

cv::Mat Masker::compute_polygon(const cv::Mat & image)
{
  const auto & x = params_.polygon.x;
  const auto & y = params_.polygon.y;
  if (x.size() != y.size() || x.size() < 3u) {
    return compute_none(image);
  }
  std::vector<cv::Point> pts;
  int w = image.cols;
  int h = image.rows;
  for (size_t i = 0; i < x.size(); ++i) {
    int px = static_cast<int>(x[i] * w + 0.5);
    int py = static_cast<int>(y[i] * h + 0.5);
    pts.push_back(cv::Point(px, py));
  }
  cv::Mat mask(image.rows, image.cols, CV_8UC1);
  mask.setTo(0);
  cv::fillConvexPoly(mask, pts, 255);
  return mask;
}

cv::Mat Masker::compute_hsv_floor(const cv::Mat & image)
{
  cv::Mat hsv;
  if (image.channels() == 3) {
    cv::cvtColor(image, hsv, cv::COLOR_BGR2HSV);
  } else {
    cv::cvtColor(image, hsv, cv::COLOR_GRAY2BGR);
    cv::cvtColor(hsv, hsv, cv::COLOR_BGR2HSV);
  }
  cv::Mat mask;
  cv::inRange(
    hsv,
    cv::Scalar(
      params_.hsv_floor.h_min,
      params_.hsv_floor.s_min,
      params_.hsv_floor.v_min
    ),
    cv::Scalar(
      params_.hsv_floor.h_max,
      params_.hsv_floor.s_max,
      params_.hsv_floor.v_max
    ),
    mask
  );
  return mask;
}

}  // namespace optical_flow_nav
