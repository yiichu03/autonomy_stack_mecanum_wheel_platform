#!/usr/bin/env python3
"""
odom_frame_relay.py
===================
将 FAST-LIO2 输出的里程计（body 帧，D455 光学惯例）转换为 ROS 标准帧，
再发布给 autonomy_stack 使用。

D455 IMU / FAST-LIO2 body 帧：X=右, Y=下, Z=前
ROS 标准车体帧（autonomy_stack 期望）：X=前, Y=左, Z=上

修正公式：
    q_corrected = q_fastlio ⊗ q_body_to_sensor
    q_body_to_sensor (x,y,z,w) = (0.5, -0.5, 0.5, 0.5)

对应旋转矩阵（将 body 帧坐标变换到 sensor 帧）：
    body.X(右)  → sensor.(-Y)(右方向)  ✓
    body.Y(下)  → sensor.(-Z)(向下)    ✓
    body.Z(前)  → sensor.X(前方向)     ✓

话题：/state_estimation_raw (FAST-LIO2) → /state_estimation (corrected)
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry


def quat_multiply(q1, q2):
    """Hamilton product q1 ⊗ q2，输入输出均为 (x, y, z, w)。"""
    x1, y1, z1, w1 = q1
    x2, y2, z2, w2 = q2
    return (
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2,
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
    )


class OdomFrameRelay(Node):
    # body→sensor 旋转四元数 (x, y, z, w)
    Q_CORRECTION = (0.5, -0.5, 0.5, 0.5)

    def __init__(self):
        super().__init__('odom_frame_relay')
        self.pub = self.create_publisher(Odometry, '/state_estimation', 5)
        self.sub = self.create_subscription(
            Odometry, '/state_estimation_raw', self.callback, 5)
        self.get_logger().info(
            'odom_frame_relay: /state_estimation_raw → /state_estimation '
            '(D455 body frame → ROS standard frame)')

    def callback(self, msg: Odometry):
        q_in = (
            msg.pose.pose.orientation.x,
            msg.pose.pose.orientation.y,
            msg.pose.pose.orientation.z,
            msg.pose.pose.orientation.w,
        )
        qx, qy, qz, qw = quat_multiply(q_in, self.Q_CORRECTION)

        out = Odometry()
        out.header = msg.header
        out.header.frame_id = 'map'    # 世界帧统一用 map
        out.child_frame_id = 'sensor'  # body → sensor (ROS 标准方向)
        out.pose.pose.position = msg.pose.pose.position  # 位置不变（IMU-LiDAR 偏移 <10cm）
        out.pose.pose.orientation.x = qx
        out.pose.pose.orientation.y = qy
        out.pose.pose.orientation.z = qz
        out.pose.pose.orientation.w = qw
        out.twist = msg.twist
        self.pub.publish(out)


def main():
    rclpy.init()
    node = OdomFrameRelay()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
