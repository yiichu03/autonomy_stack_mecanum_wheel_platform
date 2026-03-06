#include <memory>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/point_cloud2.hpp"

#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl_conversions/pcl_conversions.h>

class RegisteredScanFrameRelay : public rclcpp::Node
{
public:
  RegisteredScanFrameRelay()
  : Node("registered_scan_frame_relay")
  {
    sub_cloud_ = create_subscription<sensor_msgs::msg::PointCloud2>(
        "/registered_scan_raw",
        rclcpp::SensorDataQoS(),
        std::bind(&RegisteredScanFrameRelay::cloudHandler, this, std::placeholders::_1));
    pub_cloud_ = create_publisher<sensor_msgs::msg::PointCloud2>(
        "/registered_scan",
        rclcpp::SensorDataQoS());

    RCLCPP_INFO(
        get_logger(),
        "registered_scan_frame_relay: /registered_scan_raw -> /registered_scan "
        "(camera_init axes -> ROS map axes)");
  }

private:
  void cloudHandler(const sensor_msgs::msg::PointCloud2::ConstSharedPtr msg)
  {
    pcl::PointCloud<pcl::PointXYZI> cloud_in;
    pcl::PointCloud<pcl::PointXYZI> cloud_out;
    pcl::fromROSMsg(*msg, cloud_in);

    cloud_out.header = cloud_in.header;
    cloud_out.width = cloud_in.width;
    cloud_out.height = cloud_in.height;
    cloud_out.is_dense = cloud_in.is_dense;
    cloud_out.points.resize(cloud_in.points.size());

    for (std::size_t i = 0; i < cloud_in.points.size(); ++i) {
      const auto &src = cloud_in.points[i];
      auto &dst = cloud_out.points[i];

      // FAST-LIO world (camera_init): X=right, Y=down, Z=forward
      // ROS map used by autonomy_stack: X=forward, Y=left, Z=up
      dst.x = src.z;
      dst.y = -src.x;
      dst.z = -src.y;
      dst.intensity = src.intensity;
    }

    sensor_msgs::msg::PointCloud2 msg_out;
    pcl::toROSMsg(cloud_out, msg_out);
    msg_out.header = msg->header;
    msg_out.header.frame_id = "map";
    pub_cloud_->publish(msg_out);
  }

  rclcpp::Subscription<sensor_msgs::msg::PointCloud2>::SharedPtr sub_cloud_;
  rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr pub_cloud_;
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RegisteredScanFrameRelay>());
  rclcpp::shutdown();
  return 0;
}
