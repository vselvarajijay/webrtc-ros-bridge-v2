#!/usr/bin/env python3
"""
Publish the sim room walls as sensor_msgs/PointCloud2 so Foxglove 3D can
display them without using visualization_msgs/Marker (avoids Foxglove schema errors).
Matches box_car_world.sdf: 6x6 m room, walls at +/-3 m.
"""
import struct
import rclpy
from rclpy.node import Node
from std_msgs.msg import Header
from sensor_msgs.msg import PointCloud2, PointField


def _make_cloud(header, points_xyz):
    """Build a PointCloud2 with x,y,z float32 (no rgb)."""
    FLOAT32 = 7
    fields = [
        PointField(name="x", offset=0, datatype=FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=FLOAT32, count=1),
    ]
    point_step = 12
    data = b"".join(struct.pack("<fff", x, y, z) for x, y, z in points_xyz)
    msg = PointCloud2()
    msg.header = header
    msg.height = 1
    msg.width = len(points_xyz)
    msg.fields = fields
    msg.is_bigendian = False
    msg.point_step = point_step
    msg.row_step = point_step * len(points_xyz)
    msg.data = data
    return msg


def main(args=None):
    rclpy.init(args=args)
    node = Node("room_walls")
    pub = node.create_publisher(PointCloud2, "/room_walls", 1)

    # Wall geometry: north/south 6x0.1x0.5 at y=±3, east/west 0.1x6x0.5 at x=±3 (centers at z=0.25)
    # Sample points on each wall face (one face per wall, inward-facing or both)
    points = []
    step = 0.25  # spacing between points

    # North wall (y=3): x in [-3,3], z in [0, 0.5]
    for x in [_x * step for _x in range(int(-3 / step), int(3 / step) + 1)]:
        for z in [0.0, 0.25, 0.5]:
            points.append((x, 3.0, z))
    # South wall (y=-3)
    for x in [_x * step for _x in range(int(-3 / step), int(3 / step) + 1)]:
        for z in [0.0, 0.25, 0.5]:
            points.append((x, -3.0, z))
    # East wall (x=3): y in [-3,3], z in [0, 0.5]
    for y in [_y * step for _y in range(int(-3 / step), int(3 / step) + 1)]:
        for z in [0.0, 0.25, 0.5]:
            points.append((3.0, y, z))
    # West wall (x=-3)
    for y in [_y * step for _y in range(int(-3 / step), int(3 / step) + 1)]:
        for z in [0.0, 0.25, 0.5]:
            points.append((-3.0, y, z))

    def publish():
        header = Header()
        header.stamp = node.get_clock().now().to_msg()
        header.frame_id = "world"
        pub.publish(_make_cloud(header, points))

    publish()
    node.create_timer(1.0, publish)
    node.get_logger().info(
        f"room_walls: publishing /room_walls (PointCloud2, {len(points)} points, frame_id=world)"
    )
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
