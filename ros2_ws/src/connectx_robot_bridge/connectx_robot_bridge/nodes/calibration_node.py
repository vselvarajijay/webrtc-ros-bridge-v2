"""
Camera calibration node: subscribes to /camera/front/compressed, exposes HTTP API
for capture/run, and saves calibration YAML under repo root robot/.
Captures at full resolution via SDK /v2/front_full when available.
"""

import asyncio
import base64
import json
import os
import threading
import urllib.error
import urllib.request

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage

from connectx_robot_bridge.core.constants import (
    CAMERA_FRONT_COMPRESSED_TOPIC,
    SDK_FRONT_FULL_ENDPOINT,
)

# Checkerboard defaults (inner corners)
DEFAULT_BOARD_COLS = int(os.environ.get("CALIBRATION_BOARD_COLS", "8"))
DEFAULT_BOARD_ROWS = int(os.environ.get("CALIBRATION_BOARD_ROWS", "5"))
DEFAULT_SQUARE_SIZE_M = float(os.environ.get("CALIBRATION_SQUARE_SIZE_M", "0.025"))

# HTTP port for calibration API
DEFAULT_CALIBRATION_PORT = int(os.environ.get("CALIBRATION_HTTP_PORT", "8766"))


class CalibrationNode(Node):
    def __init__(self):
        super().__init__("calibration_node")
        self.declare_parameter("board_cols", DEFAULT_BOARD_COLS)
        self.declare_parameter("board_rows", DEFAULT_BOARD_ROWS)
        self.declare_parameter("square_size_m", DEFAULT_SQUARE_SIZE_M)
        self._board_cols = self.get_parameter("board_cols").value
        self._board_rows = self.get_parameter("board_rows").value
        self._square_size_m = self.get_parameter("square_size_m").value

        self._lock = threading.Lock()
        self._latest_frame_bytes = None
        self._collected_frames = []
        self._target_count = 25
        self._state = "idle"  # idle, collecting, ready, calibrating, done

        self._sub = self.create_subscription(
            CompressedImage,
            CAMERA_FRONT_COMPRESSED_TOPIC,
            self._camera_callback,
            10,
        )
        self.get_logger().info(
            f"Subscribed to {CAMERA_FRONT_COMPRESSED_TOPIC}; "
            f"HTTP API on port {DEFAULT_CALIBRATION_PORT}"
        )

    def _camera_callback(self, msg: CompressedImage) -> None:
        with self._lock:
            self._latest_frame_bytes = bytes(msg.data)

    def _get_latest_frame_bgr(self):
        """Return latest frame as BGR numpy array or None."""
        with self._lock:
            raw = self._latest_frame_bytes
        if raw is None:
            return None
        buf = np.frombuffer(raw, dtype=np.uint8)
        img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
        return img

    def _fetch_full_res_frame_bgr(self):
        """Fetch one frame at viewport (full) resolution from SDK for calibration. Returns BGR array or None."""
        try:
            with urllib.request.urlopen(SDK_FRONT_FULL_ENDPOINT, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            b64 = data.get("front_frame")
            if not b64:
                return None
            raw = base64.b64decode(b64)
            buf = np.frombuffer(raw, dtype=np.uint8)
            img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
            return img
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
            self.get_logger().debug("Full-res frame fetch failed: %s", e)
            return None

    def _find_checkerboard(self, img):
        """Find checkerboard corners. Returns (object_points, image_points) or None.

        Tries multiple preprocessing strategies to handle low-contrast grey boards.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        board_size = (self._board_cols, self._board_rows)
        base_flags = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

        def try_detect(g, flags):
            ret, corners = cv2.findChessboardCorners(g, board_size, flags)
            return (ret, corners) if ret and corners is not None else (False, None)

        # Mild CLAHE — general contrast boost
        clahe_mild = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        # Strong CLAHE with smaller tiles — better for locally uneven lighting
        clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4)).apply(gray)
        # Stretch to full 0-255 range then Otsu threshold — best for grey-on-white boards
        normalized = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        _, binary = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        candidates = [
            (clahe_mild,   base_flags),
            (clahe_strong, base_flags),
            (normalized,   base_flags),
            # Binary image: skip adaptive thresh since we've already binarized
            (binary,       cv2.CALIB_CB_NORMALIZE_IMAGE),
            (binary,       base_flags),
            (gray,         base_flags),
        ]

        corners = None
        for img_candidate, flags in candidates:
            ret, corners = try_detect(img_candidate, flags)
            if ret:
                self.get_logger().debug("Checkerboard found with candidate index %d", candidates.index((img_candidate, flags)))
                break

        if corners is None:
            return None

        # Always refine subpixel on original gray for best accuracy
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
        corners_refined = cv2.cornerSubPix(gray, corners, (5, 5), (-1, -1), criteria)

        objp = np.zeros((self._board_cols * self._board_rows, 3), np.float32)
        objp[:, :2] = np.mgrid[
            0 : self._board_cols, 0 : self._board_rows
        ].T.reshape(-1, 2)
        objp *= self._square_size_m
        return (objp, corners_refined)

    def start_session(self, target_count: int) -> None:
        with self._lock:
            self._collected_frames = []
            self._target_count = max(1, min(100, target_count))
            self._state = "collecting"

    def capture(self) -> tuple[bool, str]:
        """Capture current frame at full (viewport) resolution. Returns (success, message)."""
        img = self._fetch_full_res_frame_bgr()
        if img is None:
            return False, (
                "Full-resolution frame unavailable. "
                "Ensure the SDK is running and /v2/front_full is reachable."
            )

        with self._lock:
            if self._state not in ("collecting", "ready"):
                if self._state == "idle":
                    # Auto-start a session so first capture works without explicit /calibration/start
                    self._collected_frames = []
                    self._state = "collecting"
                else:
                    return False, (
                        f"Cannot capture in state '{self._state}'. "
                        "Call POST /calibration/start first, or wait for calibration to finish."
                    )

        board = self._find_checkerboard(img)
        if board is None:
            h, w = img.shape[:2]
            return False, (
                f"Checkerboard not detected (full-res image {w}×{h}); "
                "position pattern in view, check lighting and board size (board_cols/board_rows)."
            )
        objp, img_points = board

        with self._lock:
            self._collected_frames.append((img, objp, img_points))
            n = len(self._collected_frames)
            self._state = "ready" if n >= self._target_count else "collecting"
        return True, f"Captured ({n}/{self._target_count})"

    def get_status(self) -> dict:
        with self._lock:
            captured = len(self._collected_frames)
            return {
                "captured": captured,
                "target_count": self._target_count,
                "state": self._state,
            }

    def run_calibration(self) -> tuple[bool, str, str | None]:
        """Run OpenCV calibration and return YAML content (no file write).
        Returns (success, message, yaml_string or None).
        """
        with self._lock:
            if self._state not in ("ready", "collecting"):
                return False, f"Invalid state: {self._state}", None
            frames = list(self._collected_frames)
            target = self._target_count

        if len(frames) < target:
            return False, f"Need at least {target} images; have {len(frames)}", None

        with self._lock:
            self._state = "calibrating"

        try:
            object_points = []
            image_points = []
            image_size = None
            for img, objp, img_pts in frames:
                if image_size is None:
                    image_size = (img.shape[1], img.shape[0])
                object_points.append(objp)
                image_points.append(img_pts)

            rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
                object_points,
                image_points,
                image_size,
                None,
                None,
            )
            # rms is reprojection error (float), not a bool — lower is better
            if camera_matrix is None:
                return False, "Calibration failed: no camera matrix returned", None

            self.get_logger().info(f"Calibration RMS reprojection error: {rms:.4f} px")

            yaml_str = self._calibration_to_yaml(
                image_size[0],
                image_size[1],
                camera_matrix,
                dist_coeffs,
                rms,
            )
            with self._lock:
                self._state = "done"
            return True, f"Calibration complete (RMS={rms:.4f}px)", yaml_str

        except Exception as e:
            with self._lock:
                self._state = "ready"
            return False, str(e), None

    def _calibration_to_yaml(
        self,
        width: int,
        height: int,
        camera_matrix: np.ndarray,
        dist_coeffs: np.ndarray,
        rms: float = 0.0,
    ) -> str:
        import yaml

        data = {
            "image_width": width,
            "image_height": height,
            "rms_reprojection_error": round(float(rms), 6),
            "camera_matrix": {
                "rows": int(camera_matrix.shape[0]),
                "cols": int(camera_matrix.shape[1]),
                "data": camera_matrix.flatten().tolist(),
            },
            "distortion_coefficients": {
                "rows": int(dist_coeffs.shape[0]),
                "cols": int(dist_coeffs.shape[1]),
                "data": dist_coeffs.flatten().tolist(),
            },
        }
        return yaml.safe_dump(data, default_flow_style=False)


# Global node reference for HTTP handlers
_calibration_node: CalibrationNode = None


def _run_http_server(port: int) -> None:
    from aiohttp import web

    async def handle_start(request: web.Request) -> web.Response:
        try:
            body = await request.json()
            target_count = int(body.get("target_count", 25))
        except (ValueError, TypeError):
            target_count = 25
        _calibration_node.start_session(target_count)
        return web.json_response({"status": "ok"})

    async def handle_capture(request: web.Request) -> web.Response:
        ok, msg = _calibration_node.capture()
        if ok:
            return web.json_response({"status": "ok", "message": msg})
        return web.json_response({"status": "error", "message": msg}, status=400)

    async def handle_status(request: web.Request) -> web.Response:
        return web.json_response(_calibration_node.get_status())

    async def handle_run(request: web.Request) -> web.Response:
        ok, msg, yaml_content = _calibration_node.run_calibration()
        if ok:
            return web.json_response({
                "status": "ok",
                "message": msg,
                "calibration_yaml": yaml_content or "",
            })
        return web.json_response({"status": "error", "message": msg}, status=400)

    async def handle_debug(request: web.Request) -> web.Response:
        """Returns an annotated JPEG showing detection results for all preprocessing strategies."""
        img = _calibration_node._fetch_full_res_frame_bgr()
        source = "full_res"
        if img is None:
            img = _calibration_node._get_latest_frame_bgr()
            source = "compressed_topic"
        if img is None:
            return web.Response(status=503, text="No frame available")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        board_size = (_calibration_node._board_cols, _calibration_node._board_rows)

        clahe_mild   = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
        clahe_strong = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4)).apply(gray)
        normalized   = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        _, binary    = cv2.threshold(normalized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        base_flags   = cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE

        candidates = [
            ("clahe_mild",   clahe_mild,   base_flags),
            ("clahe_strong", clahe_strong, base_flags),
            ("normalized",   normalized,   base_flags),
            ("binary",       binary,       cv2.CALIB_CB_NORMALIZE_IMAGE),
            ("gray_raw",     gray,         base_flags),
        ]

        debug_img = img.copy()
        results = {}
        drawn = False

        for name, g, flags in candidates:
            ret, corners = cv2.findChessboardCorners(g, board_size, flags)
            results[name] = bool(ret)
            if ret and corners is not None and not drawn:
                cv2.drawChessboardCorners(debug_img, board_size, corners, ret)
                drawn = True

        h, w = img.shape[:2]
        cv2.putText(debug_img, f"src={source}  size={w}x{h}  board={board_size}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        for i, (name, detected) in enumerate(results.items()):
            color = (0, 255, 0) if detected else (0, 0, 255)
            cv2.putText(debug_img, f"{name}: {'OK' if detected else 'FAIL'}",
                        (10, 65 + i * 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)

        _, buf = cv2.imencode(".jpg", debug_img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        return web.Response(
            body=buf.tobytes(),
            content_type="image/jpeg",
            headers={
                "X-Detection-Results": json.dumps(results),
                "X-Source": source,
                "X-Image-Size": f"{w}x{h}",
            },
        )

    async def handle_reset(request: web.Request) -> web.Response:
        _calibration_node.start_session(_calibration_node._target_count)
        return web.json_response({"status": "ok", "message": "Session reset"})

    app = web.Application()
    app.router.add_post("/calibration/start",   handle_start)
    app.router.add_post("/calibration/capture", handle_capture)
    app.router.add_get( "/calibration/status",  handle_status)
    app.router.add_post("/calibration/run",     handle_run)
    app.router.add_get( "/calibration/debug",   handle_debug)
    app.router.add_post("/calibration/reset",   handle_reset)

    async def run_server():
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        while True:
            await asyncio.sleep(3600)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_server())


def main(args=None):
    global _calibration_node
    rclpy.init(args=args)
    _calibration_node = CalibrationNode()
    port = DEFAULT_CALIBRATION_PORT
    http_thread = threading.Thread(target=_run_http_server, args=(port,), daemon=True)
    http_thread.start()
    try:
        rclpy.spin(_calibration_node)
    finally:
        _calibration_node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()