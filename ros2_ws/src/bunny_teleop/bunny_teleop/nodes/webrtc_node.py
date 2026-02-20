#!/usr/bin/env python3
"""
WebRTC node: subscribes to /camera/front/compressed, sends video over WebRTC;
receives control on data channel and publishes to /cmd_vel.
Connects to App server WebSocket for signaling (offer/answer/ICE).
"""

import asyncio
import json
import logging
import os
import queue
import threading
import time
from fractions import Fraction
from typing import Optional

import numpy as np
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.qos import QoSProfile, HistoryPolicy, ReliabilityPolicy
from av import VideoFrame
from av.video.frame import PictureType
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import Float32MultiArray, Int32, String

from bunny_teleop.constants import (
    AUTONOMY_COMMAND_TOPIC,
    CAMERA_FRAME_ID,
    CAMERA_FRONT_COMPRESSED_TOPIC,
    CMD_VEL_TOPIC,
    LAMP_TOPIC,
    DEFAULT_IMAGE_FORMAT,
    OPTICAL_FLOW_TOPIC,
    ROBOT_TELEMETRY_TOPIC,
    VIDEO_OUTPUT_HEIGHT,
    VIDEO_OUTPUT_WIDTH,
)
from bunny_teleop.webrtc_config import get_ice_servers_dict

# Optional OpenCV for decoding; fallback to raw frame handling if unavailable
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# aiortc and websockets for WebRTC and signaling client
try:
    from aiortc import (
        RTCConfiguration,
        RTCIceCandidate,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
        VideoStreamTrack,
    )
    from aiortc.exceptions import InvalidStateError as AiortcInvalidStateError
    from aiortc.rtcrtpsender import RTCRtpSender
    HAS_AIORTC = True

    # aiortc only sets force_keyframe when it receives PLI from the browser; the first frame
    # is always encoded with force_keyframe=False, so the browser never gets a keyframe.
    # Patch so the first video frame is encoded as keyframe (encoder is None on first frame).
    _orig_next_encoded_frame = RTCRtpSender._next_encoded_frame

    async def _patched_next_encoded_frame(self, codec):
        encoder = getattr(self, "_RTCRtpSender__encoder", None)
        kind = getattr(self, "_RTCRtpSender__kind", "")
        if encoder is None and kind == "video":
            setattr(self, "_RTCRtpSender__force_keyframe", True)
        return await _orig_next_encoded_frame(self, codec)

    RTCRtpSender._next_encoded_frame = _patched_next_encoded_frame
except ImportError:
    HAS_AIORTC = False
    AiortcInvalidStateError = None  # type: ignore[misc, assignment]

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


SIGNALING_WS_URL = os.getenv("SIGNALING_WS_URL", "ws://localhost:8000/ws/signaling")
# Keep only latest frame to minimize latency (no backlog).
FRAME_QUEUE_MAXSIZE = 1
FRAME_CLOCK_RATE = 90000
# Send a keyframe (I-frame) at least this often so the browser decoder can display (and recover after packet loss).
# 5 Hz video (previously working rate; steady keyframes help browser decode)
CAMERA_TRACK_FPS = 5
KEYFRAME_INTERVAL_FRAMES = 15  # ~3 s at 5 fps
KEYFRAME_BURST_FIRST_N = 5  # First N frames as keyframes so browser gets one even if first packets are lost

# Frame metrics log: one line per frame when FRAME_METRICS_ENABLED != 0
# Default path: workspace root (project root in Docker) so frame_metrics.log appears next to cli.sh
FRAME_METRICS_ENABLED = os.getenv("FRAME_METRICS_ENABLED", "1").strip() not in ("0", "false", "False", "no")
_def_metrics_log = os.getenv("FRAME_METRICS_LOG")
if _def_metrics_log:
    FRAME_METRICS_LOG_PATH = _def_metrics_log if os.path.isabs(_def_metrics_log) else os.path.abspath(_def_metrics_log)
else:
    _nodes_dir = os.path.dirname(os.path.abspath(__file__))
    _ros2_ws = os.path.abspath(os.path.join(_nodes_dir, "..", "..", "..", ".."))
    _workspace_root = os.path.dirname(_ros2_ws)
    FRAME_METRICS_LOG_PATH = os.path.join(_workspace_root, "frame_metrics.log")
_metrics_log_file = [None]  # Open-once file handle for append


def _parse_frame_metrics_from_header(frame_id_str: str, fallback_frame_id: int) -> tuple:
    """Parse frame_id,sdk_capture_ms,fetch_ms from header.frame_id (e.g. camera_front_42_45.2_52.1)."""
    prefix = f"{CAMERA_FRAME_ID}_"
    if not frame_id_str or not frame_id_str.startswith(prefix):
        return (fallback_frame_id, 0.0, 0.0)
    parts = frame_id_str[len(prefix) :].split("_")
    if len(parts) < 3:
        return (fallback_frame_id, 0.0, 0.0)
    try:
        fid = int(parts[0])
        sdk_ms = float(parts[1])
        fetch_ms = float(parts[2])
        return (fid, sdk_ms, fetch_ms)
    except (ValueError, IndexError):
        return (fallback_frame_id, 0.0, 0.0)


def _get_metrics_log_handle():
    """Return open file handle for frame metrics log (append), or None if disabled."""
    if not FRAME_METRICS_ENABLED:
        return None
    if _metrics_log_file[0] is None:
        try:
            _metrics_log_file[0] = open(FRAME_METRICS_LOG_PATH, "a", encoding="utf-8")
        except OSError as e:
            LOG.warning("Failed to open frame metrics log %s: %s", FRAME_METRICS_LOG_PATH, e)
            return None
    return _metrics_log_file[0]


def _webrtc_ice_config() -> Optional[RTCConfiguration]:
    """Build RTCConfiguration from shared ICE config (STUN + optional TURN)."""
    if not HAS_AIORTC:
        return None
    servers_dict = get_ice_servers_dict()
    servers = [
        RTCIceServer(
            urls=s["urls"],
            username=s.get("username", ""),
            credential=s.get("credential", ""),
        )
        for s in servers_dict
    ]
    return RTCConfiguration(iceServers=servers)


CMD_VEL_DRAIN_HZ = 50
TELEMETRY_SEND_INTERVAL = 0.05  # seconds (20 Hz for responsive UI)
LOG = logging.getLogger(__name__)


def _put_latest(q: queue.Queue, item) -> None:
    """Put item in queue; if full, drop oldest then put (keep latest only)."""
    try:
        q.put_nowait(item)
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        q.put_nowait(item)


def _asyncio_exception_handler(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Downgrade aiortc 'RTCIceTransport is closed' (expected on reconnect) to debug."""
    exc = context.get("exception")
    if (
        HAS_AIORTC
        and AiortcInvalidStateError is not None
        and exc is not None
        and isinstance(exc, AiortcInvalidStateError)
        and "RTCIceTransport is closed" in str(exc)
    ):
        LOG.debug("WebRTC ICE transport closed (expected on reconnect): %s", exc)
        return
    message = context.get("message", "Unhandled exception in async task")
    LOG.error("%s: %s", message, exc if exc is not None else context)


def _decode_compressed_image(data: bytes, fmt: str) -> Optional[np.ndarray]:
    """Decode JPEG/PNG bytes to BGR numpy array for OpenCV. cv2.imdecode auto-detects format."""
    if not HAS_CV2:
        return None
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None and len(data) > 0:
        # Some OpenCV builds require a writable contiguous buffer
        arr = np.ascontiguousarray(np.copy(arr))
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def _make_placeholder_frame() -> np.ndarray:
    """Create a single 'No camera feed' placeholder image (BGR, same size as video output)."""
    h, w = VIDEO_OUTPUT_HEIGHT, VIDEO_OUTPUT_WIDTH
    # Brighter background so it's obvious even if video is small or dim
    img = np.full((h, w, 3), 80, dtype=np.uint8)
    if HAS_CV2:
        try:
            # Large, high-contrast text so it's visible when scaled
            cv2.putText(
                img,
                "No camera feed",
                (10, h // 2 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (255, 255, 255),
                2,
            )
            cv2.putText(
                img,
                "Start Earth Rovers SDK (scout_sdk) /v2/front",
                (10, h // 2 + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (220, 220, 220),
                1,
            )
        except Exception:
            pass
    return img


class CameraTrack(VideoStreamTrack):
    """Video track that yields frames from a thread-safe queue (ROS camera topic)."""

    def __init__(
        self,
        frame_queue: queue.Queue,
        clock_rate: int = FRAME_CLOCK_RATE,
        last_frame_pts_ref: Optional[list] = None,
    ) -> None:
        super().__init__()
        self._queue = frame_queue
        self._clock_rate = clock_rate
        self._pts = 0
        self._last_frame: Optional[np.ndarray] = None
        self._placeholder_frame: Optional[np.ndarray] = None
        self._last_frame_pts_ref = last_frame_pts_ref
        self._recv_count = 0

    async def recv(self):
        # Prefer latest frame from queue; else reuse last frame to keep stream alive
        got_from_queue = False
        try:
            self._last_frame = self._queue.get_nowait()
            got_from_queue = True
        except queue.Empty:
            pass
        if self._last_frame is None:
            # No frame yet: show placeholder so user sees a message instead of black
            if self._placeholder_frame is None:
                self._placeholder_frame = _make_placeholder_frame()
                LOG.info(
                    "CameraTrack: no frames from %s yet; showing placeholder. Start Earth Rovers SDK (scout_sdk) for live feed.",
                    CAMERA_FRONT_COMPRESSED_TOPIC,
                )
            self._last_frame = self._placeholder_frame
        if self._recv_count == 0:
            LOG.info("CameraTrack: first frame sent (from_queue=%s)", got_from_queue)
        elif self._recv_count < 3 or self._recv_count % 100 == 0:
            LOG.debug(
                "CameraTrack recv frame %d pts=%d",
                self._recv_count,
                self._pts,
            )
        self._recv_count += 1
        frame = VideoFrame.from_ndarray(self._last_frame, format="bgr24")
        frame.pts = self._pts
        frame.time_base = Fraction(1, self._clock_rate)
        # Force keyframe (I-frame) for first frames and periodically so the browser decoder can display.
        if (
            self._recv_count <= KEYFRAME_BURST_FIRST_N
            or (self._recv_count % KEYFRAME_INTERVAL_FRAMES) == 1
        ):
            frame.pict_type = PictureType.I
        if self._last_frame_pts_ref is not None:
            self._last_frame_pts_ref[0] = self._pts
        self._pts += int(self._clock_rate / CAMERA_TRACK_FPS)
        # Rate-limit to CAMERA_TRACK_FPS so encoder and browser get steady keyframes.
        await asyncio.sleep(1.0 / CAMERA_TRACK_FPS)
        return frame


def _twist_from_control(data: dict) -> Optional[Twist]:
    """Parse JSON control message to geometry_msgs/Twist. Supports linear_x/angular_z or full linear/angular."""
    try:
        msg = Twist()
        if "linear_x" in data and "angular_z" in data:
            msg.linear.x = float(data["linear_x"])
            msg.linear.y = 0.0
            msg.linear.z = 0.0
            msg.angular.x = 0.0
            msg.angular.y = 0.0
            msg.angular.z = float(data["angular_z"])
        elif "linear" in data and "angular" in data:
            lin = data["linear"]
            ang = data["angular"]
            msg.linear.x = float(lin.get("x", 0))
            msg.linear.y = float(lin.get("y", 0))
            msg.linear.z = float(lin.get("z", 0))
            msg.angular.x = float(ang.get("x", 0))
            msg.angular.y = float(ang.get("y", 0))
            msg.angular.z = float(ang.get("z", 0))
        else:
            return None
        return msg
    except (TypeError, ValueError, KeyError):
        return None


def run_ros_node(
    frame_queue: queue.Queue,
    control_queue: queue.Queue,
    telemetry_queue: queue.Queue,
    autonomy_command_queue: queue.Queue,
    image_format: str,
    stop_event: threading.Event,
    last_flow_ref: list,
) -> None:
    """Run rclpy node. Drains control_queue of (twist, lamp) and autonomy_command_queue of command strings."""
    rclpy.init()
    node = Node("webrtc_node")
    cmd_pub = node.create_publisher(Twist, CMD_VEL_TOPIC, 10)
    lamp_pub = node.create_publisher(Int32, LAMP_TOPIC, 10)
    autonomy_pub = node.create_publisher(String, AUTONOMY_COMMAND_TOPIC, 10)

    first_telemetry_logged = [False]

    def on_telemetry(msg: String) -> None:
        if not msg.data:
            return
        if not first_telemetry_logged[0]:
            first_telemetry_logged[0] = True
            LOG.info("First telemetry received on %s (len=%d)", ROBOT_TELEMETRY_TOPIC, len(msg.data))
        _put_latest(telemetry_queue, msg.data)

    node.create_subscription(
        String,
        ROBOT_TELEMETRY_TOPIC,
        on_telemetry,
        10,
    )

    def on_cmd_vel(msg: Twist) -> None:
        """Echo /cmd_vel as telemetry so UI shows speed; only send fields we have (no zeros)."""
        partial = {"speed": float(msg.linear.x), "timestamp": time.time()}
        _put_latest(telemetry_queue, json.dumps(partial))

    node.create_subscription(
        Twist,
        CMD_VEL_TOPIC,
        on_cmd_vel,
        10,
    )

    def on_optical_flow(msg: Float32MultiArray) -> None:
        if len(msg.data) >= 6:
            last_flow_ref[0] = list(msg.data[:6])

    node.create_subscription(
        Float32MultiArray,
        OPTICAL_FLOW_TOPIC,
        on_optical_flow,
        10,
    )

    decode_fail_logged: list = [False]
    first_frame_logged: list = [False]
    local_frame_counter = [0]

    def on_image(msg: CompressedImage) -> None:
        data = bytes(msg.data)
        if not data:
            return
        t0 = time.perf_counter()
        frame_id, sdk_capture_ms, fetch_ms = _parse_frame_metrics_from_header(
            msg.header.frame_id, local_frame_counter[0]
        )
        img = _decode_compressed_image(data, msg.format or image_format)
        t1 = time.perf_counter()
        decode_ms = (t1 - t0) * 1000
        resize_ms = 0.0
        if img is not None:
            if not first_frame_logged[0]:
                first_frame_logged[0] = True
                LOG.info("First camera frame received on %s", CAMERA_FRONT_COMPRESSED_TOPIC)
            if img.shape[1] != VIDEO_OUTPUT_WIDTH or img.shape[0] != VIDEO_OUTPUT_HEIGHT:
                t_resize_start = time.perf_counter()
                img = cv2.resize(
                    img,
                    (VIDEO_OUTPUT_WIDTH, VIDEO_OUTPUT_HEIGHT),
                    interpolation=cv2.INTER_AREA,
                )
                resize_ms = (time.perf_counter() - t_resize_start) * 1000
            try:
                frame_queue.put_nowait(img)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                    frame_queue.put_nowait(img)
                except queue.Empty:
                    pass
            local_frame_counter[0] += 1
            # One line per frame: [frame_N],[sdk_capture],[ms],[bridge_fetch],[ms],[decode],[ms],[resize],[ms],[UI],[-]
            log_handle = _get_metrics_log_handle()
            if log_handle is not None:
                line = (
                    f"[frame_{frame_id}],[sdk_capture],[{sdk_capture_ms:.2f}],[bridge_fetch],[{fetch_ms:.2f}],"
                    f"[decode],[{decode_ms:.2f}],[resize],[{resize_ms:.2f}],[UI],[-]\n"
                )
                try:
                    log_handle.write(line)
                    log_handle.flush()
                except OSError as e:
                    LOG.debug("Frame metrics log write failed: %s", e)
        else:
            if not decode_fail_logged[0]:
                decode_fail_logged[0] = True
                LOG.warning(
                    "Camera frame decode failed (format=%s, len=%d). Check IMAGE_FORMAT matches SDK. No video will show until decode succeeds.",
                    msg.format or image_format,
                    len(data),
                )

    # QoS: depth 1 + KEEP_LAST so we only get the newest frame (no lag from backlog).
    camera_qos = QoSProfile(
        depth=1,
        history=HistoryPolicy.KEEP_LAST,
        reliability=ReliabilityPolicy.BEST_EFFORT,
    )
    node.create_subscription(
        CompressedImage,
        CAMERA_FRONT_COMPRESSED_TOPIC,
        on_image,
        camera_qos,
    )
    dt = 1.0 / CMD_VEL_DRAIN_HZ
    last_drain = time.monotonic()
    start_time = time.monotonic()
    last_no_frame_log = [0.0]
    last_no_telemetry_log = [0.0]
    NO_DATA_WARN_INTERVAL = 15.0

    while not stop_event.is_set():
        now = time.monotonic()
        if not first_frame_logged[0] and (now - last_no_frame_log[0]) >= NO_DATA_WARN_INTERVAL and (now - start_time) >= 5.0:
            last_no_frame_log[0] = now
            LOG.warning(
                "No camera frames on %s yet. Is bridge_node running in the same container? Is scout_sdk reachable and /v2/front returning frames?",
                CAMERA_FRONT_COMPRESSED_TOPIC,
            )
        if not first_telemetry_logged[0] and (now - last_no_telemetry_log[0]) >= NO_DATA_WARN_INTERVAL and (now - start_time) >= 5.0:
            last_no_telemetry_log[0] = now
            LOG.warning(
                "No telemetry on %s yet. Is bridge_node running? Is scout_sdk /data reachable?",
                ROBOT_TELEMETRY_TOPIC,
            )
        try:
            rclpy.spin_once(node, timeout_sec=0.05)
        except ExternalShutdownException:
            break
        except Exception as e:
            err_str = str(e)
            if "context is not valid" in err_str or "rcl_shutdown" in err_str or "rcl_init" in err_str:
                LOG.info("ROS context shut down; exiting ROS thread.")
                break
            LOG.warning("ROS spin_once error (continuing): %s", e)
            continue
        now = time.monotonic()
        if now - last_drain >= dt:
            last_drain = now
            try:
                # Drain control queue: each item is (twist, lamp) so state is passed together
                while True:
                    item = control_queue.get_nowait()
                    try:
                        twist, lamp = item
                        lamp_pub.publish(Int32(data=int(lamp) if lamp else 0))
                        cmd_pub.publish(twist)
                    except (TypeError, ValueError) as e:
                        LOG.warning("Control queue item invalid (twist, lamp): %s", e)
            except queue.Empty:
                pass
            except Exception as e:
                LOG.warning("Control drain error (continuing): %s", e)
            try:
                while True:
                    cmd = autonomy_command_queue.get_nowait()
                    if cmd and isinstance(cmd, str) and cmd.strip():
                        autonomy_pub.publish(String(data=cmd.strip()))
                        LOG.info("Published autonomy command: %r", cmd.strip())
            except queue.Empty:
                pass
            except Exception as e:
                LOG.warning("Autonomy command drain error (continuing): %s", e)

    try:
        node.destroy_node()
    except Exception:
        pass
    try:
        rclpy.shutdown()
    except Exception:
        pass


def _is_full_telemetry(obj: dict) -> bool:
    """True if this looks like full telemetry (has battery, lat/lon, or rpms), not just speed echo."""
    return (
        obj.get("battery") is not None
        or (obj.get("latitude") is not None and obj.get("longitude") is not None)
        or (
            obj.get("rpms") is not None
            and isinstance(obj.get("rpms"), list)
            and len(obj.get("rpms", [])) > 0
        )
    )


# Minimal payload so browser gets something when no real telemetry yet (connection alive)
_HEARTBEAT_TELEMETRY = {
    "battery": None,
    "speed": 0.0,
    "lamp": 0,
    "timestamp": 0,
}

async def _telemetry_sender_loop(
    ws,
    telemetry_queue: queue.Queue,
    data_channel_ref: list,
    stop_event: threading.Event,
    last_frame_pts_ref: Optional[list] = None,
    last_flow_ref: Optional[list] = None,
) -> None:
    """Send telemetry to app server and browser. Send heartbeat when queue empty so UI stays alive."""
    last_heartbeat = [0.0]
    last_payload_ws = [None]  # last full payload we sent (for heartbeat)
    heartbeat_interval = 2.0  # seconds
    first_ws_telemetry_logged: list = [False]

    while not stop_event.is_set():
        await asyncio.sleep(TELEMETRY_SEND_INTERVAL)
        try:
            collected = []
            try:
                while True:
                    data = telemetry_queue.get_nowait()
                    collected.append(data)
            except queue.Empty:
                pass

            payload_obj_ws = None
            payload_obj_dc = None
            if collected:
                parsed = []
                for data in collected:
                    try:
                        obj = json.loads(data) if isinstance(data, str) else data
                        if obj is not None:
                            parsed.append(obj)
                    except json.JSONDecodeError:
                        continue
                if parsed:
                    for obj in reversed(parsed):
                        if _is_full_telemetry(obj):
                            payload_obj_ws = obj
                            break
                        if payload_obj_ws is None:
                            payload_obj_ws = obj
                    payload_obj_dc = parsed[-1]
            else:
                # No telemetry: send heartbeat so browser knows connection is alive
                now = time.time()
                if now - last_heartbeat[0] >= heartbeat_interval:
                    last_heartbeat[0] = now
                    hb = dict(_HEARTBEAT_TELEMETRY)
                    hb["timestamp"] = now
                    payload_obj_ws = last_payload_ws[0] if last_payload_ws[0] else hb
                    payload_obj_dc = hb

            if payload_obj_ws is None and payload_obj_dc is None:
                continue
            if payload_obj_ws is None:
                payload_obj_ws = payload_obj_dc
            if payload_obj_dc is None:
                payload_obj_dc = payload_obj_ws

            if last_flow_ref is not None and last_flow_ref[0] is not None:
                payload_obj_ws = dict(payload_obj_ws) if isinstance(payload_obj_ws, dict) else payload_obj_ws
                payload_obj_dc = dict(payload_obj_dc) if isinstance(payload_obj_dc, dict) else payload_obj_dc
                flow = last_flow_ref[0]
                payload_obj_ws["optical_flow"] = flow
                payload_obj_dc["optical_flow"] = flow

            last_payload_ws[0] = payload_obj_ws if _is_full_telemetry(payload_obj_ws) else last_payload_ws[0]
            payload_ws = {"type": "telemetry", "data": payload_obj_ws}
            if last_frame_pts_ref is not None:
                payload_ws["frame_pts"] = last_frame_pts_ref[0]
                payload_ws["frame_time_base"] = FRAME_CLOCK_RATE
            payload_str_ws = json.dumps(payload_ws)
            payload_dc = {"type": "telemetry", "data": payload_obj_dc}
            if last_frame_pts_ref is not None:
                payload_dc["frame_pts"] = last_frame_pts_ref[0]
                payload_dc["frame_time_base"] = FRAME_CLOCK_RATE
            payload_str_dc = json.dumps(payload_dc)
            await asyncio.sleep(0)
            try:
                if not first_ws_telemetry_logged[0]:
                    first_ws_telemetry_logged[0] = True
                    LOG.info("First telemetry sent over signaling WebSocket (browser receives via relay)")
                await ws.send(payload_str_ws)
            except Exception as e:
                LOG.warning("Telemetry ws.send failed (will retry): %s", e)
            if data_channel_ref and data_channel_ref[0] is not None:
                try:
                    dc = data_channel_ref[0]
                    if getattr(dc, "readyState", None) == "open":
                        dc.send(payload_str_dc)
                except Exception:
                    pass
        except Exception as e:
            LOG.debug("Telemetry sender iteration: %s", e)


async def run_signaling_and_webrtc(
    frame_queue: queue.Queue,
    control_queue: queue.Queue,
    telemetry_queue: queue.Queue,
    autonomy_command_queue: queue.Queue,
    stop_event: threading.Event,
    last_flow_ref: Optional[list] = None,
) -> None:
    """Connect to signaling WebSocket, handle offer/answer/ICE, and run WebRTC peer."""
    if not HAS_WEBSOCKETS or not HAS_AIORTC:
        LOG.error("Missing deps: websockets and aiortc required for webrtc_node")
        return

    asyncio.get_running_loop().set_exception_handler(_asyncio_exception_handler)
    LOG.info("Signaling URL: %s", SIGNALING_WS_URL)
    while not stop_event.is_set():
        try:
            async with websockets.connect(
                SIGNALING_WS_URL,
                close_timeout=2,
                open_timeout=10,
            ) as ws:
                await ws.send(json.dumps({"role": "robot"}))
                LOG.info("Connected to signaling as robot: %s", SIGNALING_WS_URL)

                pc: Optional[RTCPeerConnection] = None
                data_channel_ref: list = [None]
                last_frame_pts_ref: list = [0]
                # Persist lamp state across datachannel reconnects so it does not reset to 0 on new offer
                last_lamp_ref: list = [0]

                async def recv_loop():
                    nonlocal pc
                    async for raw in ws:
                        if stop_event.is_set():
                            break
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        typ = msg.get("type")
                        if typ == "offer" and "sdp" in msg:
                            if pc is not None:
                                await pc.close()
                            ice_config = _webrtc_ice_config()
                            pc = (
                                RTCPeerConnection(configuration=ice_config)
                                if ice_config
                                else RTCPeerConnection()
                            )
                            track = CameraTrack(frame_queue, last_frame_pts_ref=last_frame_pts_ref)
                            pc.addTrack(track)
                            LOG.debug("Video track added to peer connection (source: %s)", CAMERA_FRONT_COMPRESSED_TOPIC)

                            first_control_logged: list = [False]

                            @pc.on("icecandidate")
                            def on_ice_candidate(event):
                                """Send our ICE candidates to the browser so the peer connection can complete."""
                                if event.candidate is None:
                                    return
                                try:
                                    c = event.candidate
                                    payload = {"type": "ice", "candidate": c.candidate}
                                    if getattr(c, "sdpMid", None) is not None:
                                        payload["sdpMid"] = c.sdpMid
                                    if getattr(c, "sdpMLineIndex", None) is not None:
                                        payload["sdpMLineIndex"] = c.sdpMLineIndex
                                    asyncio.ensure_future(_send_ice(ws, payload))
                                except Exception as e:
                                    LOG.debug("icecandidate send: %s", e)

                            async def _send_ice(websocket, payload: dict) -> None:
                                try:
                                    await websocket.send(json.dumps(payload))
                                except Exception as e:
                                    LOG.debug("send ICE to browser: %s", e)

                            @pc.on("datachannel")
                            def on_datachannel(channel):
                                data_channel_ref[0] = channel
                                # Use outer last_lamp_ref so lamp state persists across reconnects (no reset to 0)

                                @channel.on("message")
                                def on_message(message):
                                    if isinstance(message, str):
                                        try:
                                            data = json.loads(message)
                                            cmd_str = data.get("command")
                                            if isinstance(cmd_str, str) and cmd_str.strip():
                                                try:
                                                    autonomy_command_queue.put_nowait(cmd_str.strip())
                                                except queue.Full:
                                                    pass
                                                return
                                            twist = _twist_from_control(data)
                                            if twist is not None:
                                                if not first_control_logged[0]:
                                                    first_control_logged[0] = True
                                                    LOG.info(
                                                        "First control received on data channel (linear_x=%.2f angular_z=%.2f)",
                                                        twist.linear.x,
                                                        twist.angular.z,
                                                    )
                                                # Update lamp only when message includes it; otherwise keep current
                                                if "lamp" in data:
                                                    last_lamp_ref[0] = 1 if data.get("lamp") else 0
                                                lamp = last_lamp_ref[0]
                                                # Always queue so robot gets a continuous stream (no deduplication)
                                                _put_latest(control_queue, (twist, lamp))
                                                # Always push partial telemetry so UI shows commanded speed
                                                partial = {"speed": float(twist.linear.x), "timestamp": time.time()}
                                                _put_latest(telemetry_queue, json.dumps(partial))
                                                if getattr(channel, "readyState", None) == "open":
                                                    try:
                                                        channel.send(json.dumps({"type": "telemetry", "data": partial}))
                                                    except Exception:
                                                        pass
                                        except json.JSONDecodeError:
                                            pass

                            offer = RTCSessionDescription(sdp=msg["sdp"], type="offer")
                            await pc.setRemoteDescription(offer)
                            answer = await pc.createAnswer()
                            await pc.setLocalDescription(answer)
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "answer",
                                        "sdp": pc.localDescription.sdp,
                                    }
                                )
                            )
                        elif typ in ("ice", "ice-candidate", "icecandidate"):
                            cand = msg.get("candidate")
                            if pc is not None and cand:
                                try:
                                    if isinstance(cand, str):
                                        c = RTCIceCandidate(
                                            candidate=cand,
                                            sdpMid=msg.get("sdpMid"),
                                            sdpMLineIndex=msg.get("sdpMLineIndex"),
                                        )
                                    else:
                                        c = RTCIceCandidate(**cand)
                                    await pc.addIceCandidate(c)
                                except Exception as e:
                                    LOG.debug("addIceCandidate: %s", e)

                telemetry_task = asyncio.create_task(
                    _telemetry_sender_loop(
                        ws, telemetry_queue, data_channel_ref, stop_event, last_frame_pts_ref, last_flow_ref
                    )
                )
                try:
                    await recv_loop()
                finally:
                    telemetry_task.cancel()
                    try:
                        await telemetry_task
                    except asyncio.CancelledError:
                        pass
        except Exception as e:
            if not stop_event.is_set():
                LOG.warning("Signaling connection error: %s; reconnecting in 5s", e)
            await asyncio.sleep(5)


def main(args=None) -> None:
    logging.basicConfig(level=logging.INFO)
    if not HAS_CV2:
        LOG.warning("opencv not available; webrtc_node will not decode camera frames")
    if not HAS_AIORTC or not HAS_WEBSOCKETS:
        LOG.error("Install aiortc and websockets to run webrtc_node")
        return

    image_format = os.getenv("IMAGE_FORMAT", DEFAULT_IMAGE_FORMAT)
    frame_queue: queue.Queue = queue.Queue(maxsize=FRAME_QUEUE_MAXSIZE)
    control_queue: queue.Queue = queue.Queue(maxsize=64)  # items: (twist, lamp) — state tracked and passed together
    telemetry_queue: queue.Queue = queue.Queue(maxsize=8)
    autonomy_command_queue: queue.Queue = queue.Queue(maxsize=32)
    stop = threading.Event()
    last_flow_ref: list = [None]

    ros_thread = threading.Thread(
        target=run_ros_node,
        args=(frame_queue, control_queue, telemetry_queue, autonomy_command_queue, image_format, stop, last_flow_ref),
        daemon=True,
    )
    ros_thread.start()

    try:
        asyncio.run(run_signaling_and_webrtc(frame_queue, control_queue, telemetry_queue, autonomy_command_queue, stop, last_flow_ref))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    ros_thread.join(timeout=2)


if __name__ == "__main__":
    main()
