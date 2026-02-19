#ifndef BUNNY_PERCEPTION_CPP__DA3_NODE_HPP_
#define BUNNY_PERCEPTION_CPP__DA3_NODE_HPP_

#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/msg/point_cloud2.hpp>
#include <cv_bridge/cv_bridge.h>
#include <opencv2/opencv.hpp>
#include <string>
#include <memory>
#include <vector>

namespace bunny_perception_cpp
{

class DepthAnything3Node : public rclcpp::Node
{
public:
  explicit DepthAnything3Node(const rclcpp::NodeOptions & options = rclcpp::NodeOptions());
  ~DepthAnything3Node();

private:
  void image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg);
  
  void depth_to_pointcloud(
    const cv::Mat & depth_image,
    const std_msgs::msg::Header & header,
    sensor_msgs::msg::PointCloud2 & pointcloud);
  
  // ROS2 subscribers and publishers
  rclcpp::Subscription<sensor_msgs::msg::CompressedImage>::SharedPtr image_sub_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr depth_pub_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pointcloud_pub_;
  
  // Camera calibration parameters
  std::vector<double> calib_K_;  // 3x3 camera matrix
  double focal_length_;
  double fx_, fy_, cx_, cy_;  // Extracted from K matrix
  
  // Model paths
  std::string models_dir_;
  std::string da3_model_path_;
  
  // TODO: Add ONNX Runtime or TensorRT inference engines here
  // For now, this node structure is ready for ONNX conversion
};

}  // namespace bunny_perception_cpp

#endif  // BUNNY_PERCEPTION_CPP__DA3_NODE_HPP_
