#include "connectx_perception_cpp/optical_flow_node.hpp"
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <cmath>
#include <algorithm>
#include <vector>

namespace connectx_perception_cpp
{

// Constants
static constexpr int DEFAULT_FLOW_WIDTH = 320;
static constexpr int DEFAULT_FLOW_HEIGHT = 240;
static constexpr double DEFAULT_MAX_DT_S = 0.5;
static constexpr double DEFAULT_FLOW_NOISE_FLOOR = 1.0;
static constexpr double DEFAULT_FLOW_MAX_MAGNITUDE = 25.0;
static constexpr double DEFAULT_FLOW_EMA_ALPHA = 0.12;
static constexpr int DEFAULT_VIZ_WIDTH = 320;
static constexpr int DEFAULT_VIZ_HEIGHT = 240;
static constexpr int DEFAULT_GAUSSIAN_BLUR_KERNEL_SIZE = 5;
static constexpr double DEFAULT_MIDDLE_START_FRACTION = 0.10;
static constexpr double DEFAULT_MIDDLE_END_FRACTION = 0.50;
static constexpr double DEFAULT_TOP_BAND_FRACTION = 0.4;
static constexpr bool DEFAULT_ENABLE_FLOW_DIVERGENCE = true;
static constexpr bool DEFAULT_USE_ENHANCED_FORMAT = true;
static constexpr bool DEFAULT_USE_FLOOR_MASK = false;
static constexpr double DEFAULT_FLOOR_MASK_TIMEOUT_S = 0.5;
static constexpr double DEFAULT_FLOOR_MASK_WEIGHT = 0.05;

static constexpr int ARROW_GRID_STEP = 8;
static constexpr double ARROW_SCALE = 2.0;
static const cv::Scalar ARROW_COLOR(100, 255, 0);  // BGR green
static constexpr int ARROW_THICKNESS = 1;
static constexpr double ARROW_TIP_LENGTH = 0.25;

OpticalFlowNode::OpticalFlowNode(const rclcpp::NodeOptions & options)
: Node("optical_flow_node", options)
{
  // Declare parameters
  this->declare_parameter<int>("flow_width", DEFAULT_FLOW_WIDTH);
  this->declare_parameter<int>("flow_height", DEFAULT_FLOW_HEIGHT);
  this->declare_parameter<double>("max_dt_s", DEFAULT_MAX_DT_S);
  this->declare_parameter<double>("flow_noise_floor", DEFAULT_FLOW_NOISE_FLOOR);
  this->declare_parameter<double>("flow_max_magnitude", DEFAULT_FLOW_MAX_MAGNITUDE);
  this->declare_parameter<double>("flow_ema_alpha", DEFAULT_FLOW_EMA_ALPHA);
  this->declare_parameter<int>("viz_width", DEFAULT_VIZ_WIDTH);
  this->declare_parameter<int>("viz_height", DEFAULT_VIZ_HEIGHT);
  this->declare_parameter<int>("gaussian_blur_kernel_size", DEFAULT_GAUSSIAN_BLUR_KERNEL_SIZE);
  this->declare_parameter<double>("middle_start_fraction", DEFAULT_MIDDLE_START_FRACTION);
  this->declare_parameter<double>("middle_end_fraction", DEFAULT_MIDDLE_END_FRACTION);
  this->declare_parameter<double>("top_band_fraction", DEFAULT_TOP_BAND_FRACTION);
  this->declare_parameter<bool>("enable_flow_divergence", DEFAULT_ENABLE_FLOW_DIVERGENCE);
  this->declare_parameter<bool>("use_enhanced_format", DEFAULT_USE_ENHANCED_FORMAT);
  this->declare_parameter<bool>("use_floor_mask", DEFAULT_USE_FLOOR_MASK);
  this->declare_parameter<double>("floor_mask_timeout_s", DEFAULT_FLOOR_MASK_TIMEOUT_S);
  this->declare_parameter<double>("floor_mask_weight", DEFAULT_FLOOR_MASK_WEIGHT);

  // Get parameters
  flow_w_ = this->get_parameter("flow_width").as_int();
  flow_h_ = this->get_parameter("flow_height").as_int();
  max_dt_ = this->get_parameter("max_dt_s").as_double();
  noise_floor_ = this->get_parameter("flow_noise_floor").as_double();
  flow_max_ = this->get_parameter("flow_max_magnitude").as_double();
  ema_alpha_ = this->get_parameter("flow_ema_alpha").as_double();
  viz_w_ = this->get_parameter("viz_width").as_int();
  viz_h_ = this->get_parameter("viz_height").as_int();
  blur_kernel_ = this->get_parameter("gaussian_blur_kernel_size").as_int();
  middle_start_ = this->get_parameter("middle_start_fraction").as_double();
  middle_end_ = this->get_parameter("middle_end_fraction").as_double();
  top_band_frac_ = this->get_parameter("top_band_fraction").as_double();
  enable_divergence_ = this->get_parameter("enable_flow_divergence").as_bool();
  use_enhanced_ = this->get_parameter("use_enhanced_format").as_bool();
  use_floor_mask_ = this->get_parameter("use_floor_mask").as_bool();
  floor_mask_timeout_ = this->get_parameter("floor_mask_timeout_s").as_double();
  floor_mask_weight_ = this->get_parameter("floor_mask_weight").as_double();

  // Ensure blur kernel is odd
  if (blur_kernel_ > 0 && blur_kernel_ % 2 == 0) {
    blur_kernel_ += 1;
    RCLCPP_WARN(this->get_logger(), "Blur kernel must be odd, adjusted to %d", blur_kernel_);
  }

  // Create subscribers
  image_sub_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(
    "/camera/front/compressed",
    1,
    std::bind(&OpticalFlowNode::image_callback, this, std::placeholders::_1)
  );

  if (use_floor_mask_) {
    mask_sub_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(
      "/perception/floor_mask",
      1,
      std::bind(&OpticalFlowNode::mask_callback, this, std::placeholders::_1)
    );
  }

  // Create publishers
  flow_pub_ = this->create_publisher<std_msgs::msg::Float32MultiArray>("/optical_flow", 10);
  flow_image_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(
    "/optical_flow/image/compressed", 10);

  const char* format_str = use_enhanced_ ? "enhanced (18)" : "legacy (9)";
  const char* blur_str = blur_kernel_ > 0 ? "blur" : "no blur";
  const char* mask_str = use_floor_mask_ ? "mask" : "no mask";
  RCLCPP_INFO(this->get_logger(),
    "optical_flow_node: sub /camera/front/compressed, pub /optical_flow "
    "(flow %dx%d, format=%s, %s, %s, middle=%.2f-%.2f, top_band=%.2f, max_dt=%.2fs, "
    "noise_floor=%.2f, ema_alpha=%.2f)",
    flow_w_, flow_h_, format_str, blur_str, mask_str,
    middle_start_, middle_end_, top_band_frac_, max_dt_, noise_floor_, ema_alpha_);
}

OpticalFlowNode::~OpticalFlowNode()
{
}

void OpticalFlowNode::mask_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
{
  try {
    std::vector<uint8_t> data(msg->data.begin(), msg->data.end());
    cv::Mat mask = cv::imdecode(data, cv::IMREAD_GRAYSCALE);
    if (mask.empty()) {
      return;
    }
    std::lock_guard<std::mutex> lock(lock_);
    latest_mask_ = mask.clone();
    mask_stamp_ = rclcpp::Time(msg->header.stamp);
  } catch (const cv::Exception & e) {
    RCLCPP_WARN(this->get_logger(), "Decode mask failed: %s", e.what());
  }
}

cv::Mat OpticalFlowNode::get_floor_mask(const std::pair<int, int> & flow_shape)
{
  if (!use_floor_mask_) {
    return cv::Mat();
  }

  cv::Mat mask;
  rclcpp::Time mask_stamp;
  {
    std::lock_guard<std::mutex> lock(lock_);
    if (latest_mask_.empty()) {
      return cv::Mat();
    }
    mask = latest_mask_.clone();
    mask_stamp = mask_stamp_;
  }

  // Check if mask is recent enough
  rclcpp::Time now = this->get_clock()->now();
  if ((now - mask_stamp).seconds() > floor_mask_timeout_) {
    return cv::Mat();
  }

  int h = flow_shape.first;
  int w = flow_shape.second;
  if (mask.rows != h || mask.cols != w) {
    cv::resize(mask, mask, cv::Size(w, h), 0, 0, cv::INTER_LINEAR);
  }

  // Normalize to 0-1 range and apply floor weight
  cv::Mat mask_normalized;
  mask.convertTo(mask_normalized, CV_64F, 1.0 / 255.0);
  
  // Compute: final_weight = 1.0 - mask_normalized * (1.0 - floor_mask_weight_)
  cv::Mat scaled_mask;
  cv::multiply(mask_normalized, cv::Scalar(1.0 - floor_mask_weight_), scaled_mask, 1.0, CV_64F);
  cv::Mat final_weight;
  cv::subtract(cv::Scalar(1.0), scaled_mask, final_weight, cv::noArray(), CV_64F);
  
  return final_weight;
}

OpticalFlowNode::MeanFlowResult OpticalFlowNode::mean_flow(
  const cv::Mat & region, const cv::Mat & region_mask)
{
  MeanFlowResult result{0.0f, 0.0f, 0.0f};
  
  if (region.empty() || region.channels() != 2) {
    return result;
  }

  std::vector<cv::Mat> channels;
  cv::split(region, channels);
  cv::Mat vx_region = channels[0];
  cv::Mat vy_region = channels[1];
  
  cv::Mat mag_region;
  cv::magnitude(vx_region, vy_region, mag_region);

  if (!region_mask.empty() && region_mask.size() == region.size()) {
    cv::Mat weights;
    if (region_mask.channels() == 1) {
      weights = region_mask;
    } else {
      std::vector<cv::Mat> mask_channels;
      cv::split(region_mask, mask_channels);
      weights = mask_channels[0];
    }
    
    // Convert weights and flow regions to same type for multiplication
    cv::Mat vx_float, vy_float, mag_float, weights_float;
    vx_region.convertTo(vx_float, CV_64F);
    vy_region.convertTo(vy_float, CV_64F);
    mag_region.convertTo(mag_float, CV_64F);
    weights.convertTo(weights_float, CV_64F);
    
    cv::Mat vx_weighted, vy_weighted, mag_weighted;
    cv::multiply(vx_float, weights_float, vx_weighted, 1.0, CV_64F);
    cv::multiply(vy_float, weights_float, vy_weighted, 1.0, CV_64F);
    cv::multiply(mag_float, weights_float, mag_weighted, 1.0, CV_64F);
    
    double total_weight = cv::sum(weights_float)[0] + 1e-6;
    result.vx = static_cast<float>(cv::sum(vx_weighted)[0] / total_weight);
    result.vy = static_cast<float>(cv::sum(vy_weighted)[0] / total_weight);
    result.mag = static_cast<float>(cv::sum(mag_weighted)[0] / total_weight);
  } else {
    cv::Scalar vx_mean = cv::mean(vx_region);
    cv::Scalar vy_mean = cv::mean(vy_region);
    cv::Scalar mag_mean = cv::mean(mag_region);
    result.vx = static_cast<float>(vx_mean[0]);
    result.vy = static_cast<float>(vy_mean[0]);
    result.mag = static_cast<float>(mag_mean[0]);
  }

  return result;
}

cv::Mat OpticalFlowNode::flow_to_arrows_image(const cv::Mat & flow, int viz_w, int viz_h)
{
  if (flow.empty() || flow.channels() != 2) {
    return cv::Mat::zeros(viz_h, viz_w, CV_8UC3);
  }

  int h = flow.rows;
  int w = flow.cols;
  cv::Mat out = cv::Mat::zeros(h, w, CV_8UC3);
  out.setTo(cv::Scalar(40, 40, 40));  // dark gray background

  std::vector<cv::Mat> channels;
  cv::split(flow, channels);
  cv::Mat vx = channels[0];
  cv::Mat vy = channels[1];

  for (int y = ARROW_GRID_STEP / 2; y < h; y += ARROW_GRID_STEP) {
    for (int x = ARROW_GRID_STEP / 2; x < w; x += ARROW_GRID_STEP) {
      float vx_val = vx.at<float>(y, x);
      float vy_val = vy.at<float>(y, x);
      float mag = std::sqrt(vx_val * vx_val + vy_val * vy_val);
      
      if (mag < 0.1f) {
        continue;
      }

      int x2 = static_cast<int>(std::round(x + vx_val * ARROW_SCALE));
      int y2 = static_cast<int>(std::round(y + vy_val * ARROW_SCALE));
      cv::Point pt1(x, y);
      cv::Point pt2(x2, y2);
      
      cv::arrowedLine(out, pt1, pt2, ARROW_COLOR, ARROW_THICKNESS, 8, 0, ARROW_TIP_LENGTH);
    }
  }

  if (w != viz_w || h != viz_h) {
    cv::resize(out, out, cv::Size(viz_w, viz_h), 0, 0, cv::INTER_LINEAR);
  }

  return out;
}

void OpticalFlowNode::image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
{
  try {
    std::vector<uint8_t> data(msg->data.begin(), msg->data.end());
    cv::Mat img = cv::imdecode(data, cv::IMREAD_COLOR);
    if (img.empty()) {
      return;
    }

    // Use message stamp if valid, else node clock
    rclcpp::Time stamp;
    if (msg->header.stamp.sec > 0 || msg->header.stamp.nanosec > 0) {
      stamp = rclcpp::Time(msg->header.stamp);
    } else {
      stamp = this->get_clock()->now();
    }

    cv::Mat gray;
    cv::cvtColor(img, gray, cv::COLOR_BGR2GRAY);
    cv::resize(gray, gray, cv::Size(flow_w_, flow_h_), 0, 0, cv::INTER_AREA);

    // Apply Gaussian blur
    if (blur_kernel_ > 0) {
      cv::GaussianBlur(gray, gray, cv::Size(blur_kernel_, blur_kernel_), 0);
    }

    // Copy previous frame under lock
    cv::Mat prev_gray;
    rclcpp::Time prev_stamp;
    {
      std::lock_guard<std::mutex> lock(lock_);
      if (prev_gray_.empty()) {
        prev_gray_ = gray.clone();
        prev_stamp_ = stamp;
        return;
      }
      prev_gray = prev_gray_.clone();
      prev_stamp = prev_stamp_;
    }

    double dt = (stamp - prev_stamp).seconds();
    if (dt <= 0.0 || dt > max_dt_) {
      std::lock_guard<std::mutex> lock(lock_);
      prev_gray_ = gray.clone();
      prev_stamp_ = stamp;
      return;
    }

    // Compute optical flow
    cv::Mat flow;
    cv::calcOpticalFlowFarneback(
      prev_gray, gray, flow,
      0.5,  // pyr_scale
      3,    // levels
      21,   // winsize
      3,    // iterations
      7,    // poly_n
      1.5,  // poly_sigma
      0     // flags
    );

    {
      std::lock_guard<std::mutex> lock(lock_);
      prev_gray_ = gray.clone();
      prev_stamp_ = stamp;
    }

    // Temporal normalization: pixels/frame -> pixels/second
    // Ensure flow is float type for division
    cv::Mat flow_float;
    flow.convertTo(flow_float, CV_32F);
    flow_float = flow_float / static_cast<float>(dt);
    flow = flow_float;

    // Noise floor and magnitude capping per channel
    std::vector<cv::Mat> flow_channels;
    cv::split(flow, flow_channels);
    for (auto & channel : flow_channels) {
      // Set values with absolute value < noise_floor to zero
      cv::Mat abs_channel = cv::abs(channel);
      cv::Mat mask_small;
      cv::compare(abs_channel, cv::Scalar(static_cast<float>(noise_floor_)), mask_small, cv::CMP_LT);
      channel.setTo(0.0f, mask_small);
      
      // Cap magnitude: clip to [-flow_max_, flow_max_]
      cv::threshold(channel, channel, static_cast<float>(flow_max_), static_cast<float>(flow_max_), cv::THRESH_TRUNC);
      cv::Mat neg_mask;
      cv::compare(channel, cv::Scalar(-static_cast<float>(flow_max_)), neg_mask, cv::CMP_LT);
      channel.setTo(-static_cast<float>(flow_max_), neg_mask);
    }
    cv::merge(flow_channels, flow);

    int h = flow.rows;
    int w = flow.cols;

    // Get floor mask
    cv::Mat mask_weights = get_floor_mask({h, w});

    // Add vertical attenuation
    cv::Mat vertical_weight = cv::Mat::ones(h, 1, CV_64F);
    for (int i = 0; i < h; ++i) {
      double y_frac = static_cast<double>(i) / h;
      vertical_weight.at<double>(i, 0) = 1.0 - std::max(0.0, std::min(1.0, (y_frac - 0.3) / 0.4));
    }

    // Combine floor mask with vertical attenuation
    if (!mask_weights.empty()) {
      cv::Mat vertical_expanded;
      cv::repeat(vertical_weight, 1, w, vertical_expanded);
      // Ensure both are same type before multiply
      cv::Mat mask_weights_64f, vertical_expanded_64f;
      mask_weights.convertTo(mask_weights_64f, CV_64F);
      vertical_expanded.convertTo(vertical_expanded_64f, CV_64F);
      cv::multiply(mask_weights_64f, vertical_expanded_64f, mask_weights, 1.0, CV_64F);
    } else {
      cv::repeat(vertical_weight, 1, w, mask_weights);
    }

    // Add brightness-based glare suppression
    cv::Mat brightness;
    gray.convertTo(brightness, CV_64F);
    cv::Mat glare_mask;
    cv::compare(brightness, cv::Scalar(230.0), glare_mask, cv::CMP_GT);
    cv::Mat glare_suppression;
    glare_mask.convertTo(glare_suppression, CV_64F, -0.8, 1.0);
    
    if (mask_weights.channels() == 1) {
      cv::Mat mask_3ch;
      cv::merge(std::vector<cv::Mat>{mask_weights, mask_weights, mask_weights}, mask_3ch);
      mask_weights = mask_3ch;
    }
    cv::Mat glare_expanded;
    cv::merge(std::vector<cv::Mat>{glare_suppression, glare_suppression, glare_suppression}, glare_expanded);
    // Ensure both are same type before multiply
    cv::Mat mask_weights_result;
    cv::multiply(mask_weights, glare_expanded, mask_weights_result, 1.0, CV_64F);
    mask_weights = mask_weights_result;

    // Calculate region boundaries
    int third = w / 3;
    int middle_start_px = static_cast<int>(h * middle_start_);
    int middle_end_px = static_cast<int>(h * middle_end_);
    int usable_h = middle_end_px - middle_start_px;

    std::vector<float> raw;
    if (use_enhanced_) {
      int top_band_end_px = middle_start_px + static_cast<int>(usable_h * top_band_frac_);

      // Top band regions
      cv::Rect left_top_rect(0, middle_start_px, third, top_band_end_px - middle_start_px);
      cv::Rect center_top_rect(third, middle_start_px, third, top_band_end_px - middle_start_px);
      cv::Rect right_top_rect(2 * third, middle_start_px, w - 2 * third, top_band_end_px - middle_start_px);

      // Mid band regions
      cv::Rect left_mid_rect(0, top_band_end_px, third, middle_end_px - top_band_end_px);
      cv::Rect center_mid_rect(third, top_band_end_px, third, middle_end_px - top_band_end_px);
      cv::Rect right_mid_rect(2 * third, top_band_end_px, w - 2 * third, middle_end_px - top_band_end_px);

      cv::Mat left_top = flow(left_top_rect);
      cv::Mat center_top = flow(center_top_rect);
      cv::Mat right_top = flow(right_top_rect);
      cv::Mat left_mid = flow(left_mid_rect);
      cv::Mat center_mid = flow(center_mid_rect);
      cv::Mat right_mid = flow(right_mid_rect);

      cv::Mat left_top_mask, center_top_mask, right_top_mask;
      cv::Mat left_mid_mask, center_mid_mask, right_mid_mask;
      if (!mask_weights.empty()) {
        left_top_mask = mask_weights(left_top_rect);
        center_top_mask = mask_weights(center_top_rect);
        right_top_mask = mask_weights(right_top_rect);
        left_mid_mask = mask_weights(left_mid_rect);
        center_mid_mask = mask_weights(center_mid_rect);
        right_mid_mask = mask_weights(right_mid_rect);
      }

      MeanFlowResult left_top_result = mean_flow(left_top, left_top_mask);
      MeanFlowResult center_top_result = mean_flow(center_top, center_top_mask);
      MeanFlowResult right_top_result = mean_flow(right_top, right_top_mask);
      MeanFlowResult left_mid_result = mean_flow(left_mid, left_mid_mask);
      MeanFlowResult center_mid_result = mean_flow(center_mid, center_mid_mask);
      MeanFlowResult right_mid_result = mean_flow(right_mid, right_mid_mask);

      raw = {
        left_top_result.vx, left_top_result.vy, left_top_result.mag,
        center_top_result.vx, center_top_result.vy, center_top_result.mag,
        right_top_result.vx, right_top_result.vy, right_top_result.mag,
        left_mid_result.vx, left_mid_result.vy, left_mid_result.mag,
        center_mid_result.vx, center_mid_result.vy, center_mid_result.mag,
        right_mid_result.vx, right_mid_result.vy, right_mid_result.mag
      };
    } else {
      cv::Rect left_rect(0, middle_start_px, third, middle_end_px - middle_start_px);
      cv::Rect center_rect(third, middle_start_px, third, middle_end_px - middle_start_px);
      cv::Rect right_rect(2 * third, middle_start_px, w - 2 * third, middle_end_px - middle_start_px);

      cv::Mat left = flow(left_rect);
      cv::Mat center = flow(center_rect);
      cv::Mat right = flow(right_rect);

      cv::Mat left_mask, center_mask, right_mask;
      if (!mask_weights.empty()) {
        left_mask = mask_weights(left_rect);
        center_mask = mask_weights(center_rect);
        right_mask = mask_weights(right_rect);
      }

      MeanFlowResult left_result = mean_flow(left, left_mask);
      MeanFlowResult center_result = mean_flow(center, center_mask);
      MeanFlowResult right_result = mean_flow(right, right_mask);

      raw = {
        left_result.vx, left_result.vy, left_result.mag,
        center_result.vx, center_result.vy, center_result.mag,
        right_result.vx, right_result.vy, right_result.mag
      };
    }

    // EMA smoothing
    if (flow_ema_.empty()) {
      flow_ema_ = raw;
    } else {
      if (flow_ema_.size() != raw.size()) {
        flow_ema_ = raw;
      } else {
        for (size_t i = 0; i < raw.size(); ++i) {
          flow_ema_[i] = ema_alpha_ * raw[i] + (1.0 - ema_alpha_) * flow_ema_[i];
        }
      }
    }

    // Publish flow array
    std_msgs::msg::Float32MultiArray flow_msg;
    flow_msg.data = flow_ema_;
    flow_pub_->publish(flow_msg);

    // Publish flow visualization
    cv::Mat viz_bgr = flow_to_arrows_image(flow, viz_w_, viz_h_);
    std::vector<uint8_t> jpeg_data;
    std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 85};
    cv::imencode(".jpg", viz_bgr, jpeg_data, params);

    sensor_msgs::msg::CompressedImage flow_img_msg;
    flow_img_msg.header = msg->header;
    flow_img_msg.format = "jpeg";
    flow_img_msg.data = jpeg_data;
    flow_image_pub_->publish(flow_img_msg);

  } catch (const cv::Exception & e) {
    RCLCPP_WARN(this->get_logger(), "Decode image failed: %s", e.what());
  } catch (const std::exception & e) {
    RCLCPP_ERROR(this->get_logger(), "Exception in callback: %s", e.what());
  }
}

}  // namespace connectx_perception_cpp

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::NodeOptions options;
  auto node = std::make_shared<connectx_perception_cpp::OpticalFlowNode>(options);
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
