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
from geometry_msgs.msg import Twist
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

from scout_robot_bridge.core.constants import (
    CAMERA_FRONT_COMPRESSED_TOPIC,
    CMD_VEL_TOPIC,
    DEFAULT_IMAGE_FORMAT,
    ROBOT_TELEMETRY_TOPIC,
)
from scout_robot_bridge.core.webrtc_config import get_ice_servers_dict

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
    HAS_AIORTC = True
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
        self._last_frame_pts_ref = last_frame_pts_ref
        self._recv_count = 0

    async def recv(self):
        # Prefer latest frame from queue; else reuse last frame to keep stream alive
        try:
            self._last_frame = self._queue.get_nowait()
        except queue.Empty:
            pass
        if self._last_frame is None:
            # No frame yet: yield a tiny black frame to satisfy recv
            self._last_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        if self._recv_count == 0:
            LOG.info("CameraTrack: first frame sent (from_queue=%s)", self._last_frame is not None)
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
        if self._last_frame_pts_ref is not None:
            self._last_frame_pts_ref[0] = self._pts
        self._pts += 3000  # ~30fps at 90k clock
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
    cmd_vel_queue: queue.Queue,
    telemetry_queue: queue.Queue,
    image_format: str,
    stop_event: threading.Event,
) -> None:
    """Run rclpy node in a dedicated thread: camera sub -> frame_queue; telemetry sub -> telemetry_queue; timer drains cmd_vel_queue -> /cmd_vel."""
    rclpy.init()
    node = Node("webrtc_node")
    cmd_pub = node.create_publisher(Twist, CMD_VEL_TOPIC, 10)

    def on_telemetry(msg: String) -> None:
        if not msg.data:
            return
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

    decode_fail_logged: list = [False]

    def on_image(msg: CompressedImage) -> None:
        data = bytes(msg.data)
        if not data:
            return
        img = _decode_compressed_image(data, msg.format or image_format)
        if img is not None:
            try:
                frame_queue.put_nowait(img)
            except queue.Full:
                try:
                    frame_queue.get_nowait()
                    frame_queue.put_nowait(img)
                except queue.Empty:
                    pass
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

    while not stop_event.is_set():
        try:
            rclpy.spin_once(node, timeout_sec=0.05)
        except ExternalShutdownException:
            break
        now = time.monotonic()
        if now - last_drain >= dt:
            last_drain = now
            try:
                while True:
                    twist = cmd_vel_queue.get_nowait()
                    cmd_pub.publish(twist)
            except queue.Empty:
                pass

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


async def _telemetry_sender_loop(
    ws,
    telemetry_queue: queue.Queue,
    data_channel_ref: list,
    stop_event: threading.Event,
    last_frame_pts_ref: Optional[list] = None,
) -> None:
    """Send telemetry to app server (prefer full) and browser (newest). Drain queue each tick."""
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
            if not collected:
                continue
            # Parse all collected items
            parsed = []
            for data in collected:
                try:
                    obj = json.loads(data) if isinstance(data, str) else data
                    if obj is not None:
                        parsed.append(obj)
                except json.JSONDecodeError:
                    continue
            if not parsed:
                continue
            # For signaling WS (logging): prefer last full telemetry
            payload_obj_ws = None
            for obj in reversed(parsed):
                if _is_full_telemetry(obj):
                    payload_obj_ws = obj
                    break
                if payload_obj_ws is None:
                    payload_obj_ws = obj
            if payload_obj_ws is None:
                continue
            payload_ws = {"type": "telemetry", "data": payload_obj_ws}
            if last_frame_pts_ref is not None:
                payload_ws["frame_pts"] = last_frame_pts_ref[0]
                payload_ws["frame_time_base"] = FRAME_CLOCK_RATE
            payload_str_ws = json.dumps(payload_ws)
            # For data channel (browser): send newest so UI reflects latest state immediately
            payload_obj_dc = parsed[-1]
            payload_dc = {"type": "telemetry", "data": payload_obj_dc}
            if last_frame_pts_ref is not None:
                payload_dc["frame_pts"] = last_frame_pts_ref[0]
                payload_dc["frame_time_base"] = FRAME_CLOCK_RATE
            payload_str_dc = json.dumps(payload_dc)
            await asyncio.sleep(0)
            try:
                await ws.send(payload_str_ws)
            except Exception:
                break
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
    cmd_vel_queue: queue.Queue,
    telemetry_queue: queue.Queue,
    stop_event: threading.Event,
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
                            LOG.info("Video track added to peer connection (source: %s)", CAMERA_FRONT_COMPRESSED_TOPIC)

                            @pc.on("datachannel")
                            def on_datachannel(channel):
                                data_channel_ref[0] = channel

                                @channel.on("message")
                                def on_message(message):
                                    if isinstance(message, str):
                                        try:
                                            data = json.loads(message)
                                            twist = _twist_from_control(data)
                                            if twist is not None:
                                                _put_latest(cmd_vel_queue, twist)
                                                # Push partial telemetry so UI shows commanded speed; only fields we have
                                                partial = {"speed": float(twist.linear.x), "timestamp": time.time()}
                                                _put_latest(telemetry_queue, json.dumps(partial))
                                                # Send partial to browser immediately so speed echo appears in one RTT
                                                if getattr(channel, "readyState", None) == "open":
                                                    try:
                                                        payload_str = json.dumps({"type": "telemetry", "data": partial})
                                                        channel.send(payload_str)
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
                        ws, telemetry_queue, data_channel_ref, stop_event, last_frame_pts_ref
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
    cmd_vel_queue: queue.Queue = queue.Queue(maxsize=64)
    telemetry_queue: queue.Queue = queue.Queue(maxsize=8)
    stop = threading.Event()

    ros_thread = threading.Thread(
        target=run_ros_node,
        args=(frame_queue, cmd_vel_queue, telemetry_queue, image_format, stop),
        daemon=True,
    )
    ros_thread.start()

    try:
        asyncio.run(run_signaling_and_webrtc(frame_queue, cmd_vel_queue, telemetry_queue, stop))
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
    ros_thread.join(timeout=2)


if __name__ == "__main__":
    main()
