cmake_minimum_required(VERSION 3.5)
project(dynamic_octomap_server)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 14)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(OCTOMAP REQUIRED)
find_package(PCL REQUIRED)
find_package(octomap_ros REQUIRED)
find_package(octomap_server REQUIRED)
find_package(pcl_conversions REQUIRED)
find_package(pcl_ros REQUIRED)
find_package(rcl_interfaces REQUIRED)
find_package(rclcpp REQUIRED)
find_package(tf2 REQUIRED)

add_executable(dynamic_octomap_server_node
  src/dynamic_octomap_server.cpp
)

target_include_directories(dynamic_octomap_server_node
  PUBLIC
    include
    ${OCTOMAP_INCLUDE_DIRS}
    ${PCL_INCLUDE_DIRS}
)

ament_target_dependencies(dynamic_octomap_server_node
  octomap_ros
  octomap_server
  pcl_conversions
  pcl_ros
  rcl_interfaces
  rclcpp
  tf2
)

target_link_libraries(dynamic_octomap_server_node
  ${OCTOMAP_LIBRARIES}
  ${PCL_LIBRARIES}
)

install(TARGETS
  dynamic_octomap_server_node
  DESTINATION lib/${PROJECT_NAME}
)

install(
  DIRECTORY include/
  DESTINATION include
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
