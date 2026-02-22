cmake_minimum_required(VERSION 3.20)
project(optical_flow_nav)

set(CMAKE_CXX_STANDARD 17)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Dependencies
find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(cv_bridge REQUIRED)
find_package(image_transport REQUIRED)
find_package(OpenCV REQUIRED)

# Custom message
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/NavigationState.msg"
  DEPENDENCIES std_msgs
)

# Library: flow, mask, band metrics, motion compensation, risk (no ROS in lib)
add_library(optical_flow_nav_lib
  include/optical_flow_nav/flow_estimator.cpp
  include/optical_flow_nav/masker.cpp
  include/optical_flow_nav/band_metrics.cpp
  include/optical_flow_nav/motion_compensation.cpp
  include/optical_flow_nav/risk_estimator.cpp
)
target_include_directories(optical_flow_nav_lib PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(optical_flow_nav_lib PUBLIC ${OpenCV_LIBS})

# Node executable
add_executable(optical_flow_node src/optical_flow_node.cpp)
target_include_directories(optical_flow_node PRIVATE include)
# All links in keyword form to satisfy CMake (no mix with ament_target_dependencies)
rosidl_get_typesupport_target(cpp_typesupport_target ${PROJECT_NAME} "rosidl_typesupport_cpp")
target_link_libraries(optical_flow_node
  PUBLIC
    ${sensor_msgs_TARGETS}
    ${std_msgs_TARGETS}
    cv_bridge::cv_bridge
    image_transport::image_transport
    rclcpp::rclcpp
    sensor_msgs::sensor_msgs_library
  PRIVATE
    "${cpp_typesupport_target}"
    optical_flow_nav_lib
)

# Install
install(TARGETS optical_flow_node optical_flow_nav_lib
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION lib/${PROJECT_NAME}
)
install(PROGRAMS scripts/test_video_publisher_node scripts/video_overlay_recorder_node
  DESTINATION lib/${PROJECT_NAME}
)
install(DIRECTORY include/ config/ launch/
  DESTINATION share/${PROJECT_NAME}
  USE_SOURCE_PERMISSIONS
)

ament_export_dependencies(rosidl_default_runtime)
ament_export_include_directories(include)
ament_export_libraries(optical_flow_nav_lib)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
