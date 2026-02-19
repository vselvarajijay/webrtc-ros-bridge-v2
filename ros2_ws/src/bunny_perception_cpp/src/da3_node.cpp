#include "bunny_perception_cpp/da3_node.hpp"
#include <cv_bridge/cv_bridge.h>
#include <opencv2/imgproc/imgproc.hpp>
#include <opencv2/highgui/highgui.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include <sensor_msgs/msg/point_field.hpp>
#include <cmath>
#include <limits>
#include <cstring>

namespace bunny_perception_cpp
{

DepthAnything3Node::DepthAnything3Node(const rclcpp::NodeOptions & options)
: Node("da3_node", options)
{
  // Declare parameters
  this->declare_parameter<std::string>("models_dir", "");
  this->declare_parameter<double>("focal_length", 341.93);
  this->declare_parameter<std::vector<double>>("calib_K", {
    340.102399, 0.0, 308.345727,
    0.0, 341.766597, 272.151785,
    0.0, 0.0, 1.0
  });
  
  // Get parameters
  std::string models_dir = this->get_parameter("models_dir").as_string();
  focal_length_ = this->get_parameter("focal_length").as_double();
  calib_K_ = this->get_parameter("calib_K").as_double_array();
  
  // Extract camera intrinsics from K matrix
  if (calib_K_.size() >= 9) {
    fx_ = calib_K_[0];
    fy_ = calib_K_[4];
    cx_ = calib_K_[2];
    cy_ = calib_K_[5];
  } else {
    RCLCPP_WARN(this->get_logger(), "Invalid K matrix, using defaults");
    fx_ = fy_ = focal_length_;
    cx_ = cy_ = 0.0;
  }
  
  // Set model paths
  if (models_dir.empty()) {
    // Default to workspace/models
    const char * workspace = std::getenv("COLCON_PREFIX_PATH");
    if (workspace) {
      models_dir = std::string(workspace) + "/../models";
    } else {
      models_dir = "/root/workspace/models";
    }
  }
  models_dir_ = models_dir;
  da3_model_path_ = models_dir + "/DA3Metric-Large";
  
  RCLCPP_INFO(this->get_logger(), "DA3 Model Path: %s", da3_model_path_.c_str());
  RCLCPP_INFO(this->get_logger(), "Camera intrinsics: fx=%.2f, fy=%.2f, cx=%.2f, cy=%.2f", 
               fx_, fy_, cx_, cy_);
  
  // TODO: Initialize ONNX Runtime or TensorRT inference engines
  // For now, log that models need to be loaded
  RCLCPP_WARN(this->get_logger(), 
    "C++ inference not yet implemented. Use Python node (da3_node.py) for now.");
  RCLCPP_WARN(this->get_logger(), 
    "To use C++: Convert models to ONNX and use ONNX Runtime C++ API");
  
  // Create subscribers and publishers
  image_sub_ = this->create_subscription<sensor_msgs::msg::CompressedImage>(
    "/camera/front/compressed",
    10,
    std::bind(&DepthAnything3Node::image_callback, this, std::placeholders::_1)
  );
  
  depth_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/da3/depth", 10);
  pointcloud_pub_ = this->create_publisher<sensor_msgs::msg::PointCloud2>(
    "/da3/pointcloud", 10);
  
  RCLCPP_INFO(this->get_logger(), "DA3 Node initialized (C++ structure ready for ONNX)");
}

DepthAnything3Node::~DepthAnything3Node()
{
}

void DepthAnything3Node::image_callback(const sensor_msgs::msg::CompressedImage::SharedPtr msg)
{
  try {
    // Convert ROS compressed image to OpenCV
    cv::Mat cv_img;
    try {
      // Decode compressed image
      cv_img = cv::imdecode(cv::Mat(msg->data), cv::IMREAD_COLOR);
      if (cv_img.empty()) {
        RCLCPP_ERROR(this->get_logger(), "Failed to decode compressed image");
        return;
      }
    } catch (const cv::Exception & e) {
      RCLCPP_ERROR(this->get_logger(), "OpenCV exception: %s", e.what());
      return;
    }
    int orig_h = cv_img.rows;
    int orig_w = cv_img.cols;
    
    // TODO: Run depth inference using ONNX Runtime
    // For now, create a placeholder depth image
    cv::Mat depth_image(orig_h, orig_w, CV_32FC1);
    depth_image.setTo(0.0f);  // Placeholder - replace with actual inference
    
    RCLCPP_WARN_ONCE(this->get_logger(), 
      "C++ inference not implemented. Depth image is placeholder. Use Python node instead.");
    
    // Publish depth image
    sensor_msgs::msg::Image depth_msg;
    depth_msg.header = msg->header;
    depth_msg.height = orig_h;
    depth_msg.width = orig_w;
    depth_msg.encoding = "32FC1";
    depth_msg.is_bigendian = false;
    depth_msg.step = orig_w * sizeof(float);
    depth_msg.data.resize(orig_h * orig_w * sizeof(float));
    memcpy(depth_msg.data.data(), depth_image.data, depth_msg.data.size());
    depth_pub_->publish(depth_msg);
    
    // Convert depth to PointCloud2
    sensor_msgs::msg::PointCloud2 pointcloud_msg;
    depth_to_pointcloud(depth_image, msg->header, pointcloud_msg);
    pointcloud_pub_->publish(pointcloud_msg);
    
  } catch (const cv_bridge::Exception & e) {
    RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
  } catch (const std::exception & e) {
    RCLCPP_ERROR(this->get_logger(), "Exception in callback: %s", e.what());
  }
}

void DepthAnything3Node::depth_to_pointcloud(
  const cv::Mat & depth_image,
  const std_msgs::msg::Header & header,
  sensor_msgs::msg::PointCloud2 & pointcloud)
{
  int height = depth_image.rows;
  int width = depth_image.cols;
  
  // Prepare PointCloud2 message
  pointcloud.header = header;
  pointcloud.height = height;
  pointcloud.width = width;
  pointcloud.is_dense = false;
  pointcloud.is_bigendian = false;
  
  // Set fields using modifier
  sensor_msgs::PointCloud2Modifier modifier(pointcloud);
  modifier.setPointCloud2Fields(3,
    "x", 1, sensor_msgs::msg::PointField::FLOAT32,
    "y", 1, sensor_msgs::msg::PointField::FLOAT32,
    "z", 1, sensor_msgs::msg::PointField::FLOAT32);
  
  modifier.resize(height * width);
  
  sensor_msgs::PointCloud2Iterator<float> iter_x(pointcloud, "x");
  sensor_msgs::PointCloud2Iterator<float> iter_y(pointcloud, "y");
  sensor_msgs::PointCloud2Iterator<float> iter_z(pointcloud, "z");
  
  for (int v = 0; v < height; ++v) {
    for (int u = 0; u < width; ++u) {
      float depth = depth_image.at<float>(v, u);
      
      // Filter invalid depth values
      if (std::isnan(depth) || std::isinf(depth) || depth <= 0.0f) {
        *iter_x = *iter_y = *iter_z = std::numeric_limits<float>::quiet_NaN();
      } else {
        // Convert pixel coordinates to 3D points
        *iter_x = (u - cx_) * depth / fx_;
        *iter_y = (v - cy_) * depth / fy_;
        *iter_z = depth;
      }
      
      ++iter_x;
      ++iter_y;
      ++iter_z;
    }
  }
}

}  // namespace bunny_perception_cpp

int main(int argc, char * argv[])
{
  rclcpp::init(argc, argv);
  rclcpp::NodeOptions options;
  auto node = std::make_shared<bunny_perception_cpp::DepthAnything3Node>(options);
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
