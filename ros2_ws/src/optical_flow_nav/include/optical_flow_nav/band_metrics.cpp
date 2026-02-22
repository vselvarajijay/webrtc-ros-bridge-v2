#include "optical_flow_nav/band_metrics.hpp"
#include <cmath>
#include <algorithm>

namespace optical_flow_nav
{

BandMetrics::BandMetrics(int num_bands)
: num_bands_(std::max(1, num_bands))
{
}

void BandMetrics::set_num_bands(int num_bands)
{
  num_bands_ = std::max(1, num_bands);
}

BandMagnitudes BandMetrics::compute(
  const cv::Mat & flow_magnitude,
  const cv::Mat & mask) const
{
  BandMagnitudes out;
  if (flow_magnitude.empty() || flow_magnitude.type() != CV_32FC1) {
    return out;
  }

  const int W = flow_magnitude.cols;
  const int H = flow_magnitude.rows;
  const bool use_mask = !mask.empty() && mask.rows == H && mask.cols == W;

  if (num_bands_ == 1) {
    double sum = 0.0;
    int n = 0;
    for (int y = 0; y < H; ++y) {
      const float * row = flow_magnitude.ptr<float>(y);
      const uchar * mrow = use_mask ? mask.ptr<uchar>(y) : nullptr;
      for (int x = 0; x < W; ++x) {
        if (use_mask && mrow[x] == 0) { continue; }
        float v = row[x];
        if (std::isfinite(v)) {
          sum += static_cast<double>(v);
          n++;
        }
      }
    }
    float mean = (n > 0) ? static_cast<float>(sum / n) : 0.0f;
    out.flow_mag_left = out.flow_mag_center = out.flow_mag_right = mean;
    return out;
  }

  if (num_bands_ == 2) {
    int mid = W / 2;
    double sum_left = 0.0, sum_right = 0.0;
    int n_left = 0, n_right = 0;
    for (int y = 0; y < H; ++y) {
      const float * row = flow_magnitude.ptr<float>(y);
      const uchar * mrow = use_mask ? mask.ptr<uchar>(y) : nullptr;
      for (int x = 0; x < W; ++x) {
        if (use_mask && mrow[x] == 0) { continue; }
        float v = row[x];
        if (!std::isfinite(v)) { continue; }
        if (x < mid) {
          sum_left += static_cast<double>(v);
          n_left++;
        } else {
          sum_right += static_cast<double>(v);
          n_right++;
        }
      }
    }
    out.flow_mag_left = (n_left > 0) ? static_cast<float>(sum_left / n_left) : 0.0f;
    out.flow_mag_right = (n_right > 0) ? static_cast<float>(sum_right / n_right) : 0.0f;
    out.flow_mag_center = (out.flow_mag_left + out.flow_mag_right) / 2.0f;
    return out;
  }

  int band_width = W / num_bands_;
  std::vector<double> sums(static_cast<size_t>(num_bands_), 0.0);
  std::vector<int> counts(static_cast<size_t>(num_bands_), 0);

  for (int y = 0; y < H; ++y) {
    const float * row = flow_magnitude.ptr<float>(y);
    const uchar * mrow = use_mask ? mask.ptr<uchar>(y) : nullptr;
    for (int x = 0; x < W; ++x) {
      if (use_mask && mrow[x] == 0) { continue; }
      float v = row[x];
      if (!std::isfinite(v)) { continue; }
      int band = std::min(x / band_width, num_bands_ - 1);
      sums[static_cast<size_t>(band)] += static_cast<double>(v);
      counts[static_cast<size_t>(band)]++;
    }
  }

  auto safe_mean = [&](size_t i) {
    return (counts[i] > 0) ? static_cast<float>(sums[i] / counts[i]) : 0.0f;
  };

  if (num_bands_ >= 3) {
    out.flow_mag_left = safe_mean(0);
    out.flow_mag_right = safe_mean(static_cast<size_t>(num_bands_ - 1));
    if (num_bands_ == 3) {
      out.flow_mag_center = safe_mean(1);
    } else {
      double sum = 0.0;
      int n = 0;
      for (int b = 1; b < num_bands_ - 1; ++b) {
        sum += safe_mean(static_cast<size_t>(b));
        n++;
      }
      out.flow_mag_center = (n > 0) ? static_cast<float>(sum / n) : 0.0f;
    }
  }

  return out;
}

}  // namespace optical_flow_nav
