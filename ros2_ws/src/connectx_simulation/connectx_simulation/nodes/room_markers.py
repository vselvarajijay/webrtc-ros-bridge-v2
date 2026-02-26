#!/usr/bin/env python3
"""
Publish the sim room walls as visualization_msgs/MarkerArray so Foxglove 3D
can display them. Matches box_car_world.sdf: 6x6 m room, walls at +/-3 m.
"""
import rclpy
from rclpy.node import Node
from visualization_msgs.msg import Marker, MarkerArray


def main(args=None):
    rclpy.init(args=args)
    node = Node("room_markers")
    pub = node.create_publisher(MarkerArray, "/room_markers", 1)

    # Same layout as box_car_world.sdf: north/south 6x0.1x0.5 at y=±3, east/west 0.1x6x0.5 at x=±3
    markers = MarkerArray()
    t = node.get_clock().now().to_msg()

    def wall_marker(mid: int, x: float, y: float, sx: float, sy: float, sz: float):
        m = Marker()
        m.header.frame_id = "world"
        m.header.stamp = t
        m.ns = "room"
        m.id = mid
        m.type = Marker.CUBE
        m.action = Marker.ADD
        m.pose.position.x = x
        m.pose.position.y = y
        m.pose.position.z = 0.25
        m.pose.orientation.w = 1.0
        m.scale.x = sx
        m.scale.y = sy
        m.scale.z = sz
        m.color.r = 0.7
        m.color.g = 0.7
        m.color.b = 0.7
        m.color.a = 1.0
        # Leave lifetime default (zero) to avoid schema quirks with builtin_interfaces in Foxglove
        return m

    markers.markers.append(wall_marker(0, 0.0, 3.0, 6.0, 0.1, 0.5))   # north
    markers.markers.append(wall_marker(1, 0.0, -3.0, 6.0, 0.1, 0.5))  # south
    markers.markers.append(wall_marker(2, 3.0, 0.0, 0.1, 6.0, 0.5))  # east
    markers.markers.append(wall_marker(3, -3.0, 0.0, 0.1, 6.0, 0.5))  # west

    def publish():
        markers.markers[0].header.stamp = node.get_clock().now().to_msg()
        markers.markers[1].header.stamp = markers.markers[0].header.stamp
        markers.markers[2].header.stamp = markers.markers[0].header.stamp
        markers.markers[3].header.stamp = markers.markers[0].header.stamp
        pub.publish(markers)

    publish()
    node.create_timer(1.0, publish)  # re-publish at 1 Hz so late-joining Foxglove gets it
    node.get_logger().info("room_markers: publishing /room_markers (4 walls, frame_id=world)")
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
