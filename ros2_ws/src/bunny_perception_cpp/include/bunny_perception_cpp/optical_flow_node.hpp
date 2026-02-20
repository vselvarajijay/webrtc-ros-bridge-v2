#ifndef BUNNY_PERCEPTION_CPP__OPTICAL_FLOW_NODE_HPP_
#define BUNNY_PERCEPTION_CPP__OPTICAL_FLOW_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <std_msgs/msg/float32_multi_array.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <memory>
#include <vector>
#include <mutex>

namespace bunny_perception_cpp
{

class OpticalFlowNode : public rclcpp::Node
{
public:
  explicit OpticalFlowNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~OpticalFlowNode();

private:
  void image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
  void mask_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
  
  cv::Mat flow_to_arrows_image(const cv::Mat & flow, int viz_w, int viz_h);
  cv::Mat get_floor_mask(const std::pair<int, int> & flow_shape);
  
  struct MeanFlowResult {
    float vx, vy, mag;
  };
  MeanFlowResult mean_flow(const cv::Mat & region, const cv::Mat & region_mask = cv::Mat());
  
  // ROS2 subscribers and publishers
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr image_sub_;
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr mask_sub_;
  rclcpp::Publisher<std_msgs::msg::Float32MultiArray>::SharedPtr flow_pub_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr flow_image_pub_;
  
  // State
  cv::Mat prev_gray_;
  rclcpp::Time prev_stamp_;
  std::vector<float> flow_ema_;
  std::mutex lock_;
  
  // Floor mask state
  cv::Mat latest_mask_;
  rclcpp::Time mask_stamp_;
  
  // Parameters
  int flow_w_, flow_h_;
  double max_dt_;
  double noise_floor_;
  double flow_max_;
  double ema_alpha_;
  int viz_w_, viz_h_;
  int blur_kernel_;
  double middle_start_, middle_end_;
  double top_band_frac_;
  bool enable_divergence_;
  bool use_enhanced_;
  bool use_floor_mask_;
  double floor_mask_timeout_;
  double floor_mask_weight_;
};

}  // namespace bunny_perception_cpp

#endif  // BUNNY_PERCEPTION_CPP__OPTICAL_FLOW_NODE_HPP_
