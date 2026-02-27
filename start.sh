#!/bin/bash
# Start all life.ai services: daemon, web server
# Usage: ./start.sh

set -e
cd "$(dirname "$0")"

cleanup() {
    echo "Stopping all services..."
    kill $DAEMON_PID $WEB_PID 2>/dev/null
    wait $DAEMON_PID $WEB_PID 2>/dev/null
    echo "All services stopped."
}
trap cleanup EXIT INT TERM

# Daemon
.venv/bin/python -m life start &
DAEMON_PID=$!

# Web server (API + frontend)
cd web && npx tsx server/index.ts &
WEB_PID=$!
cd ..

echo "All services started. Press Ctrl+C to stop."
wait
