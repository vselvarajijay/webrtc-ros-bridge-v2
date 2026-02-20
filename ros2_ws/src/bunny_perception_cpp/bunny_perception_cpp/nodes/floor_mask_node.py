#!/usr/bin/env python3
"""
Floor mask node: subscribes to front camera, computes RGB-based floor mask using HSV color clustering,
publishes binary mask as CompressedImage (mono8 encoding).

Topic: /perception/floor_mask (CompressedImage, mono8)
- 0 = not floor (obstacle/structure)
- 255 = floor

Used by optical_flow_node to weight flow computation, preventing floor pixels from dominating navigation.
"""

import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np


CAMERA_TOPIC = "/camera/front/compressed"
FLOOR_MASK_TOPIC = "/perception/floor_mask"
FLOOR_MASK_IMAGE_TOPIC = "/perception/floor_mask/image/compressed"

# Mask resolution (matches optical flow resolution)
DEFAULT_MASK_WIDTH = 320
DEFAULT_MASK_HEIGHT = 240

# Floor seed region parameters
DEFAULT_SEED_BOTTOM_FRACTION = 0.3  # Bottom 30% of image
DEFAULT_SEED_CENTER_WIDTH_FRACTION = 0.5  # Center 50% width

# HSV similarity threshold (lower = stricter matching)
# Threshold is in standard deviation units (sigma), typically 1.5-4.0
DEFAULT_HSV_SIMILARITY_THRESHOLD = 2.5

# Morphological operations
DEFAULT_ERODE_KERNEL_SIZE = 3
DEFAULT_DILATE_KERNEL_SIZE = 5
DEFAULT_ENABLE_MORPHOLOGY = True


class FloorMaskNode(Node):
    def __init__(self):
        super().__init__("floor_mask_node")
        self._lock = threading.Lock()
        self._latest_mask = None
        self._mask_stamp = None
        self._latest_image = None  # Store original image for visualization

        # Parameters
        self.declare_parameter("mask_width", DEFAULT_MASK_WIDTH)
        self.declare_parameter("mask_height", DEFAULT_MASK_HEIGHT)
        self.declare_parameter("seed_bottom_fraction", DEFAULT_SEED_BOTTOM_FRACTION)
        self.declare_parameter("seed_center_width_fraction", DEFAULT_SEED_CENTER_WIDTH_FRACTION)
        self.declare_parameter("hsv_similarity_threshold", DEFAULT_HSV_SIMILARITY_THRESHOLD)
        self.declare_parameter("erode_kernel_size", DEFAULT_ERODE_KERNEL_SIZE)
        self.declare_parameter("dilate_kernel_size", DEFAULT_DILATE_KERNEL_SIZE)
        self.declare_parameter("enable_morphology", DEFAULT_ENABLE_MORPHOLOGY)

        self._mask_w = self.get_parameter("mask_width").value
        self._mask_h = self.get_parameter("mask_height").value
        self._seed_bottom_frac = self.get_parameter("seed_bottom_fraction").value
        self._seed_center_width_frac = self.get_parameter("seed_center_width_fraction").value
        self._hsv_threshold = self.get_parameter("hsv_similarity_threshold").value
        self._erode_kernel = self.get_parameter("erode_kernel_size").value
        self._dilate_kernel = self.get_parameter("dilate_kernel_size").value
        self._enable_morph = self.get_parameter("enable_morphology").value

        # Ensure kernel sizes are odd
        if self._erode_kernel > 0 and self._erode_kernel % 2 == 0:
            self._erode_kernel += 1
            self.get_logger().warn("Erode kernel must be odd, adjusted to %d" % self._erode_kernel)
        if self._dilate_kernel > 0 and self._dilate_kernel % 2 == 0:
            self._dilate_kernel += 1
            self.get_logger().warn("Dilate kernel must be odd, adjusted to %d" % self._dilate_kernel)

        # Subscriber and publisher
        self.subscription = self.create_subscription(
            CompressedImage,
            CAMERA_TOPIC,
            self._image_callback,
            1,
        )
        self.pub_mask = self.create_publisher(CompressedImage, FLOOR_MASK_TOPIC, 10)
        self.pub_mask_image = self.create_publisher(CompressedImage, FLOOR_MASK_IMAGE_TOPIC, 10)

        self.get_logger().info(
            "floor_mask_node: sub %s, pub %s, %s (mask %dx%d, seed_bottom=%.2f, seed_width=%.2f, hsv_thresh=%.1f, morph=%s)"
            % (CAMERA_TOPIC, FLOOR_MASK_TOPIC, FLOOR_MASK_IMAGE_TOPIC, self._mask_w, self._mask_h,
               self._seed_bottom_frac, self._seed_center_width_frac, self._hsv_threshold,
               "enabled" if self._enable_morph else "disabled")
        )

    def _compute_floor_mask(self, img: np.ndarray) -> np.ndarray:
        """
        Compute floor mask from RGB image using HSV color clustering.
        
        Args:
            img: BGR image (h, w, 3)
            
        Returns:
            Binary mask (h, w) where 255 = floor, 0 = not floor
        """
        h, w = img.shape[:2]
        
        # Resize to mask resolution
        if (w, h) != (self._mask_w, self._mask_h):
            img = cv2.resize(img, (self._mask_w, self._mask_h), interpolation=cv2.INTER_AREA)
            h, w = self._mask_h, self._mask_w
        
        # Convert to HSV
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        
        # Extract seed region (bottom-center patch)
        seed_bottom_start = int(h * (1.0 - self._seed_bottom_frac))
        seed_width_start = int(w * (0.5 - self._seed_center_width_frac / 2.0))
        seed_width_end = int(w * (0.5 + self._seed_center_width_frac / 2.0))
        
        seed_region = hsv[seed_bottom_start:, seed_width_start:seed_width_end, :]
        
        if seed_region.size == 0:
            # Fallback: use entire bottom region
            seed_region = hsv[seed_bottom_start:, :, :]
        
        # Compute HSV mean and std from seed region
        seed_flat = seed_region.reshape(-1, 3)
        hsv_mean = np.mean(seed_flat, axis=0)
        hsv_std = np.std(seed_flat, axis=0)
        
        # Use adaptive threshold: mean ± (threshold * std)
        # For H channel (hue), handle circularity (0-180 wraps around)
        h_mean = hsv_mean[0]
        h_std = max(hsv_std[0], 3.0)   # Minimum std to handle uniform colors
        s_std = max(hsv_std[1], 5.0)   # Minimum std for saturation
        v_std = max(hsv_std[2], 5.0)   # Minimum std for value
        
        # Compute distance from mean for each pixel
        h_diff = np.abs(hsv[:, :, 0].astype(np.float32) - h_mean)
        # Handle hue circularity
        h_diff = np.minimum(h_diff, 180.0 - h_diff)
        h_dist = h_diff / (h_std + 1e-6)
        
        # S and V channels use simple distance
        s_dist = np.abs(hsv[:, :, 1].astype(np.float32) - hsv_mean[1]) / (s_std + 1e-6)
        v_dist = np.abs(hsv[:, :, 2].astype(np.float32) - hsv_mean[2]) / (v_std + 1e-6)
        
        # Combined distance (equal weighting, threshold in sigma units)
        # Threshold of 2.5 ≈ within 2.5σ on each channel
        combined_dist = np.sqrt(h_dist**2 + s_dist**2 + v_dist**2)
        
        # Threshold: pixels within threshold distance are floor
        mask = (combined_dist <= self._hsv_threshold).astype(np.uint8) * 255
        
        # Morphological operations to clean up mask
        if self._enable_morph:
            # Erode to remove small noise
            if self._erode_kernel > 0:
                kernel_erode = np.ones((self._erode_kernel, self._erode_kernel), np.uint8)
                mask = cv2.erode(mask, kernel_erode, iterations=1)
            
            # Dilate to fill small holes
            if self._dilate_kernel > 0:
                kernel_dilate = np.ones((self._dilate_kernel, self._dilate_kernel), np.uint8)
                mask = cv2.dilate(mask, kernel_dilate, iterations=1)
        
        return mask

    def _create_visualization(self, img: np.ndarray, mask: np.ndarray, stamp) -> None:
        """
        Create visualization by overlaying mask on original image.
        
        Args:
            img: Original BGR image (h, w, 3)
            mask: Binary mask (h_mask, w_mask) where 255 = floor, 0 = not floor
            stamp: ROS2 timestamp for the message header
        """
        # Get original image dimensions
        orig_h, orig_w = img.shape[:2]
        mask_h, mask_w = mask.shape[:2]
        
        # Resize mask to match original image if needed
        if (mask_w, mask_h) != (orig_w, orig_h):
            mask_resized = cv2.resize(mask, (orig_w, orig_h), interpolation=cv2.INTER_NEAREST)
        else:
            mask_resized = mask
        
        # Create colored overlay: green for floor pixels
        overlay = img.copy()
        # Convert mask to 3-channel for blending
        mask_3ch = cv2.cvtColor(mask_resized, cv2.COLOR_GRAY2BGR)
        # Create green overlay (BGR: [0, 255, 0])
        green_overlay = np.zeros_like(img)
        green_overlay[:, :, 1] = 255  # Green channel
        
        # Blend: where mask is 255 (floor), use green overlay with 30% opacity
        mask_normalized = mask_3ch.astype(np.float32) / 255.0
        alpha = 0.3  # 30% opacity
        overlay = (img.astype(np.float32) * (1.0 - alpha * mask_normalized) + 
                   green_overlay.astype(np.float32) * (alpha * mask_normalized)).astype(np.uint8)
        
        # Encode as JPEG
        _, encoded = cv2.imencode(".jpg", overlay, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if encoded is None:
            self.get_logger().warn("Failed to encode visualization")
            return
        
        # Publish visualization
        viz_msg = CompressedImage()
        viz_msg.header.stamp = stamp
        viz_msg.format = "jpeg"
        viz_msg.data = np.array(encoded).tobytes()
        self.pub_mask_image.publish(viz_msg)

    def _image_callback(self, msg: CompressedImage) -> None:
        """Process incoming camera image and publish floor mask."""
        try:
            arr = np.frombuffer(msg.data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return
        except Exception as e:
            self.get_logger().warn("Decode image failed: %s" % e)
            return

        # Store original image for visualization (thread-safe)
        with self._lock:
            self._latest_image = img.copy()
            self._mask_stamp = msg.header.stamp

        # Compute floor mask (this may resize the image internally)
        # We need the mask at mask resolution, but visualization needs original image
        mask = self._compute_floor_mask(img.copy())
        
        # Store latest mask (for potential future use)
        with self._lock:
            self._latest_mask = mask.copy()
        
        # Encode mask as PNG (lossless, required for binary masks)
        # JPEG compression corrupts binary masks with intermediate gray values
        _, encoded = cv2.imencode(".png", mask)
        if encoded is None:
            self.get_logger().warn("Failed to encode mask")
            return
        
        # Publish mask
        mask_msg = CompressedImage()
        mask_msg.header = msg.header
        mask_msg.format = "png"
        mask_msg.data = np.array(encoded).tobytes()
        self.pub_mask.publish(mask_msg)
        
        # Create and publish visualization
        try:
            self._create_visualization(img, mask, msg.header.stamp)
        except Exception as e:
            self.get_logger().warn("Failed to create visualization: %s" % e)


def main(args=None):
    rclpy.init(args=args)
    node = FloorMaskNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
