#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <sensor_msgs/msg/camera_info.hpp>
#include <std_msgs/msg/string.hpp>
#include <cv_bridge/cv_bridge.hpp>
#include <optical_flow_nav/msg/navigation_state.hpp>

#include "optical_flow_nav/flow_estimator.hpp"
#include "optical_flow_nav/masker.hpp"
#include "optical_flow_nav/band_metrics.hpp"
#include "optical_flow_nav/motion_compensation.hpp"
#include "optical_flow_nav/risk_estimator.hpp"
#include "optical_flow_nav/types.hpp"

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <cmath>
#include <exception>
#include <mutex>
#include <string>
#include <regex>

namespace optical_flow_nav
{

static void parse_telemetry_json(const std::string & data, double & linear, double & angular)
{
  linear = 0.0;
  angular = 0.0;
  std::regex linear_re(R"("linear_velocity"\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?))");
  std::regex angular_re(R"("angular_velocity"\s*:\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?))");
  std::smatch m;
  if (std::regex_search(data, m, linear_re) && m.size() > 1) {
    linear = std::stod(m[1].str());
  }
  if (std::regex_search(data, m, angular_re) && m.size() > 1) {
    angular = std::stod(m[1].str());
  }
}

class OpticalFlowNode : public rclcpp::Node
{
public:
  OpticalFlowNode()
  : Node("optical_flow_node")
  {
    declare_parameters();
    flow_params_ = get_flow_params();
    mask_params_ = get_mask_params();
    motion_params_ = get_motion_params();
    risk_params_ = get_risk_params();
    num_bands_ = 3;

    flow_estimator_ = std::make_shared<FlowEstimator>(flow_params_);
    masker_ = std::make_shared<Masker>(mask_params_);
    band_metrics_ = std::make_shared<BandMetrics>(num_bands_);
    motion_compensation_ = std::make_shared<MotionCompensation>(motion_params_);
    risk_estimator_ = std::make_shared<RiskEstimator>(risk_params_);

    pub_nav_ = create_publisher<optical_flow_nav::msg::NavigationState>(
      "/navigation_state", 10);
    pub_debug_flow_ = create_publisher<sensor_msgs::msg::Image>(
      "/optical_flow_nav/debug_flow_image", 10);
    pub_debug_mask_ = create_publisher<sensor_msgs::msg::Image>(
      "/optical_flow_nav/debug_mask", 10);

    // Match test_video_publisher_node: BEST_EFFORT, KEEP_LAST(10), VOLATILE
    rclcpp::QoS image_qos(rclcpp::KeepLast(10));
    image_qos.best_effort();
    image_qos.durability_volatile();
    sub_image_ = create_subscription<sensor_msgs::msg::Image>(
      "/camera/image_raw",
      image_qos,
      [this](const sensor_msgs::msg::Image::SharedPtr msg) { on_image(msg); });
    sub_telemetry_ = create_subscription<std_msgs::msg::String>(
      "/robot/telemetry",
      10,
      [this](const std_msgs::msg::String::SharedPtr msg) { on_telemetry(msg); });

    RCLCPP_INFO(get_logger(), "optical_flow_nav node started");
  }

private:
  void declare_parameters()
  {
    declare_parameter("camera.use_camera_info", true);
    declare_parameter("camera.frame_id", std::string("camera_link"));
    declare_parameter("camera.position.x", 0.0);
    declare_parameter("camera.position.y", 0.0);
    declare_parameter("camera.position.z", 0.10);
    declare_parameter("camera.orientation.pitch_deg", 15.0);

    declare_parameter("flow.method", std::string("lucas_kanade"));
    declare_parameter("flow.resize_width", 320);
    declare_parameter("flow.resize_height", 240);
    declare_parameter("flow.history_window", 5);
    declare_parameter("flow.min_features", 100);

    declare_parameter("mask.enabled", true);
    declare_parameter("mask.type", std::string("floor_band"));
    declare_parameter("mask.floor_band.bottom_fraction", 0.4);
    declare_parameter("mask.polygon.x", std::vector<double>{});
    declare_parameter("mask.polygon.y", std::vector<double>{});
    declare_parameter("mask.hsv_floor.h_min", 0);
    declare_parameter("mask.hsv_floor.h_max", 180);
    declare_parameter("mask.hsv_floor.s_min", 0);
    declare_parameter("mask.hsv_floor.s_max", 255);
    declare_parameter("mask.hsv_floor.v_min", 0);
    declare_parameter("mask.hsv_floor.v_max", 255);

    declare_parameter("motion_compensation.enabled", true);
    declare_parameter("motion_compensation.min_linear_velocity", 0.05);
    declare_parameter("motion_compensation.ignore_rotation_threshold_deg_s", 15.0);
    declare_parameter("motion_compensation.angular_damping_factor", 0.7);

    declare_parameter("risk.forward_risk_threshold", 0.6f);
    declare_parameter("risk.center_weight", 1.5f);
    declare_parameter("risk.urgency_gain", 1.2f);
    declare_parameter("risk.smoothing_alpha", 0.4f);

    declare_parameter("debug.publish_flow_image", false);
    declare_parameter("debug.publish_mask", false);
  }

  FlowParams get_flow_params()
  {
    FlowParams p;
    p.method = get_parameter("flow.method").as_string();
    p.resize_width = get_parameter("flow.resize_width").as_int();
    p.resize_height = get_parameter("flow.resize_height").as_int();
    p.history_window = get_parameter("flow.history_window").as_int();
    p.min_features = get_parameter("flow.min_features").as_int();
    return p;
  }

  MaskParams get_mask_params()
  {
    MaskParams p;
    p.enabled = get_parameter("mask.enabled").as_bool();
    p.type = get_parameter("mask.type").as_string();
    p.floor_band.bottom_fraction = get_parameter("mask.floor_band.bottom_fraction").as_double();
    try {
      p.polygon.x = get_parameter("mask.polygon.x").as_double_array();
    } catch (const std::exception &) {
      p.polygon.x = {};
    }
    try {
      p.polygon.y = get_parameter("mask.polygon.y").as_double_array();
    } catch (const std::exception &) {
      p.polygon.y = {};
    }
    p.hsv_floor.h_min = get_parameter("mask.hsv_floor.h_min").as_int();
    p.hsv_floor.h_max = get_parameter("mask.hsv_floor.h_max").as_int();
    p.hsv_floor.s_min = get_parameter("mask.hsv_floor.s_min").as_int();
    p.hsv_floor.s_max = get_parameter("mask.hsv_floor.s_max").as_int();
    p.hsv_floor.v_min = get_parameter("mask.hsv_floor.v_min").as_int();
    p.hsv_floor.v_max = get_parameter("mask.hsv_floor.v_max").as_int();
    return p;
  }

  MotionCompensationParams get_motion_params()
  {
    MotionCompensationParams p;
    p.enabled = get_parameter("motion_compensation.enabled").as_bool();
    p.min_linear_velocity = get_parameter("motion_compensation.min_linear_velocity").as_double();
    p.ignore_rotation_threshold_deg_s =
      get_parameter("motion_compensation.ignore_rotation_threshold_deg_s").as_double();
    p.angular_damping_factor =
      get_parameter("motion_compensation.angular_damping_factor").as_double();
    return p;
  }

  RiskParams get_risk_params()
  {
    RiskParams p;
    p.forward_risk_threshold = get_parameter("risk.forward_risk_threshold").as_double();
    p.center_weight = get_parameter("risk.center_weight").as_double();
    p.urgency_gain = get_parameter("risk.urgency_gain").as_double();
    p.smoothing_alpha = get_parameter("risk.smoothing_alpha").as_double();
    return p;
  }

  void on_telemetry(const std_msgs::msg::String::SharedPtr msg)
  {
    double lin = 0.0, ang = 0.0;
    parse_telemetry_json(msg->data, lin, ang);
    std::lock_guard<std::mutex> lock(telemetry_mutex_);
    telemetry_.linear_velocity = lin;
    telemetry_.angular_velocity = ang;
    telemetry_.has_data = true;
  }

  void on_image(const sensor_msgs::msg::Image::SharedPtr msg)
  {
    cv_bridge::CvImageConstPtr cv_ptr;
    try {
      cv_ptr = cv_bridge::toCvShare(msg, "bgr8");
    } catch (const cv_bridge::Exception & e) {
      RCLCPP_WARN_THROTTLE(get_logger(), *get_clock(), 1000, "cv_bridge: %s", e.what());
      publish_fallback(msg->header);
      return;
    }

    const cv::Mat & bgr = cv_ptr->image;
    if (bgr.empty()) {
      publish_fallback(msg->header);
      return;
    }

    if (resized_buf_.empty() ||
        resized_buf_.cols != flow_params_.resize_width ||
        resized_buf_.rows != flow_params_.resize_height) {
      resized_buf_.create(flow_params_.resize_height, flow_params_.resize_width, CV_8UC3);
    }
    cv::resize(bgr, resized_buf_, resized_buf_.size());

    if (gray_buf_.empty() || gray_buf_.size() != resized_buf_.size()) {
      gray_buf_.create(resized_buf_.rows, resized_buf_.cols, CV_8UC1);
    }
    if (resized_buf_.channels() == 3) {
      cv::cvtColor(resized_buf_, gray_buf_, cv::COLOR_BGR2GRAY);
    } else {
      resized_buf_.copyTo(gray_buf_);
    }

    if (prev_gray_.empty()) {
      prev_gray_ = gray_buf_.clone();
      frame_id_ = msg->header.frame_id;
      publish_fallback(msg->header);
      return;
    }

    mask_params_ = get_mask_params();
    masker_->set_params(mask_params_);
    cv::Mat mask = masker_->compute_mask(resized_buf_);

    flow_params_ = get_flow_params();
    flow_estimator_->set_params(flow_params_);
    int feature_count = 0;
    cv::Mat flow_mag = flow_estimator_->compute_flow(prev_gray_, gray_buf_, mask, feature_count);

    bool flow_failed = flow_mag.empty();
    if (flow_failed) {
      publish_fallback(msg->header);
      prev_gray_ = gray_buf_.clone();
      return;
    }

    BandMagnitudes bands = band_metrics_->compute(flow_mag, mask);

    Telemetry telemetry;
    {
      std::lock_guard<std::mutex> lock(telemetry_mutex_);
      telemetry = telemetry_;
    }

    motion_compensation_->set_params(get_motion_params());
    MotionCompensationResult comp =
      motion_compensation_->apply(bands, telemetry);

    bool rotating = telemetry.has_data &&
      (std::fabs(telemetry.angular_velocity) * (180.0 / 3.141592653589793) >=
       get_parameter("motion_compensation.ignore_rotation_threshold_deg_s").as_double());
    risk_estimator_->set_rotation_active(rotating);
    risk_estimator_->set_params(get_risk_params());

    float flow_variance = 0.0f;
    if (flow_mag.isContinuous()) {
      double mean = 0.0, var = 0.0;
      const float * p = flow_mag.ptr<float>();
      size_t n = flow_mag.total();
      for (size_t i = 0; i < n; ++i) { mean += p[i]; }
      mean /= n;
      for (size_t i = 0; i < n; ++i) {
        double d = p[i] - mean;
        var += d * d;
      }
      flow_variance = static_cast<float>(var / n);
    }
    int valid_mask = 0;
    if (!mask.empty()) {
      valid_mask = cv::countNonZero(mask);
    } else {
      valid_mask = flow_mag.rows * flow_mag.cols;
    }
    float mask_coverage = (flow_mag.rows * flow_mag.cols > 0)
      ? static_cast<float>(valid_mask) / (flow_mag.rows * flow_mag.cols) : 1.0f;

    RiskOutput risk = risk_estimator_->compute(
      comp.adjusted,
      comp.ignore_forward_risk,
      feature_count,
      flow_variance,
      mask_coverage,
      false);

    optical_flow_nav::msg::NavigationState nav_msg;
    nav_msg.header = msg->header;
    nav_msg.forward_safe = risk.forward_safe;
    nav_msg.forward_risk = std::max(0.0f, std::min(1.0f, risk.forward_risk));
    nav_msg.safest_turn = risk.safest_turn;
    nav_msg.turn_confidence = std::max(0.0f, std::min(1.0f, risk.turn_confidence));
    nav_msg.urgency_score = std::max(0.0f, std::min(1.0f, risk.urgency_score));
    nav_msg.confidence = std::max(0.0f, std::min(1.0f, risk.confidence));
    nav_msg.flow_mag_left = comp.adjusted.flow_mag_left;
    nav_msg.flow_mag_center = comp.adjusted.flow_mag_center;
    nav_msg.flow_mag_right = comp.adjusted.flow_mag_right;

    if (std::isnan(nav_msg.forward_risk)) { nav_msg.forward_risk = 0.0f; }
    if (std::isnan(nav_msg.turn_confidence)) { nav_msg.turn_confidence = 0.0f; }
    if (std::isnan(nav_msg.urgency_score)) { nav_msg.urgency_score = 0.0f; }
    if (std::isnan(nav_msg.confidence)) { nav_msg.confidence = 0.0f; }
    if (std::isnan(nav_msg.flow_mag_left)) { nav_msg.flow_mag_left = 0.0f; }
    if (std::isnan(nav_msg.flow_mag_center)) { nav_msg.flow_mag_center = 0.0f; }
    if (std::isnan(nav_msg.flow_mag_right)) { nav_msg.flow_mag_right = 0.0f; }

    pub_nav_->publish(nav_msg);

    bool pub_flow = get_parameter("debug.publish_flow_image").as_bool();
    bool pub_mask = get_parameter("debug.publish_mask").as_bool();
    if (pub_flow && pub_debug_flow_->get_subscription_count() > 0) {
      cv::Mat vis;
      flow_mag.convertTo(vis, CV_8UC1, 255.0);
      cv::applyColorMap(vis, vis, cv::COLORMAP_JET);
      cv_bridge::CvImage out;
      out.header = msg->header;
      out.encoding = "bgr8";
      out.image = vis;
      pub_debug_flow_->publish(*out.toImageMsg());
    }
    if (pub_mask && pub_debug_mask_->get_subscription_count() > 0) {
      cv_bridge::CvImage out;
      out.header = msg->header;
      out.encoding = "mono8";
      out.image = mask;
      pub_debug_mask_->publish(*out.toImageMsg());
    }

    prev_gray_ = gray_buf_.clone();
    frame_id_ = msg->header.frame_id;
  }

  void publish_fallback(const std_msgs::msg::Header & header)
  {
    optical_flow_nav::msg::NavigationState nav_msg;
    nav_msg.header = header;
    nav_msg.forward_safe = true;
    nav_msg.forward_risk = 0.0f;
    nav_msg.safest_turn = 0;
    nav_msg.turn_confidence = 0.0f;
    nav_msg.urgency_score = 0.0f;
    nav_msg.confidence = 0.0f;
    nav_msg.flow_mag_left = 0.0f;
    nav_msg.flow_mag_center = 0.0f;
    nav_msg.flow_mag_right = 0.0f;
    pub_nav_->publish(nav_msg);
  }

  FlowParams flow_params_;
  MaskParams mask_params_;
  MotionCompensationParams motion_params_;
  RiskParams risk_params_;
  int num_bands_;

  std::shared_ptr<FlowEstimator> flow_estimator_;
  std::shared_ptr<Masker> masker_;
  std::shared_ptr<BandMetrics> band_metrics_;
  std::shared_ptr<MotionCompensation> motion_compensation_;
  std::shared_ptr<RiskEstimator> risk_estimator_;

  rclcpp::Publisher<optical_flow_nav::msg::NavigationState>::SharedPtr pub_nav_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_debug_flow_;
  rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr pub_debug_mask_;

  rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr sub_image_;
  rclcpp::Subscription<std_msgs::msg::String>::SharedPtr sub_telemetry_;

  cv::Mat prev_gray_;
  cv::Mat gray_buf_;
  cv::Mat resized_buf_;
  std::string frame_id_;
  std::mutex telemetry_mutex_;
  Telemetry telemetry_;
};

}  // namespace optical_flow_nav

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<optical_flow_nav::OpticalFlowNode>();
  rclcpp::spin(node);
  rclcpp::shutdown();
  return 0;
}
