#!/usr/bin/env python3
"""
Arrow-key teleop: publish Twist to /cmd_vel on arrow key press.
Up = forward, Down = backward, Left = left, Right = right.
Uses termios for raw key reading (no extra deps). Run in a terminal.
"""
import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


def read_key():
    """Read a single key; return arrow key name or None."""
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch2 = sys.stdin.read(1)
            ch3 = sys.stdin.read(1)
            if ch2 == "[" and ch3 == "A":
                return "up"
            if ch2 == "[" and ch3 == "B":
                return "down"
            if ch2 == "[" and ch3 == "C":
                return "right"
            if ch2 == "[" and ch3 == "D":
                return "left"
        if ch in "\x03\x04":  # Ctrl+C / Ctrl+D
            return "quit"
        return None
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def main(args=None):
    rclpy.init(args=args)
    node = Node("arrow_key_teleop")
    pub = node.create_publisher(Twist, "/cmd_vel", 10)
    twist = Twist()
    twist.linear.x = 0.0
    twist.linear.y = 0.0
    twist.linear.z = 0.0
    twist.angular.x = 0.0
    twist.angular.y = 0.0
    twist.angular.z = 0.0

    # Values above bridge cmd_vel_threshold (default 0.1)
    LINEAR = 0.5
    ANGULAR = 0.5

    node.get_logger().info("Arrow-key teleop: Up=forward, Down=back, Left/Right=turn. Ctrl+C quit.")
    try:
        while rclpy.ok():
            key = read_key()
            if key == "quit":
                break
            if key == "up":
                twist.linear.x = LINEAR
                twist.angular.z = 0.0
            elif key == "down":
                twist.linear.x = -LINEAR
                twist.angular.z = 0.0
            elif key == "left":
                twist.linear.x = 0.0
                twist.angular.z = -ANGULAR  # bridge: angular.z < 0 -> move_left
            elif key == "right":
                twist.linear.x = 0.0
                twist.angular.z = ANGULAR   # bridge: angular.z > 0 -> move_right
            else:
                continue
            node.get_logger().info("Publishing: %s" % key)
            pub.publish(twist)
            # Brief stop so we don't hold forever
            twist.linear.x = 0.0
            twist.angular.z = 0.0
            pub.publish(twist)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
