"""
Robot profile CRUD – JSON file-based storage.

Schema for each profile:
  id            – UUID string (generated on create)
  name          – human-readable label
  robot_type    – key from ROBOT_TYPES
  host          – hostname or IP of the robot bridge
  port          – TCP port of the robot bridge (default 8001)
  optical_flow  – bool, show optical-flow overlay by default
  floor_mask    – bool, show floor-mask overlay by default
"""

import json
import logging
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Available robot types (extend as new SDK adapters are added to robot_factory.py)
ROBOT_TYPES: List[str] = [
    "earth_rover",
    "spot",
    "go2",
    "generic_ros2",
    "custom",
]

# Persistent storage path – override via ROBOT_PROFILES_PATH env var
_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "robot_profiles.json"
_PROFILES_PATH = Path(os.environ.get("ROBOT_PROFILES_PATH", str(_DEFAULT_PATH)))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load() -> List[Dict[str, Any]]:
    """Load profiles from the JSON file. Returns an empty list if missing."""
    try:
        if _PROFILES_PATH.is_file():
            with _PROFILES_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    return data
    except Exception as exc:
        logger.warning("Failed to load robot profiles: %s", exc)
    return []


def _save(profiles: List[Dict[str, Any]]) -> None:
    """Persist profiles to the JSON file."""
    try:
        _PROFILES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _PROFILES_PATH.open("w", encoding="utf-8") as fh:
            json.dump(profiles, fh, indent=2)
    except Exception as exc:
        logger.error("Failed to save robot profiles: %s", exc)
        raise


def _find(profiles: List[Dict[str, Any]], robot_id: str) -> Optional[int]:
    """Return the index of the profile with the given id, or None."""
    for i, p in enumerate(profiles):
        if p.get("id") == robot_id:
            return i
    return None


def _validate(body: Dict[str, Any]) -> None:
    """Raise HTTPException 422 if required fields are missing or invalid."""
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="'name' is required and must be non-empty")
    robot_type = body.get("robot_type", "").strip()
    if not robot_type:
        raise HTTPException(status_code=422, detail="'robot_type' is required")


# ---------------------------------------------------------------------------
# API Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/api")


@router.get("/robot_types")
def get_robot_types() -> JSONResponse:
    """Return the list of supported robot types."""
    return JSONResponse({"robot_types": ROBOT_TYPES})


@router.get("/robots")
def list_robots() -> JSONResponse:
    """Return all robot profiles."""
    return JSONResponse(_load())


@router.post("/robots", status_code=201)
async def create_robot(request: Request) -> JSONResponse:
    """Create a new robot profile. Body: {name, robot_type, host?, port?, optical_flow?, floor_mask?}"""
    try:
        body: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    _validate(body)

    profile: Dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "name": body["name"].strip(),
        "robot_type": body.get("robot_type", "generic_ros2").strip(),
        "host": body.get("host", "localhost").strip(),
        "port": int(body.get("port", 8001)),
        "optical_flow": bool(body.get("optical_flow", False)),
        "floor_mask": bool(body.get("floor_mask", False)),
    }

    profiles = _load()
    profiles.append(profile)
    _save(profiles)
    logger.info("Created robot profile: %s (%s)", profile["name"], profile["id"])
    return JSONResponse(profile, status_code=201)


@router.get("/robots/{robot_id}")
def get_robot(robot_id: str) -> JSONResponse:
    """Return a single robot profile by id."""
    profiles = _load()
    idx = _find(profiles, robot_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Robot profile not found")
    return JSONResponse(profiles[idx])


@router.put("/robots/{robot_id}")
async def update_robot(robot_id: str, request: Request) -> JSONResponse:
    """Update an existing robot profile. Partial updates are supported."""
    try:
        body: Dict[str, Any] = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    profiles = _load()
    idx = _find(profiles, robot_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Robot profile not found")

    profile = profiles[idx]
    # Allow partial updates – only overwrite supplied fields
    for field in ("name", "robot_type", "host"):
        if field in body and isinstance(body[field], str):
            profile[field] = body[field].strip()
    if "port" in body:
        profile["port"] = int(body["port"])
    if "optical_flow" in body:
        profile["optical_flow"] = bool(body["optical_flow"])
    if "floor_mask" in body:
        profile["floor_mask"] = bool(body["floor_mask"])

    _validate(profile)
    profiles[idx] = profile
    _save(profiles)
    logger.info("Updated robot profile: %s (%s)", profile["name"], robot_id)
    return JSONResponse(profile)


@router.delete("/robots/{robot_id}", status_code=204)
def delete_robot(robot_id: str) -> None:
    """Delete a robot profile by id."""
    profiles = _load()
    idx = _find(profiles, robot_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Robot profile not found")
    name = profiles[idx].get("name", robot_id)
    profiles.pop(idx)
    _save(profiles)
    logger.info("Deleted robot profile: %s (%s)", name, robot_id)


@router.post("/robots/{robot_id}/test_connection")
def test_connection(robot_id: str) -> JSONResponse:
    """
    Ping the robot bridge to verify connectivity.
    Returns {ok: bool, detail: str}.
    """
    profiles = _load()
    idx = _find(profiles, robot_id)
    if idx is None:
        raise HTTPException(status_code=404, detail="Robot profile not found")

    profile = profiles[idx]
    host = profile.get("host", "localhost")
    port = int(profile.get("port", 8001))

    try:
        with socket.create_connection((host, port), timeout=3):
            pass
        return JSONResponse({"ok": True, "detail": f"Connected to {host}:{port}"})
    except OSError as exc:
        return JSONResponse({"ok": False, "detail": str(exc)})
