#!/bin/bash
# Start all homelife.ai services: daemon, web (dev mode with HMR)
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

# Daemon (includes RAG server on :3003)
.venv/bin/python -m daemon start &
DAEMON_PID=$!

# Web (Vite dev :5173 + API server :3001, with HMR)
cd web && npm run dev &
WEB_PID=$!
cd ..

echo "All services started. Press Ctrl+C to stop."
echo "  Daemon:  running (PID $DAEMON_PID)"
echo "  Web:     http://localhost:5173 (dev) / http://localhost:3001 (API)"
wait
