#!/usr/bin/env python3
"""
odom_frame_relay.py
===================
将 FAST-LIO2 输出的里程计（camera_init/body 原始惯例）转换为 ROS 标准帧，
再发布给 autonomy_stack 使用。

D455 IMU / FAST-LIO2 body 帧：X=右, Y=下, Z=前
ROS 标准车体帧（autonomy_stack 期望）：X=前, Y=左, Z=上

修正公式：
    p_map        = R_map_camera_init * p_camera_init
    q_map_sensor = q_map_camera_init ⊗ q_camera_init_body ⊗ q_body_sensor

其中：
    q_map_camera_init (x,y,z,w) = (-0.5, 0.5, -0.5, 0.5)
    q_body_sensor     (x,y,z,w) = ( 0.5,-0.5,  0.5, 0.5)

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
    # camera_init/body 原始轴系 -> ROS map/sensor 轴系
    Q_MAP_CAMERA_INIT = (-0.5, 0.5, -0.5, 0.5)
    # body <- sensor
    Q_BODY_SENSOR = (0.5, -0.5, 0.5, 0.5)

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
        q_map_body = quat_multiply(self.Q_MAP_CAMERA_INIT, q_in)
        qx, qy, qz, qw = quat_multiply(q_map_body, self.Q_BODY_SENSOR)

        px, py, pz = rotate_vector(
            self.Q_MAP_CAMERA_INIT,
            (
                msg.pose.pose.position.x,
                msg.pose.pose.position.y,
                msg.pose.pose.position.z,
            ),
        )
        lvx, lvy, lvz = rotate_vector(
            self.Q_MAP_CAMERA_INIT,
            (
                msg.twist.twist.linear.x,
                msg.twist.twist.linear.y,
                msg.twist.twist.linear.z,
            ),
        )
        avx, avy, avz = rotate_vector(
            self.Q_MAP_CAMERA_INIT,
            (
                msg.twist.twist.angular.x,
                msg.twist.twist.angular.y,
                msg.twist.twist.angular.z,
            ),
        )

        out = Odometry()
        out.header = msg.header
        out.header.frame_id = 'map'    # 世界帧统一用 map
        out.child_frame_id = 'sensor'  # body → sensor (ROS 标准方向)
        out.pose.pose.position.x = px
        out.pose.pose.position.y = py
        out.pose.pose.position.z = pz
        out.pose.pose.orientation.x = qx
        out.pose.pose.orientation.y = qy
        out.pose.pose.orientation.z = qz
        out.pose.pose.orientation.w = qw
        out.twist = msg.twist
        out.twist.twist.linear.x = lvx
        out.twist.twist.linear.y = lvy
        out.twist.twist.linear.z = lvz
        out.twist.twist.angular.x = avx
        out.twist.twist.angular.y = avy
        out.twist.twist.angular.z = avz
        self.pub.publish(out)


def quat_conjugate(q):
    x, y, z, w = q
    return (-x, -y, -z, w)


def rotate_vector(q, v):
    """Use q to rotate a 3D vector, q in (x, y, z, w)."""
    vx, vy, vz = v
    qv = (vx, vy, vz, 0.0)
    qr = quat_multiply(quat_multiply(q, qv), quat_conjugate(q))
    return (qr[0], qr[1], qr[2])


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
