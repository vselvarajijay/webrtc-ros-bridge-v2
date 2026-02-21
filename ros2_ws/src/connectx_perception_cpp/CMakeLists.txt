cmake_minimum_required(VERSION 3.20)
project(connectx_perception_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(std_msgs REQUIRED)
find_package(OpenCV REQUIRED)
# cv_bridge and image_transport are optional - we use OpenCV directly for image handling
find_package(cv_bridge QUIET)
find_package(image_transport QUIET)

# Include directories
include_directories(include)

# Build all C++ executables
add_executable(optical_flow_node src/optical_flow_node.cpp)
target_include_directories(optical_flow_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(optical_flow_node PUBLIC
  rclcpp::rclcpp
  sensor_msgs::sensor_msgs_library
  ${OpenCV_LIBS}
)
if(cv_bridge_FOUND)
  target_link_libraries(optical_flow_node PUBLIC cv_bridge::cv_bridge)
endif()
target_compile_features(optical_flow_node PUBLIC c_std_99 cxx_std_17)

add_executable(floor_mask_node src/floor_mask_node.cpp)
target_include_directories(floor_mask_node PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
target_link_libraries(floor_mask_node PUBLIC
  rclcpp::rclcpp
  sensor_msgs::sensor_msgs_library
  ${OpenCV_LIBS}
)
if(cv_bridge_FOUND)
  target_link_libraries(floor_mask_node PUBLIC cv_bridge::cv_bridge)
endif()
target_compile_features(floor_mask_node PUBLIC c_std_99 cxx_std_17)

install(TARGETS optical_flow_node floor_mask_node
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  # the following line skips the linter which checks for copyrights
  # comment the line when a copyright and license is added to all source files
  set(ament_cmake_copyright_FOUND TRUE)
  # the following line skips cpplint (only works in a git repo)
  # comment the line when this package is in a git repo and when
  # a copyright and license is added to all source files
  set(ament_cmake_cpplint_FOUND TRUE)
  # Exclude vendored third_party from all linters (onnxruntime headers use C++ that uncrustify cannot parse)
  file(GLOB_RECURSE AMENT_LINT_AUTO_FILE_EXCLUDE "${CMAKE_CURRENT_SOURCE_DIR}/third_party/*")
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
