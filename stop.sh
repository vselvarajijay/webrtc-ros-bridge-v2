#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping container ros2-kilted..."
docker compose stop ros2-kilted

echo "Container stopped. Run ./start.sh to start it again."
