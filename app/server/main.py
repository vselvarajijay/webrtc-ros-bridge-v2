import logging
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse, JSONResponse, Response

from .ice_servers import get_ice_servers
from .signaling import handle_signaling_websocket

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI()

WWW_DIR = Path(__file__).resolve().parent.parent / "www"


@app.on_event("startup")
async def startup():
    logger.info("App starting: WebSocket /ws/signaling and /ws/signaling/")


@app.get("/")
def read_root():
    """Serve the browser client (WebRTC + telemetry)."""
    index = WWW_DIR / "index.html"
    if index.is_file():
        return FileResponse(index)
    return {"hello": "world"}


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
    """WebRTC config: ICE servers (STUN + optional TURN from env)."""
    return {"iceServers": get_ice_servers()}


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


@app.get("/data")
def data():
    """
    Stub for Earth Rovers SDK /data endpoint.
    Scout_bridge polls this when it expects the SDK on port 8000.
    Returns minimal telemetry so the bridge does not 404; real telemetry
    flows via ROS from the bridge and is sent to the browser over WebRTC.
    """
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


@app.websocket("/ws/signaling")
async def ws_signaling(websocket: WebSocket):
    """WebRTC signaling: exchange offer/answer and ICE between browser and robot."""
    await handle_signaling_websocket(websocket)


@app.websocket("/ws/signaling/")
async def ws_signaling_trailing(websocket: WebSocket):
    """Same as /ws/signaling for clients that send a trailing slash."""
    await handle_signaling_websocket(websocket)
