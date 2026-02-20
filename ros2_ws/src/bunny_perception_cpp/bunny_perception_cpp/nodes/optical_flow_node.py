#!/usr/bin/env python3
"""
Optical flow node: subscribes to front camera, computes dense optical flow,
publishes mean flow per sector (left, center, right) with horizontal bands (top, mid) as Float32MultiArray.

Topic: /optical_flow with layout:
- Legacy (9 elements): [vx_left, vy_left, mag_left, vx_center, vy_center, mag_center, vx_right, vy_right, mag_right]
- Enhanced (18 elements): [vx_left_top, vy_left_top, mag_left_top, vx_center_top, vy_center_top, mag_center_top, vx_right_top, vy_right_top, mag_right_top,
                           vx_left_mid, vy_left_mid, mag_left_mid, vx_center_mid, vy_center_mid, mag_center_mid, vx_right_mid, vy_right_mid, mag_right_mid]
- flow[:,:,0] = dx (horizontal; positive = motion to the right in image).
- flow[:,:,1] = dy (vertical; positive = downward in image).
Used by wander_node for flow-based steering. Values are in pixels/second (temporally normalized).
Bottom region is ignored to reduce floor noise.
"""

import threading
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Float32MultiArray
import cv2
import numpy as np


# Flow computation size (higher = better for stairs/pillars; more CPU)
DEFAULT_FLOW_WIDTH = 320
DEFAULT_FLOW_HEIGHT = 240
OPTICAL_FLOW_TOPIC = "/optical_flow"
OPTICAL_FLOW_IMAGE_TOPIC = "/optical_flow/image/compressed"
CAMERA_TOPIC = "/camera/front/compressed"
FLOOR_MASK_TOPIC = "/perception/floor_mask"

# Temporal: reject dt > this (dropped frames -> meaningless flow)
DEFAULT_MAX_DT_S = 0.5
# Values below this (pixels/s after norm) are treated as zero to reduce noise reaction.
# Motor vibration + compression can produce 2–4 px/s at rest; raise to reduce flicker.
# Lowered from 3.0 to 1.0 to detect slow-speed expansion signals indoors.
DEFAULT_FLOW_NOISE_FLOOR = 1.0
# Cap per-component magnitude (pixels/s) to avoid huge spikes from bad frames
DEFAULT_FLOW_MAX_MAGNITUDE = 25.0
# EMA alpha for temporal smoothing (0=heavy, 1=none). Lower = less flicker; 0.1–0.15 typical.
DEFAULT_FLOW_EMA_ALPHA = 0.12

# Display size for published flow image (optional upscale for UI)
DEFAULT_VIZ_WIDTH = 320
DEFAULT_VIZ_HEIGHT = 240

# Gaussian blur kernel size for preprocessing (odd number, 0 = disabled)
DEFAULT_GAUSSIAN_BLUR_KERNEL_SIZE = 5
# Middle fraction of image to use (0.0-1.0); use middle N% of frame, ignore top and bottom
# For low camera (4 inches): use upper 20% (10%-30%) to exclude floor-dominated flow and glare reflections
# At 4 inches, bottom 70% includes reflected geometry - use only upper portion with structural geometry
# Widened to 0.50 to use much more of the frame for mid band (better coverage)
DEFAULT_MIDDLE_START_FRACTION = 0.10  # Start of middle region (ignore top 10%)
DEFAULT_MIDDLE_END_FRACTION = 0.50  # Increased from 0.30 - use much more of frame for mid band
# Top band fraction (0.0-1.0) of the usable region; top band is 0 to this fraction of usable region
# Note: Top band is computed but ignored for navigation - only mid band is used
# Adjusted: top band = 10%-28%, mid band = 28%-50%
DEFAULT_TOP_BAND_FRACTION = 0.4  # Reduced from 0.5 - top band = 10%-28%, mid band = 28%-50%
# Enable flow divergence computation for TTC estimation (adds overhead)
# Divergence (expansion) is more robust to glare than magnitude for obstacle detection
DEFAULT_ENABLE_FLOW_DIVERGENCE = True
# Use enhanced 18-element format (backward compatible if False, uses 9-element legacy format)
DEFAULT_USE_ENHANCED_FORMAT = True
# Floor mask parameters
DEFAULT_USE_FLOOR_MASK = False  # Disabled: floor flow is needed for navigation, not masked out
DEFAULT_FLOOR_MASK_TIMEOUT_S = 0.5
DEFAULT_FLOOR_MASK_WEIGHT = 0.05  # Weight for floor pixels (0.05=slight negative bias, avoids sharp edges in weighted averaging)


# Arrow grid: step in pixels (smaller = more arrows)
ARROW_GRID_STEP = 8
# Scale factor so arrow length in pixels is visible (flow is in px/s)
ARROW_SCALE = 2.0
ARROW_COLOR = (0, 255, 100)  # BGR green
ARROW_THICKNESS = 1
ARROW_TIP_LENGTH = 0.25


def flow_to_arrows_image(flow: np.ndarray, viz_w: int, viz_h: int) -> np.ndarray:
    """Draw a grid of vector arrows from flow (h, w, 2). Returns BGR image."""
    h, w = flow.shape[:2]
    out = np.zeros((h, w, 3), dtype=np.uint8)
    out[:] = (40, 40, 40)  # dark gray background

    for y in range(ARROW_GRID_STEP // 2, h, ARROW_GRID_STEP):
        for x in range(ARROW_GRID_STEP // 2, w, ARROW_GRID_STEP):
            vx = float(flow[y, x, 0])
            vy = float(flow[y, x, 1])
            mag = np.sqrt(vx * vx + vy * vy)
            if mag < 0.1:
                continue
            x2 = x + vx * ARROW_SCALE
            y2 = y + vy * ARROW_SCALE
            pt1 = (int(round(x)), int(round(y)))
            pt2 = (int(round(x2)), int(round(y2)))
            cv2.arrowedLine(
                out,
                pt1,
                pt2,
                ARROW_COLOR,
                ARROW_THICKNESS,
                tipLength=ARROW_TIP_LENGTH,
            )
    if (w, h) != (viz_w, viz_h):
        out = cv2.resize(out, (viz_w, viz_h), interpolation=cv2.INTER_LINEAR)
    return out


class OpticalFlowNode(Node):
    def __init__(self):
        super().__init__("optical_flow_node")
        self._prev_gray = None
        self._prev_stamp = None  # seconds, for dt
        self._flow_ema = None  # 9 or 18-element array for temporal smoothing
        self._lock = threading.Lock()
        # Floor mask state
        self._latest_mask = None  # Latest floor mask (h, w) uint8, 0-255
        self._mask_stamp = None  # Timestamp of latest mask

        self.declare_parameter("flow_width", DEFAULT_FLOW_WIDTH)
        self.declare_parameter("flow_height", DEFAULT_FLOW_HEIGHT)
        self.declare_parameter("max_dt_s", DEFAULT_MAX_DT_S)
        self.declare_parameter("flow_noise_floor", DEFAULT_FLOW_NOISE_FLOOR)
        self.declare_parameter("flow_max_magnitude", DEFAULT_FLOW_MAX_MAGNITUDE)
        self.declare_parameter("flow_ema_alpha", DEFAULT_FLOW_EMA_ALPHA)
        self.declare_parameter("viz_width", DEFAULT_VIZ_WIDTH)
        self.declare_parameter("viz_height", DEFAULT_VIZ_HEIGHT)
        self.declare_parameter("gaussian_blur_kernel_size", DEFAULT_GAUSSIAN_BLUR_KERNEL_SIZE)
        self.declare_parameter("middle_start_fraction", DEFAULT_MIDDLE_START_FRACTION)
        self.declare_parameter("middle_end_fraction", DEFAULT_MIDDLE_END_FRACTION)
        self.declare_parameter("top_band_fraction", DEFAULT_TOP_BAND_FRACTION)
        self.declare_parameter("enable_flow_divergence", DEFAULT_ENABLE_FLOW_DIVERGENCE)
        self.declare_parameter("use_enhanced_format", DEFAULT_USE_ENHANCED_FORMAT)
        self.declare_parameter("use_floor_mask", DEFAULT_USE_FLOOR_MASK)
        self.declare_parameter("floor_mask_timeout_s", DEFAULT_FLOOR_MASK_TIMEOUT_S)
        self.declare_parameter("floor_mask_weight", DEFAULT_FLOOR_MASK_WEIGHT)

        self._flow_w = self.get_parameter("flow_width").value
        self._flow_h = self.get_parameter("flow_height").value
        self._max_dt = self.get_parameter("max_dt_s").value
        self._noise_floor = self.get_parameter("flow_noise_floor").value
        self._flow_max = self.get_parameter("flow_max_magnitude").value
        self._ema_alpha = self.get_parameter("flow_ema_alpha").value
        self._viz_w = self.get_parameter("viz_width").value
        self._viz_h = self.get_parameter("viz_height").value
        self._blur_kernel = self.get_parameter("gaussian_blur_kernel_size").value
        self._middle_start = self.get_parameter("middle_start_fraction").value
        self._middle_end = self.get_parameter("middle_end_fraction").value
        self._top_band_frac = self.get_parameter("top_band_fraction").value
        self._enable_divergence = self.get_parameter("enable_flow_divergence").value
        self._use_enhanced = self.get_parameter("use_enhanced_format").value
        self._use_floor_mask = self.get_parameter("use_floor_mask").value
        self._floor_mask_timeout = self.get_parameter("floor_mask_timeout_s").value
        self._floor_mask_weight = self.get_parameter("floor_mask_weight").value
        
        # Ensure blur kernel is odd and valid
        if self._blur_kernel > 0:
            if self._blur_kernel % 2 == 0:
                self._blur_kernel += 1
                self.get_logger().warn("Blur kernel must be odd, adjusted to %d" % self._blur_kernel)

        self.subscription = self.create_subscription(
            CompressedImage,
            CAMERA_TOPIC,
            self._image_callback,
            1,
        )
        # Floor mask subscription (optional)
        if self._use_floor_mask:
            self.mask_subscription = self.create_subscription(
                CompressedImage,
                FLOOR_MASK_TOPIC,
                self._mask_callback,
                1,
            )
        self.pub_flow = self.create_publisher(Float32MultiArray, OPTICAL_FLOW_TOPIC, 10)
        self.pub_flow_image = self.create_publisher(CompressedImage, OPTICAL_FLOW_IMAGE_TOPIC, 10)

        format_str = "enhanced (18)" if self._use_enhanced else "legacy (9)"
        blur_str = "blur=%d" % self._blur_kernel if self._blur_kernel > 0 else "no blur"
        mask_str = "mask=%s" % FLOOR_MASK_TOPIC if self._use_floor_mask else "no mask"
        self.get_logger().info(
            "optical_flow_node: sub %s, pub %s (flow %dx%d, format=%s, %s, %s, middle=%.2f-%.2f, top_band=%.2f, max_dt=%.2fs, noise_floor=%.2f, ema_alpha=%.2f)"
            % (CAMERA_TOPIC, OPTICAL_FLOW_TOPIC, self._flow_w, self._flow_h, format_str, blur_str, mask_str,
               self._middle_start, self._middle_end, self._top_band_frac, self._max_dt, self._noise_floor, self._ema_alpha)
        )

    def _mask_callback(self, msg: CompressedImage) -> None:
        """Store latest floor mask."""
        try:
            arr = np.frombuffer(msg.data, np.uint8)
            mask = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            if mask is None:
                return
        except Exception as e:
            self.get_logger().warn("Decode mask failed: %s" % e)
            return
        
        with self._lock:
            self._latest_mask = mask.copy()
            self._mask_stamp = msg.header.stamp

    def _get_floor_mask(self, flow_shape: tuple) -> np.ndarray | None:
        """
        Get floor mask resized to match flow resolution.
        
        Args:
            flow_shape: (height, width) of flow array
            
        Returns:
            Normalized mask (0-1) where 1.0 = floor, 0.0 = not floor, or None if unavailable
        """
        if not self._use_floor_mask:
            return None
        
        with self._lock:
            mask = self._latest_mask.copy() if self._latest_mask is not None else None
            mask_stamp = self._mask_stamp
        
        if mask is None:
            return None
        
        # Check if mask is recent enough
        now_ns = self.get_clock().now().nanoseconds
        if mask_stamp is not None:
            mask_stamp_ns = mask_stamp.sec * 1e9 + mask_stamp.nanosec
            if (now_ns - mask_stamp_ns) > self._floor_mask_timeout * 1e9:
                # Mask is too old, fall back to no mask
                return None
        
        # Resize mask to match flow resolution
        h, w = flow_shape[:2]
        if mask.shape != (h, w):
            mask = cv2.resize(mask, (w, h), interpolation=cv2.INTER_LINEAR)
        
        # Normalize to 0-1 range (1.0 = floor, 0.0 = not floor)
        mask_normalized = mask.astype(np.float64) / 255.0
        
        # Apply floor weight: if weight=0, floor contributes nothing; if weight=1, full contribution
        # We want: weight = floor_mask_weight for floor, 1.0 for non-floor
        # So: final_weight = (1.0 - mask_normalized) + (mask_normalized * floor_mask_weight)
        #     = 1.0 - mask_normalized * (1.0 - floor_mask_weight)
        final_weight = 1.0 - mask_normalized * (1.0 - self._floor_mask_weight)
        
        return final_weight

    def _image_callback(self, msg: CompressedImage) -> None:
        try:
            arr = np.frombuffer(msg.data, np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                return
        except Exception as e:
            self.get_logger().warn("Decode image failed: %s" % e)
            return

        # Use message stamp if valid, else node clock (some sources don't set header.stamp)
        msg_stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        now_s = self.get_clock().now().nanoseconds * 1e-9
        stamp = msg_stamp if msg_stamp > 0 else now_s

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (self._flow_w, self._flow_h), interpolation=cv2.INTER_AREA)
        
        # Apply Gaussian blur to reduce noise and stabilize flow on textureless surfaces
        if self._blur_kernel > 0:
            gray = cv2.GaussianBlur(gray, (self._blur_kernel, self._blur_kernel), 0)

        # Copy previous frame under lock; compute flow outside lock
        with self._lock:
            prev_gray = self._prev_gray.copy() if self._prev_gray is not None else None
            prev_stamp = self._prev_stamp

        if prev_gray is None:
            with self._lock:
                self._prev_gray = gray.copy()
                self._prev_stamp = stamp
            return

        dt = stamp - prev_stamp
        if dt <= 0 or dt > self._max_dt:
            with self._lock:
                self._prev_gray = gray.copy()
                self._prev_stamp = stamp
            return

        flow = cv2.calcOpticalFlowFarneback(
            prev_gray,
            gray,
            None,
            pyr_scale=0.5,
            levels=3,
            winsize=21,
            iterations=3,
            poly_n=7,
            poly_sigma=1.5,
            flags=0,
        )
        # Copy into numpy-owned array to avoid OpenCV/NumPy ABI issues in container
        flow = np.array(flow, dtype=np.float64, copy=True)

        with self._lock:
            self._prev_gray = gray.copy()
            self._prev_stamp = stamp

        # Temporal normalization: pixels/frame -> pixels/second
        flow = flow / dt

        # Noise floor: clamp small values to zero
        flow = np.where(np.abs(flow) < self._noise_floor, 0.0, flow)

        # Cap magnitude to avoid spikes from bad/dropped frames
        flow = np.clip(flow, -self._flow_max, self._flow_max)

        h, w = flow.shape[:2]
        
        # Get floor mask (if available)
        mask_weights = self._get_floor_mask((h, w))
        
        # Add vertical attenuation: smooth falloff from bottom (suppresses glare reflections)
        # Creates smooth suppression near bottom instead of hard cutoff
        # Weight should be high at top, low at bottom (suppress bottom region)
        y_coords = np.linspace(0, 1, h)
        # Invert user's formula to get falloff from bottom: 1.0 - np.clip((y - 0.3)/0.4, 0, 1)
        # This gives: y < 0.3 -> weight = 1.0 (top), y > 0.7 -> weight = 0.0 (bottom)
        vertical_weight = 1.0 - np.clip((y_coords - 0.3) / 0.4, 0, 1)
        vertical_weight = vertical_weight[:, np.newaxis]  # Shape: (h, 1) for broadcasting
        
        # Combine floor mask with vertical attenuation
        if mask_weights is not None:
            # Multiply floor mask weight by vertical attenuation
            mask_weights = mask_weights * vertical_weight
        else:
            # Apply vertical attenuation even without floor mask
            mask_weights = vertical_weight
        
        # Add brightness-based glare suppression
        # Glare pixels are very bright (>230), low gradient, often near white
        brightness = gray.copy()
        glare_mask = (brightness > 230).astype(np.float64)  # Bright pixels
        # Suppress glare: reduce weight by 80% for glare pixels
        glare_suppression = 1.0 - glare_mask * 0.8
        glare_suppression = glare_suppression[:, :, np.newaxis]  # Shape: (h, w, 1) for broadcasting
        
        # Apply glare suppression to mask weights
        if mask_weights.ndim == 2:
            mask_weights = mask_weights[:, :, np.newaxis]  # Add channel dimension
        mask_weights = mask_weights * glare_suppression
        
        # Compute flow divergence if enabled (for TTC estimation)
        divergence = None
        if self._enable_divergence:
            # Compute divergence: ∂vx/∂x + ∂vy/∂y using Sobel operators
            vx = flow[:, :, 0]
            vy = flow[:, :, 1]
            grad_vx_x = cv2.Sobel(vx, cv2.CV_64F, 1, 0, ksize=3)
            grad_vy_y = cv2.Sobel(vy, cv2.CV_64F, 0, 1, ksize=3)
            divergence = grad_vx_x + grad_vy_y
        
        # Calculate region boundaries
        third = w // 3
        # Use middle portion of frame (e.g., middle 50%: 25% to 75%)
        middle_start_px = int(h * self._middle_start)
        middle_end_px = int(h * self._middle_end)
        usable_h = middle_end_px - middle_start_px
        
        if self._use_enhanced:
            # Enhanced format: 6 regions (3 vertical × 2 horizontal)
            # Top band: middle_start to middle_start + (usable_h * top_band_frac) - IGNORED for navigation
            # Mid band: middle_start + (usable_h * top_band_frac) to middle_end - USED for navigation
            top_band_end_px = middle_start_px + int(usable_h * self._top_band_frac)
            
            # Top band regions (computed but will be ignored in navigation)
            left_top = flow[middle_start_px:top_band_end_px, 0:third, :]
            center_top = flow[middle_start_px:top_band_end_px, third : 2 * third, :]
            right_top = flow[middle_start_px:top_band_end_px, 2 * third :, :]
            
            # Mid band regions (middle portion - THIS IS WHAT WE USE FOR NAVIGATION)
            left_mid = flow[top_band_end_px:middle_end_px, 0:third, :]
            center_mid = flow[top_band_end_px:middle_end_px, third : 2 * third, :]
            right_mid = flow[top_band_end_px:middle_end_px, 2 * third :, :]
            
            # Extract corresponding mask regions if available
            # Handle 3D mask (h, w, 1) or 2D mask (h, w)
            if mask_weights is not None:
                if mask_weights.ndim == 3:
                    mask_2d = mask_weights[:, :, 0]  # Extract single channel for indexing
                else:
                    mask_2d = mask_weights
                left_mid_mask = mask_2d[top_band_end_px:middle_end_px, 0:third]
                center_mid_mask = mask_2d[top_band_end_px:middle_end_px, third : 2 * third]
                right_mid_mask = mask_2d[top_band_end_px:middle_end_px, 2 * third :]
                left_top_mask = mask_2d[middle_start_px:top_band_end_px, 0:third]
                center_top_mask = mask_2d[middle_start_px:top_band_end_px, third : 2 * third]
                right_top_mask = mask_2d[middle_start_px:top_band_end_px, 2 * third :]
            else:
                left_mid_mask = None
                center_mid_mask = None
                right_mid_mask = None
                left_top_mask = None
                center_top_mask = None
                right_top_mask = None
            
            def mean_flow(region, region_mask=None):
                # Compute magnitude per pixel first, then average magnitudes
                # This prevents cancellation of symmetric expansion patterns
                vx_region = region[:, :, 0]
                vy_region = region[:, :, 1]
                mag_region = np.sqrt(vx_region**2 + vy_region**2)
                
                if region_mask is not None:
                    # Handle 3D mask (h, w, 1) or 2D mask (h, w)
                    if region_mask.ndim == 3:
                        weights = region_mask[:, :, 0]  # Extract single channel
                    else:
                        weights = region_mask
                    total_weight = np.sum(weights) + 1e-6  # Avoid division by zero
                    vx = float(np.sum(vx_region * weights) / total_weight)
                    vy = float(np.sum(vy_region * weights) / total_weight)
                    mag = float(np.sum(mag_region * weights) / total_weight)
                else:
                    # Fallback to simple mean (backward compatibility)
                    vx = float(np.nanmean(vx_region))
                    vy = float(np.nanmean(vy_region))
                    mag = float(np.nanmean(mag_region))
                
                return vx, vy, mag
            
            vx_left_top, vy_left_top, mag_left_top = mean_flow(left_top, left_top_mask)
            vx_center_top, vy_center_top, mag_center_top = mean_flow(center_top, center_top_mask)
            vx_right_top, vy_right_top, mag_right_top = mean_flow(right_top, right_top_mask)
            vx_left_mid, vy_left_mid, mag_left_mid = mean_flow(left_mid, left_mid_mask)
            vx_center_mid, vy_center_mid, mag_center_mid = mean_flow(center_mid, center_mid_mask)
            vx_right_mid, vy_right_mid, mag_right_mid = mean_flow(right_mid, right_mid_mask)
            
            raw = np.array(
                [vx_left_top, vy_left_top, mag_left_top, vx_center_top, vy_center_top, mag_center_top, vx_right_top, vy_right_top, mag_right_top,
                 vx_left_mid, vy_left_mid, mag_left_mid, vx_center_mid, vy_center_mid, mag_center_mid, vx_right_mid, vy_right_mid, mag_right_mid],
                dtype=np.float64,
            )
        else:
            # Legacy format: 3 regions (vertical only, using middle portion)
            left = flow[middle_start_px:middle_end_px, 0:third, :]
            center = flow[middle_start_px:middle_end_px, third : 2 * third, :]
            right = flow[middle_start_px:middle_end_px, 2 * third :, :]
            
            # Extract corresponding mask regions if available
            # Handle 3D mask (h, w, 1) or 2D mask (h, w)
            if mask_weights is not None:
                if mask_weights.ndim == 3:
                    mask_2d = mask_weights[:, :, 0]  # Extract single channel for indexing
                else:
                    mask_2d = mask_weights
                left_mask = mask_2d[middle_start_px:middle_end_px, 0:third]
                center_mask = mask_2d[middle_start_px:middle_end_px, third : 2 * third]
                right_mask = mask_2d[middle_start_px:middle_end_px, 2 * third :]
            else:
                left_mask = None
                center_mask = None
                right_mask = None
            
            def mean_flow(region, region_mask=None):
                # Compute magnitude per pixel first, then average magnitudes
                # This prevents cancellation of symmetric expansion patterns
                vx_region = region[:, :, 0]
                vy_region = region[:, :, 1]
                mag_region = np.sqrt(vx_region**2 + vy_region**2)
                
                if region_mask is not None:
                    # Handle 3D mask (h, w, 1) or 2D mask (h, w)
                    if region_mask.ndim == 3:
                        weights = region_mask[:, :, 0]  # Extract single channel
                    else:
                        weights = region_mask
                    total_weight = np.sum(weights) + 1e-6  # Avoid division by zero
                    vx = float(np.sum(vx_region * weights) / total_weight)
                    vy = float(np.sum(vy_region * weights) / total_weight)
                    mag = float(np.sum(mag_region * weights) / total_weight)
                else:
                    # Fallback to simple mean (backward compatibility)
                    vx = float(np.nanmean(vx_region))
                    vy = float(np.nanmean(vy_region))
                    mag = float(np.nanmean(mag_region))
                
                return vx, vy, mag
            
            vx_left, vy_left, mag_left = mean_flow(left, left_mask)
            vx_center, vy_center, mag_center = mean_flow(center, center_mask)
            vx_right, vy_right, mag_right = mean_flow(right, right_mask)
            
            raw = np.array(
                [vx_left, vy_left, mag_left, vx_center, vy_center, mag_center, vx_right, vy_right, mag_right],
                dtype=np.float64,
            )
        
        if self._flow_ema is None:
            self._flow_ema = raw.copy()
        else:
            # Ensure EMA array matches current format
            if len(self._flow_ema) != len(raw):
                self._flow_ema = raw.copy()
            else:
                self._flow_ema = self._ema_alpha * raw + (1.0 - self._ema_alpha) * self._flow_ema

        out = Float32MultiArray()
        out.data = self._flow_ema.tolist()
        self.pub_flow.publish(out)

        # Publish flow as grid of vector arrows for UI
        viz_bgr = flow_to_arrows_image(flow, self._viz_w, self._viz_h)
        _, jpeg = cv2.imencode(".jpg", viz_bgr)
        img_msg = CompressedImage()
        img_msg.header = msg.header
        img_msg.format = "jpeg"
        img_msg.data = np.array(jpeg).tobytes()
        self.pub_flow_image.publish(img_msg)


def main(args=None):
    rclpy.init(args=args)
    node = OpticalFlowNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
