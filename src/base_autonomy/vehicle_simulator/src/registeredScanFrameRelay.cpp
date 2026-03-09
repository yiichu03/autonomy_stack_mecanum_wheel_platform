#include <array>
#include <cmath>
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
    declare_parameter<double>("gravity_level_qx", 0.0);
    declare_parameter<double>("gravity_level_qy", 0.0);
    declare_parameter<double>("gravity_level_qz", 0.0);
    declare_parameter<double>("gravity_level_qw", 1.0);

    const Quaternion q_level = normalizeQuaternion({
        get_parameter("gravity_level_qx").as_double(),
        get_parameter("gravity_level_qy").as_double(),
        get_parameter("gravity_level_qz").as_double(),
        get_parameter("gravity_level_qw").as_double()});
    q_total_ = normalizeQuaternion(quatMultiply(q_level, mapCameraInit()));

    auto pub_qos = rclcpp::QoS(rclcpp::KeepLast(5));
    pub_qos.reliable();
    pub_qos.durability_volatile();

    sub_cloud_ = create_subscription<sensor_msgs::msg::PointCloud2>(
        "/registered_scan_raw",
        rclcpp::SensorDataQoS(),
        std::bind(&RegisteredScanFrameRelay::cloudHandler, this, std::placeholders::_1));
    pub_cloud_ = create_publisher<sensor_msgs::msg::PointCloud2>(
        "/registered_scan",
        pub_qos);

    RCLCPP_INFO(
        get_logger(),
        "registered_scan_frame_relay: /registered_scan_raw -> /registered_scan "
        "(camera_init axes -> ROS leveled map axes), gravity leveling "
        "q=(%.6f, %.6f, %.6f, %.6f)",
        q_level[0], q_level[1], q_level[2], q_level[3]);
  }

private:
  using Quaternion = std::array<double, 4>;
  using Vector3 = std::array<double, 3>;

  static Quaternion mapCameraInit()
  {
    return {-0.5, 0.5, -0.5, 0.5};
  }

  static Quaternion quatMultiply(const Quaternion &q1, const Quaternion &q2)
  {
    return {
        q1[3] * q2[0] + q1[0] * q2[3] + q1[1] * q2[2] - q1[2] * q2[1],
        q1[3] * q2[1] - q1[0] * q2[2] + q1[1] * q2[3] + q1[2] * q2[0],
        q1[3] * q2[2] + q1[0] * q2[1] - q1[1] * q2[0] + q1[2] * q2[3],
        q1[3] * q2[3] - q1[0] * q2[0] - q1[1] * q2[1] - q1[2] * q2[2]};
  }

  static Quaternion quatConjugate(const Quaternion &q)
  {
    return {-q[0], -q[1], -q[2], q[3]};
  }

  static Quaternion normalizeQuaternion(const Quaternion &q)
  {
    const double norm =
        std::sqrt(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    if (norm < 1e-12) {
      return {0.0, 0.0, 0.0, 1.0};
    }
    return {q[0] / norm, q[1] / norm, q[2] / norm, q[3] / norm};
  }

  static Vector3 rotateVector(const Quaternion &q, const Vector3 &v)
  {
    const Quaternion qv{v[0], v[1], v[2], 0.0};
    const Quaternion qr =
        quatMultiply(quatMultiply(q, qv), quatConjugate(q));
    return {qr[0], qr[1], qr[2]};
  }

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

      const Vector3 rotated = rotateVector(q_total_, {src.x, src.y, src.z});
      dst.x = static_cast<float>(rotated[0]);
      dst.y = static_cast<float>(rotated[1]);
      dst.z = static_cast<float>(rotated[2]);
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
  Quaternion q_total_{mapCameraInit()};
};

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<RegisteredScanFrameRelay>());
  rclcpp::shutdown();
  return 0;
}
