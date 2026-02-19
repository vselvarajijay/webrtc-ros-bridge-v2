#!/usr/bin/env python3
import sys
import os
from pathlib import Path
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image, CompressedImage, PointCloud2, PointField
from cv_bridge import CvBridge
import torch
import cv2
import numpy as np
from depth_anything_3.api import DepthAnything3
import struct


class DepthAnything3Node(Node):
    def __init__(self):
        super().__init__('da3_node')
        self.get_logger().info("Loading AI Models...")
        
        # Get models directory from parameter or environment (workspace root: __file__ -> nodes -> pkg -> pkg -> src -> ros2_ws -> workspace)
        workspace_root = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
        default_models_dir = workspace_root / "models"
        
        self.declare_parameter('models_dir', str(default_models_dir))
        models_dir = Path(self.get_parameter('models_dir').value)
        
        da3_model_path = models_dir / "DA3Metric-Large"
        
        if not da3_model_path.exists():
            self.get_logger().error(f"DA3 model not found at {da3_model_path}")
            self.get_logger().error("Run: python3 scripts/download_models.py")
            raise FileNotFoundError(f"Model not found: {da3_model_path}")
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.get_logger().info(f"Using device: {self.device}")
        
        # Load model from local path
        self.get_logger().info(f"Loading DepthAnything3 from {da3_model_path}...")
        self.model = DepthAnything3.from_pretrained(str(da3_model_path)).to(self.device)
        
        self.cv_bridge = CvBridge()
        
        # Topics
        self.subscription = self.create_subscription(
            CompressedImage, '/camera/front/compressed', self.listener_callback, 10
        )
        self.pub_depth = self.create_publisher(Image, '/da3/depth', 10)
        self.pub_depth_colored = self.create_publisher(CompressedImage, '/da3/depth_colored', 10)
        self.pub_pointcloud = self.create_publisher(PointCloud2, '/da3/pointcloud', 10)
        
        # Camera calibration parameters
        self.declare_parameter('focal_length', 341.93)
        self.focal = self.get_parameter('focal_length').value
        
        self.declare_parameter('calib_K', [
            340.102399, 0.0, 308.345727,
            0.0, 341.766597, 272.151785,
            0.0, 0.0, 1.0
        ])
        calib_K = self.get_parameter('calib_K').value
        self.fx = calib_K[0]
        self.fy = calib_K[4]
        self.cx = calib_K[2]
        self.cy = calib_K[5]
        
        self.get_logger().info(f"Camera intrinsics: fx={self.fx:.2f}, fy={self.fy:.2f}, cx={self.cx:.2f}, cy={self.cy:.2f}")
        self.get_logger().info("DA3 Node ready!")

    def listener_callback(self, msg):
        try:
            # Input Image (Original Resolution)
            cv_img = self.cv_bridge.compressed_imgmsg_to_cv2(msg, "bgr8")
            orig_h, orig_w = cv_img.shape[:2]

            # Depth Inference
            pred = self.model.inference([cv_img])
            depth = pred.depth[0]
            metric_depth = (self.focal * depth) / 300.0
            depth = metric_depth
            if depth.shape[0] != orig_h or depth.shape[1] != orig_w:
                depth = cv2.resize(depth, (orig_w, orig_h), interpolation=cv2.INTER_LINEAR)
            
            # Ensure depth is float32
            depth = depth.astype(np.float32)

            # Publish Depth Image
            header = msg.header
            if not header.frame_id:
                header.frame_id = "front_camera_link"
            
            d_msg = self.cv_bridge.cv2_to_imgmsg(depth, "32FC1")
            d_msg.header = header
            self.pub_depth.publish(d_msg)
            
            # Create colored depth visualization for UI
            depth_colored = self.depth_to_colored(depth)
            self._draw_safe_distance_overlay(depth_colored, depth)
            depth_colored_msg = self.cv_bridge.cv2_to_compressed_imgmsg(depth_colored, "jpeg")
            depth_colored_msg.header = header
            self.pub_depth_colored.publish(depth_colored_msg)
            
            # Convert depth to PointCloud2
            pointcloud_msg = self.depth_to_pointcloud(depth, header)
            self.pub_pointcloud.publish(pointcloud_msg)
            
        except Exception as e:
            self.get_logger().error(f"Error in callback: {e}", exc_info=True)

    def safe_distance_meters(self, depth_image):
        """Minimum valid depth in lower-center region (path in front of robot). Returns meters or nan."""
        height, width = depth_image.shape
        # Lower half, center 50% of width
        row_start = height // 2
        col_start = width // 4
        col_end = 3 * width // 4
        region = depth_image[row_start:, col_start:col_end]
        valid = np.isfinite(region) & (region > 0.0)
        if not np.any(valid):
            return np.nan
        return float(np.nanmin(np.where(valid, region, np.nan)))

    def _draw_safe_distance_overlay(self, depth_colored, depth_image):
        """Draw 'X.X ft clear' (or inches if < 1 ft) on the colored depth image."""
        meters = self.safe_distance_meters(depth_image)
        if np.isnan(meters) or meters <= 0:
            text = "— ft clear"
        elif meters < 0.3048:  # < 1 ft
            inches = meters * 39.37
            text = f"{inches:.0f} in clear"
        else:
            feet = meters * 3.28084
            text = f"{feet:.1f} ft clear"
        h, w = depth_colored.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = max(0.5, min(1.2, w / 500))
        thick = max(1, int(round(scale * 2)))
        (text_w, text_h), baseline = cv2.getTextSize(text, font, scale, thick)
        # Bottom center, with padding
        x = (w - text_w) // 2
        y = h - 16
        # Outline (black) then fill (white)
        for dx, dy in [(-1, -1), (-1, 1), (1, -1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]:
            cv2.putText(depth_colored, text, (x + dx, y + dy), font, scale, (0, 0, 0), thick)
        cv2.putText(depth_colored, text, (x, y), font, scale, (255, 255, 255), thick)

    def depth_to_colored(self, depth_image):
        """Convert depth image to colored visualization (jet colormap)."""
        # Normalize depth to 0-255 range for visualization
        depth_normalized = depth_image.copy()
        # Clip to reasonable range (0-10 meters)
        depth_normalized = np.clip(depth_normalized, 0, 10.0)
        depth_normalized = (depth_normalized / 10.0 * 255).astype(np.uint8)
        
        # Apply jet colormap
        depth_colored = cv2.applyColorMap(depth_normalized, cv2.COLORMAP_JET)
        return depth_colored
    
    def depth_to_pointcloud(self, depth_image, header):
        """Convert depth image to PointCloud2 message."""
        height, width = depth_image.shape
        
        # Create PointCloud2 message
        pointcloud = PointCloud2()
        pointcloud.header = header
        pointcloud.height = height
        pointcloud.width = width
        pointcloud.is_dense = False
        pointcloud.is_bigendian = False
        
        # Set fields: x, y, z (all float32)
        pointcloud.fields = [
            PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
            PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
            PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        ]
        
        pointcloud.point_step = 12  # 3 floats * 4 bytes
        pointcloud.row_step = width * pointcloud.point_step
        
        # Generate point cloud data
        points = []
        for v in range(height):
            for u in range(width):
                depth = depth_image[v, u]
                
                # Filter invalid depth values
                if np.isnan(depth) or np.isinf(depth) or depth <= 0.0:
                    x = y = z = float('nan')
                else:
                    # Convert pixel coordinates to 3D points
                    x = (u - self.cx) * depth / self.fx
                    y = (v - self.cy) * depth / self.fy
                    z = depth
                
                # Pack as 3 floats (12 bytes)
                points.append(struct.pack('fff', x, y, z))
        
        pointcloud.data = b''.join(points)
        return pointcloud


def main(args=None):
    rclpy.init(args=args)
    node = DepthAnything3Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
