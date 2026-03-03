#!/usr/bin/env python3
"""
twist_stamped_to_twist.py
=========================
将 pathFollower (realRobot=false) 发布的 geometry_msgs/TwistStamped
从 /cmd_vel_stamped 转发为 geometry_msgs/Twist 到 /cmd_vel，
供 Scout Mini ROS2 驱动 (agilex_ros2_sdk) 消费。

背景：
  pathFollower 在 realRobot=false 时发布 TwistStamped（含 header）；
  Scout Mini 驱动订阅 Twist（无 header）；两者类型不兼容，需要此中继节点。

话题：
  订阅：/cmd_vel_stamped  (geometry_msgs/TwistStamped)
  发布：/cmd_vel          (geometry_msgs/Twist)
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist, TwistStamped


class TwistStampedToTwist(Node):
    def __init__(self):
        super().__init__('twist_stamped_to_twist')
        self._pub = self.create_publisher(Twist, '/cmd_vel', 5)
        self._sub = self.create_subscription(
            TwistStamped, '/cmd_vel_stamped', self._cb, 5)

    def _cb(self, msg: TwistStamped):
        out = Twist()
        out.linear = msg.twist.linear
        out.angular = msg.twist.angular
        self._pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = TwistStampedToTwist()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
