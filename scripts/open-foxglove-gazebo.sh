#!/usr/bin/env bash
# Open Foxglove Studio (desktop app) and connect to the Gazebo simulation WebSocket.
# Run this after starting the sim: docker compose --profile gazebo up gazebo
#
# Usage: ./scripts/open-foxglove-gazebo.sh

set -e
FOXGLOVE_URL="foxglove://open?ds=foxglove-websocket&ds.url=ws://localhost:8766/"

if command -v foxglove-studio &>/dev/null; then
  exec foxglove-studio "$FOXGLOVE_URL"
elif [[ "$OSTYPE" == "darwin"* ]]; then
  open "$FOXGLOVE_URL"
else
  echo "Install Foxglove Studio from https://foxglove.dev/download then run:"
  echo "  foxglove-studio \"$FOXGLOVE_URL\""
  echo "Or on macOS, run: open \"$FOXGLOVE_URL\""
  exit 1
fi
