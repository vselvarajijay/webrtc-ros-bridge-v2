#ifndef CONNECTX_PERCEPTION_CPP__FLOOR_MASK_NODE_HPP_
#define CONNECTX_PERCEPTION_CPP__FLOOR_MASK_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <opencv2/opencv.hpp>
#include <string>
#include <memory>
#include <mutex>

namespace connectx_perception_cpp
{

class FloorMaskNode : public rclcpp::Node
{
public:
  explicit FloorMaskNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~FloorMaskNode();

private:
  void image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
  cv::Mat compute_floor_mask(const cv::Mat & img);
  cv::Mat create_visualization(const cv::Mat & img, const cv::Mat & mask);

  // ROS2 subscribers and publishers
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr image_sub_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr mask_pub_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr mask_image_pub_;

  // State
  std::mutex lock_;
  cv::Mat latest_mask_;
  rclcpp::Time mask_stamp_;
  cv::Mat latest_image_;

  // Parameters
  int mask_w_, mask_h_;
  double seed_bottom_frac_;
  double seed_center_width_frac_;
  double hsv_similarity_threshold_;
  int erode_kernel_;
  int dilate_kernel_;
  bool enable_morphology_;
};

}  // namespace connectx_perception_cpp

#endif  // CONNECTX_PERCEPTION_CPP__FLOOR_MASK_NODE_HPP_
