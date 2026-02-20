#include "connectx_perception_cpp/floor_mask_node.hpp"
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <cmath>
#include <algorithm>

namespace connectx_perception_cpp
{

// Constants
static constexpr int DEFAULT_MASK_WIDTH = 320;
static constexpr int DEFAULT_MASK_HEIGHT = 240;
static constexpr double DEFAULT_SEED_BOTTOM_FRACTION = 0.3;
static constexpr double DEFAULT_SEED_CENTER_WIDTH_FRACTION = 0.5;
static constexpr double DEFAULT_HSV_SIMILARITY_THRESHOLD = 2.5;
static constexpr int DEFAULT_ERODE_KERNEL_SIZE = 3;
static constexpr int DEFAULT_DILATE_KERNEL_SIZE = 5;
static constexpr bool DEFAULT_ENABLE_MORPHOLOGY = true;

FloorMaskNode::FloorMaskNode(const rclcpp::NodeOptions & options)
: Node("floor_mask_node", options)
{
  // Declare parameters
  this->declare_parameter<int>("mask_width", DEFAULT_MASK_WIDTH);
  this->declare_parameter<int>("mask_height", DEFAULT_MASK_HEIGHT);
  this->declare_parameter<double>("seed_bottom_fraction", DEFAULT_SEED_BOTTOM_FRACTION);
  this->declare_parameter<double>("seed_center_width_fraction", DEFAULT_SEED_CENTER_WIDTH_FRACTION);
  this->declare_parameter<double>("hsv_similarity_threshold", DEFAULT_HSV_SIMILARITY_THRESHOLD);
  this->declare_parameter<int>("erode_kernel_size", DEFAULT_ERODE_KERNEL_SIZE);
  this->declare_parameter<int>("dilate_kernel_size", DEFAULT_DILATE_KERNEL_SIZE);
  this->declare_parameter<bool>("enable_morphology", DEFAULT_ENABLE_MORPHOLOGY);

  // Get parameters
  mask_w_ = this->get_parameter("mask_width").as_int();
  mask_h_ = this->get_parameter("mask_height").as_int();
  seed_bottom_frac_ = this->get_parameter("seed_bottom_fraction").as_double();
  seed_center_width_frac_ = this->get_parameter("seed_center_width_fraction").as_double();
  hsv_similarity_threshold_ = this->get_parameter("hsv_similarity_threshold").as_double();
  erode_kernel_ = this->get_parameter("erode_kernel_size").as_int();
  dilate_kernel_ = this->get_parameter("dilate_kernel_size").as_int();
  enable_morphology_ = this->get_parameter("enable_morphology").as_bool();

  // Ensure kernel sizes are odd
  if (erode_kernel_ > 0 && erode_kernel_ % 2 == 0) {
    erode_kernel_ += 1;
    RCLCPP_WARN(this->get_logger(), "Erode kernel must be odd, adjusted to %d", erode_kernel_);
  }
  if (dilate_kernel_ > 0 && dilate_kernel_ % 2 == 0) {
    dilate_kernel_ += 1;
    RCLCPP_WARN(this->get_logger(), "Dilate kernel must be odd, adjusted to %d", dilate_kernel_);
  }

  // Create subscriber and publishers
  image_sub_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(
    "/camera/front/compressed",
    1,
    std::bind(&FloorMaskNode::image_callback, this, std::placeholders::_1)
  );

  mask_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(
    "/perception/floor_mask", 10);
  mask_image_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>(
    "/perception/floor_mask/image/compressed", 10);

  RCLCPP_INFO(this->get_logger(),
    "floor_mask_node: sub /camera/front/compressed, pub /perception/floor_mask, "
    "/perception/floor_mask/image/compressed (mask %dx%d, seed_bottom=%.2f, "
    "seed_width=%.2f, hsv_thresh=%.1f, morph=%s)",
    mask_w_, mask_h_, seed_bottom_frac_, seed_center_width_frac_, hsv_similarity_threshold_,
    enable_morphology_ ? "enabled" : "disabled");
}

FloorMaskNode::~FloorMaskNode()
{
}

cv::Mat FloorMaskNode::compute_floor_mask(const cv::Mat & img)
{
  if (img.empty()) {
    return cv::Mat();
  }

  int h = img.rows;
  int w = img.cols;
  cv::Mat img_resized = img;

  // Resize to mask resolution
  if (w != mask_w_ || h != mask_h_) {
    cv::resize(img, img_resized, cv::Size(mask_w_, mask_h_), 0, 0, cv::INTER_AREA);
    h = mask_h_;
    w = mask_w_;
  }

  // Convert to HSV
  cv::Mat hsv;
  cv::cvtColor(img_resized, hsv, cv::COLOR_BGR2HSV);

  // Extract seed region (bottom-center patch)
  int seed_bottom_start = static_cast<int>(h * (1.0 - seed_bottom_frac_));
  int seed_width_start = static_cast<int>(w * (0.5 - seed_center_width_frac_ / 2.0));
  int seed_width_end = static_cast<int>(w * (0.5 + seed_center_width_frac_ / 2.0));

  cv::Rect seed_rect(seed_width_start, seed_bottom_start, 
                     seed_width_end - seed_width_start, h - seed_bottom_start);
  if (seed_rect.width <= 0 || seed_rect.height <= 0) {
    seed_rect = cv::Rect(0, seed_bottom_start, w, h - seed_bottom_start);
  }

  cv::Mat seed_region = hsv(seed_rect);

  // Compute HSV mean and std from seed region
  cv::Scalar hsv_mean_scalar, hsv_std_scalar;
  cv::meanStdDev(seed_region, hsv_mean_scalar, hsv_std_scalar);

  double h_mean = hsv_mean_scalar[0];
  double h_std = std::max(hsv_std_scalar[0], 3.0);
  double s_mean = hsv_mean_scalar[1];
  double s_std = std::max(hsv_std_scalar[1], 5.0);
  double v_mean = hsv_mean_scalar[2];
  double v_std = std::max(hsv_std_scalar[2], 5.0);

  // Compute distance from mean for each pixel
  std::vector<cv::Mat> hsv_channels;
  cv::split(hsv, hsv_channels);
  cv::Mat h_channel = hsv_channels[0];
  cv::Mat s_channel = hsv_channels[1];
  cv::Mat v_channel = hsv_channels[2];

  // H channel: handle circularity (0-180 wraps around)
  cv::Mat h_diff1, h_diff2;
  cv::absdiff(h_channel, cv::Scalar(h_mean), h_diff1);
  cv::absdiff(h_channel, cv::Scalar(h_mean + 180.0), h_diff2);
  cv::Mat h_diff = cv::min(h_diff1, h_diff2);
  cv::Mat h_dist;
  h_diff.convertTo(h_dist, CV_64F);
  h_dist /= (h_std + 1e-6);

  // S and V channels: simple distance
  cv::Mat s_diff, v_diff;
  cv::absdiff(s_channel, cv::Scalar(s_mean), s_diff);
  cv::absdiff(v_channel, cv::Scalar(v_mean), v_diff);
  cv::Mat s_dist, v_dist;
  s_diff.convertTo(s_dist, CV_64F);
  v_diff.convertTo(v_dist, CV_64F);
  s_dist /= (s_std + 1e-6);
  v_dist /= (v_std + 1e-6);

  // Combined distance
  cv::Mat combined_dist;
  cv::Mat h_dist_sq, s_dist_sq, v_dist_sq;
  cv::multiply(h_dist, h_dist, h_dist_sq);
  cv::multiply(s_dist, s_dist, s_dist_sq);
  cv::multiply(v_dist, v_dist, v_dist_sq);
  cv::sqrt(h_dist_sq + s_dist_sq + v_dist_sq, combined_dist);

  // Threshold: pixels within threshold distance are floor
  cv::Mat mask;
  cv::threshold(combined_dist, mask, hsv_similarity_threshold_, 255.0, cv::THRESH_BINARY_INV);
  mask.convertTo(mask, CV_8U);

  // Morphological operations
  if (enable_morphology_) {
    if (erode_kernel_ > 0) {
      cv::Mat kernel_erode = cv::getStructuringElement(cv::MORPH_RECT, 
                                                        cv::Size(erode_kernel_, erode_kernel_));
      cv::erode(mask, mask, kernel_erode);
    }
    if (dilate_kernel_ > 0) {
      cv::Mat kernel_dilate = cv::getStructuringElement(cv::MORPH_RECT,
                                                         cv::Size(dilate_kernel_, dilate_kernel_));
      cv::dilate(mask, mask, kernel_dilate);
    }
  }

  return mask;
}

cv::Mat FloorMaskNode::create_visualization(const cv::Mat & img, const cv::Mat & mask)
{
  if (img.empty() || mask.empty()) {
    return cv::Mat();
  }

  int orig_h = img.rows;
  int orig_w = img.cols;
  int mask_h = mask.rows;
  int mask_w = mask.cols;

  cv::Mat mask_resized = mask;
  if (mask_w != orig_w || mask_h != orig_h) {
    cv::resize(mask, mask_resized, cv::Size(orig_w, orig_h), 0, 0, cv::INTER_NEAREST);
  }

  // Create colored overlay: green for floor pixels
  cv::Mat overlay = img.clone();
  cv::Mat mask_3ch;
  cv::cvtColor(mask_resized, mask_3ch, cv::COLOR_GRAY2BGR);

  // Create green overlay (BGR: [0, 255, 0])
  cv::Mat green_overlay = cv::Mat::zeros(img.size(), img.type());
  green_overlay.setTo(cv::Scalar(0, 255, 0));

  // Blend: where mask is 255 (floor), use green overlay with 30% opacity
  cv::Mat mask_normalized;
  mask_3ch.convertTo(mask_normalized, CV_32F, 1.0 / 255.0);
  double alpha = 0.3;  // 30% opacity

  cv::Mat img_float, green_float;
  img.convertTo(img_float, CV_32F);
  green_overlay.convertTo(green_float, CV_32F);

  cv::Mat overlay_float = img_float.mul(cv::Scalar::all(1.0) - alpha * mask_normalized) +
                           green_float.mul(alpha * mask_normalized);
  overlay_float.convertTo(overlay, CV_8U);

  return overlay;
}

void FloorMaskNode::image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
{
  try {
    std::vector<uint8_t> data(msg->data.begin(), msg->data.end());
    cv::Mat img = cv::imdecode(data, cv::IMREAD_COLOR);
    if (img.empty()) {
      return;
    }

    // Store original image for visualization (thread-safe)
    {
      std::lock_guard<std::mutex> lock(lock_);
      latest_image_ = img.clone();
      mask_stamp_ = rclcpp::Time(msg->header.stamp);
    }

    // Compute floor mask
    cv::Mat mask = compute_floor_mask(img);

    // Store latest mask
    {
      std::lock_guard<std::mutex> lock(lock_);
      latest_mask_ = mask.clone();
    }

    // Encode mask as PNG (lossless, required for binary masks)
    std::vector<uint8_t> png_data;
    std::vector<int> params = {cv::IMWRITE_PNG_COMPRESSION, 1};
    if (!cv::imencode(".png", mask, png_data, params)) {
      RCLCPP_WARN(this->get_logger(), "Failed to encode mask");
      return;
    }

    // Publish mask
    sensor_msgs::msg::CompressedImage mask_msg;
    mask_msg.header = msg->header;
    mask_msg.format = "png";
    mask_msg.data = png_data;
    mask_pub_->publish(mask_msg);

    // Create and publish visualization
    try {
      cv::Mat viz = create_visualization(img, mask);
      std::vector<uint8_t> jpeg_data;
      std::vector<int> jpeg_params = {cv::IMWRITE_JPEG_QUALITY, 85};
      if (cv::imencode(".jpg", viz, jpeg_data, jpeg_params)) {
        sensor_msgs::msg::CompressedImage viz_msg;
        viz_msg.header.stamp = msg->header.stamp;
        viz_msg.format = "jpeg";
        viz_msg.data = jpeg_data;
        mask_image_pub_->publish(viz_msg);
      }
    } catch (const cv::Exception & e) {
      RCLCPP_WARN(this->get_logger(), "Failed to create visualization: %s", e.what());
    }

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
  auto node = std::make_shared<connectx_perception_cpp::FloorMaskNode>(options);
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
