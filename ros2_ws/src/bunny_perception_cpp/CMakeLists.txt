cmake_minimum_required(VERSION 3.20)
project(bunny_perception_cpp)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(cv_bridge QUIET)
find_package(image_transport QUIET)
find_package(OpenCV QUIET)

# Include directories
include_directories(include)

# C++ executable only when explicitly requested (e.g. in scout_perception image with cv_bridge).
# Default OFF so colcon build in scout_bridge (no cv_bridge) succeeds; Python node (da3_node) always works.
# To build the C++ node: colcon build --cmake-args -DBUILD_DA3_CPP=ON
option(BUILD_DA3_CPP "Build C++ da3_node_cpp (requires cv_bridge)" OFF)
if(BUILD_DA3_CPP AND cv_bridge_FOUND AND image_transport_FOUND AND OpenCV_FOUND)
  add_executable(da3_node_cpp src/da3_node.cpp)
  target_link_libraries(da3_node_cpp PUBLIC
    rclcpp::rclcpp
    sensor_msgs::sensor_msgs_library
    cv_bridge::cv_bridge
    image_transport::image_transport
    ${OpenCV_LIBS}
  )
  install(TARGETS da3_node_cpp DESTINATION lib/${PROJECT_NAME})
endif()

install(DIRECTORY include/
  DESTINATION include
)

# Python package installation
ament_python_install_package(${PROJECT_NAME}
  PACKAGE_DIR bunny_perception_cpp
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
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
