# WebRTC Latency Reduction Plan

Goal: Minimize delay from **key press → telemetry/video feedback** so WebRTC feels real-time.

---

## 1. End-to-end data flow (current)

```
[Browser]                          [App server]                    [Robot / webrtc_node]
   |                                      |                                    |
   | keydown → dataChannel.send(control)  |                                    |
   | ---------------------------------------- WebRTC data channel -----------> |
   |                                      |                    on_message → cmd_vel_queue
   |                                      |                    partial telemetry → telemetry_queue
   |                                      |                    timer 50Hz → publish /cmd_vel
   |                                      |                                    |
   |                                      |     telemetry_sender_loop (every TELEMETRY_SEND_INTERVAL)
   |                                      |     → ws.send() + dc.send(telemetry)
   | <-------- WebRTC data channel (dc.onmessage) ------------------------------|
   | renderTelemetry(data)                |                                    |
   |                                      |                                    |
   | Video: ontrack → remoteVideo         |     CameraTrack.recv() ← frame_queue ← ROS /camera/...
   | requestVideoFrameCallback → updateTelemetryForVideoTime (if frame_pts)
```

---

## 2. Identified latency sources (code-backed)

| # | Source | Location | Current value | Effect |
|---|--------|----------|---------------|--------|
| **A** | **Telemetry send interval** | `webrtc_node.py` | `TELEMETRY_SEND_INTERVAL = 0.2` (200 ms) | Telemetry (including speed echo) is only sent every 200 ms. Key press → partial in queue → **up to 200 ms** before it’s sent to the browser. |
| **B** | **Telemetry preference (full vs partial)** | `_telemetry_sender_loop` | Prefers “last full” over “partial” | When both exist, we send older full telemetry instead of newest partial (speed). UI can show stale speed. |
| **C** | **Robot full telemetry rate** | `constants.py` / `bridge_node.py` | `DEFAULT_TELEMETRY_PUBLISH_RATE = 5.0` (5 Hz) | Full telemetry from robot every 200 ms. Limits how fast “real” state (battery, GPS, etc.) can update. |
| **D** | **Camera publish rate** | `constants.py` / config | Default 10 Hz; frodobot 5 Hz | New frame every 100 ms (or 200 ms). Lower bound on video “new content” latency. |
| **E** | **cmd_vel drain rate** | `webrtc_node.py` | `CMD_VEL_DRAIN_HZ = 50` (20 ms) | Already good; control → /cmd_vel within ~20 ms. |
| **F** | **Data channel ordered** | `app/www/index.html` | `createDataChannel('control', { ordered: true })` | Ordered channel can cause head-of-line blocking; one lost packet delays later ones. |
| **G** | **Telemetry over signaling WS** | `webrtc_node.py` | Sends same telemetry to both `ws` and `dc` | Browser only uses `dataChannel.onmessage`. WS path is for server logging; not the main lag. |
| **H** | **Video + telemetry sync** | `index.html` | `pushTelemetryWithPts` + `updateTelemetryForVideoTime` | When `frame_pts` is set, telemetry is shown by video time. Video buffering = telemetry feels delayed. |

---

## 2b. Video pipeline and why video feels slow

```
[Robot/SDK]                    [Bridge/ROS]              [webrtc_node]              [Browser]
get_front_camera_frame()  →   CompressedImage topic  →  frame_queue (size 1)  →   CameraTrack.recv()
(HTTP GET per frame)          (depth 1, KEEP_LAST)       decode → BGR               encode (aiortc)
     ↑                                ↑                         ↑                         ↑
  Main bottleneck              No backlog                     Always latest            Decoder buffer
  (SDK + network RTT)          (good)                        (good)                   (e.g. 3 frames)
```

| # | Source | Location | Effect on video lag |
|---|--------|----------|----------------------|
| **V1** | **Camera source rate** | `earth_rovers_robot.py` | When `camera_use_stream: true`, each frame is one **HTTP GET** to the SDK (`get_front_camera_frame()`). Frame rate = 1 / (HTTP latency + SDK capture time). The stream loop then `time.sleep(0.01)` (100 Hz cap). **This is usually the dominant video latency.** |
| **V2** | **Timer-based camera rate** | `frodobot_params.yaml`, `bridge_node.py` | When `camera_use_stream: false`, frames are published at `camera_publish_rate` (e.g. 5 Hz = 200 ms per frame). Very slow for real-time feel. |
| **V3** | **Browser decode buffer** | Browser / `<video>` | Browsers often wait for a few decoded frames (e.g. Chromium: 3 video frames) before starting playback. Adds tens to ~100 ms. |
| **V4** | **CameraTrack output rate** | `webrtc_node.py` | `recv()` advances PTS at ~30 fps; when the source is 5–10 fps, the same frame is sent multiple times. No extra latency, but “new” content only when a new frame arrives from the queue. |
| **V5** | **WebRTC encoder** | aiortc (libav) | Default encoder settings may favor quality over latency (e.g. larger GOP). Low-latency tuning (e.g. zerolatency) would need aiortc/encoder options. |

**How to address video slowness:**

1. **Camera source (V1, V2)**  
   - Keep `camera_use_stream: true` (default) so the bridge pulls at max sustainable rate.  
   - If using timer mode, set `camera_publish_rate` to 10–15 Hz (or as high as the SDK allows).  
   - The real limit is **how fast the SDK can serve frames** (HTTP + capture). Improving the SDK or using a push/streaming API would help most.

2. **Browser buffer (V3)**  
   - Set **`latencyHint`** on the `<video>` element (e.g. `0.075` or `0` for “minimum”) where supported (e.g. WICG `media-latency-hint`). Set it **before** assigning `srcObject` so the UA can minimize buffering.

3. **Encoder (V5)**  
   - Future: if aiortc exposes encoder options, use low-latency settings (e.g. VP8/VP9/H264 with minimal frame buffering / zerolatency-style tuning).

4. **Don’t block telemetry on video (H)**  
   - So that “video feels slow” doesn’t make the whole UI feel slow: update numeric telemetry from the **latest** message immediately; use `frame_pts` only where you need sync with the video frame.

---

## 3. Prioritized plan (what to change)

### Tier 1 – High impact, low risk (do first)

1. **Reduce telemetry send interval (A)**  
   - **Change:** Lower `TELEMETRY_SEND_INTERVAL` from `0.2` to e.g. `0.05` (50 ms, 20 Hz) or `0.033` (~30 Hz).  
   - **Why:** Single biggest lever for “I pressed a key and the number didn’t update.”  
   - **Risk:** Slightly more CPU and bandwidth; monitor.

2. **Prefer “newest” over “full” for immediate feedback (B)**  
   - **Change:** When sending to the data channel (browser), prefer **newest by timestamp** (or always send the last item in `collected`) so speed echo is not delayed by older full telemetry.  
   - **Option:** Keep “prefer full” only for the signaling WS (logging), and send **latest** (full or partial) to the data channel.  
   - **Why:** Ensures the last thing that happened (e.g. key press → partial) is what the UI shows first.

3. **Send partial telemetry immediately on control (optional fast path)**  
   - **Change:** In `on_message` (data channel), after `_put_latest(telemetry_queue, partial)`, trigger an immediate send of that partial over the data channel (one-shot send), instead of waiting for the next loop tick.  
   - **Why:** Speed echo can reach the UI in one RTT instead of waiting for the next interval.

### Tier 2 – Medium impact

4. **Increase robot telemetry rate (C)**  
   - **Change:** Raise `DEFAULT_TELEMETRY_PUBLISH_RATE` (e.g. to 10 Hz) or make it configurable per deployment.  
   - **Why:** Full telemetry (battery, GPS, etc.) updates more often; less “stale” feeling.  
   - **Risk:** More CPU on robot and more messages; keep an eye on load.

5. **Increase camera rate where possible (D)**  
   - **Change:** Use 10 Hz (or higher if the camera/SDK allows) in config; avoid 5 Hz if latency is critical.  
   - **Why:** Video reflects reality sooner; also helps if telemetry is synced to video time.

6. **Data channel: consider unordered (F)**  
   - **Change:** Try `createDataChannel('control', { ordered: false })` for control + telemetry.  
   - **Why:** Reduces head-of-line blocking; newer messages can be delivered even if one is lost.  
   - **Risk:** Telemetry could occasionally appear out of order; UI should merge by timestamp.

### Tier 3 – Polish and measurement

7. **Avoid tying telemetry display to video when not needed (H)**  
   - **Change:** For “live” values (e.g. speed), always update from latest message; use `frame_pts` only for overlay/sync if you add it later. Or use a hybrid: immediate update for speed, PTS-based for overlay.  
   - **Why:** Video buffering or codec delay shouldn’t block numeric feedback.

8. **Add simple latency instrumentation**  
   - **Change:** Optional: add a “round-trip” or “echo” message (browser sends timestamp, robot echoes; browser computes RTT). Or log timestamps on keydown vs `renderTelemetry` to measure perceived lag.  
   - **Why:** Validates improvements and catches regressions.

---

## 4. Suggested implementation order

1. **Phase 1 (quick wins)**  
   - Reduce `TELEMETRY_SEND_INTERVAL` to 50 ms (or 33 ms).  
   - In `_telemetry_sender_loop`, when sending to the data channel, send the **last** item in `collected` (newest) instead of “last full”. Optionally keep current “prefer full” logic only for `ws.send()`.

2. **Phase 2 (immediate feedback)**  
   - On data channel `on_message`, after pushing partial telemetry to the queue, call `dc.send(partial_payload)` once so the browser gets speed echo without waiting for the next interval.

3. **Phase 3 (tuning)**  
   - Increase telemetry publish rate and camera rate as needed; consider unordered data channel and telemetry/video display policy.

4. **Phase 4 (observability)**  
   - Add optional timestamps or echo messages to measure end-to-end latency.

---

## 5. Files to touch

| Change | File |
|--------|------|
| `TELEMETRY_SEND_INTERVAL`, telemetry selection, optional immediate send | `ros2_ws/src/scout_robot_bridge/scout_robot_bridge/nodes/webrtc_node.py` |
| Data channel `ordered: false` (optional) | `app/www/index.html` |
| Telemetry display policy (immediate vs PTS) | `app/www/index.html` |
| `DEFAULT_TELEMETRY_PUBLISH_RATE` | `ros2_ws/src/scout_robot_bridge/scout_robot_bridge/core/constants.py` |
| Camera rate | `ros2_ws/src/scout_robot_bridge/config/frodobot_params.yaml` or bridge params |
| Video `latencyHint` (browser) | `app/www/index.html` |
| Camera stream loop sleep (robot) | `earth_rovers_robot.py` (optional; bottleneck is usually HTTP) |

---

## 6. Summary

- **Largest cause of perceived lag:** Telemetry is sent only every **200 ms** and the loop prefers **full** over **partial**, so the speed echo from a key press can be delayed and sometimes overwritten by older full telemetry.
- **Fast path:** Send telemetry more often (e.g. 50 ms), send **newest** to the browser (and optionally send partial immediately when a control message is received), then tune robot telemetry rate and camera rate. Optional: unordered data channel and decoupling numeric telemetry from video time for immediate feedback.

- **Video:** The main limit is **camera source rate** (HTTP GET per frame in the Earth Rovers SDK). Use `camera_use_stream: true` and, on the browser, set **`latencyHint`** on the video element to reduce decode buffering where supported. Increasing SDK frame rate or moving to a streaming API has the highest impact.
