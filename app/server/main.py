import json
import logging
import os
import time
import threading
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from .ice_servers import get_ice_servers

# Script extensions that must be served as application/javascript for module scripts
_JS_MIME_EXTENSIONS = frozenset({".js", ".mjs", ".ts", ".tsx", ".jsx"})


class StaticFilesWithJsMime(StaticFiles):
    """Serve static files with correct MIME type for JS/TS module scripts (avoids text/plain)."""

    def file_response(self, full_path, stat_result, scope, status_code=200):
        from starlette.responses import FileResponse as StarletteFileResponse

        suffix = Path(full_path).suffix.lower()
        media_type = "application/javascript" if suffix in _JS_MIME_EXTENSIONS else None
        response = StarletteFileResponse(
            full_path, status_code=status_code, stat_result=stat_result, media_type=media_type
        )
        from starlette.datastructures import Headers
        from starlette.staticfiles import NotModifiedResponse

        request_headers = Headers(scope=scope)
        if self.is_not_modified(response.headers, request_headers):
            return NotModifiedResponse(response.headers)
        return response


from .signaling import get_last_telemetry, handle_signaling_websocket, send_control_to_robot
from .robot_profiles import router as robot_profiles_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

# Robot profile CRUD routes (must be included before the static-file catch-all)
app.include_router(robot_profiles_router)

WWW_DIR = Path(__file__).resolve().parent.parent / "www"
# Prefer built frontend (dist) when it has index.html; otherwise serve raw www
_DIST_INDEX = WWW_DIR / "dist" / "index.html"
STATIC_DIR = WWW_DIR / "dist" if _DIST_INDEX.is_file() else WWW_DIR

# Optical flow visualization image (JPEG)
_latest_optical_flow_image: Optional[bytes] = None
_latest_optical_flow_image_timestamp: Optional[float] = None
_optical_flow_image_lock = threading.Lock()

# Floor mask visualization image (JPEG)
_latest_floor_mask_image: Optional[bytes] = None
_latest_floor_mask_image_timestamp: Optional[float] = None
_floor_mask_image_lock = threading.Lock()

# ROS2 subscriber thread (optional, only if ROS2 is available)
_optical_flow_subscriber_thread: Optional[threading.Thread] = None


def _ros2_optical_flow_subscriber():
    """Background thread to subscribe to ROS2 optical flow image topic."""
    try:
        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import CompressedImage

        rclpy.init()
        node = Node("optical_flow_image_server")

        def flow_callback(msg: CompressedImage):
            global _latest_optical_flow_image, _latest_optical_flow_image_timestamp
            stamp = msg.header.stamp
            frame_time = stamp.sec + stamp.nanosec * 1e-9
            with _optical_flow_image_lock:
                _latest_optical_flow_image = bytes(msg.data)
                _latest_optical_flow_image_timestamp = frame_time

        node.create_subscription(
            CompressedImage,
            "/optical_flow/image/compressed",
            flow_callback,
            10,
        )

        logger.info("ROS2 optical flow image subscriber started")
        rclpy.spin(node)
    except ImportError:
        logger.warning("ROS2 not available, optical flow image endpoint will return placeholder")
    except Exception as e:
        logger.error(f"ROS2 optical flow subscriber error: {e}")


@app.on_event("startup")
async def startup():
    logger.info("App starting: WebSocket /ws/signaling and /ws/signaling/")
    # Start ROS2 subscriber in background thread
    global _optical_flow_subscriber_thread
    _optical_flow_subscriber_thread = threading.Thread(target=_ros2_optical_flow_subscriber, daemon=True)
    _optical_flow_subscriber_thread.start()


@app.get("/")
def read_root():
    """Serve the React app (built from Vite). Prefer dist/index.html, fallback to www/index.html."""
    # Prefer built React app so localhost:8000 shows the Vite app after `pnpm build`
    for path in (_DIST_INDEX, WWW_DIR / "index.html"):
        if path.is_file():
            return FileResponse(path)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "React app not built. Run: pnpm build (in app/www), then restart the server.",
        },
    )


@app.get("/favicon.ico")
def favicon():
    """Avoid 404 in console when browser requests favicon."""
    return Response(status_code=204)

@app.get("/health")
def health():
    """Health check for containers."""
    return {"status": "ok"}


@app.get("/api/config")
def api_config():
    """WebRTC config: ICE servers (STUN + optional TURN from env), optional front camera intrinsics for tap-to-orient."""
    out = {"iceServers": get_ice_servers()}
    # Front camera intrinsics for tap-to-orient (stream resolution, e.g. 320x240). Optional; UI uses 60° FOV if not set.
    # Override via env: CAMERA_FX, CAMERA_CX, CAMERA_CY, CAMERA_WIDTH, CAMERA_HEIGHT.
    import os
    import math
    w = 320
    h = 240
    fx = cx = cy = None
    for key, default, conv in [
        ("CAMERA_WIDTH", 320, int),
        ("CAMERA_HEIGHT", 240, int),
        ("CAMERA_FX", None, float),
        ("CAMERA_CX", None, float),
        ("CAMERA_CY", None, float),
    ]:
        v = os.environ.get(key, "").strip()
        if v:
            try:
                val = conv(v)
                if key == "CAMERA_WIDTH":
                    w = val
                elif key == "CAMERA_HEIGHT":
                    h = val
                elif key == "CAMERA_FX":
                    fx = val
                elif key == "CAMERA_CX":
                    cx = val
                elif key == "CAMERA_CY":
                    cy = val
            except (ValueError, TypeError):
                pass
    if fx is None:
        fx = (w / 2.0) / math.tan(30.0 * math.pi / 180.0)
    if cx is None:
        cx = w / 2.0
    if cy is None:
        cy = h / 2.0
    out["camera"] = {"fx": fx, "cx": cx, "cy": cy, "width": w, "height": h}
    return out


@app.get("/v2/front")
def v2_front():
    """
    This is the WebRTC app, not the Earth Rovers SDK.
    For front camera, run the Earth Rovers SDK on another port (e.g. 8001)
    and set SDK_LOCAL_URL=http://127.0.0.1:8001 in .env so the bridge uses it.
    """
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Front camera is served by the Earth Rovers SDK. Run the SDK on another port (e.g. 8001) and set SDK_LOCAL_URL in .env to that URL.",
        },
    )


def _stub_telemetry():
    """Minimal telemetry when no robot data is available."""
    return {
        "battery": 0.0,
        "signal_level": 0,
        "speed": 0.0,
        "lamp": 0,
        "latitude": 0.0,
        "longitude": 0.0,
        "gps_signal": 0.0,
        "orientation": 0,
        "vibration": None,
        "accels": [],
        "gyros": [],
        "mags": [],
        "rpms": [],
        "timestamp": time.time(),
    }


@app.get("/data")
def data():
    """
    Telemetry endpoint. Bridge (scout_bridge) polls this when SDK is expected on port 8000.
    Returns last telemetry received from robot via signaling when available;
    otherwise returns minimal stub so the bridge does not 404 and the UI can show something.
    """
    last = get_last_telemetry()
    if last is not None:
        return last
    return _stub_telemetry()


@app.post("/api/control")
async def api_control(request: Request):
    """
    Send velocity command to the robot (when connected via signaling).
    Body: {"linear_x": float, "angular_z": float} (optional, default 0).
    Used by MCP server and other HTTP clients for agent-driven control.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    linear_x = float(body.get("linear_x", 0))
    angular_z = float(body.get("angular_z", 0))
    sent = await send_control_to_robot(linear_x, angular_z)
    if not sent:
        return JSONResponse(
            status_code=503,
            content={"detail": "Robot not connected. Connect the robot via ConnectX signaling first."},
        )
    return {"ok": True, "linear_x": linear_x, "angular_z": angular_z}


@app.websocket("/ws/signaling")
async def ws_signaling(websocket: WebSocket):
    """WebRTC signaling: exchange offer/answer and ICE between browser and robot (default room)."""
    await handle_signaling_websocket(websocket)


@app.websocket("/ws/signaling/")
async def ws_signaling_trailing(websocket: WebSocket):
    """Same as /ws/signaling for clients that send a trailing slash."""
    await handle_signaling_websocket(websocket)


@app.websocket("/ws/signaling/{robot_id}")
async def ws_signaling_robot(websocket: WebSocket, robot_id: str):
    """Per-robot WebRTC signaling room. Use robot profile id as robot_id."""
    await handle_signaling_websocket(websocket, robot_id=robot_id)


# Max body size for perception image ingest (e.g. 5 MB JPEG)
_IMAGE_INGEST_MAX_BYTES = 5 * 1024 * 1024


@app.post("/api/optical_flow_image_ingest")
async def optical_flow_image_ingest(request: Request):
    """Accept JPEG optical flow viz from relay. Updates latest for GET /api/optical_flow_image."""
    global _latest_optical_flow_image, _latest_optical_flow_image_timestamp
    content_type = request.headers.get("content-type", "")
    if content_type and "image/jpeg" not in content_type and "application/octet-stream" not in content_type:
        return Response(status_code=415, content="Content-Type must be image/jpeg or application/octet-stream")
    frame_time_header = request.headers.get("X-Depth-Frame-Time", "").strip()
    try:
        frame_time = float(frame_time_header) if frame_time_header else time.time()
    except ValueError:
        frame_time = time.time()
    body = await request.body()
    if len(body) > _IMAGE_INGEST_MAX_BYTES:
        return Response(status_code=413, content="Body too large")
    with _optical_flow_image_lock:
        _latest_optical_flow_image = bytes(body)
        _latest_optical_flow_image_timestamp = frame_time
    return Response(status_code=204)


@app.get("/api/optical_flow_image")
def optical_flow_image():
    """Serve the latest optical flow visualization as JPEG."""
    global _latest_optical_flow_image, _latest_optical_flow_image_timestamp
    with _optical_flow_image_lock:
        if _latest_optical_flow_image is None:
            return Response(
                status_code=503,
                content="Optical flow image not available. Ensure optical_flow_node is running.",
                media_type="text/plain",
            )
        body = _latest_optical_flow_image
        frame_time = _latest_optical_flow_image_timestamp
    headers = {}
    if frame_time is not None:
        headers["X-Depth-Frame-Time"] = str(frame_time)
    return Response(
        content=body,
        media_type="image/jpeg",
        headers=headers,
    )


@app.post("/api/floor_mask_image_ingest")
async def floor_mask_image_ingest(request: Request):
    """Accept JPEG floor mask viz from relay. Updates latest for GET /api/floor_mask_image."""
    global _latest_floor_mask_image, _latest_floor_mask_image_timestamp
    content_type = request.headers.get("content-type", "")
    if content_type and "image/jpeg" not in content_type and "application/octet-stream" not in content_type:
        return Response(status_code=415, content="Content-Type must be image/jpeg or application/octet-stream")
    frame_time_header = request.headers.get("X-Depth-Frame-Time", "").strip()
    try:
        frame_time = float(frame_time_header) if frame_time_header else time.time()
    except ValueError:
        frame_time = time.time()
    body = await request.body()
    if len(body) > _IMAGE_INGEST_MAX_BYTES:
        return Response(status_code=413, content="Body too large")
    with _floor_mask_image_lock:
        _latest_floor_mask_image = bytes(body)
        _latest_floor_mask_image_timestamp = frame_time
    return Response(status_code=204)


@app.get("/api/floor_mask_image")
def floor_mask_image():
    """Serve the latest floor mask visualization as JPEG."""
    global _latest_floor_mask_image, _latest_floor_mask_image_timestamp
    with _floor_mask_image_lock:
        if _latest_floor_mask_image is None:
            return Response(
                status_code=503,
                content="Floor mask image not available. Ensure floor_mask_node is running.",
                media_type="text/plain",
            )
        body = _latest_floor_mask_image
        frame_time = _latest_floor_mask_image_timestamp
    headers = {}
    if frame_time is not None:
        headers["X-Depth-Frame-Time"] = str(frame_time)
    return Response(
        content=body,
        media_type="image/jpeg",
        headers=headers,
    )


# Calibration proxy: forward to scout_bridge calibration HTTP API
_CALIBRATION_BRIDGE_URL = os.environ.get("CALIBRATION_BRIDGE_URL", "http://scout_bridge:8766").rstrip("/")
_CALIBRATION_TIMEOUT = 10


def _calibration_proxy(method: str, path: str, body: Optional[bytes] = None) -> Response:
    """Forward request to calibration service; return 503 on connection error."""
    url = f"{_CALIBRATION_BRIDGE_URL}{path}"
    try:
        req = urllib.request.Request(url, data=body, method=method)
        if body is not None:
            req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=_CALIBRATION_TIMEOUT) as resp:
            return Response(
                content=resp.read(),
                status_code=resp.status,
                media_type="application/json",
            )
    except urllib.error.HTTPError as e:
        return Response(
            content=e.read() if e.fp else b"",
            status_code=e.code,
            media_type="application/json",
        )
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        logger.warning("Calibration proxy error: %s", e)
        return JSONResponse(
            status_code=503,
            content={"detail": "Calibration service unavailable. Ensure scout_bridge is running."},
        )


@app.post("/api/calibration/start")
async def api_calibration_start(request: Request):
    """Start calibration session with target image count."""
    try:
        body = await request.json()
        target_count = int(body.get("target_count", 25))
    except (ValueError, TypeError):
        target_count = 25
    payload = json.dumps({"target_count": target_count}).encode("utf-8")
    return _calibration_proxy("POST", "/calibration/start", body=payload)


@app.post("/api/calibration/capture")
async def api_calibration_capture():
    """Capture current camera frame for calibration."""
    return _calibration_proxy("POST", "/calibration/capture")


@app.get("/api/calibration/status")
def api_calibration_status():
    """Return calibration status (captured count, target, state)."""
    return _calibration_proxy("GET", "/calibration/status")


@app.post("/api/calibration/run")
async def api_calibration_run():
    """Run calibration and save to robot/."""
    return _calibration_proxy("POST", "/calibration/run")


# Serve static assets (JS, CSS, etc.) so that index.html can load /src/main.tsx or built /assets/*
# Mount last so API and WebSocket routes take precedence.
# Use StaticFilesWithJsMime so .js/.ts/.tsx are served as application/javascript (avoids MIME type error).
app.mount("/", StaticFilesWithJsMime(directory=str(STATIC_DIR), html=False), name="www")
